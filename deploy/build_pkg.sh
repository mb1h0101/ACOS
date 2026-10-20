#!/bin/bash
# Build StudentAgent.pkg on a Mac.
#
# The student runtime is installed as a real macOS app bundle:
#   /Applications/ACOS Student Agent.app
# with a stable bundle identifier:
#   com.acos.studentagent
#
# This gives macOS privacy/permission UI a stable, visible app identity.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
DIST="$ROOT/dist"
VERSION="${ACOS_VERSION:-0.2.0}"
rm -rf "$BUILD" "$DIST"; mkdir -p "$BUILD" "$DIST"

echo "[1/6] Installing build deps…"
python3 -m pip install --quiet --upgrade pyinstaller aiohttp zeroconf pillow

echo "[2/6] Building student agent executable…"
cd "$ROOT"
pyinstaller --onefile --name acos-agent \
  --paths "$ROOT" \
  --hidden-import aiohttp --hidden-import zeroconf --hidden-import PIL \
  --collect-submodules common --collect-submodules agent --collect-submodules teacher \
  deploy/agent_entry.py \
  --distpath "$BUILD/bin" --workpath "$BUILD/work" --specpath "$BUILD"

echo "[3/6] Assembling ACOS Student Agent.app…"
APP="$BUILD/ACOS Student Agent.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BUILD/bin/acos-agent" "$APP/Contents/MacOS/acos-agent"
chmod 755 "$APP/Contents/MacOS/acos-agent"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key>
  <string>com.acos.studentagent</string>
  <key>CFBundleName</key>
  <string>ACOS Student Agent</string>
  <key>CFBundleDisplayName</key>
  <string>ACOS Student Agent</string>
  <key>CFBundleExecutable</key>
  <string>acos-agent</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$VERSION</string>
  <key>CFBundleVersion</key>
  <string>$VERSION</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSAppleEventsUsageDescription</key>
  <string>ACOS 需要讀取目前瀏覽器分頁網址，以套用教師設定的網站規則。</string>
</dict>
</plist>
EOF

# Ad-hoc sign the test build so macOS sees one coherent app identity.
codesign --deep --force --sign - "$APP"

echo "[4/6] Assembling package payload…"
PAYLOAD="$BUILD/payload"
mkdir -p "$PAYLOAD/Applications" "$PAYLOAD/usr/local/acos"
cp -R "$APP" "$PAYLOAD/Applications/"
cp "$ROOT/deploy/com.acos.studentagent.plist" "$PAYLOAD/usr/local/acos/"
chmod 644 "$PAYLOAD/usr/local/acos/com.acos.studentagent.plist"

echo "[5/6] Building component pkg…"
mkdir -p "$BUILD/scripts"
cp "$ROOT/deploy/postinstall" "$BUILD/scripts/postinstall"
chmod 755 "$BUILD/scripts/postinstall"
pkgbuild --root "$PAYLOAD" \
  --scripts "$BUILD/scripts" \
  --identifier com.acos.studentagent.pkg \
  --version "$VERSION" \
  --install-location / \
  "$BUILD/StudentAgent-component.pkg"

echo "[6/6] Building product archive…"
productbuild --package "$BUILD/StudentAgent-component.pkg" "$DIST/StudentAgent.pkg"

echo
echo "Built: $DIST/StudentAgent.pkg"
echo "Installed app identity: /Applications/ACOS Student Agent.app"
echo "Bundle ID: com.acos.studentagent"
echo
echo "For production classroom deployment, replace ad-hoc signing with a"
echo "Developer ID Application signature and notarize the pkg."
