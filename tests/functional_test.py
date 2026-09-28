"""
Functional test suite for ACOS.

Covers the logic that can be verified without macOS-specific OS behaviour:
  * policy semantics (allowlist / blocklist / off, host suffix matching)
  * protocol validation
  * live integration: connect, mode switch, ack latency recorded
  * soft enforcement: blocked site + blocked app produce analytics events
  * emergency focus returns agent to EXERCISE and clears overlay
  * reward auto-return to EXERCISE after countdown
  * crash-recovery flag on restart
  * CSV / JSON export shape

macOS-only behaviour (real screencapture, real app termination, TCC prompts,
overlay rendering) is NOT asserted here — it is listed in the QA checklist
for on-device verification, and is never faked as passing.

Run: python tests/functional_test.py
"""
from __future__ import annotations

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
from teacher.policy import Policy, site_allowed, app_allowed
from agent.main import Agent
from agent import enforcement as ENF
from common import protocol as P
from common import analytics_events as EV

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"test": name, "pass": bool(cond), "detail": detail})
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(cond)


# ---------------------------------------------------------------------------
def test_policy():
    print("\n[unit] policy semantics")
    p = Policy(mode="EXERCISE", site_mode="allowlist", site_allow=["khanacademy.org"])
    check("allowlist allows exact host", site_allowed("khanacademy.org", p))
    check("allowlist allows subdomain", site_allowed("www.khanacademy.org", p))
    check("allowlist blocks other host", not site_allowed("youtube.com", p))
    b = Policy(mode="EXERCISE", site_mode="blocklist", site_block=["youtube.com"])
    check("blocklist blocks listed", not site_allowed("m.youtube.com", b))
    check("blocklist allows unlisted", site_allowed("khanacademy.org", b))
    off = Policy(mode="FREE", site_mode="off")
    check("site off allows everything", site_allowed("anything.example", off))
    ap = Policy(mode="EXERCISE", app_mode="blocklist", app_block=["Messages"])
    check("app blocklist blocks Messages", not app_allowed("Messages", ap))
    check("app blocklist allows Safari", app_allowed("Safari", ap))
    aa = Policy(mode="EXERCISE", app_mode="allowlist", app_allow=["Safari"])
    check("app allowlist blocks Terminal", not app_allowed("Terminal", aa))


def test_protocol():
    print("\n[unit] protocol")
    check("validate accepts good msg", P.validate(P.msg(P.T_HELLO, agent_id="x")))
    check("validate rejects wrong version", not P.validate({"v": 999, "type": "x"}))
    check("validate rejects non-dict", not P.validate("nope"))
    check("session id anonymous format", P.new_session_id().startswith("s-"))


def test_export_shape():
    print("\n[unit] export shape")
    a = Analytics("/tmp/acos_func_export.db")
    a.record("s-1", EV.TASK_COMPLETION, {"task_id": "t", "completed": True})
    js = json.loads(a.export_json())
    check("json export is list of events", isinstance(js, list) and js[0]["kind"] == EV.TASK_COMPLETION)
    csv = a.export_csv()
    check("csv has header", csv.splitlines()[0].startswith("ts,session_id,kind,data"))
    check("csv contains no name column", "name" not in csv.splitlines()[0])


# ---------------------------------------------------------------------------
async def _server(port, db):
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
    return console, analytics, runner, reaper


async def _api(port, action, **kw):
    async with aiohttp.ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{port}/api/command",
                          json={"action": action, **kw}) as r:
            return await r.json()


async def test_integration():
    print("\n[integration] connect / command / enforcement / emergency / reward")
    port = 8911
    console, analytics, runner, reaper = await _server(port, "/tmp/acos_func.db")

    # single agent so the shared enforcement sim state is unambiguous
    ENF.sim_set(app="TextEdit", url="https://khanacademy.org/x")
    agent = Agent(console=f"127.0.0.1:{port}", thumb_push=False,
                  agent_id="func-001", use_marker=False)
    task = asyncio.create_task(agent.run())

    # wait online
    for _ in range(100):
        if any(a.online for a in console.agents.values()):
            break
        await asyncio.sleep(0.1)
    check("agent connects", any(a.online for a in console.agents.values()))

    # strict EXERCISE policy pushed
    await _api(port, "set_policy", mode="EXERCISE", patch={
        "site_mode": "allowlist", "site_allow": ["khanacademy.org"],
        "app_mode": "blocklist", "app_block": ["Messages"],
        "kill_blocked_apps": False}, targets="all")
    await _api(port, "set_mode", mode="EXERCISE", targets="all")
    await asyncio.sleep(0.6)
    check("agent applied EXERCISE", agent.mode == P.MODE_EXERCISE)

    # command latency recorded
    await asyncio.sleep(0.3)
    check("command latency recorded",
          analytics.count_by_kind().get(EV.AGENT_COMMAND_LATENCY, 0) > 0)

    # now drive a BLOCKED site + app and wait for the monitor to notice
    ENF.sim_set(app="Messages", url="https://youtube.com/watch")
    await asyncio.sleep(3.5)  # monitor runs every 1.5s
    counts = analytics.count_by_kind()
    check("blocked_navigation logged", counts.get(EV.BLOCKED_NAVIGATION, 0) > 0,
          f"count={counts.get(EV.BLOCKED_NAVIGATION,0)}")
    check("blocked_app logged", counts.get(EV.BLOCKED_APP, 0) > 0,
          f"count={counts.get(EV.BLOCKED_APP,0)}")

    # allowed content produces no NEW block after reset
    ENF.sim_set(app="Safari", url="https://khanacademy.org/ok")
    before = analytics.count_by_kind().get(EV.BLOCKED_NAVIGATION, 0)
    await asyncio.sleep(2.5)
    after = analytics.count_by_kind().get(EV.BLOCKED_NAVIGATION, 0)
    check("allowed content not blocked", after == before,
          f"{before}->{after}")

    # emergency focus
    await _api(port, "set_mode", mode="FREE", targets="all")
    await asyncio.sleep(0.4)
    await _api(port, "emergency_focus", targets="all")
    await asyncio.sleep(0.5)
    check("emergency returns to EXERCISE", agent.mode == P.MODE_EXERCISE)
    check("emergency clears overlay", agent.overlay == P.OVERLAY_NONE)

    # reward auto-return
    await _api(port, "set_mode", mode="REWARD", targets="all", reward_seconds=2)
    await asyncio.sleep(0.4)
    check("reward applied", agent.mode == P.MODE_REWARD)
    await asyncio.sleep(3.0)  # countdown expires
    check("reward auto-returns to EXERCISE", console.class_mode == P.MODE_EXERCISE,
          f"class_mode={console.class_mode}")
    check("reward_start + reward_end logged",
          analytics.count_by_kind().get(EV.REWARD_START, 0) > 0 and
          analytics.count_by_kind().get(EV.REWARD_END, 0) > 0)

    task.cancel()
    reaper.cancel()
    await runner.cleanup()


async def test_crash_recovery():
    print("\n[integration] crash recovery flag")
    port = 8912
    console, analytics, runner, reaper = await _server(port, "/tmp/acos_func_cr.db")

    # First boot writes a marker (use_marker=True), then we simulate a crash by
    # cancelling without clearing the marker, and boot again -> recovered=True.
    import agent.main as AM
    AM.SUPPORT_DIR = "/tmp/acos_cr_support"
    AM.AGENT_ID_FILE = os.path.join(AM.SUPPORT_DIR, "agent_id")
    AM.CRASH_MARKER = os.path.join(AM.SUPPORT_DIR, "session.marker")
    if os.path.exists(AM.CRASH_MARKER):
        os.unlink(AM.CRASH_MARKER)

    a1 = Agent(console=f"127.0.0.1:{port}", thumb_push=False, use_marker=True)
    t1 = asyncio.create_task(a1.run())
    await asyncio.sleep(1.0)
    check("first boot not flagged as recovery", not a1.recovered)
    t1.cancel()  # simulate crash: marker NOT cleared
    await asyncio.sleep(0.3)

    a2 = Agent(console=f"127.0.0.1:{port}", thumb_push=False, use_marker=True)
    check("second boot detects crash recovery", a2.recovered,
          f"prev={a2.prev_session}")
    t2 = asyncio.create_task(a2.run())
    await asyncio.sleep(1.0)
    check("crash_recovery event reported",
          analytics.count_by_kind().get(EV.CRASH_RECOVERY, 0) > 0)
    t2.cancel()
    reaper.cancel()
    await runner.cleanup()


def main():
    print("==== ACOS FUNCTIONAL TESTS ====")
    test_policy()
    test_protocol()
    test_export_shape()
    asyncio.run(test_integration())
    asyncio.run(test_crash_recovery())

    npass = sum(1 for r in RESULTS if r["pass"])
    total = len(RESULTS)
    print(f"\n==== RESULT: {npass}/{total} passed ====")
    report = {"passed": npass, "total": total,
              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "results": RESULTS}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "functional_report.json")
    json.dump(report, open(out, "w"), indent=2)
    print("report written:", out)
    sys.exit(0 if npass == total else 1)


if __name__ == "__main__":
    main()
