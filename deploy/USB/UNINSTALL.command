#!/bin/bash
# ACOS Student Agent — clean uninstall.
set -uo pipefail
echo "Removing ACOS Student Agent…"

PLIST="$HOME/Library/LaunchAgents/com.acos.studentagent.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"

# Remove installed binary (needs admin).
osascript -e 'do shell script "rm -rf /usr/local/acos" with administrator privileges' 2>/dev/null || \
  rm -rf /usr/local/acos 2>/dev/null || true

# Remove local app-support (analytics markers, timing — no PII).
rm -rf "$HOME/Library/Application Support/ACOS"
rm -f /tmp/acos-agent.out.log /tmp/acos-agent.err.log

# Forget the pkg receipt.
pkgutil --forget com.acos.studentagent >/dev/null 2>&1 || true

echo "Uninstall complete."
echo "NOTE: macOS keeps the Screen Recording / Accessibility entries in"
echo "System Settings until you remove them there manually (macOS does not"
echo "let an app delete its own TCC grants)."
read -n1 -r -p "Press any key to close."
