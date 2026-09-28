# Installation Test Report

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
