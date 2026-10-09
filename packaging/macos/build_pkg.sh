#!/usr/bin/env bash
# Build the macOS BlueMail installer (runs ON macOS, Xcode CLT required).
#
#  1. Compiles dist/BlueMail.app  (PyInstaller, windowed)
#  2. Wraps it in a signed-by-nobody .pkg that opens the standard
#     macOS "Install BlueMail" wizard (pkgbuild)
#  3. Also produces a drag-to-Applications .dmg (hdiutil)
#
# Artifacts:  dist/BlueMail.dmg   and   dist/BlueMail-<ver>.pkg
set -euo pipefail
cd "$(dirname "$0")/../.."      # repo root

APP=BlueMail
VERSION=0.2.0
ID=org.bluemail.BlueMail

# ------------------------------------------------------------------- venv
python3 -m venv build/macos-venv
build/macos-venv/bin/pip install --quiet --upgrade pip
build/macos-venv/bin/pip install --quiet PyQt5 pyinstaller

# ------------------------------------------------------------------- app
build/macos-venv/bin/pyinstaller --noconfirm --windowed \
    --name "$APP" --paths . main.py

# ------------------------------------------------------------------- pkg
PKG_STAGE="build/pkgstage/Applications"
rm -rf build/pkgstage
mkdir -p "$PKG_STAGE"
cp -R "dist/$APP.app" "$PKG_STAGE/"
pkgbuild --root build/pkgstage \
    --identifier "$ID" \
    --version "$VERSION" \
    --install-location / \
    --timestamp=none \
    --sign - \
    "dist/$APP-$VERSION.pkg" 2>/dev/null || \
pkgbuild --root build/pkgstage \
    --identifier "$ID" \
    --version "$VERSION" \
    --install-location / \
    "dist/$APP-$VERSION.pkg"

# ------------------------------------------------------------------- dmg
hdiutil create -volname "$APP" \
    -srcfolder "dist/$APP.app" \
    -ov -format UDZO \
    "dist/$APP.dmg"

echo
echo "=== artifacts ==="
ls -lh "dist/$APP.dmg" "dist/$APP-$VERSION.pkg"