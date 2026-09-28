# Known Limitations & Honest Enforcement Boundary

This document exists because your stated rule is: *if a permission cannot be
granted legitimately by a normal installer, do not pretend it succeeded.* ACOS
follows that rule. Here is exactly where the walls are.

## 1. The three macOS permission walls

### 1a. Screen Recording (TCC) — REQUIRED for thumbnails & teacher broadcast
* Used by: student thumbnail monitoring, teacher "Broadcast my screen".
* **Cannot be auto-granted by a pkg.** Apple's TCC requires the user to enable
  it manually, OR an MDM-pushed **PPPC profile** to pre-approve it.
* First-run action (per Mac): **System Settings → Privacy & Security → Screen
  Recording → enable "ACOS Student Agent"** (and, on the teacher Mac, for
  TeacherConsole). `INSTALL.command` detects this and opens the pane for you.
* Until granted: thumbnails/broadcast return nothing; ACOS reports the
  permission as **not granted** — it never reports a black/failed capture as
  success.

### 1b. Accessibility / Automation (TCC) — REQUIRED for URL detection & focus
* Used by: reading the frontmost browser tab's host (for site enforcement),
  bringing the learning environment to front.
* **Cannot be auto-granted by a pkg.** Same manual grant or PPPC profile.
* First-run action: **System Settings → Privacy & Security → Accessibility →
  enable "ACOS Student Agent"**.
* Until granted: app-name enforcement still works; **browser-URL** enforcement
  is degraded (ACOS can see the app is a browser but not the tab host).

### 1c. Real network-level blocking — needs MDM or a signed Network Extension
* A packet-level content filter that a student **cannot** get around requires
  a **NEFilterDataProvider** system extension with the
  `com.apple.developer.networking.networkextension` entitlement (a paid Apple
  Developer account + user/MDM approval), or an MDM web-content-filter payload.
* ACOS v0.1 ships **soft enforcement** instead: it detects a disallowed
  foreground app or browser host, logs `blocked_app` / `blocked_navigation`,
  raises the BLACKOUT/kiosk overlay, and (optionally) quits the app. This is
  effective for ordinary classroom use and is **honest about its limits**: a
  determined student on an un-managed Mac can still reach a site between monitor
  ticks (~1.5 s) or by using an app ACOS cannot quit.

> **Recommended path to hard enforcement:** enroll the lab Macs in an MDM and
> push (a) a PPPC profile pre-approving Screen Recording + Accessibility for
> ACOS, and (b) a web content-filter payload. With that, first-run clicks
> disappear and site blocking becomes packet-level. ACOS is built to run
> alongside such profiles; it does not require them to function at the soft
> level.

## 2. Packaging / distribution
* `StudentAgent.pkg` and `TeacherConsole.app` must be **signed (Developer ID)
  and notarized** to install on other Macs without Gatekeeper warnings, and to
  satisfy most MDM allowlists. Build scripts print the exact commands; the
  unsigned build is for your own test Mac only.
* The `.pkg`/`.app` are **built on a Mac** (PyInstaller). They cannot be built
  on the Linux CI box; `build_pkg.sh` / `build_app.sh` are provided for you to
  run once on a Mac. This is why this repo ships source + build scripts rather
  than pre-built macOS binaries.

## 3. Broadcast fidelity
* Teacher broadcast is capture-and-relay of JPEG frames at ~1 fps (configurable)
  — suitable for showing slides/steps, **not** smooth video. Higher fps
  increases bandwidth; 40 clients × full-screen JPEG is the load ceiling to
  watch. For motion-heavy demos, 金偉 remains a reasonable **fallback** (its
  only sanctioned role here).

## 4. Reset-on-reboot labs
* ACOS assumes disks may revert on reboot and therefore does not persist across
  reboots. You re-deploy each lesson from USB. The `agent_id` regenerates each
  boot (so it is effectively per-lesson) — this is privacy-positive but means
  seat labels must be re-applied if the image resets. (If your image is *not*
  reset, the id and labels persist normally.)

## 5. What is NOT yet implemented in v0.1
* No teacher authentication on the console (assumes a trusted teacher LAN /
  single teacher machine). Add a token before using on an open network.
* No TLS on the LAN WebSocket (add a self-signed cert + pinning for hostile
  networks). Fine for an isolated classroom VLAN.
* Broadcast is one-way (teacher→students); no student-initiated screen share.
* Learning-content task events (`task_start`, `first_attempt_accuracy`, etc.)
  are emitted by the agent's event API — wire your actual courseware to call
  them, or they only populate from the demo/driver.
* Overlay hardening (hiding Dock/menu bar, blocking Cmd-Tab) is basic; a
  hardened kiosk needs the PPPC/MDM path above.
