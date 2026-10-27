#!/bin/bash
# ACOS Teacher Console — one-step classroom launcher.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/TeacherConsole.app"

if [[ ! -d "$APP" ]]; then
  echo "ERROR: TeacherConsole.app not found next to this launcher."
  read -n1 -r -p "Press any key to close."
  exit 1
fi

# GitHub/browser downloads may carry macOS quarantine attributes.
# Clear them for this ACOS deployment folder, then launch the Teacher Console.
xattr -dr com.apple.quarantine "$HERE" 2>/dev/null || true
open "$APP"
