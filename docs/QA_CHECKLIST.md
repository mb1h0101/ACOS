# QA Checklist

Legend: ✅ automated & passing in this repo · 🖥️ must be verified on a real Mac
(cannot run on Linux CI) · ⬜ to check during your pilot.

## A. Networking & protocol (✅ automated)
- ✅ Agent discovers console via manual override
- 🖥️ Agent discovers console via mDNS on school LAN
- 🖥️ Agent discovers console via UDP beacon when mDNS is filtered
- ✅ 40 agents connect (load test: 40/40 online in ~205 ms)
- ✅ Command round-trip latency measured (p50 ≈ 24–98 ms @ 40 clients)
- ✅ Heartbeat keeps agent "online"; missing heartbeat flips to "offline"
- ✅ Forced socket drop → agent reconnects (load test: 40/40 recovered)
- ✅ `reconnect` downtime + `disconnect` events logged

## B. Modes & overlays (✅ logic / 🖥️ visual)
- ✅ DEMO / EXERCISE / REWARD / FREE applied to whole class
- ✅ DEMO / EXERCISE / REWARD / FREE applied to a single seat
- ✅ Reward countdown auto-returns class to EXERCISE
- ✅ `reward_start` + `reward_end` logged
- ✅ Emergency → Focus returns all seats to EXERCISE and clears overlay
- 🖥️ BLACKOUT actually blacks out the student screen (Tk overlay renders)
- 🖥️ FOCUS_NOW brings learning env to front / quits disallowed app
- 🖥️ Teacher broadcast frames render fullscreen on students (needs Pillow)

## C. Policy enforcement (✅ logic / 🖥️ OS effect)
- ✅ Site allowlist / blocklist / off semantics (unit tested)
- ✅ App allowlist / blocklist / off semantics (unit tested)
- ✅ Blocked site → `blocked_navigation` logged (integration test)
- ✅ Blocked app → `blocked_app` logged (integration test)
- ✅ Allowed content produces no block event
- 🖥️ Blocked app is actually quit when "quit blocked app" is on
- 🖥️ Frontmost browser host is read from Safari/Chrome (needs Accessibility)

## D. Monitoring & analytics (✅ automated)
- ✅ Thumbnail request round-trip measured (p50 ≈ 16–51 ms)
- 🖥️ Thumbnails show the real student screen (needs Screen Recording)
- ✅ Broadcast frame latency measured (p50 ≈ 34 ms)
- ✅ Completion %, first-attempt accuracy computed
- ✅ Class milestones 25/50/75/90% fire once each
- ✅ CSV export has header, no name column (privacy)
- ✅ JSON export is a list of `{ts, session_id, kind, data}`
- ✅ No PII in any event (session_id only)

## E. Deployment (🖥️ on real Macs)
- 🖥️ `StudentAgent.pkg` installs with a single admin prompt
- 🖥️ LaunchAgent starts the agent immediately and on next login
- 🖥️ LaunchAgent restarts the agent after a crash (KeepAlive)
- 🖥️ `INSTALL.command` opens the correct System Settings panes when a
  permission is missing, and does NOT claim success while it is missing
- 🖥️ `install_duration` / `permission_duration` / `connect_duration` recorded
  and forwarded to the console
- 🖥️ `EMERGENCY_RESET.command` frees a stuck student immediately
- 🖥️ `UNINSTALL.command` leaves no agent process / LaunchAgent behind
- ⬜ Single-Mac deploy time measured on your hardware (target: minimise)
- ⬜ Whole-lab (40 Mac) deploy time measured end-to-end

## F. Security review (⬜ before pilot)
- ✅ No admin password stored on USB or in scripts (GUI prompt only)
- ✅ No credentials hardcoded anywhere in the source
- ✅ No macOS security bypass; permissions requested through the OS
- ⬜ Add a console access token before running on a shared network
- ⬜ Add TLS/cert pinning if the classroom LAN is not isolated
- ⬜ Confirm signing + notarization + (if MDM) PPPC profile deployed
