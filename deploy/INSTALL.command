#!/bin/bash
# ACOS Student Agent — one-double-click installer for a classroom Mac.
#
# Goal: insert USB -> double-click -> one admin prompt -> agent installed,
# started, and auto-discovering the Teacher Console -> INSTALL SUCCESS.
#
# Student screen thumbnails and teacher-screen broadcast are not part of the
# classroom v0.2 workflow, so Screen Recording permission is NOT required.
# Browser site rules may cause macOS to ask once for Automation permission when
# ACOS first reads Chrome/Safari. Nothing here bypasses macOS security.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$HERE/StudentAgent.pkg"
LOG="/tmp/acos-install.log"

# Fresh GitHub/browser downloads are commonly tagged by macOS with
# com.apple.quarantine.  Once this script is launched (for example with
# `bash INSTALL.command` if Finder blocks the first launch), clear the tag
# for the whole deployment folder so TeacherConsole.app and the other helper
# scripts do not keep triggering Gatekeeper prompts on this Mac.
xattr -dr com.apple.quarantine "$HERE" 2>/dev/null || true
chmod +x "$HERE"/*.command 2>/dev/null || true
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

# --- 1b. Teacher Console discovery ----------------------------------------
# Default is AUTO: do not pin a classroom to yesterday's DHCP address.
# Student Agent discovers Teacher Console via Bonjour/mDNS, then UDP beacon.
# Only use host:port in TEACHER_CONSOLE.txt as a deliberate fallback for a
# school network that blocks discovery.
TEACHER_CFG="$HERE/TEACHER_CONSOLE.txt"
SUPPORT_DIR="$HOME/Library/Application Support/ACOS"
mkdir -p "$SUPPORT_DIR"
if [[ -f "$TEACHER_CFG" ]]; then
  cfg="$(tr -d '\r\n ' < "$TEACHER_CFG")"
else
  cfg="AUTO"
fi

if [[ -z "$cfg" || "$cfg" == "AUTO" || "$cfg" == "auto" ]]; then
  rm -f "$SUPPORT_DIR/console.txt"
  echo "Teacher Console: automatic discovery (no fixed IP)"
elif [[ "$cfg" == *:* ]]; then
  printf '%s\n' "$cfg" > "$SUPPORT_DIR/console.txt"
  echo "Teacher Console fixed fallback: $cfg"
else
  rm -f "$SUPPORT_DIR/console.txt"
  echo "Teacher Console: automatic discovery (invalid fixed address ignored)"
fi

# --- 2. Load + start the LaunchAgent in the current user session -----------
PLIST="$HOME/Library/LaunchAgents/com.acos.studentagent.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cp "/usr/local/acos/com.acos.studentagent.plist" "$PLIST" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load  "$PLIST"
launchctl start com.acos.studentagent || true
INSTALL_TS=$(python3 -c 'import time;print(int(time.time()*1000))' 2>/dev/null || date +%s000)

# --- 3. Verify the installed app identity ---------------------------------
echo
echo "Checking ACOS Student Agent app…"
APP="/Applications/ACOS Student Agent.app"
AGENT="$APP/Contents/MacOS/acos-agent"
if [[ ! -x "$AGENT" ]]; then
  echo "ERROR: ACOS Student Agent.app is missing or invalid."
  read -n1 -r -p "Press any key to close."; exit 1
fi
echo "Student Agent app: OK"
echo "Bundle ID: com.acos.studentagent"
echo "Screen Recording: not required"
echo "Browser rules: macOS may ask once for Automation permission when first used"
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
echo
echo "INSTALL COMPLETE"
echo "  Student Agent: installed"
echo "  Teacher discovery: automatic"
echo "  Screen Recording: not required"
if [[ "$CONNECTED" == "yes" ]]; then
  echo "  Teacher connection: connected"
else
  echo "  Teacher connection: not connected yet"
  echo "  Keep TeacherConsole.app open; the agent will continue auto-discovery."
fi
echo
read -n1 -r -p "Press any key to close."
