"""
40-client simulated load test — REAL agents, REAL WebSockets, REAL server.

Spins up the actual Teacher Console and N actual Student Agent instances
(default 40) in one process, then drives a realistic class scenario and
measures end-to-end latencies from the analytics the system recorded itself.

This is not a mock: every agent runs the production agent code path
(discovery is bypassed via --console, everything else is identical). On
macOS the enforcement calls would hit the OS; on this Linux box they use
the simulated hooks, which does not change the networking/latency being
measured here.

Usage:  python tests/load_test.py --agents 40 --out report.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import web
import aiohttp

from teacher.analytics import Analytics
from teacher.server import Console, make_app, _offline_reaper
from agent.main import Agent
from agent import enforcement as ENF
from common import analytics_events as EV
from common import protocol as P


async def run(n_agents: int, out_path: str, port: int = 8899):
    db = "/tmp/acos_load.db"
    if os.path.exists(db):
        os.unlink(db)
    analytics = Analytics(db)
    console = Console(analytics)
    app = make_app(console)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    reaper = asyncio.create_task(_offline_reaper(console))

    # --- launch agents -----------------------------------------------------
    t_connect0 = time.time()
    agents = [Agent(console=f"127.0.0.1:{port}", thumb_push=True,
                    agent_id=f"load-{i:03d}", use_marker=False)
              for i in range(n_agents)]
    for i, a in enumerate(agents):
        ENF.sim_set(app=("Safari" if i % 3 else "Messages"),
                    url="https://khanacademy.org/x" if i % 4 else "https://youtube.com/x")
    tasks = [asyncio.create_task(a.run()) for a in agents]

    # wait until all online (or timeout)
    async def online_count():
        return sum(1 for a in console.agents.values() if a.online)
    deadline = time.time() + 30
    while await online_count() < n_agents and time.time() < deadline:
        await asyncio.sleep(0.2)
    all_online_ms = (time.time() - t_connect0) * 1000
    online = await online_count()
    print(f"[load] {online}/{n_agents} agents online in {all_online_ms:.0f} ms")

    async def api(action, **kw):
        async with aiohttp.ClientSession() as s:
            async with s.post(f"http://127.0.0.1:{port}/api/command",
                              json={"action": action, **kw}) as r:
                return await r.json()

    # --- scenario ----------------------------------------------------------
    print("[load] scenario: DEMO -> broadcast -> EXERCISE -> blackout -> thumbs -> REWARD(auto) -> completions")
    # 1. whole-class mode changes (measures command + transition latency)
    for mode in ["DEMO", "EXERCISE", "FREE", "EXERCISE"]:
        await api("set_mode", mode=mode, targets="all")
        await asyncio.sleep(0.8)

    # 2. broadcast a burst of frames (measures broadcast latency)
    frame = ENF._simulated_thumbnail(1024)
    for _ in range(5):
        await api("broadcast_frame", data=frame, targets="all")
        await asyncio.sleep(0.4)

    # 3. blackout + focus overlays
    await api("set_overlay", overlay="BLACKOUT", targets="all"); await asyncio.sleep(0.5)
    await api("set_overlay", overlay="NONE", targets="all"); await asyncio.sleep(0.3)

    # 4. thumbnails from everyone (measures thumbnail latency)
    for _ in range(3):
        await api("request_thumbs", targets="all")
        await asyncio.sleep(1.0)

    # 5. single-student targeting
    await api("set_mode", mode="DEMO", targets=["load-000"])
    await asyncio.sleep(0.3)
    await api("set_mode", mode="EXERCISE", targets=["load-000"])

    # 6. simulate learning events + staggered completions to trip milestones
    await api("set_mode", mode="EXERCISE", targets="all")  # fresh round
    await asyncio.sleep(0.5)
    for i, a in enumerate(agents):
        await a.event(EV.TASK_START, {"task_id": "t1"})
        await a.event(EV.FIRST_ATTEMPT_ACCURACY, {"task_id": "t1", "correct": i % 2 == 0})
        if i % 3 == 0:
            await a.event(EV.HINT, {"task_id": "t1"})
        if i % 5 == 0:
            await a.event(EV.RETRY, {"task_id": "t1", "n": 1})
        await a.event(EV.TIME_ON_TASK, {"task_id": "t1", "ms": 30000 + i * 500})
        await a.event(EV.TASK_COMPLETION, {"task_id": "t1", "completed": i < int(n_agents * 0.92)})
        if i % 6 == 0:
            await asyncio.sleep(0.05)
    await asyncio.sleep(0.5)

    # 7. reconnect resilience: drop 5 agents' sockets, ensure they recover
    dropped = 0
    for a in agents[:5]:
        if a.ws:
            await a.ws.close()
            dropped += 1
    print(f"[load] forcibly dropped {dropped} sockets; waiting for reconnect…")
    await asyncio.sleep(12)
    reconnected = await online_count()
    print(f"[load] online after drop+wait: {reconnected}/{n_agents}")

    # 8. reward with short countdown -> auto return to EXERCISE
    await api("set_mode", mode="REWARD", targets="all", reward_seconds=3)
    await asyncio.sleep(5)  # let it expire and auto-return
    class_mode_after_reward = console.class_mode

    # --- collect results ---------------------------------------------------
    await asyncio.sleep(1)
    dash = analytics.dashboard()
    counts = dash["counts"]
    result = {
        "config": {"agents": n_agents, "transport": "websocket",
                   "host": "127.0.0.1", "note": "real agent code; OS enforcement simulated on Linux"},
        "connect": {"all_online_ms": round(all_online_ms, 1),
                    "online_peak": online, "online_after_forced_drop": reconnected,
                    "forced_drops": dropped},
        "reward_auto_return_to": class_mode_after_reward,
        "latency_ms": dash["latency"],
        "completion": dash["completion"],
        "first_attempt_accuracy": dash["first_attempt_accuracy"],
        "event_counts": counts,
        "milestones_fired": sorted(console.milestones_fired),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    # cleanup
    for t in tasks:
        t.cancel()
    reaper.cancel()
    await runner.cleanup()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", type=int, default=40)
    ap.add_argument("--out", default="/tmp/acos_load_report.json")
    ap.add_argument("--port", type=int, default=8899)
    args = ap.parse_args()
    res = asyncio.run(run(args.agents, args.out, args.port))
    print("\n===== LOAD TEST SUMMARY =====")
    print(f"agents: {res['config']['agents']}")
    print(f"all online in: {res['connect']['all_online_ms']} ms")
    print(f"online after forced drop of {res['connect']['forced_drops']}: "
          f"{res['connect']['online_after_forced_drop']}/{res['config']['agents']}")
    print(f"reward auto-returned class to: {res['reward_auto_return_to']}")
    print(f"milestones fired: {res['milestones_fired']}")
    for k, v in res["latency_ms"].items():
        if v:
            print(f"  {k:26s} p50={v.get('p50')}ms  p95={v.get('p95')}ms  "
                  f"max={v.get('max')}ms  n={v.get('n')}")
    print(f"completion: {res['completion']}")
    print(f"report written: {args.out}")


if __name__ == "__main__":
    main()
