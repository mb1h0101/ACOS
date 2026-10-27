# Known Limitations & Classroom Boundary

## 1. macOS permissions in classroom v0.2

### Screen Recording
Not required for the current classroom workflow.

Student thumbnails and teacher-screen Broadcast were removed from the normal
Teacher Console because the teacher can directly observe student screens in the
physical lab and ACOS is not intended to duplicate a traditional broadcast
suite.

The codebase may still contain legacy capture helpers for compatibility, but
INSTALL.command does not ask for Screen Recording permission.

### Browser Automation
Website rules read the active Chrome/Safari tab using Apple Events. macOS may
ask once whether **ACOS Student Agent** may control/read the browser. The
Student Agent is now a real app bundle with bundle ID
`com.acos.studentagent`, so macOS has a stable application identity for this
permission.

If browser Automation is denied, App rules and teacher attention still work,
but URL-based website rules are degraded.

## 2. Website/App enforcement

ACOS currently uses soft classroom enforcement, not packet-level filtering.
It checks the foreground context roughly every 1.5 seconds and responds to a
rule violation with a policy notice (and can optionally quit blocked Apps in
legacy/backend policy settings).

This is the chosen behaviour for the current classroom pilot. A determined user
could briefly reach a site before the next check. True packet-level filtering
would require MDM or a signed Network Extension and is outside v0.2.

## 3. Packaging

The student runtime is installed as:

`/Applications/ACOS Student Agent.app`

Bundle ID:

`com.acos.studentagent`

Test builds are ad-hoc signed. For broad managed deployment, Developer ID
signing and notarization are still recommended to avoid Gatekeeper warnings.

## 4. Automatic discovery

Students normally use Bonjour/mDNS and UDP beacon to find TeacherConsole.app.
If the school LAN blocks both mechanisms, a fixed address can still be placed
in `TEACHER_CONSOLE.txt` as a fallback.

## 5. Security

The console currently assumes a trusted classroom LAN. There is no teacher
authentication or TLS yet. Add those before using ACOS on an untrusted/shared
network.
