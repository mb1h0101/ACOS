# ACOS — Adaptive Classroom Orchestration System (v0.2 classroom candidate)

A self-contained classroom orchestration system for macOS computer labs:
**one Teacher Console** driving **~40 Student Agents** over the local network.
No dependency on 金偉 (Jinwei) or any third-party broadcast suite — ACOS
implements its own broadcast, blackout, monitoring and policy enforcement.

> **Status: first deployable version.** The networking, protocol, analytics,
> policy engine, console UI, agent lifecycle (heartbeat / reconnect / crash
> recovery), reward countdown and deployment scripts are implemented and
> tested with a **real 40-client load test** (see `docs/TEST_REPORT_LOAD.md`)
> and a **30/30 functional suite** (`docs/TEST_REPORT_FUNCTIONAL.md`).
>
> macOS-only behaviour that cannot run on the CI/build machine — real
> `screencapture` thumbnails, real app termination, TCC permission prompts,
> and overlay rendering — is **not faked**. It is implemented in
> `agent/enforcement.py` using only sanctioned macOS facilities and is listed
> for **on-device verification** in `docs/QA_CHECKLIST.md`.

## What the teacher uses
A single Traditional-Chinese web console served locally by
`TeacherConsole.app`.

The normal classroom workflow is deliberately small:

1. set the websites/apps allowed for this lesson;
2. press **請全班看老師** when the teacher needs attention;
3. press the same control (**讓學生繼續操作**) to return students to the
   existing work state;
4. use **結束課堂／解除全部限制** as the guaranteed release.

The backend still contains earlier experimental mode/analytics/lesson APIs for
compatibility, but they are intentionally not exposed as a wall of controls in
the classroom UI. See `docs/ACOS_CLASSROOM_V02_HANDOFF.md` for the design and
real-Mac acceptance test.

## Repository layout
```
common/      protocol, discovery (mDNS + UDP beacon), analytics event names
teacher/     console backend (aiohttp WS+HTTP), analytics store, policy, web UI
agent/       student agent core + macOS enforcement layer (guarded stub off-Mac)
deploy/      INSTALL/UNINSTALL/EMERGENCY_RESET.command, launchd plist,
             build_pkg.sh, entry points, USB/ folder
tools/       build_app.sh (TeacherConsole.app)
tests/       load_test.py (real 40 clients), functional_test.py (30 checks),
             screenshot.py, generated reports + UI screenshots
docs/        ARCHITECTURE, BUILD, KNOWN_LIMITATIONS, QA_CHECKLIST, test reports
```

## Quick start (developer machine, no packaging)
```bash
pip install aiohttp zeroconf pillow          # pillow only needed for broadcast render
python teacher/server.py --port 8770         # open http://localhost:8770
ACOS_CONSOLE=127.0.0.1:8770 python agent/main.py   # run a student agent
```

## Build the shippable artifacts (on a Mac)
```bash
tools/build_app.sh        # -> dist/TeacherConsole.app
deploy/build_pkg.sh       # -> dist/StudentAgent.pkg
```
Then assemble the USB folder (see `docs/BUILD.md`).

## Privacy
No student names, usernames, emails or device serials are ever collected. The
only identifiers are an anonymous per-boot `agent_id` and `session_id`. Teachers
may attach **non-identifying seat labels** (e.g. "Row 1 Left") in the console.

## The three permission walls (read before deploying)
See `docs/KNOWN_LIMITATIONS.md`. In short: Screen Recording and Accessibility
are macOS TCC permissions that **no plain installer can auto-grant** — each Mac
needs one manual click the first time (or a PPPC profile via MDM). Real
network-level site *blocking* needs MDM or a signed Network Extension; without
them ACOS does honest **soft enforcement** (detect + overlay + log + optional
quit). ACOS never bypasses macOS security or acquires permissions silently.
