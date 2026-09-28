ACOS — Student Agent USB deployment
===================================

BEFORE FIRST USE: copy the built StudentAgent.pkg into this folder
(build it on a Mac with deploy/build_pkg.sh — see docs/BUILD.md).
This folder should contain:
    StudentAgent.pkg          <-- you add this (built + signed on a Mac)
    INSTALL.command
    UNINSTALL.command
    EMERGENCY_RESET.command
    README_FIRST.txt          <-- this file

TO DEPLOY ON A STUDENT MAC
1. Make sure TeacherConsole.app is running on the teacher's Mac (same network).
2. Insert this USB stick.
3. Double-click  INSTALL.command
4. Type the administrator password ONCE when macOS asks.
5. If asked, grant Screen Recording and Accessibility (the installer opens the
   exact settings pane). This is the only unavoidable manual step — macOS does
   not allow an installer to grant these automatically.
6. Wait for "INSTALL SUCCESS". The seat appears on the teacher console.

IF A MAC GETS STUCK (black screen / locked)
   Double-click  EMERGENCY_RESET.command  — it stops the agent and returns full
   control to the student. It does NOT uninstall.

TO REMOVE
   Double-click  UNINSTALL.command

PRIVACY: ACOS collects no student names — only an anonymous session id.
