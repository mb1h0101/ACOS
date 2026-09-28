"""
ACOS Teacher Console — backend.

Runs on the teacher's Mac. Serves:
  * a local web UI (the console the teacher actually uses)          GET  /
  * a WebSocket endpoint for Student Agents                          /ws/agent
  * a WebSocket endpoint for the console UI (live push)              /ws/console
  * a small REST API the UI calls to issue commands                  /api/*

The teacher only ever touches the web UI. Everything else is machinery.

Design notes
------------
* Agents dial OUT to this server, so no ports are opened on student Macs.
* Every command carries a cmd_id; agents ack it, letting us measure real
  command latency. Same pattern for thumbnails and broadcast frames.
* Reward runs a server-side countdown that auto-returns the class to EXERCISE.
* No PII anywhere. Agents are keyed by a random per-boot agent_id; the teacher
  may attach a non-identifying seat label (e.g. "Row 1 Left").
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Dict, List, Optional

# allow running as `python teacher/server.py` from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import web, WSMsgType

from common import protocol as P
from common import analytics_events as EV
from common.discovery import ConsoleAdvertiser
from teacher.analytics import Analytics
from teacher.policy import Policy, default_policies

HEARTBEAT_TIMEOUT_S = 12  # mark offline if no heartbeat within this window
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class AgentConn:
    def __init__(self, agent_id: str, ws: web.WebSocketResponse, ip: str):
        self.agent_id = agent_id
        self.ws = ws
        self.ip = ip
        self.session_id: str = ""
        self.label: str = ""
        self.mode: str = P.MODE_FREE
        self.overlay: str = P.OVERLAY_NONE
        self.online: bool = True
        self.last_seen: float = time.time()
        self.last_thumb_b64: Optional[str] = None
        self.last_thumb_ts: float = 0.0
        self.platform: str = "?"
        self.pending: Dict[str, dict] = {}  # cmd_id -> {"ts":, "cmd":}
        self.thumb_reqs: Dict[str, float] = {}  # req_id -> send ts
        self.bcast_sent: Dict[str, float] = {}  # frame_id -> send ts

    def public(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "label": self.label,
            "mode": self.mode,
            "overlay": self.overlay,
            "online": self.online,
            "ip": self.ip,
            "platform": self.platform,
            "last_thumb_ts": int(self.last_thumb_ts * 1000),
            "age": round(time.time() - self.last_seen, 1),
        }


class Console:
    def __init__(self, analytics: Analytics):
        self.agents: Dict[str, AgentConn] = {}
        self.console_ws: List[web.WebSocketResponse] = []
        self.analytics = analytics
        self.policies: Dict[str, Policy] = default_policies()
        self.class_mode: str = P.MODE_FREE
        self.labels: Dict[str, str] = {}  # persisted seat labels by agent_id
        self.reward_task: Optional[asyncio.Task] = None
        self.reward_ends_at: float = 0.0
        self.completed_sessions = set()  # for current exercise round
        self.milestones_fired = set()
        self.broadcast_task: Optional[asyncio.Task] = None
        self.broadcast_targets = "all"

    # ---- console UI push --------------------------------------------------
    async def push_console(self, obj: dict):
        dead = []
        for ws in self.console_ws:
            try:
                await ws.send_json(obj)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.console_ws:
                self.console_ws.remove(ws)

    async def push_state(self):
        await self.push_console({
            "type": "state",
            "class_mode": self.class_mode,
            "reward_remaining": max(0, int(self.reward_ends_at - time.time())) if self.reward_ends_at else 0,
            "agents": [a.public() for a in self.agents.values()],
            "online": sum(1 for a in self.agents.values() if a.online),
            "total": len(self.agents),
        })

    # ---- send to agents ---------------------------------------------------
    async def send_agent(self, a: AgentConn, m: dict):
        try:
            await a.ws.send_json(m)
        except Exception:
            a.online = False

    def _targets(self, targets) -> List[AgentConn]:
        if targets in (None, "all", ["all"]):
            return list(self.agents.values())
        if isinstance(targets, str):
            targets = [targets]
        return [self.agents[t] for t in targets if t in self.agents]

    async def cmd_set_mode(self, mode: str, targets=None, reward_seconds: int = 0):
        if mode not in P.MODES:
            return
        applied = self._targets(targets)
        if targets in (None, "all", ["all"]):
            self.class_mode = mode
        for a in applied:
            cmd_id = P.uuid.uuid4().hex[:12]
            pol = self.policies.get(mode, Policy(mode=mode)).to_dict()
            a.pending[cmd_id] = {"ts": time.time(), "cmd": "set_mode"}
            await self.send_agent(a, P.msg(P.T_SET_MODE, cmd_id=cmd_id,
                                           mode=mode, policy=pol))
            a.mode = mode
        # reward countdown
        if mode == P.MODE_REWARD and reward_seconds > 0:
            await self._start_reward(reward_seconds, applied)
        else:
            await self._cancel_reward()
        if mode == P.MODE_EXERCISE and targets in (None, "all", ["all"]):
            # fresh exercise round -> reset completion tracking
            self.completed_sessions.clear()
            self.milestones_fired.clear()
        self.analytics.record("_teacher", EV.TEACHER_INTERVENTION,
                              {"kind": "set_mode", "mode": mode})
        await self.push_state()

    async def cmd_set_overlay(self, overlay: str, targets=None):
        for a in self._targets(targets):
            cmd_id = P.uuid.uuid4().hex[:12]
            a.pending[cmd_id] = {"ts": time.time(), "cmd": "set_overlay"}
            await self.send_agent(a, P.msg(P.T_SET_OVERLAY, cmd_id=cmd_id,
                                           overlay=overlay))
            a.overlay = overlay
        self.analytics.record("_teacher", EV.TEACHER_INTERVENTION,
                              {"kind": "overlay", "overlay": overlay})
        await self.push_state()

    async def cmd_set_policy(self, mode: str, patch: dict):
        base = self.policies.get(mode, Policy(mode=mode)).to_dict()
        base.update(patch)
        base["mode"] = mode
        self.policies[mode] = Policy.from_dict(base)
        # re-push to any agent currently in that mode
        for a in self.agents.values():
            if a.mode == mode:
                cmd_id = P.uuid.uuid4().hex[:12]
                a.pending[cmd_id] = {"ts": time.time(), "cmd": "set_policy"}
                await self.send_agent(a, P.msg(P.T_SET_POLICY, cmd_id=cmd_id,
                                               mode=mode,
                                               policy=self.policies[mode].to_dict()))
        await self.push_state()

    async def cmd_request_thumbs(self, targets=None):
        for a in self._targets(targets):
            req_id = P.uuid.uuid4().hex[:12]
            a.thumb_reqs[req_id] = time.time()
            await self.send_agent(a, P.msg(P.T_REQUEST_THUMB, req_id=req_id))

    async def cmd_emergency_focus(self, targets=None):
        for a in self._targets(targets):
            await self.send_agent(a, P.msg(P.T_EMERGENCY_FOCUS))
            a.mode = P.MODE_EXERCISE
            a.overlay = P.OVERLAY_NONE
        self.class_mode = P.MODE_EXERCISE
        await self._cancel_reward()
        self.analytics.record("_teacher", EV.TEACHER_INTERVENTION,
                              {"kind": "emergency_focus"})
        await self.push_state()

    async def cmd_broadcast_frame(self, jpeg_b64: str, targets=None):
        fid = P.uuid.uuid4().hex[:8]
        for a in self._targets(targets):
            a.bcast_sent[fid] = time.time()
            await self.send_agent(a, P.msg(P.T_BROADCAST_FRAME, frame_id=fid,
                                           data=jpeg_b64))

    async def broadcast_start(self, targets="all", fps: float = 1.0):
        """Capture the teacher's own screen and relay frames to targets.
        Requires Screen Recording permission on the TEACHER Mac."""
        await self.broadcast_stop()
        self.broadcast_targets = targets

        async def _run():
            from agent import enforcement as ENF  # reuse screencapture wrapper
            try:
                while True:
                    b64 = ENF.capture_thumbnail_jpeg_b64(max_w=1024, quality=55)
                    if b64:
                        await self.cmd_broadcast_frame(b64, self.broadcast_targets)
                    await asyncio.sleep(max(0.2, 1.0 / fps))
            except asyncio.CancelledError:
                pass

        self.broadcast_task = asyncio.create_task(_run())
        self.analytics.record("_teacher", EV.TEACHER_INTERVENTION,
                              {"kind": "broadcast_start"})

    async def broadcast_stop(self):
        if self.broadcast_task and not self.broadcast_task.done():
            self.broadcast_task.cancel()
        self.broadcast_task = None
        # clear broadcast overlay on agents by re-pushing their mode
        for a in self._targets(self.broadcast_targets):
            await self.send_agent(a, P.msg(P.T_SET_OVERLAY,
                                           cmd_id=P.uuid.uuid4().hex[:12],
                                           overlay=P.OVERLAY_NONE))
            a.overlay = P.OVERLAY_NONE
        await self.push_state()

    # ---- reward countdown -------------------------------------------------
    async def _start_reward(self, seconds: int, applied: List[AgentConn]):
        await self._cancel_reward()
        self.reward_ends_at = time.time() + seconds
        for a in applied:
            self.analytics.record(a.session_id or a.agent_id, EV.REWARD_START,
                                  {"seconds": seconds})

        async def _run():
            try:
                while time.time() < self.reward_ends_at:
                    await asyncio.sleep(0.5)
                    await self.push_state()
                # time's up -> auto return to EXERCISE
                for a in list(self.agents.values()):
                    self.analytics.record(a.session_id or a.agent_id,
                                          EV.REWARD_END, {"reason": "timeout"})
                await self.cmd_set_mode(P.MODE_EXERCISE, "all")
            except asyncio.CancelledError:
                pass
            finally:
                self.reward_ends_at = 0.0

        self.reward_task = asyncio.create_task(_run())

    async def _cancel_reward(self):
        if self.reward_task and not self.reward_task.done():
            self.reward_task.cancel()
        self.reward_task = None
        self.reward_ends_at = 0.0

    # ---- completion milestones -------------------------------------------
    async def _maybe_milestone(self):
        online = [a for a in self.agents.values() if a.online]
        if not online:
            return
        pct = 100 * len(self.completed_sessions) / len(online)
        for thresh in (25, 50, 75, 90):
            if pct >= thresh and thresh not in self.milestones_fired:
                self.milestones_fired.add(thresh)
                self.analytics.record("_class", EV.CLASS_COMPLETION_MILESTONE,
                                      {"pct": thresh})
                await self.push_console({"type": "milestone", "pct": thresh})


# ---------------------------------------------------------------------------
# HTTP / WS handlers
# ---------------------------------------------------------------------------
def make_app(console: Console) -> web.Application:
    app = web.Application(client_max_size=8 * 1024 * 1024)
    app["console"] = console

    async def index(request):
        return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

    async def ws_agent(request):
        ws = web.WebSocketResponse(max_msg_size=8 * 1024 * 1024, heartbeat=20)
        await ws.prepare(request)
        peer = request.transport.get_extra_info("peername")
        ip = peer[0] if peer else "?"
        conn: Optional[AgentConn] = None
        try:
            async for raw in ws:
                if raw.type != WSMsgType.TEXT:
                    continue
                try:
                    m = json.loads(raw.data)
                except Exception:
                    continue
                if not P.validate(m):
                    continue
                t = m.get("type")

                if t == P.T_HELLO:
                    aid = m.get("agent_id") or P.uuid.uuid4().hex[:12]
                    conn = console.agents.get(aid) or AgentConn(aid, ws, ip)
                    conn.ws = ws
                    conn.ip = ip
                    conn.online = True
                    conn.last_seen = time.time()
                    conn.session_id = m.get("session_id", "")
                    conn.platform = m.get("platform", "?")
                    conn.label = console.labels.get(aid, conn.label)
                    prev = m.get("prev_session_id")
                    console.agents[aid] = conn
                    # crash recovery signal from agent
                    if m.get("recovered") and prev:
                        console.analytics.record(conn.session_id, EV.CRASH_RECOVERY,
                                                 {"prev_session_id": prev})
                    await console.send_agent(conn, P.msg(
                        P.T_WELCOME, agent_id=aid,
                        class_mode=console.class_mode,
                        policy=console.policies.get(console.class_mode,
                                                    Policy(mode=console.class_mode)).to_dict()))
                    conn.mode = console.class_mode
                    await console.push_state()

                elif conn is None:
                    continue  # ignore anything before hello

                elif t == P.T_HEARTBEAT:
                    conn.last_seen = time.time()
                    if not conn.online:
                        conn.online = True
                        await console.push_state()

                elif t == P.T_EVENT:
                    kind = m.get("kind", "")
                    data = m.get("data", {})
                    console.analytics.record(conn.session_id or conn.agent_id,
                                             kind, data, ts=m.get("ts"))
                    if kind == EV.TASK_COMPLETION and data.get("completed"):
                        console.completed_sessions.add(conn.session_id or conn.agent_id)
                        await console._maybe_milestone()

                elif t == P.T_ACK:
                    cmd_id = m.get("cmd_id")
                    p = conn.pending.pop(cmd_id, None)
                    if p:
                        ms = (time.time() - p["ts"]) * 1000
                        console.analytics.record(conn.session_id or conn.agent_id,
                                                 EV.AGENT_COMMAND_LATENCY,
                                                 {"ms": round(ms, 1), "cmd": p["cmd"]})

                elif t == P.T_THUMBNAIL:
                    req_id = m.get("req_id")
                    conn.last_thumb_b64 = m.get("data")
                    conn.last_thumb_ts = time.time()
                    send_ts = conn.thumb_reqs.pop(req_id, None)
                    if send_ts:
                        ms = (time.time() - send_ts) * 1000
                        console.analytics.record(conn.session_id or conn.agent_id,
                                                 EV.THUMBNAIL_LATENCY, {"ms": round(ms, 1)})
                    await console.push_console({
                        "type": "thumb", "agent_id": conn.agent_id,
                        "data": conn.last_thumb_b64,
                        "ts": int(conn.last_thumb_ts * 1000)})

                elif t == P.T_STATE:
                    conn.mode = m.get("mode", conn.mode)
                    conn.overlay = m.get("overlay", conn.overlay)
                    # broadcast frame ack (latency)
                    fid = m.get("bcast_ack")
                    if fid:
                        send_ts = conn.bcast_sent.pop(fid, None)
                        if send_ts:
                            ms = (time.time() - send_ts) * 1000
                            console.analytics.record(conn.session_id or conn.agent_id,
                                                     EV.BROADCAST_LATENCY, {"ms": round(ms, 1)})
        finally:
            if conn:
                conn.online = False
                console.analytics.record(conn.session_id or conn.agent_id, EV.DISCONNECT)
                await console.push_state()
        return ws

    async def ws_console(request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        console.console_ws.append(ws)
        await console.push_state()
        try:
            async for _ in ws:
                pass
        finally:
            if ws in console.console_ws:
                console.console_ws.remove(ws)
        return ws

    # ---- REST API ---------------------------------------------------------
    async def api_state(request):
        return web.json_response({
            "class_mode": console.class_mode,
            "reward_remaining": max(0, int(console.reward_ends_at - time.time())) if console.reward_ends_at else 0,
            "agents": [a.public() for a in console.agents.values()],
            "policies": {k: v.to_dict() for k, v in console.policies.items()},
            "online": sum(1 for a in console.agents.values() if a.online),
            "total": len(console.agents),
        })

    async def api_command(request):
        body = await request.json()
        action = body.get("action")
        targets = body.get("targets", "all")
        if action == "set_mode":
            await console.cmd_set_mode(body["mode"], targets,
                                       int(body.get("reward_seconds", 0)))
        elif action == "set_overlay":
            await console.cmd_set_overlay(body["overlay"], targets)
        elif action == "set_policy":
            await console.cmd_set_policy(body["mode"], body.get("patch", {}))
        elif action == "request_thumbs":
            await console.cmd_request_thumbs(targets)
        elif action == "emergency_focus":
            await console.cmd_emergency_focus(targets)
        elif action == "broadcast_frame":
            await console.cmd_broadcast_frame(body["data"], targets)
        elif action == "broadcast_start":
            await console.broadcast_start(targets, float(body.get("fps", 1.0)))
        elif action == "broadcast_stop":
            await console.broadcast_stop()
        elif action == "label":
            aid = body["agent_id"]
            console.labels[aid] = body.get("label", "")
            if aid in console.agents:
                console.agents[aid].label = console.labels[aid]
            await console.push_state()
        else:
            return web.json_response({"error": "unknown action"}, status=400)
        return web.json_response({"ok": True})

    async def api_analytics(request):
        return web.json_response(console.analytics.dashboard())

    async def api_export_json(request):
        return web.Response(text=console.analytics.export_json(),
                            content_type="application/json",
                            headers={"Content-Disposition": "attachment; filename=acos_events.json"})

    async def api_export_csv(request):
        return web.Response(text=console.analytics.export_csv(),
                            content_type="text/csv",
                            headers={"Content-Disposition": "attachment; filename=acos_events.csv"})

    app.router.add_get("/", index)
    app.router.add_get("/ws/agent", ws_agent)
    app.router.add_get("/ws/console", ws_console)
    app.router.add_get("/api/state", api_state)
    app.router.add_post("/api/command", api_command)
    app.router.add_get("/api/analytics", api_analytics)
    app.router.add_get("/api/export.json", api_export_json)
    app.router.add_get("/api/export.csv", api_export_csv)
    app.router.add_static("/static/", STATIC_DIR)
    return app


async def _offline_reaper(console: Console):
    while True:
        await asyncio.sleep(3)
        changed = False
        for a in console.agents.values():
            if a.online and (time.time() - a.last_seen) > HEARTBEAT_TIMEOUT_S:
                a.online = False
                changed = True
        # periodic online-rate snapshot for analytics
        total = len(console.agents)
        online = sum(1 for a in console.agents.values() if a.online)
        if total:
            console.analytics.record("_class", EV.AGENT_ONLINE_SNAPSHOT,
                                     {"online": online, "total": total,
                                      "rate": round(online / total, 3)})
        if changed:
            await console.push_state()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--db", default=os.path.expanduser("~/ACOS/analytics.db"))
    ap.add_argument("--no-advertise", action="store_true")
    args = ap.parse_args()

    analytics = Analytics(args.db)
    console = Console(analytics)
    app = make_app(console)

    async def on_start(app):
        app["reaper"] = asyncio.create_task(_offline_reaper(console))

    async def on_cleanup(app):
        app["reaper"].cancel()

    app.on_startup.append(on_start)
    app.on_cleanup.append(on_cleanup)

    adv = None
    if not args.no_advertise:
        adv = ConsoleAdvertiser(args.port)
        adv.start()

    print(f"[ACOS] Teacher Console on http://localhost:{args.port}  (db={args.db})")
    try:
        web.run_app(app, port=args.port, print=None)
    finally:
        if adv:
            adv.stop()


if __name__ == "__main__":
    main()
