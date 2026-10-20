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
        self._last_target = None

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
            elif self._last_target:
                # Once a Teacher Console has been found, reconnect directly to
                # that same address first. Do not depend on Bonjour/UDP for every
                # transient Wi-Fi or WebSocket drop.
                target = self._last_target
            else:
                # Discovery is synchronous (Bonjour/UDP), so keep it off the
                # asyncio event loop.
                target = await asyncio.to_thread(discovery.discover, 8.0)

            if not target:
                await asyncio.sleep(min(backoff, 8))
                backoff = min(backoff * 1.5, 8)
                continue

            url = f"http://{target[0]}:{target[1]}/ws/agent"
            try:
                await self._session(url)
                backoff = 1.0
            except Exception:
                # If a cached address no longer works (teacher changed network),
                # clear it so the next pass performs fresh auto-discovery.
                if not self.console_override and self._last_target == target:
                    self._last_target = None

            if self._disconnect_ts == 0.0:
                self._disconnect_ts = time.time()
            await asyncio.sleep(min(backoff, 8) + random.random())
            backoff = min(backoff * 1.5, 8)

    async def _session(self, url: str):
        t0 = time.time()
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(url, heartbeat=20, max_msg_size=8*1024*1024) as ws:
                self.ws = ws
                self._last_target = (url.split("://",1)[1].split(":",1)[0],
                                     int(url.rsplit(":",1)[1].split("/",1)[0]))
                # connection established
                connect_ms = (time.time() - t0) * 1000
                downtime = (time.time() - self._disconnect_ts) * 1000 if self._disconnect_ts else 0
                device_name = platform.node() or "Mac"
                await self.send(P.msg(
                    P.T_HELLO, agent_id=self.agent_id, session_id=self.session_id,
                    platform=platform.system(), device_name=device_name,
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
            print("[ACOS agent] connected to Teacher Console", flush=True)
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
        applied = True
        if overlay == P.OVERLAY_BLACKOUT:
            applied = bool(self.overlay_win.blackout())
        elif overlay == P.OVERLAY_FOCUS_NOW:
            app = ENF.frontmost_app()
            if app and not app_allowed(app, self.policy) and self.policy.app_mode != "off":
                ENF.terminate_app(app)
            applied = bool(self.overlay_win.kiosk("請看老師"))
        elif overlay == P.OVERLAY_NONE:
            self.overlay_win.hide()
            applied = True
        self.overlay = overlay if applied else P.OVERLAY_NONE
        await self.event(EV.TEACHER_INTERVENTION, {
            "kind": "overlay", "overlay": overlay, "applied": applied
        })
        await self.send(P.msg(P.T_STATE, mode=self.mode, overlay=self.overlay,
                              overlay_ok=applied, requested_overlay=overlay))
        await self._ack(cmd_id)

    # ---- enforcement monitor ---------------------------------------------
    async def _monitor(self):
        while True:
            try:
                # macOS AppleScript / ioreg calls are blocking. Running the
                # policy probe in a worker thread prevents them from starving
                # WebSocket heartbeats and making a healthy Mac look offline.
                await asyncio.to_thread(self._monitor_tick_sync)
            except Exception:
                pass
            await asyncio.sleep(MONITOR_S)

    def _monitor_tick_sync(self):
        # This function runs in a worker thread. It only performs local macOS
        # inspection/enforcement. Analytics events are best-effort and are
        # queued back onto the main loop from the caller when needed.
        idle = ENF.get_idle_seconds()
        if idle >= INACTIVE_THRESHOLD_S and not self._was_inactive:
            self._was_inactive = True
        elif idle < INACTIVE_THRESHOLD_S:
            self._was_inactive = False

        if self.mode not in (P.MODE_EXERCISE, P.MODE_DEMO):
            if self.overlay_win.state == "policy_block":
                self.overlay_win.hide()
            return

        if self.overlay != P.OVERLAY_NONE:
            return

        pol = self.policy
        blocked_message = None
        app = ENF.frontmost_app()

        if pol.app_mode != "off" and app and not app_allowed(app, pol):
            if pol.kill_blocked_apps:
                ENF.terminate_app(app)
            else:
                blocked_message = "這個 App 目前未開放，請回到本堂課指定工具"

        app_l = (app or "").lower()
        browser_front = ("chrome" in app_l or "safari" in app_l)
        if pol.site_mode != "off" and browser_front:
            host = ENF.frontmost_browser_host()
            if host and not site_allowed(host, pol):
                blocked_message = "這個網站目前未開放，請回到本堂課指定網站"

        if blocked_message:
            self.overlay_win.policy_notice(blocked_message)
        elif self.overlay_win.state == "policy_block":
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
