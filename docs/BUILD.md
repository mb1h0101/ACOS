# Build & Deploy Guide — classroom v0.2

## Build outputs

- `dist/TeacherConsole.app`
- `dist/StudentAgent.pkg`

StudentAgent.pkg installs a real macOS application:

`/Applications/ACOS Student Agent.app`

Bundle ID: `com.acos.studentagent`

The app runs in the background through the per-user LaunchAgent
`com.acos.studentagent`.

## Build

```bash
tools/build_app.sh
deploy/build_pkg.sh
```

## Classroom deployment

1. Open TeacherConsole.app on the teacher Mac.
2. On each student Mac run INSTALL.command.
3. Enter the administrator password once.
4. The Student Agent starts automatically and discovers Teacher Console.
5. Teacher Console should show the student online.

The default `TEACHER_CONSOLE.txt` value is:

```
AUTO
```

Do not edit IP addresses during normal use. Fixed `host:port` is only a
fallback if the school LAN blocks Bonjour/mDNS and UDP beacon discovery.

## Permissions

Screen Recording is not required for v0.2.

When website rules are first used, macOS may ask once for Automation permission
so ACOS Student Agent can read the current Chrome/Safari tab. Approve that
prompt if website filtering is required.

## Signing

Current CI test artifacts are ad-hoc signed. For broad deployment use a
Developer ID Application signature for ACOS Student Agent.app and
TeacherConsole.app, a Developer ID Installer signature for StudentAgent.pkg,
and notarize the final package.

## Emergency

- `EMERGENCY_RESET.command`: stops the background agent and clears its overlay.
- `UNINSTALL.command`: removes the app bundle, LaunchAgent and ACOS local data.
