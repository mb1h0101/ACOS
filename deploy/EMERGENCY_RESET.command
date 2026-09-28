#!/bin/bash
# ACOS Student Agent — EMERGENCY RESET.
#
# Use if a Mac is stuck in BLACKOUT / broadcast / kiosk, or the agent is
# misbehaving. This immediately stops the agent and clears any overlay so the
# student regains full control of the machine. It does NOT uninstall.
set -uo pipefail
echo "ACOS emergency reset — stopping agent and clearing overlays…"

PLIST="$HOME/Library/LaunchAgents/com.acos.studentagent.plist"
# Stop keep-alive first so it doesn't relaunch, then kill.
launchctl unload "$PLIST" 2>/dev/null || true
pkill -f "/usr/local/acos/acos-agent" 2>/dev/null || true

# The overlay is a child window of the agent process; killing the agent closes
# it. As a belt-and-braces measure, also clear the crash marker so the next
# start is clean rather than a "recovery".
rm -f "$HOME/Library/Application Support/ACOS/session.marker" 2>/dev/null || true

echo "Agent stopped and overlays cleared. The student now has full control."
echo "To resume class control, run INSTALL.command again (fast re-deploy)."
read -n1 -r -p "Press any key to close."
