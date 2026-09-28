# Build & Deploy Guide

## 0. Machines
* **Build Mac** (once): produces `TeacherConsole.app` and `StudentAgent.pkg`.
* **Teacher Mac**: runs `TeacherConsole.app` (can be the build Mac).
* **Student Macs** (~40): receive `StudentAgent.pkg` via the USB folder.

## 1. Build prerequisites (Build Mac)
```bash
xcode-select --install                       # Command Line Tools
python3 -m pip install pyinstaller aiohttp zeroconf pillow
```

## 2. Build the Teacher Console
```bash
tools/build_app.sh          # -> dist/TeacherConsole.app
open dist/TeacherConsole.app # console opens at http://localhost:8770
```
On first run, grant **Screen Recording** to TeacherConsole if you will use
"Broadcast my screen".

## 3. Build the Student Agent package
```bash
deploy/build_pkg.sh         # -> dist/StudentAgent.pkg  (version via ACOS_VERSION)
```

## 4. Sign & notarize (required for real deployment)
Unsigned artifacts trigger Gatekeeper and are usually blocked by MDM.
```bash
# App
codesign --deep --force --options runtime \
  --sign "Developer ID Application: YOUR NAME (TEAMID)" dist/TeacherConsole.app
# Pkg
productbuild --package build/StudentAgent-component.pkg \
  --sign "Developer ID Installer: YOUR NAME (TEAMID)" dist/StudentAgent.pkg
xcrun notarytool submit dist/StudentAgent.pkg --keychain-profile ACOS --wait
xcrun stapler staple dist/StudentAgent.pkg
```

## 5. Assemble the USB deployment folder
```bash
mkdir -p ACOS_USB
cp dist/StudentAgent.pkg ACOS_USB/
cp deploy/INSTALL.command deploy/UNINSTALL.command deploy/EMERGENCY_RESET.command ACOS_USB/
chmod +x ACOS_USB/*.command
```
Copy `ACOS_USB/` to the USB stick. (A template lives in `deploy/USB/`.)

## 6. Per-lesson deployment on each student Mac
1. Start `TeacherConsole.app` on the teacher Mac (it advertises on the LAN).
2. Insert USB → open `INSTALL.command` (double-click).
3. Enter the admin password **once** in the macOS prompt.
4. If prompted, grant **Screen Recording** and **Accessibility** (the script
   opens the exact panes). This is the only unavoidable manual step, per the
   TCC walls in `KNOWN_LIMITATIONS.md`.
5. The agent auto-discovers the console; the console shows the seat online.

`INSTALL.command` records `install_duration`, `permission_duration`,
`connect_duration` and the agent forwards them to the console analytics.

### Optional: skip discovery on a locked-down network
Set the console address before install:
```bash
echo "192.168.1.50:8770" > "$HOME/Library/Application Support/ACOS/console.txt"
```
or export `ACOS_CONSOLE=192.168.1.50:8770`.

## 7. Zero-click permissions (managed labs)
If the Macs are MDM-enrolled, push a **PPPC configuration profile** pre-approving
Screen Recording and Accessibility for `com.acos.studentagent`, plus a web
content-filter payload for hard site blocking. Then step 4 disappears entirely.
A sample PPPC identifier map:
```
Identifier:       com.acos.studentagent   (type: bundleID / path /usr/local/acos/acos-agent)
Services:         ScreenCapture = Allow,  Accessibility = Allow
```

## 8. Uninstall / emergency
* `UNINSTALL.command` — remove agent + LaunchAgent + local data.
* `EMERGENCY_RESET.command` — instantly stop the agent and clear any overlay so
  a stuck student regains control (does not uninstall).
