"""
ACOS Student Agent.

A long-running process in the logged-in student's session (launched by a
LaunchAgent). It:
  * discovers the Teacher Console (mDNS / UDP beacon / manual override),
  * connects over WebSocket and announces itself with an anonymous session id,
  * sends heartbeats, reconnects with backoff, and records crash-recovery,
  * applies DEMO / EXERCISE / REWARD / FREE modes and BLACKOUT / FOCUS_NOW /
    BROADCAST overlays via the enforcement layer,
  * enforces the current policy (soft): monitors the foreground app + browser
    host, logs blocked_app / blocked_navigation, raises the overlay,
  * pushes screen thumbnails on request,
  * reports anonymous analytics events.

No PII is ever collected or transmitted. The only identifiers are a random
per-boot agent_id and session_id.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp

from common import protocol as P
from common import analytics_events as EV
from common import discovery
from teacher.policy import Policy, site_allowed, app_allowed
from agent import enforcement as ENF

SUPPORT_DIR = os.path.expanduser("~/Library/Application Support/ACOS") \
    if platform.system() == "Darwin" else os.path.expanduser("~/.acos")
AGENT_ID_FILE = os.path.join(SUPPORT_DIR, "agent_id")
CRASH_MARKER = os.path.join(SUPPORT_DIR, "session.marker")
HEARTBEAT_S = 4
MONITOR_S = 1.5
THUMB_PUSH_S = 6           # unsolicited thumbnail push cadence
INACTIVE_THRESHOLD_S = 45


def _load_agent_id() -> str:
    os.makedirs(SUPPORT_DIR, exist_ok=True)
    try:
        if os.path.exists(AGENT_ID_FILE):
            v = open(AGENT_ID_FILE).read().strip()
            if v:
                return v
    except Exception:
        pass
    v = "a-" + uuid.uuid4().hex[:12]
    try:
        open(AGENT_ID_FILE, "w").write(v)
    except Exception:
        pass
    return v


class Agent:
    def __init__(self, console: str = None, thumb_push: bool = True,
                 agent_id: str = None, use_marker: bool = True):
        self.agent_id = agent_id or _load_agent_id()
        self.use_marker = use_marker
        self.session_id = P.new_session_id()
        self.console_override = console
        self.thumb_push = thumb_push
        self.ws = None
        self.mode = P.MODE_FREE
        self.overlay = P.OVERLAY_NONE
        self.policy = Policy(mode=P.MODE_FREE)
        self.overlay_win = ENF.Overlay()
        self.recovered, self.prev_session = self._check_crash()
        self._blocked_seen = {}   # throttle repeat block events
        self._was_inactive = False
        self._disconnect_ts = 0.0
        self._mode_cmd_recv_ts = 0.0

    # ---- crash recovery ---------------------------------------------------
    def _check_crash(self):
        """If a session marker exists from a previous run that did not exit
        cleanly, this boot is a crash recovery."""
        if not self.use_marker:
            return False, None
        try:
            if os.path.exists(CRASH_MARKER):
                prev = open(CRASH_MARKER).read().strip()
                return True, prev
        except Exception:
            pass
        return False, None

    def _write_marker(self):
        if not self.use_marker:
            return
        try:
            open(CRASH_MARKER, "w").write(self.session_id)
        except Exception:
            pass

    def _clear_marker(self):
        try:
            if os.path.exists(CRASH_MARKER):
                os.unlink(CRASH_MARKER)
        except Exception:
            pass

    # ---- send helpers -----------------------------------------------------
    async def send(self, m: dict):
        if self.ws and not self.ws.closed:
            try:
                await self.ws.send_json(m)
            except Exception:
                pass

    async def event(self, kind: str, data: dict = None):
        await self.send(P.msg(P.T_EVENT, kind=kind, data=data or {}))

    async def _forward_deploy_timing(self):
        """One-shot: forward install/permission/connect durations recorded by
        INSTALL.command, then delete the file so it is only reported once."""
        path = os.path.join(SUPPORT_DIR, "deploy_timing.json")
        try:
            if not os.path.exists(path):
                return
            d = json.load(open(path))
            if "install_ms" in d:
                await self.event(EV.INSTALL_DURATION, {"ms": d["install_ms"]})
            if "permission_ms" in d:
                await self.event(EV.PERMISSION_DURATION,
                                 {"ms": d["permission_ms"], "permission": "first_run"})
            if "connect_ms" in d:
                await self.event(EV.CONNECT_DURATION, {"ms": d["connect_ms"]})
            os.unlink(path)
        except Exception:
            pass

    # ---- main run loop with reconnect ------------------------------------
    async def run(self):
        self._write_marker()
        backoff = 1.0
        while True:
            target = None
            if self.console_override:
                host, port = self.console_override.rsplit(":", 1)
                target = (host, int(port))
            else:
                target = discovery.discover(total_timeout=8.0)
            if not target:
                await asyncio.sleep(min(backoff, 8))
                backoff = min(backoff * 1.5, 8)
                continue
            url = f"http://{target[0]}:{target[1]}/ws/agent"
            try:
                await self._session(url)
                backoff = 1.0
            except Exception:
                pass
            # disconnected -> record and retry
            if self._disconnect_ts == 0.0:
                self._disconnect_ts = time.time()
            await asyncio.sleep(min(backoff, 8) + random.random())
            backoff = min(backoff * 1.5, 8)

    async def _session(self, url: str):
        t0 = time.time()
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(url, heartbeat=20, max_msg_size=8*1024*1024) as ws:
                self.ws = ws
                # connection established
                connect_ms = (time.time() - t0) * 1000
                downtime = (time.time() - self._disconnect_ts) * 1000 if self._disconnect_ts else 0
                await self.send(P.msg(
                    P.T_HELLO, agent_id=self.agent_id, session_id=self.session_id,
                    platform=platform.system(),
                    recovered=self.recovered, prev_session_id=self.prev_session))
                await self.event(EV.CONNECT_DURATION, {"ms": round(connect_ms, 1)})
                await self._forward_deploy_timing()
                if self._disconnect_ts:
                    await self.event(EV.RECONNECT, {"downtime_ms": round(downtime, 1)})
                    self._disconnect_ts = 0.0
                # spawn background loops
                tasks = [
                    asyncio.create_task(self._heartbeat()),
                    asyncio.create_task(self._monitor()),
                ]
                if self.thumb_push:
                    tasks.append(asyncio.create_task(self._thumb_pusher()))
                try:
                    async for raw in ws:
                        if raw.type == aiohttp.WSMsgType.TEXT:
                            await self._handle(json.loads(raw.data))
                        elif raw.type in (aiohttp.WSMsgType.CLOSED,
                                          aiohttp.WSMsgType.ERROR):
                            break
                finally:
                    for t in tasks:
                        t.cancel()
                    self.ws = None

    async def _heartbeat(self):
        while True:
            await self.send(P.msg(P.T_HEARTBEAT))
            await asyncio.sleep(HEARTBEAT_S)

    async def _thumb_pusher(self):
        while True:
            await asyncio.sleep(THUMB_PUSH_S)
            b64 = ENF.capture_thumbnail_jpeg_b64()
            if b64:
                await self.send(P.msg(P.T_THUMBNAIL, req_id=None, data=b64))

    # ---- command handling -------------------------------------------------
    async def _handle(self, m: dict):
        if not P.validate(m):
            return
        t = m.get("type")
        if t == P.T_WELCOME:
            self.agent_id = m.get("agent_id", self.agent_id)
            await self._apply_mode(m.get("class_mode", P.MODE_FREE),
                                   m.get("policy"), cmd_id=None)
        elif t == P.T_SET_MODE:
            self._mode_cmd_recv_ts = time.time()
            await self._apply_mode(m.get("mode"), m.get("policy"),
                                   cmd_id=m.get("cmd_id"))
        elif t == P.T_SET_POLICY:
            if m.get("policy"):
                self.policy = Policy.from_dict(m["policy"])
            await self._ack(m.get("cmd_id"))
        elif t == P.T_SET_OVERLAY:
            await self._apply_overlay(m.get("overlay"), cmd_id=m.get("cmd_id"))
        elif t == P.T_REQUEST_THUMB:
            b64 = ENF.capture_thumbnail_jpeg_b64()
            await self.send(P.msg(P.T_THUMBNAIL, req_id=m.get("req_id"), data=b64))
        elif t == P.T_BROADCAST_FRAME:
            self.overlay = P.OVERLAY_BROADCAST
            self.overlay_win.show_broadcast(m.get("data"))
            await self.send(P.msg(P.T_STATE, mode=self.mode,
                                  overlay=self.overlay, bcast_ack=m.get("frame_id")))
        elif t == P.T_EMERGENCY_FOCUS:
            self.overlay_win.hide()
            self.overlay = P.OVERLAY_NONE
            await self._apply_mode(P.MODE_EXERCISE, None, cmd_id=None)
            await self.event(EV.TEACHER_INTERVENTION, {"kind": "emergency_focus"})
        elif t == P.T_PING:
            await self.send(P.msg(P.T_ACK, cmd_id=m.get("cmd_id")))

    async def _ack(self, cmd_id):
        if cmd_id:
            await self.send(P.msg(P.T_ACK, cmd_id=cmd_id))

    async def _apply_mode(self, mode, policy, cmd_id):
        if mode not in P.MODES:
            await self._ack(cmd_id)
            return
        prev = self.mode
        self.mode = mode
        if policy:
            self.policy = Policy.from_dict(policy)
        else:
            self.policy = Policy(mode=mode)
        # overlay behaviour per mode
        if mode == P.MODE_DEMO:
            # DEMO waits for broadcast frames; until then, a hold screen.
            self.overlay = P.OVERLAY_NONE
            self.overlay_win.hide()
        else:
            self.overlay = P.OVERLAY_NONE
            self.overlay_win.hide()
        await self.event(EV.MODE_ENTER, {"mode": mode})
        # mode transition latency = command receipt -> applied
        if self._mode_cmd_recv_ts:
            ms = (time.time() - self._mode_cmd_recv_ts) * 1000
            await self.event(EV.MODE_TRANSITION_LATENCY,
                             {"from": prev, "to": mode, "ms": round(ms, 2)})
            self._mode_cmd_recv_ts = 0.0
        await self._ack(cmd_id)
        # reset block throttle on mode change
        self._blocked_seen.clear()

    async def _apply_overlay(self, overlay, cmd_id):
        self.overlay = overlay
        if overlay == P.OVERLAY_BLACKOUT:
            self.overlay_win.blackout()
        elif overlay == P.OVERLAY_FOCUS_NOW:
            # snap to learning env: quit disallowed foreground app, kiosk hold
            app = ENF.frontmost_app()
            if app and not app_allowed(app, self.policy) and self.policy.app_mode != "off":
                ENF.terminate_app(app)
            self.overlay_win.kiosk("請看老師")
        elif overlay in (P.OVERLAY_NONE,):
            self.overlay_win.hide()
        await self.event(EV.TEACHER_INTERVENTION, {"kind": "overlay", "overlay": overlay})
        await self._ack(cmd_id)

    # ---- enforcement monitor ---------------------------------------------
    async def _monitor(self):
        while True:
            try:
                await self._monitor_tick()
            except Exception:
                pass
            await asyncio.sleep(MONITOR_S)

    async def _monitor_tick(self):
        # inactivity
        idle = ENF.get_idle_seconds()
        if idle >= INACTIVE_THRESHOLD_S and not self._was_inactive:
            self._was_inactive = True
            await self.event(EV.INACTIVE, {"ms": int(idle * 1000)})
        elif idle < INACTIVE_THRESHOLD_S:
            self._was_inactive = False

        if self.mode not in (P.MODE_EXERCISE, P.MODE_DEMO):
            if self.overlay_win.state == "policy_block":
                self.overlay_win.hide()
            return  # only enforce in restricted modes

        # A teacher-initiated overlay owns the screen until the teacher releases
        # it. Policy monitoring must not replace or fight that overlay.
        if self.overlay != P.OVERLAY_NONE:
            return

        pol = self.policy
        blocked_message = None

        # app enforcement
        if pol.app_mode != "off":
            app = ENF.frontmost_app()
            if app and not app_allowed(app, pol):
                if self._throttle("app:" + app):
                    await self.event(EV.BLOCKED_APP, {"app": app})
                if pol.kill_blocked_apps:
                    ENF.terminate_app(app)
                else:
                    blocked_message = "這個 App 目前未開放，請回到本堂課指定工具"

        # site enforcement
        if pol.site_mode != "off":
            host = ENF.frontmost_browser_host()
            if host and not site_allowed(host, pol):
                if self._throttle("site:" + host):
                    await self.event(EV.BLOCKED_NAVIGATION, {"host": host})
                blocked_message = "這個網站目前未開放，請回到本堂課指定網站"

        if blocked_message:
            self.overlay_win.policy_notice(blocked_message)
        elif self.overlay_win.state == "policy_block":
            # Critical recovery rule: a policy warning disappears automatically
            # as soon as the student returns to an allowed resource.
            self.overlay_win.hide()

    def _throttle(self, key: str, window: float = 8.0) -> bool:
        now = time.time()
        last = self._blocked_seen.get(key, 0)
        if now - last > window:
            self._blocked_seen[key] = now
            return True
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--console", default=os.environ.get("ACOS_CONSOLE"),
                    help="host:port override (else auto-discover)")
    ap.add_argument("--auto-thumb", action="store_true",
                    help="enable unsolicited periodic thumbnail pushes (off by default)")
    ap.add_argument("--check-perms", action="store_true",
                    help="print permission status and exit")
    args = ap.parse_args()

    if args.check_perms:
        print(json.dumps(ENF.check_permissions(), indent=2))
        return

    agent = Agent(console=args.console, thumb_push=args.auto_thumb)
    print(f"[ACOS agent] id={agent.agent_id} session={agent.session_id} "
          f"recovered={agent.recovered}")
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        agent._clear_marker()


if __name__ == "__main__":
    main()
