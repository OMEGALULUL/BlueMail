"""Reading pane: message header block, attachments bar, HTML/plain body."""

import html as html_mod
import re
from email import message_from_bytes
from email.utils import formataddr, getaddresses

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..protocols.common import decode_header_value, format_size
from . import animations, avatars, icons, theme

_SCRIPT_RE = re.compile(r"(?is)<script\b.*?</script\s*>")
_STYLE_RE = re.compile(r"(?is)<style\b.*?</style\s*>")
_IFRAME_RE = re.compile(r"(?is)<iframe\b.*?</iframe\s*>")
_OBJECT_RE = re.compile(r"(?is)<object\b.*?</object\s*>")
_EMBED_RE = re.compile(r"(?is)<embed\b[^>]*>")
_FORM_RE = re.compile(r"(?is)<form\b.*?</form\s*>")
_ON_ATTR_RE = re.compile(r"(?is)\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")
_EVENT_ATTR_RE = re.compile(r"(?is)\s(?:onclick|onload|onerror|onmouseover)=\S+")


def sanitize_html(text: str) -> str:
    text = _SCRIPT_RE.sub("", text)
    text = _STYLE_RE.sub("", text)
    text = _IFRAME_RE.sub("", text)
    text = _OBJECT_RE.sub("", text)
    text = _EMBED_RE.sub("", text)
    text = _FORM_RE.sub("", text)
    text = _ON_ATTR_RE.sub("", text)
    text = _EVENT_ATTR_RE.sub("", text)
    return text


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        if isinstance(raw, str):
            return raw
        payload = str(raw or "").encode("utf-8", "replace")
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


class BodyView(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("msgBody")
        self.setOpenExternalLinks(True)
        self.setOpenLinks(True)
        self.setReadOnly(True)
        self.setFrameShape(QFrame.NoFrame)
        self._resources = {}

    def set_resources(self, resources):
        self._resources = resources or {}

    def loadResource(self, rtype, name):
        try:
            key = str(name)
        except Exception:
            return None
        if key.startswith("cid:"):
            data = self._resources.get(key[4:].strip("<>"))
            if data is not None:
                return data
            data = self._resources.get(key[4:])
            if data is not None:
                return data
        # no remote fetching (privacy) — Qt falls back to empty resource
        return None


class ReadingPane(QFrame):
    attachment_clicked = pyqtSignal(bytes, str)
    action_requested = pyqtSignal(str)  # reply / reply_all / forward / …

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("readingPane")
        self._current = None  # row dict
        self._current_uid = None
        self._attachments = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 0)
        root.setSpacing(0)

        # ------------------------------------------------ header card
        head = QWidget()
        head.setObjectName("msgHeadCard")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(0, 0, 0, 2)
        hh.setSpacing(12)

        self.avatar = QLabel()
        self.avatar.setObjectName("msgAvatar")
        self.avatar.setFixedSize(44, 44)
        self.avatar.setAttribute(Qt.WA_TranslucentBackground, True)
        hh.addWidget(self.avatar, 0, Qt.AlignTop)

        who = QVBoxLayout()
        who.setSpacing(1)
        self.sender_name = QLabel("")
        self.sender_name.setObjectName("msgSenderName")
        self.sender_mail = QLabel("")
        self.sender_mail.setObjectName("msgSenderMail")
        who.addWidget(self.sender_name)
        who.addWidget(self.sender_mail)
        who.addStretch(1)
        hh.addLayout(who, 1)

        right = QVBoxLayout()
        right.setSpacing(4)
        self.date_label = QLabel("")
        self.date_label.setObjectName("msgDateTop")
        right.addWidget(self.date_label, 0, Qt.AlignRight)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(2)
        self._action_buttons = []
        for text, icon_name, act in (
            ("Reply", "reply", "reply"),
            ("Reply All", "reply_all", "reply_all"),
            ("Forward", "forward", "forward"),
            ("Mark as read/unread", "open_mail", "toggle_read"),
            ("Delete", "delete", "delete"),
        ):
            btn = QToolButton()
            btn.setObjectName("readingAction")
            btn.setIcon(icons.icon(icon_name, 16))
            btn.setIconSize(QSize(16, 16))
            btn.setToolTip(text)
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            btn.setAutoRaise(True)
            btn.setFixedSize(30, 30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, a=act: self.action_requested.emit(a))
            actions_row.addWidget(btn)
            self._action_buttons.append(btn)
        right.addLayout(actions_row)
        hh.addLayout(right)
        root.addWidget(head)

        # ------------------------------------------------ subject line
        self.subject_label = QLabel("")
        self.subject_label.setObjectName("msgSubject")
        self.subject_label.setWordWrap(True)
        root.addWidget(self.subject_label)

        # ------------------------------------------------ recipients only
        meta = QWidget()
        grid = QVBoxLayout(meta)
        grid.setContentsMargins(0, 2, 0, 8)
        grid.setSpacing(2)
        self._meta_labels = {}
        for key, caption in (("to", "To:"), ("cc", "Cc:")):
            row = QHBoxLayout()
            row.setSpacing(6)
            cap = QLabel(caption)
            cap.setObjectName("msgMetaLabel")
            cap.setFixedWidth(48)
            val = QLabel("")
            val.setObjectName("msgMetaValue")
            val.setWordWrap(True)
            val.setTextFormat(Qt.RichText)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            val.setOpenExternalLinks(True)
            row.addWidget(cap, 0, Qt.AlignTop)
            row.addWidget(val, 1)
            grid.addLayout(row)
            self._meta_labels[key] = (cap, val)
        root.addWidget(meta)

        self.header_sep = QFrame()
        self.header_sep.setObjectName("msgHeaderSep")
        root.addWidget(self.header_sep)

        self.attachment_bar = QFrame()
        self.attachment_bar.setObjectName("attachmentBar")
        self.attachment_layout = QHBoxLayout(self.attachment_bar)
        self.attachment_layout.setContentsMargins(8, 5, 8, 5)
        self.attachment_layout.setSpacing(6)
        clip = QLabel()
        clip.setPixmap(icons.icon("attach", 16).pixmap(16, 16))
        self.attachment_layout.addWidget(clip)
        self.attachment_layout.addStretch(1)
        self.attachment_bar.hide()
        root.addWidget(self.attachment_bar)

        self.body = BodyView(self)
        root.addWidget(self.body, 1)
        self.clear()

    # -------------------------------------------------------------- public
    def clear(self):
        self._current = None
        self._current_uid = None
        self._attachments = []
        self.subject_label.setText("")
        self.sender_name.setText("")
        self.sender_mail.setText("")
        self.date_label.setText("")
        self.avatar.clear()
        for cap, val in self._meta_labels.values():
            cap.hide()
            val.hide()
        for btn in self._action_buttons:
            btn.setEnabled(False)
        self.attachment_bar.hide()
        self.body.set_resources({})
        self.body.setHtml(
            "<html><body style='color:#8a8886;'>"
            "<p style='margin-top:72px; text-align:center; font-size:15px;'>"
            "Select an item to read it.</p>"
            "<p style='text-align:center; font-size:12px; color:#a19f9d;'>"
            "Messages appear here</p></body></html>"
        )
        self.header_sep.hide()
        animations.fade_in(self, 160)

    def show_message(self, row, raw=None):
        """Show header info; render body if raw is available."""
        self._current = row
        self._current_uid = str(row.get("uid"))
        subject = row.get("subject") or "(no subject)"
        self.subject_label.setText(html_mod.escape(subject))

        from_name = (row.get("from_display") or "").strip()
        from_addr = (row.get("from_addr") or "").strip()
        display = from_name or from_addr
        self.sender_name.setText(
            html_mod.escape(display) if display else "(unknown sender)")
        same = from_name and from_addr and from_name != from_addr
        self.sender_mail.setText(
            html_mod.escape(from_addr) if same and from_addr else "")
        self.sender_mail.setVisible(bool(self.sender_mail.text()))
        self.avatar.setPixmap(avatars.avatar_pixmap(
            from_name, from_addr, 44))
        self.date_label.setText(self._friendly_date(row.get("date_ts")))
        for btn in self._action_buttons:
            btn.setEnabled(True)

        to_html = self._addr_html(row.get("to_addr"))
        cc_html = self._addr_html(row.get("cc_addr"))
        values = {"to": to_html, "cc": cc_html}
        for key, (cap, val) in self._meta_labels.items():
            text = values.get(key) or ""
            if not text:
                cap.hide()
                val.hide()
                continue
            val.setText(text)
            val.show()
            cap.show()

        self.header_sep.show()
        # let the content land first, then rise into place
        animations.slide_in(self, self.layout(), distance=12, duration=330)

        if raw is not None:
            self.show_body(str(row.get("uid")), raw)
        else:
            self.body.set_resources({})
            self.body.setHtml(
                "<html><body style='color:#8a8886;'>"
                "<p style='margin-top:30px; text-align:center;'>"
                "Loading message…</p></body></html>"
            )
            self._set_attachments([])

    def show_body(self, uid, raw: bytes):
        if self._current is None or str(uid) != str(self._current_uid):
            return
        animations.stop(self)   # freeze entrance before html load/repaint
        try:
            msg = message_from_bytes(raw)
        except Exception:
            self.body.setHtml(
                "<html><body><p>Unable to display this message.</p></body></html>"
            )
            return

        plain, html_text, attachments, resources = self._extract(msg)
        self._set_attachments(attachments)

        body_html = None
        if html_text:
            body_html = sanitize_html(html_text)
            if "<body" in body_html.lower():
                m = re.search(r"(?is)<body[^>]*>(.*)</body\s*>", body_html)
                if m:
                    body_html = m.group(1)
        if body_html and body_html.strip():
            wrapped = (
                "<html><head><meta charset='utf-8'></head>"
                "<body style=\"font-family:'Segoe UI','Noto Sans','DejaVu Sans',"
                "sans-serif; font-size:13px; color:#201f1e;\">"
                f"{body_html}</body></html>"
            )
        elif plain:
            paras = []
            for line in plain.splitlines() or [""]:
                escaped = html_mod.escape(line)
                paras.append(f"<p style='margin:0 0 6px 0;'>{escaped or '&nbsp;'}</p>")
            wrapped = (
                "<html><body style=\"font-family:'Segoe UI','Noto Sans',"
                "'DejaVu Sans',sans-serif; font-size:13px; color:#201f1e;\">"
                + "".join(paras) + "</body></html>"
            )
        else:
            wrapped = ("<html><body style='color:#8a8886;'>"
                       "<p><i>This message has no content.</i></p></body></html>")

        self.body.set_resources(resources)
        self.body.setHtml(wrapped)
        self.body.scrollToAnchor("")

    # ------------------------------------------------------------- internals
    @staticmethod
    def _addr_html(value):
        if not value:
            return ""
        out = []
        for name, addr in getaddresses([value]):
            name = decode_header_value(name).strip()
            addr = addr.strip()
            if addr:
                label = html_mod.escape(name or addr)
                if name and name != addr:
                    out.append(f"{label} &lt;<a href='mailto:{html_mod.escape(addr)}'>{html_mod.escape(addr)}</a>&gt;")
                else:
                    out.append(f"<a href='mailto:{html_mod.escape(addr)}'>{label}</a>")
            elif name:
                out.append(html_mod.escape(name))
        return ", ".join(out)

    @staticmethod
    def _date_str(ts):
        if not ts:
            return ""
        import datetime
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%A, %d %B %Y %H:%M")

    @staticmethod
    def _friendly_date(ts):
        if not ts:
            return ""
        import datetime
        dt = datetime.datetime.fromtimestamp(ts)
        now = datetime.datetime.now()
        if dt.date() == now.date():
            return dt.strftime("Today · %H:%M")
        if dt.year == now.year:
            return dt.strftime("%a, %d %b · %H:%M")
        return dt.strftime("%a, %d %b %Y · %H:%M")

    @staticmethod
    def _extract(msg):
        plain = None
        html_text = None
        attachments = []
        resources = {}

        def handle(part, filename=None):
            nonlocal plain, html_text
            ctype = part.get_content_type()
            if filename or (part.get_content_disposition() == "attachment"):
                data = part.get_payload(decode=True) or b""
                attachments.append((filename or "attachment", data, ctype))
                return
            if ctype == "text/plain" and plain is None:
                plain = _decode_part(part)
            elif ctype == "text/html" and html_text is None:
                html_text = _decode_part(part)
            elif ctype.startswith(("image/", "application/pdf")):
                data = part.get_payload(decode=True) or b""
                cid = (part.get("Content-ID") or "").strip().strip("<>")
                if cid:
                    resources[cid] = data

        if msg.is_multipart():
            for part in msg.walk():
                if part.is_multipart():
                    continue
                handle(part, filename=part.get_filename())
        else:
            handle(msg, filename=msg.get_filename())
        return plain, html_text, attachments, resources

    def _set_attachments(self, attachments):
        self._attachments = attachments
        # clear old buttons (keep first index label)
        while self.attachment_layout.count() > 2:
            item = self.attachment_layout.takeAt(1)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not attachments:
            self.attachment_bar.hide()
            return
        for filename, data, _ctype in attachments:
            btn = QToolButtonSafe(filename, data, self)
            self.attachment_layout.insertWidget(
                self.attachment_layout.count() - 1, btn)
        self.attachment_bar.show()

    def current_row(self):
        return self._current


class QToolButtonSafe(QWidget):
    """Small attachment chip button."""

    def __init__(self, filename, data, pane):
        super().__init__()
        self._pane = pane
        self._filename = filename
        self._data = data
        from PyQt5.QtWidgets import QToolButton
        btn = QToolButton()
        btn.setObjectName("attachmentButton")
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setAutoRaise(True)
        btn.setIcon(icons.icon("attach", 14))
        from PyQt5.QtCore import QSize
        btn.setIconSize(QSize(14, 14))
        btn.setText(f"{filename} ({format_size(len(data))})")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self._clicked)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(btn)

    def _clicked(self):
        self._pane.attachment_clicked.emit(self._data, self._filename)
