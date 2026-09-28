# ACOS Architecture

## Topology
```
                      ┌─────────────────────────────┐
                      │      TeacherConsole.app       │
                      │  aiohttp server + web UI      │
                      │  :8770  /ws/agent  /ws/console│
                      │  SQLite analytics             │
                      └───────▲───────────▲───────────┘
             WebSocket (JSON) │           │ WebSocket (live push to UI)
        ┌─────────────────────┘           └────────── teacher's browser
        │            │            │
   ┌────┴───┐   ┌────┴───┐   ┌────┴───┐    … ~40 agents
   │ agent  │   │ agent  │   │ agent  │
   │ (Mac)  │   │ (Mac)  │   │ (Mac)  │
   └────────┘   └────────┘   └────────┘
```

* **Agents dial OUT** to the console. No inbound ports are opened on student
  Macs — firewall-friendly and lower attack surface.
* **Discovery** (agent → console), tried in order:
  1. Manual override (`ACOS_CONSOLE=host:port` or
     `~/Library/Application Support/ACOS/console.txt`).
  2. mDNS/Bonjour service `_acos._tcp`.
  3. UDP broadcast beacon on port 47800 (survives networks where mDNS is
     filtered). The console advertises via **all three** simultaneously.

## Why this stack
* **Python + aiohttp** for both sides → one language, one dependency,
  bundles cleanly with PyInstaller so classroom Macs need **no** system Python.
* **Web UI for the console** → nothing for the teacher to install beyond the
  app; works fully offline (UI assets bundled, no CDN).
* **WebSocket** → low-latency bidirectional push; measured p50 command latency
  ≈ 24–98 ms at 40 clients (see load report).
* **SQLite** → durable, queryable analytics with trivial CSV/JSON export.

## Message protocol (`common/protocol.py`)
Every frame: `{ "v":1, "type":..., "ts":epoch_ms, ... }`.

| Direction | Types |
|-----------|-------|
| Agent→Console | `hello`, `heartbeat`, `event`, `thumbnail`, `state`, `ack` |
| Console→Agent | `welcome`, `set_mode`, `set_overlay`, `set_policy`, `request_thumb`, `broadcast_frame`, `ping`, `emergency_focus` |

**Latency instrumentation** is built into the protocol: every command carries a
`cmd_id` the agent acks; thumbnails carry a `req_id`; broadcast frames carry a
`frame_id`. The console times each round-trip and records
`agent_command_latency`, `thumbnail_latency`, `broadcast_latency`. The agent
records `mode_transition_latency` (command-receipt → applied).

## Modes and overlays
* **Modes** (mutually exclusive): `DEMO`, `EXERCISE`, `REWARD`, `FREE`.
* **Overlays** (layered): `BLACKOUT`, `FOCUS_NOW`, `BROADCAST`, `NONE`.
* Each mode maps to a **Policy** (`teacher/policy.py`): site rule
  (off/allowlist/blocklist), app rule (off/allowlist/blocklist), fullscreen,
  and "quit blocked app". Policies are authored on the console and shipped to
  agents, so classroom behaviour is auditable and changeable without touching
  agent code.

## Reward countdown
`set_mode REWARD` with `reward_seconds` starts a **server-side** countdown.
When it expires the console auto-issues `set_mode EXERCISE` to the class and
logs `reward_start` / `reward_end{reason:timeout}`. A teacher ending it early
logs `reason:teacher`. The countdown is server-side so it survives a student
Mac reconnecting mid-reward.

## Enforcement (`agent/enforcement.py`)
Platform-aware. On macOS uses only sanctioned facilities:
* `screencapture` + `sips` → thumbnails and teacher-broadcast capture
  (needs **Screen Recording** TCC).
* `osascript`/System Events → frontmost app; Chrome/Safari active-tab host
  (needs **Automation/Accessibility** TCC).
* `osascript … to quit` → soft-terminate a blocked foreground app (no elevated
  privileges; same-user only).
* Tkinter fullscreen window → BLACKOUT / broadcast display / FOCUS_NOW kiosk
  (Pillow decodes broadcast JPEGs).
* `ioreg HIDIdleTime` → inactivity detection.

Off-macOS every OS call becomes a no-op or a simulated signal, so the entire
agent logic (networking, state machine, analytics) runs and is tested on Linux
CI without changing the behaviour under measurement.

**Soft-enforcement boundary:** without MDM or a signed Network Extension
content filter, ACOS detects → overlays → logs → optionally quits, rather than
blocking at the packet/exec level. This is transparent and documented; nothing
is bypassed. See `KNOWN_LIMITATIONS.md`.

## Analytics (`teacher/analytics.py`)
Append-only `events(ts, session_id, kind, data)` in SQLite. The dashboard
computes completion %, first-attempt accuracy, latency percentiles, and event
counts. Class-completion milestones (25/50/75/90%) are computed console-side
from the fraction of **online** agents that reported a completed task in the
current exercise round.

## Fast re-deploy model (reset-on-reboot labs)
ACOS assumes each Mac may revert to a clean image on reboot, so it does **not**
rely on permanent installation. The LaunchAgent restarts the agent within a
session (crash recovery), and `INSTALL.command` is optimised for a fast
per-lesson USB re-deploy. Install/permission/connect durations are measured and
reported (`install_duration`, `permission_duration`, `connect_duration`).
