#!/usr/bin/env bash
# Build distributable packages for BlueMail.
# Produces (in dist/):
#   BlueMail-x86_64.AppImage     — double-click runnable app
#   bluemail_0.2.0_amd64.deb     — Debian/Ubuntu package
#   BlueMail-linux-x86_64.tar.gz — portable tarball
set -euo pipefail
cd "$(dirname "$0")"

APP=BlueMail
VERSION=0.2.0
ARCH=$(uname -m)
BUILD=build
ICON=/tmp/bluemail-icon.png

# ---------------------------------------------------------------- icon
python3 - <<'EOF'
import sys, os
sys.path.insert(0, ".")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from outlook.ui import icons
icons.icon("new_mail", 256).pixmap(256, 256).save("/tmp/bluemail-icon.png")
EOF
cp "$ICON" packaging/bluemail.png

# ----------------------------------------------------------- pyinstaller
pyinstaller --noconfirm --windowed --name "$APP" --paths . main.py

# ---------------------------------------------------------------- AppImage
APPDIR="$BUILD/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/share/bluemail" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "dist/$APP/." "$APPDIR/usr/share/bluemail/"
cp packaging/AppRun "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp packaging/bluemail.desktop "$APPDIR/"
cp packaging/bluemail.desktop "$APPDIR/usr/share/applications/"
cp packaging/bluemail.png "$APPDIR/bluemail.png"
cp packaging/bluemail.png "$APPDIR/.DirIcon"
cp packaging/bluemail.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/bluemail.png"
desktop-file-validate packaging/bluemail.desktop

TOOL=${APPIMAGETOOL:-/tmp/opencode/appimagetool}
if [ ! -x "$TOOL" ]; then
    TOOL="$BUILD/appimagetool"
    curl -sL -o "$TOOL" \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" \
    "dist/$APP-$ARCH.AppImage"

# ------------------------------------------------------------------- .deb
DEBROOT="$BUILD/debroot"
rm -rf "$DEBROOT"
mkdir -p "$DEBROOT/DEBIAN" "$DEBROOT/opt" \
         "$DEBROOT/usr/bin" "$DEBROOT/usr/share/applications" \
         "$DEBROOT/usr/share/icons/hicolor/256x256/apps"
cp -a "dist/$APP" "$DEBROOT/opt/"
install -m 755 packaging/bluemail.sh "$DEBROOT/usr/bin/bluemail"
install -m 644 packaging/bluemail.desktop "$DEBROOT/usr/share/applications/"
install -m 644 packaging/bluemail.png \
    "$DEBROOT/usr/share/icons/hicolor/256x256/apps/bluemail.png"
SIZE=$(du -sk "$DEBROOT" | cut -f1)
cat > "$DEBROOT/DEBIAN/control" <<EOF
Package: bluemail
Version: $VERSION
Section: mail
Priority: optional
Architecture: amd64
Maintainer: BlueMail
Installed-Size: $SIZE
Description: Free local desktop mail client
  Outlook 2016-style desktop mail client with a friendly look.
  Gmail, Outlook, Hotmail, Yahoo, iCloud and custom IMAP/POP3/SMTP.
EOF
fakeroot dpkg-deb --build "$DEBROOT" "dist/bluemail_${VERSION}_${ARCH}.deb"

# --------------------------------------------------------------- tarball
tar -C dist -czf "dist/$APP-linux-$ARCH.tar.gz" "$APP"

echo
echo "=== artifacts ==="
ls -lh dist/*.AppImage dist/*.deb dist/*.tar.gz
