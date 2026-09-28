#!/bin/bash
# Build StudentAgent.pkg on a Mac. Produces a self-contained agent binary
# (no system Python required on the target) and an installer package.
#
# Prereqs on the BUILD Mac (not the classroom Macs):
#   * Xcode Command Line Tools  (xcode-select --install)
#   * Python 3.9+               (python3)
#   * pip install pyinstaller aiohttp zeroconf pillow
#
# Signing/notarization (REQUIRED for double-click install on other Macs without
# Gatekeeper warnings) is optional here; see the SIGN section at the bottom.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
DIST="$ROOT/dist"
VERSION="${ACOS_VERSION:-0.1.0}"
rm -rf "$BUILD" "$DIST"; mkdir -p "$BUILD" "$DIST"

echo "[1/5] Installing build deps…"
python3 -m pip install --quiet --upgrade pyinstaller aiohttp zeroconf pillow

echo "[2/5] Building acos-agent binary with PyInstaller…"
cd "$ROOT"
pyinstaller --onefile --name acos-agent \
  --paths "$ROOT" \
  --hidden-import aiohttp --hidden-import zeroconf --hidden-import PIL \
  --collect-submodules common --collect-submodules agent --collect-submodules teacher \
  deploy/agent_entry.py \
  --distpath "$BUILD/bin" --workpath "$BUILD/work" --specpath "$BUILD"

echo "[3/5] Assembling package payload…"
PAYLOAD="$BUILD/payload"
mkdir -p "$PAYLOAD/usr/local/acos"
cp "$BUILD/bin/acos-agent" "$PAYLOAD/usr/local/acos/acos-agent"
cp "$ROOT/deploy/com.acos.studentagent.plist" "$PAYLOAD/usr/local/acos/"
chmod 755 "$PAYLOAD/usr/local/acos/acos-agent"

echo "[4/5] Building component pkg…"
mkdir -p "$BUILD/scripts"
cp "$ROOT/deploy/postinstall" "$BUILD/scripts/postinstall"
chmod 755 "$BUILD/scripts/postinstall"
pkgbuild --root "$PAYLOAD" \
  --scripts "$BUILD/scripts" \
  --identifier com.acos.studentagent \
  --version "$VERSION" \
  --install-location / \
  "$BUILD/StudentAgent-component.pkg"

echo "[5/5] Building product archive (StudentAgent.pkg)…"
productbuild --package "$BUILD/StudentAgent-component.pkg" "$DIST/StudentAgent.pkg"

echo
echo "Built: $DIST/StudentAgent.pkg  (version $VERSION)"
echo
echo "==== SIGNING / NOTARIZATION (do this for real classroom deployment) ===="
echo "Unsigned pkgs trigger a Gatekeeper warning and may be blocked by MDM."
echo "With a Developer ID Installer certificate:"
echo "  productbuild --package \"$BUILD/StudentAgent-component.pkg\" \\"
echo "     --sign \"Developer ID Installer: YOUR NAME (TEAMID)\" \"$DIST/StudentAgent.pkg\""
echo "  xcrun notarytool submit \"$DIST/StudentAgent.pkg\" --keychain-profile ACOS --wait"
echo "  xcrun stapler staple \"$DIST/StudentAgent.pkg\""
echo
echo "NOTE: Screen Recording & Accessibility are TCC permissions. A plain pkg"
echo "cannot pre-grant them. For zero-click permission on managed Macs, ship a"
echo "PPPC configuration profile via MDM (see BUILD.md > Managed permissions)."
