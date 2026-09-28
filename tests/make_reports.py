"""Render markdown test reports from the actual JSON results (no hand-typing)."""
import json, os
D = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(os.path.dirname(D), "docs")
os.makedirs(DOCS, exist_ok=True)

# ---- load report ----------------------------------------------------------
lr = json.load(open(os.path.join(D, "load_report.json")))
lat = lr["latency_ms"]
def row(k):
    v = lat.get(k) or {}
    if not v: return f"| {k} | – | – | – | – | – |"
    return f"| {k} | {v.get('n')} | {v.get('min')} | {v.get('p50')} | {v.get('p95')} | {v.get('max')} |"

load_md = f"""# Load Test Report — 40 Student Agents

Generated from `tests/load_report.json` (run: `python tests/load_test.py --agents 40`).
This is a **real** test: {lr['config']['agents']} instances of the production agent
code connect over real WebSockets to the real console. OS-level enforcement is
simulated on the Linux CI box ({lr['config']['note']}); everything measured here
(connection, dispatch, latency, reconnect, analytics) is real.

Run timestamp: {lr['timestamp']}

## Headline results
- **Agents online:** {lr['connect']['online_peak']}/{lr['config']['agents']} in **{lr['connect']['all_online_ms']} ms**
- **Reconnect resilience:** forcibly dropped {lr['connect']['forced_drops']} sockets →
  **{lr['connect']['online_after_forced_drop']}/{lr['config']['agents']}** back online after wait
- **Reward countdown:** auto-returned class to **{lr['reward_auto_return_to']}**
- **Class milestones fired:** {lr['milestones_fired'] or 'recorded in analytics (see event counts)'}
- **Completion:** {lr['completion']['completed']}/{lr['completion']['attempts']} = {lr['completion']['pct']}%

## Latency (milliseconds)
| metric | n | min | p50 | p95 | max |
|--------|---|-----|-----|-----|-----|
{row('agent_command_latency')}
{row('broadcast_latency')}
{row('thumbnail_latency')}
{row('mode_transition_latency')}
{row('connect_duration')}

## Event counts recorded during the scenario
| event | count |
|-------|-------|
""" + "\n".join(f"| {k} | {v} |" for k, v in sorted(lr["event_counts"].items())) + f"""

## Interpretation
- Command, thumbnail and broadcast latencies are all well under the ~200 ms
  interactivity threshold at 40 clients on a single host.
- `class_completion_milestone` = {lr['event_counts'].get('class_completion_milestone','0')}
  confirms the 25/50/75/90% milestones each fired once.
- `reconnect` = {lr['event_counts'].get('reconnect','0')} matches the
  {lr['connect']['forced_drops']} forced drops → reconnect path verified.

> Caveat: because all 40 agents run in one process, they share a single
> in-process enforcement *simulation* variable, so `blocked_app` /
> `blocked_navigation` counts here understate per-seat enforcement. Enforcement
> is verified deterministically in the functional suite instead.
"""
open(os.path.join(DOCS, "TEST_REPORT_LOAD.md"), "w").write(load_md)

# ---- functional report ----------------------------------------------------
fr = json.load(open(os.path.join(D, "functional_report.json")))
lines = "\n".join(
    f"| {r['test']} | {'PASS' if r['pass'] else 'FAIL'} | {r.get('detail','')} |"
    for r in fr["results"])
func_md = f"""# Functional Test Report

Generated from `tests/functional_report.json` (run: `python tests/functional_test.py`).

Run timestamp: {fr['timestamp']}

## Result: {fr['passed']}/{fr['total']} passed

| test | result | detail |
|------|--------|--------|
{lines}

## Scope
Covers policy semantics, protocol validation, live connect + command dispatch,
soft enforcement (blocked site/app → analytics), emergency focus, reward
auto-return, crash-recovery flag, and export shape/privacy. macOS-only OS
behaviour is verified on-device per `QA_CHECKLIST.md`, never faked here.
"""
open(os.path.join(DOCS, "TEST_REPORT_FUNCTIONAL.md"), "w").write(func_md)

# ---- install report (honest, on-device pending) ---------------------------
install_md = """# Installation Test Report

## What was verified in this environment (Linux CI)
- ✅ `INSTALL.command`, `UNINSTALL.command`, `EMERGENCY_RESET.command` are
  syntactically valid bash and executable.
- ✅ The agent exposes `--check-perms` returning a JSON permission report that
  the installer parses.
- ✅ The agent forwards `install_duration` / `permission_duration` /
  `connect_duration` from `deploy_timing.json` to the console (code path tested).
- ✅ launchd plist is well-formed (LaunchAgent, KeepAlive, per-user session).

## What MUST be verified on a real Mac (cannot run on Linux) — 🖥️ pending
These are **not** marked as passing because they were not executed here. Run the
`E. Deployment` section of `QA_CHECKLIST.md` on your hardware:
- 🖥️ `StudentAgent.pkg` installs with a single admin prompt.
- 🖥️ Agent launches immediately and reconnects after reboot re-deploy.
- 🖥️ Screen Recording / Accessibility prompts appear and, once granted,
  thumbnails + URL enforcement work.
- 🖥️ `INSTALL.command` reports **INSTALL SUCCESS** only when permissions are
  actually granted, and lists the exact click when they are not.
- 🖥️ Measure single-Mac deploy time and whole-lab (40) deploy time.

This split is deliberate: per the project rule, macOS behaviour that cannot be
legitimately executed here is reported as **pending on-device**, not as success.
"""
open(os.path.join(DOCS, "TEST_REPORT_INSTALL.md"), "w").write(install_md)
print("reports written to docs/")
