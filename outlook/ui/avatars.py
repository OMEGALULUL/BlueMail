"""Sender avatar circles: deterministic initials on a flat accent color."""

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap

# Outlook-style flat accent palette
PALETTE = [
    "#d13438",  # red
    "#0078d4",  # blue
    "#107c10",  # green
    "#8764b8",  # purple
    "#ca5010",  # orange
    "#038387",  # teal
    "#c239b3",  # magenta
    "#498205",  # olive
    "#005b70",  # dark teal
    "#8e562e",  # brown
    "#2d7f9e",  # steel
    "#742774",  # plum
]

_cache = {}


def initials(name, addr=""):
    text = (name or "").strip() or (addr or "").strip() or "?"
    if "<" in text:
        text = text.split("<")[0].strip()
    if "@" in text and " " not in text:
        text = text.split("@")[0]
    parts = [p for p in text.replace(".", " ").replace("_", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def avatar_color(name, addr=""):
    key = ((name or "").strip() or (addr or "").strip() or "?").lower()
    total = sum(ord(c) for c in key)
    return QColor(PALETTE[total % len(PALETTE)])


def avatar_pixmap(name, addr="", size=40):
    """Render a filled circle with white initials (cached)."""
    key = (name or "", addr or "", int(size))
    pm = _cache.get(key)
    if pm is not None:
        return pm
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(avatar_color(name, addr))
    p.drawEllipse(0, 0, size, size)
    p.setPen(QColor("white"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(max(10, int(size * 0.40)))
    p.setFont(font)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter,
               initials(name, addr))
    p.end()
    _cache[key] = pm
    return pm


def unread_dot(size=20):
    """Small filled accent dot used as the unread indicator in the list."""
    key = ("dot", int(size))
    pm = _cache.get(key)
    if pm is not None:
        return pm
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#0563c1"))
    r = size * 0.34
    p.drawEllipse(QRectF((size - r * 2) / 2, (size - r * 2) / 2, r * 2, r * 2))
    p.end()
    _cache[key] = pm
    return pm
