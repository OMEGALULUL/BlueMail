"""Flat icon set painted with QPainter (Outlook-style, 24x24 grid)."""

import sys

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_CACHE = {}

BLUE = "#0078d4"
BLUE_DARK = "#2b579a"
GRAY = "#605e5c"
GRAY_DARK = "#3b3a39"
RED = "#d13438"
GREEN = "#107c10"
GOLD = "#f6c445"
GOLD_EDGE = "#c6952a"
WHITE = "#ffffff"


def _qcolor(value):
    return QColor(value)


def _envelope(p, body=WHITE, edge=BLUE_DARK, x=3, y=6, w=18, h=13):
    from PyQt5.QtGui import QColor
    p.setBrush(QColor(body))
    p.setPen(QPen(QColor(edge), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawRoundedRect(QRectF(x, y, w, h), 1.6, 1.6)
    path = QPainterPath()
    path.moveTo(x + 1.2, y + 1.5)
    path.lineTo(x + w / 2, y + h * 0.58)
    path.lineTo(x + w - 1.2, y + 1.5)
    p.drawPath(path)


def _arrow_head(p, tip, angle_deg, size=4.2, color=BLUE):
    from PyQt5.QtGui import QColor, QPolygonF
    import math
    a = math.radians(angle_deg)
    b = math.radians(angle_deg + 140)
    c = math.radians(angle_deg - 140)
    pts = [
        QPointF(*tip),
        QPointF(tip[0] + size * math.cos(b), tip[1] + size * math.sin(b)),
        QPointF(tip[0] + size * math.cos(c), tip[1] + size * math.sin(c)),
    ]
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF(pts))


def draw_new_mail(p):
    _envelope(p)


def draw_open_mail(p):
    from PyQt5.QtGui import QColor
    _envelope(p, body="#e8f2fb")
    p.setBrush(QColor(BLUE))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(18.5, 17.5), 2.6, 2.6)


def draw_delete(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(GRAY), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(5.5, 7.5, 13, 13), 1.5, 1.5)
    p.drawLine(QPointF(4, 7.5), QPointF(20, 7.5))
    p.drawLine(QPointF(10, 4.5), QPointF(14, 4.5))
    p.drawLine(QPointF(9.5, 10.5), QPointF(9.5, 17.5))
    p.drawLine(QPointF(14.5, 10.5), QPointF(14.5, 17.5))


def draw_reply(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(BLUE), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(18, 7)
    path.cubicTo(18, 14, 15, 16, 9.5, 16)
    p.drawPath(path)
    _arrow_head(p, (7.5, 16), 180, 4.4, BLUE)


def draw_reply_all(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(BLUE), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(19, 7)
    path.cubicTo(19, 14, 16, 16.5, 11, 16.5)
    p.drawPath(path)
    path2 = QPainterPath()
    path2.moveTo(17, 3.5)
    path2.cubicTo(17, 11, 14, 13.5, 9, 13.5)
    p.setPen(QPen(QColor("#4da3ff"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path2)
    _arrow_head(p, (7.5, 13.5), 180, 4, BLUE)
    _arrow_head(p, (9.5, 16.5), 180, 4.4, BLUE)


def draw_forward(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(BLUE), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(6, 7)
    path.cubicTo(6, 14, 9, 16, 14.5, 16)
    p.drawPath(path)
    _arrow_head(p, (16.5, 16), 0, 4.4, BLUE)


def draw_flag(p):
    from PyQt5.QtGui import QColor, QPolygonF
    p.setPen(QPen(QColor(GRAY_DARK), 1.7, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(7.5, 3.5), QPointF(7.5, 20.5))
    p.setBrush(QColor(RED))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(8.6, 4.5), QPointF(19.5, 7.6), QPointF(8.6, 11),
    ]))


def draw_unflag(p):
    from PyQt5.QtGui import QColor, QPolygonF
    p.setPen(QPen(QColor(GRAY), 1.7, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(7.5, 3.5), QPointF(7.5, 20.5))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(GRAY), 1.4, Qt.SolidLine, Qt.RoundCap))
    p.drawPolygon(QPolygonF([
        QPointF(8.6, 4.5), QPointF(19.5, 7.6), QPointF(8.6, 11),
    ]))


def draw_attach(p):
    from PyQt5.QtGui import QColor
    p.save()
    p.translate(12, 12)
    p.rotate(-45)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(GRAY), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawRoundedRect(QRectF(-7.5, -3.5, 15, 7), 3.5, 3.5)
    p.setPen(QPen(QColor("#8a8886"), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawRoundedRect(QRectF(-4.5, -1.8, 9, 3.6), 1.8, 1.8)
    p.restore()


def draw_send_recv(p):
    from PyQt5.QtGui import QColor, QPolygonF
    # up (send)
    p.setPen(QPen(QColor(BLUE), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(8.5, 19.5), QPointF(8.5, 7))
    p.setBrush(QColor(BLUE))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(8.5, 4), QPointF(5.3, 8.6), QPointF(11.7, 8.6),
    ]))
    # down (receive)
    p.setPen(QPen(QColor(GREEN), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(15.5, 4.5), QPointF(15.5, 17))
    p.setBrush(QColor(GREEN))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(15.5, 20), QPointF(12.3, 15.4), QPointF(18.7, 15.4),
    ]))


def draw_send(p):
    from PyQt5.QtGui import QColor, QPolygonF
    _envelope(p, x=3, y=7, w=15, h=11)
    p.setBrush(QColor(GREEN))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(21, 5), QPointF(13, 11.5), QPointF(18, 12.5),
        QPointF(14.5, 19), QPointF(17.5, 13.4), QPointF(13.5, 13),
    ]))


def draw_folder_base(p, overlay=None):
    from PyQt5.QtGui import QColor
    path = QPainterPath()
    path.moveTo(3.5, 7.5)
    path.lineTo(9.5, 7.5)
    path.lineTo(11.6, 10)
    path.lineTo(20.5, 10)
    path.lineTo(20.5, 19.5)
    path.lineTo(3.5, 19.5)
    path.closeSubpath()
    p.setBrush(QColor(GOLD))
    p.setPen(QPen(QColor(GOLD_EDGE), 1.4, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
    p.drawPath(path)
    if overlay:
        overlay(p)


def _overlay_down_arrow(p):
    from PyQt5.QtGui import QColor, QPolygonF
    p.setPen(QPen(QColor(BLUE_DARK), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(12, 12.4), QPointF(12, 16.6))
    p.setBrush(QColor(BLUE_DARK))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(12, 18.6), QPointF(9.9, 15), QPointF(14.1, 15),
    ]))


def _overlay_up_arrow(p):
    from PyQt5.QtGui import QColor, QPolygonF
    p.setPen(QPen(QColor(BLUE_DARK), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(12, 17.4), QPointF(12, 13))
    p.setBrush(QColor(BLUE_DARK))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(12, 11.4), QPointF(9.9, 15), QPointF(14.1, 15),
    ]))


def _overlay_pencil(p):
    from PyQt5.QtGui import QColor, QPolygonF
    p.setPen(QPen(QColor(GRAY_DARK), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(8.8, 17.6), QPointF(15.6, 11.6))
    p.setBrush(QColor(GRAY_DARK))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(16.4, 10.8), QPointF(15.2, 14), QPointF(13.6, 12.4),
    ]))


def _overlay_junk(p):
    from PyQt5.QtGui import QColor
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(RED), 1.8, Qt.SolidLine, Qt.RoundCap))
    p.drawEllipse(QPointF(12, 15), 4.2, 4.2)
    p.drawLine(QPointF(9.4, 17.8), QPointF(14.6, 12.2))


def draw_folder(p):
    draw_folder_base(p)


def draw_folder_inbox(p):
    draw_folder_base(p, _overlay_down_arrow)


def draw_folder_sent(p):
    draw_folder_base(p, _overlay_up_arrow)


def draw_folder_drafts(p):
    draw_folder_base(p, _overlay_pencil)


def draw_folder_junk(p):
    draw_folder_base(p, _overlay_junk)


def draw_importance_high(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(RED), 2.4, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(12, 5.5), QPointF(12, 14))
    p.setBrush(QColor(RED))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(12, 18.5), 1.5, 1.5)


def draw_importance_low(p):
    from PyQt5.QtGui import QColor, QPolygonF
    p.setPen(QPen(QColor(BLUE), 2.2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(12, 5), QPointF(12, 14.5))
    p.setBrush(QColor(BLUE))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([
        QPointF(12, 19), QPointF(8.8, 14), QPointF(15.2, 14),
    ]))


def draw_search(p):
    from PyQt5.QtGui import QColor
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(GRAY_DARK), 2, Qt.SolidLine, Qt.RoundCap))
    p.drawEllipse(QPointF(10.5, 10.5), 5.6, 5.6)
    p.setPen(QPen(QColor(GRAY_DARK), 2.6, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(14.7, 14.7), QPointF(19.5, 19.5))


def draw_account(p):
    from PyQt5.QtGui import QColor
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(GRAY))
    p.drawEllipse(QPointF(12, 8.5), 4, 4)
    path = QPainterPath()
    path.moveTo(4.8, 20.5)
    path.cubicTo(5.6, 14.8, 18.4, 14.8, 19.2, 20.5)
    p.drawPath(path)


def draw_refresh(p):
    from PyQt5.QtGui import QColor
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(GREEN), 2.2, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(QRectF(4.5, 4.5, 15, 15), -50 * 16, -240 * 16)
    _arrow_head(p, (17.6, 7.4), 200, 3.8, GREEN)


def draw_new_folder(p):
    from PyQt5.QtGui import QColor
    draw_folder_base(p)
    p.setPen(QPen(QColor(BLUE_DARK), 1.8, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(12, 12.4), QPointF(12, 17.4))
    p.drawLine(QPointF(9.5, 14.9), QPointF(14.5, 14.9))


def draw_reading_pane_bottom(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(GRAY), 1.5, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(3.5, 4.5, 17, 15), 1.5, 1.5)
    p.setBrush(QColor("#cfe4f7"))
    p.drawRoundedRect(QRectF(5, 13, 14, 5), 1, 1)
    p.setPen(QPen(QColor(GRAY), 1.2))
    p.drawLine(QPointF(6.5, 7), QPointF(17.5, 7))
    p.drawLine(QPointF(6.5, 9.5), QPointF(17.5, 9.5))


def draw_reading_pane_right(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(GRAY), 1.5, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(3.5, 4.5, 17, 15), 1.5, 1.5)
    p.setBrush(QColor("#cfe4f7"))
    p.drawRoundedRect(QRectF(13, 6, 6, 12), 1, 1)
    p.setPen(QPen(QColor(GRAY), 1.2))
    p.drawLine(QPointF(6, 8), QPointF(11, 8))
    p.drawLine(QPointF(6, 11), QPointF(11, 11))
    p.drawLine(QPointF(6, 14), QPointF(11, 14))


def draw_folder_pane(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(GRAY), 1.5, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(3.5, 4.5, 17, 15), 1.5, 1.5)
    p.setBrush(QColor("#e1dfdd"))
    p.drawRect(QRectF(3.5, 4.5, 6.5, 15))
    p.setPen(QPen(QColor(GRAY), 1.2))
    p.drawLine(QPointF(12, 8), QPointF(18.5, 8))
    p.drawLine(QPointF(12, 11), QPointF(18.5, 11))
    p.drawLine(QPointF(12, 14), QPointF(18.5, 14))


def draw_exit(p):
    from PyQt5.QtGui import QColor, QPolygonF
    p.setPen(QPen(QColor(GRAY_DARK), 2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(5, 5), QPointF(13.5, 12))
    p.drawLine(QPointF(5, 19), QPointF(13.5, 12))
    p.setPen(QPen(QColor(RED), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(14, 5.5), QPointF(20, 5.5))
    p.drawLine(QPointF(20, 5.5), QPointF(20, 18.5))
    p.drawLine(QPointF(20, 18.5), QPointF(14, 18.5))
    p.drawLine(QPointF(14, 18.5), QPointF(14, 14))
    p.drawLine(QPointF(14, 14), QPointF(17.5, 12))
    p.drawLine(QPointF(17.5, 12), QPointF(14, 10))
    p.drawLine(QPointF(14, 10), QPointF(14, 5.5))


def draw_archive(p):
    from PyQt5.QtGui import QColor
    p.setPen(QPen(QColor(GRAY), 1.5, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
    p.setBrush(QColor("#e1dfdd"))
    p.drawRoundedRect(QRectF(3.5, 4.5, 17, 5), 1.2, 1.2)
    p.setBrush(QColor("#f3f2f1"))
    p.drawRoundedRect(QRectF(5, 9.5, 14, 10), 1.2, 1.2)
    p.setPen(QPen(QColor(GRAY), 1.4, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(9.5, 13), QPointF(14.5, 13))


_DRAWERS = {
    "new_mail": draw_new_mail,
    "open_mail": draw_open_mail,
    "delete": draw_delete,
    "reply": draw_reply,
    "reply_all": draw_reply_all,
    "forward": draw_forward,
    "flag": draw_flag,
    "unflag": draw_unflag,
    "attach": draw_attach,
    "send_recv": draw_send_recv,
    "send": draw_send,
    "folder": draw_folder,
    "folder_inbox": draw_folder_inbox,
    "folder_sent": draw_folder_sent,
    "folder_drafts": draw_folder_drafts,
    "folder_junk": draw_folder_junk,
    "trash": draw_delete,
    "archive": draw_archive,
    "importance_high": draw_importance_high,
    "importance_low": draw_importance_low,
    "search": draw_search,
    "account": draw_account,
    "refresh": draw_refresh,
    "new_folder": draw_new_folder,
    "pane_bottom": draw_reading_pane_bottom,
    "pane_right": draw_reading_pane_right,
    "folder_pane": draw_folder_pane,
    "exit": draw_exit,
}


def icon(name, size=24) -> QIcon:
    key = (name, size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    scale = size / 24.0
    p.scale(scale, scale)
    drawer = _DRAWERS.get(name)
    if drawer is not None:
        try:
            drawer(p)
        except Exception as exc:
            print(f"icon {name!r} failed: {exc}", file=sys.stderr)
    p.end()
    ico = QIcon(pm)
    _CACHE[key] = ico
    return ico


def pixmap(name, size=24) -> QPixmap:
    return icon(name, size).pixmap(size, size)
