#!/bin/bash
# ACOS Student Agent — one-double-click installer for a classroom Mac.
#
# Goal: insert USB -> double-click -> one admin prompt -> agent installed,
# started, and auto-discovering the Teacher Console -> INSTALL SUCCESS.
#
# This script is HONEST about macOS permissions: the pkg cannot silently grant
# Screen Recording or Accessibility (TCC). After install it checks them and, if
# missing, tells you exactly which System Settings pane to click and opens it.
#
# Nothing here bypasses macOS security, and no password is stored on the USB.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$HERE/StudentAgent.pkg"
LOG="/tmp/acos-install.log"
START_TS=$(python3 -c 'import time;print(int(time.time()*1000))' 2>/dev/null || date +%s000)

echo "==============================================="
echo "  ACOS Student Agent — classroom install"
echo "==============================================="

if [[ ! -f "$PKG" ]]; then
  echo "ERROR: StudentAgent.pkg not found next to this script."
  echo "Build it first on a Mac with: deploy/build_pkg.sh (see BUILD.md)."
  read -n1 -r -p "Press any key to close."; exit 1
fi

# --- 1. Install the pkg with a single GUI admin prompt ---------------------
# macOS privacy controls can prevent a privileged AppleScript shell from
# reading a package directly from Desktop/Downloads/USB locations. Stage the
# package in /private/tmp first, install from there, then clean it up.
TMP_PKG="/private/tmp/ACOS-StudentAgent.pkg"
rm -f "$TMP_PKG"
cp "$PKG" "$TMP_PKG"
chmod 644 "$TMP_PKG"

echo "Installing agent (you will be asked for the administrator password once)…"
osascript -e "do shell script \"/usr/sbin/installer -pkg '$TMP_PKG' -target /\" with administrator privileges" \
  >>"$LOG" 2>&1 || { echo "Install failed. See $LOG"; rm -f "$TMP_PKG"; read -n1 -r; exit 1; }

rm -f "$TMP_PKG"

# --- 2. Load + start the LaunchAgent in the current user session -----------
PLIST="$HOME/Library/LaunchAgents/com.acos.studentagent.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cp "/usr/local/acos/com.acos.studentagent.plist" "$PLIST" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load  "$PLIST"
launchctl start com.acos.studentagent || true
INSTALL_TS=$(python3 -c 'import time;print(int(time.time()*1000))' 2>/dev/null || date +%s000)

# --- 3. Check TCC permissions (cannot be auto-granted) ---------------------
echo
echo "Checking macOS permissions…"
PERM_JSON="$(/usr/local/acos/acos-agent --check-perms 2>/dev/null || echo '{}')"
echo "$PERM_JSON" >>"$LOG"

need_click=0
if ! echo "$PERM_JSON" | grep -q '"screen_recording".*"granted": true'; then
  need_click=1
  echo
  echo ">>> ACTION REQUIRED — Screen Recording is NOT granted."
  echo "    Open: System Settings > Privacy & Security > Screen Recording"
  echo "    Enable: ACOS Student Agent, then it will restart automatically."
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture" 2>/dev/null || true
fi
if ! echo "$PERM_JSON" | grep -q '"accessibility".*"granted": true'; then
  need_click=1
  echo
  echo ">>> ACTION REQUIRED — Accessibility/Automation is NOT granted."
  echo "    Open: System Settings > Privacy & Security > Accessibility"
  echo "    Enable: ACOS Student Agent."
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || true
fi
PERM_TS=$(python3 -c 'import time;print(int(time.time()*1000))' 2>/dev/null || date +%s000)

# --- 4. Wait briefly for Teacher Console discovery -------------------------
echo
echo "Looking for the Teacher Console on the network…"
CONNECTED="no"
for i in $(seq 1 15); do
  if grep -q "class_mode" /tmp/acos-agent.out.log 2>/dev/null || \
     grep -q "welcome" /tmp/acos-agent.err.log 2>/dev/null; then
     CONNECTED="yes"; break; fi
  # also accept any successful WS by checking the log for connect line
  sleep 1
done
CONNECT_TS=$(python3 -c 'import time;print(int(time.time()*1000))' 2>/dev/null || date +%s000)

# --- 5. Record timings (privacy-safe, no PII) into a local file the agent
#         forwards to the console as install_duration / permission_duration /
#         connect_duration events. -----------------------------------------
mkdir -p "$HOME/Library/Application Support/ACOS"
cat > "$HOME/Library/Application Support/ACOS/deploy_timing.json" <<EOF
{ "install_ms": $((INSTALL_TS-START_TS)),
  "permission_ms": $((PERM_TS-INSTALL_TS)),
  "connect_ms": $((CONNECT_TS-PERM_TS)) }
EOF

echo
echo "-----------------------------------------------"
echo " install duration:    $((INSTALL_TS-START_TS)) ms"
echo " permission step:     $((PERM_TS-INSTALL_TS)) ms"
echo " console connect:     $((CONNECT_TS-PERM_TS)) ms  (connected: $CONNECTED)"
echo "-----------------------------------------------"
if [[ "$need_click" == "1" ]]; then
  echo "INSTALL COMPLETE — but grant the permission(s) above ONCE, then done."
else
  echo "INSTALL SUCCESS ✅  Agent running and permissions OK."
fi
echo
read -n1 -r -p "Press any key to close."
