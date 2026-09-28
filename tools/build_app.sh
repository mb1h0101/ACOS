#!/bin/bash
# Build TeacherConsole.app on a Mac (the teacher's machine or a build Mac).
#
# Prereqs: Python 3.9+, and:  pip install pyinstaller aiohttp zeroconf pillow
#
# The app bundles the web UI (teacher/static) as data so the console works
# fully offline — no CDN, no internet needed in the classroom.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build_app"; DIST="$ROOT/dist"
rm -rf "$BUILD"; mkdir -p "$BUILD" "$DIST"

echo "[1/2] Installing build deps…"
python3 -m pip install --quiet --upgrade pyinstaller aiohttp zeroconf pillow

echo "[2/2] Building TeacherConsole.app…"
cd "$ROOT"
pyinstaller --windowed --name TeacherConsole \
  --paths "$ROOT" \
  --hidden-import aiohttp --hidden-import zeroconf \
  --collect-submodules common --collect-submodules teacher --collect-submodules agent \
  --add-data "$ROOT/teacher/static:teacher/static" \
  deploy/teacher_entry.py \
  --distpath "$DIST" --workpath "$BUILD/work" --specpath "$BUILD"

echo
echo "Built: $DIST/TeacherConsole.app"
echo "Run it: open '$DIST/TeacherConsole.app'  (console opens in your browser)"
echo
echo "For distribution to another Mac, sign + notarize:"
echo "  codesign --deep --force --options runtime \\"
echo "    --sign \"Developer ID Application: YOUR NAME (TEAMID)\" \"$DIST/TeacherConsole.app\""
echo "  xcrun notarytool submit ... --wait ; xcrun stapler staple \"$DIST/TeacherConsole.app\""
echo
echo "NOTE: 'Broadcast my screen' on the teacher Mac also needs Screen Recording"
echo "permission (System Settings > Privacy & Security > Screen Recording)."
