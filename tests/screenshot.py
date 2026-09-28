"""Boot console + sim agents, drive a scenario, screenshot the real UI."""
import asyncio, os, sys, base64, time, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aiohttp import web
import aiohttp
from teacher.analytics import Analytics
from teacher.server import Console, make_app, _offline_reaper
from agent.main import Agent
from agent import enforcement as ENF
from common import analytics_events as EV

PORT = 8933

async def boot():
    db = "/tmp/acos_shot.db"
    if os.path.exists(db): os.unlink(db)
    console = Console(Analytics(db))
    app = make_app(console)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT).start()
    asyncio.create_task(_offline_reaper(console))
    agents = [Agent(console=f"127.0.0.1:{PORT}", thumb_push=True,
                    agent_id=f"seat-{i:02d}", use_marker=False) for i in range(12)]
    for a in agents: asyncio.create_task(a.run())
    await asyncio.sleep(2)
    async def api(action, **kw):
        async with aiohttp.ClientSession() as s:
            await s.post(f"http://127.0.0.1:{PORT}/api/command", json={"action":action, **kw})
    await api("set_mode", mode="EXERCISE", targets="all")
    await api("request_thumbs", targets="all")
    # seed some analytics
    for i,a in enumerate(agents):
        await a.event(EV.TASK_START, {"task_id":"t1"})
        await a.event(EV.FIRST_ATTEMPT_ACCURACY, {"task_id":"t1","correct": i%2==0})
        await a.event(EV.TASK_COMPLETION, {"task_id":"t1","completed": i<9})
    # put one seat in DEMO to show per-seat mode + one overlay
    await api("set_mode", mode="DEMO", targets=["seat-00"])
    await api("set_overlay", overlay="BLACKOUT", targets=["seat-01"])
    await asyncio.sleep(1.5)
    return runner

def main():
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    runner = loop.run_until_complete(boot())
    # keep loop running in background thread
    t = threading.Thread(target=loop.run_forever, daemon=True); t.start()
    time.sleep(1)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
        pg = b.new_page(viewport={"width":1400,"height":900})
        pg.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
        pg.wait_for_timeout(1500)
        pg.screenshot(path="/home/claude/acos/tests/console_exercise.png")
        # analytics tab
        pg.click("text=Analytics"); pg.wait_for_timeout(1500)
        pg.screenshot(path="/home/claude/acos/tests/console_analytics.png")
        b.close()
    print("screenshots written")

if __name__ == "__main__":
    main()
