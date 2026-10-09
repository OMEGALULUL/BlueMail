"""Compose window: new message, reply, reply all, forward, drafts."""

import html as html_mod
import mimetypes
import re
import uuid
from datetime import datetime
from email import message_from_bytes
from email.message import EmailMessage
from email.utils import formataddr, getaddresses, make_msgid, formatdate

from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from ..protocols.common import decode_header_value, format_size
from . import animations, icons, theme


def _wrap_html(inner: str) -> str:
    return (
        "<html><head><meta charset='utf-8'></head>"
        "<body style=\"font-family:'Segoe UI','Noto Sans','DejaVu Sans',"
        "sans-serif; font-size:13px; color:#201f1e;\">"
        f"{inner}</body></html>"
    )


def ensure_prefix(subject: str, prefix: str) -> str:
    subject = subject or ""
    if subject.lower().startswith(prefix.lower()):
        return subject
    return f"{prefix}{subject}"


def plain_from_html(text: str) -> str:
    m = re.search(r"(?is)<body[^>]*>(.*)</body\s*>", text)
    inner = m.group(1) if m else text
    inner = re.sub(r"(?is)<br\s*/?>", "\n", inner)
    inner = re.sub(r"(?is)</(p|div|h\d|tr)>", "\n", inner)
    inner = re.sub(r"(?s)<[^>]+>", "", inner)
    inner = html_mod.unescape(inner)
    return re.sub(r"\n{3,}", "\n\n", inner).strip()


class ComposeWindow(QDialog):
    send_requested = pyqtSignal(object)     # emits self
    save_draft_requested = pyqtSignal(object)

    def __init__(self, account, parent=None, mode="new"):
        super().__init__(parent, Qt.Window | Qt.WindowMinimizeButtonHint
                         | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Untitled - Message")
        self.resize(760, 620)
        self.setModal(False)
        self.account = account
        self.mode = mode
        self.attachments = []  # (filename, bytes, mime)
        self._original_raw = None
        self._original_meta = None
        self.sending = False
        self.sent = False
        self._build()
        if account is not None:
            self.from_label.setText(
                html_mod.escape(formataddr((account.name, account.email))
                                if account.name and account.name != account.email
                                else account.email))

    def showEvent(self, event):
        super().showEvent(event)
        # defer past show() — opacity effects that run while a top-level
        # window is being shown trigger QPainter conflicts on X11
        QTimer.singleShot(0, lambda: animations.fade_window(self, 260))

    # ------------------------------------------------------------------ UI
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("ribbon")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(8, 6, 8, 6)
        bar.setSpacing(4)

        self.send_button = QToolButton()
        self.send_button.setObjectName("sendTool")
        self.send_button.setText("Send")
        self.send_button.setIcon(icons.icon("send", 32))
        self.send_button.setIconSize(QSize(32, 32))
        self.send_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.send_button.setAutoRaise(True)
        self.send_button.setFixedSize(66, 64)
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.clicked.connect(self._on_send)
        bar.addWidget(self.send_button)

        self.attach_button = self._tool("Attach", "attach", self._add_attachment)
        self.save_button = self._tool("Save", "folder_drafts", self._on_save)
        bar.addWidget(self.attach_button)
        bar.addWidget(self.save_button)

        bar.addSpacing(10)
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background:{theme.BORDER_SOFT};")
        bar.addWidget(sep)
        bar.addSpacing(4)

        self.bold_btn = self._fmt("B", lambda: self.body.bold())
        self.bold_btn.setFont(self._bold_font())
        self.italic_btn = self._fmt("I", lambda: self.body.italic())
        italic_font = self.italic_btn.font()
        italic_font.setItalic(True)
        self.italic_btn.setFont(italic_font)
        self.underline_btn = self._fmt("U", lambda: self.body.underline())
        ufont = self.underline_btn.font()
        ufont.setUnderline(True)
        self.underline_btn.setFont(ufont)
        bar.addWidget(self.bold_btn)
        bar.addWidget(self.italic_btn)
        bar.addWidget(self.underline_btn)

        bar.addStretch(1)
        self.from_label = QLabel("")
        self.from_label.setObjectName("msgMetaValue")
        self.from_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cap = QLabel("From:")
        cap.setObjectName("msgMetaLabel")
        bar.addWidget(cap)
        bar.addWidget(self.from_label)
        root.addWidget(toolbar)

        fields = QWidget()
        grid = QVBoxLayout(fields)
        grid.setContentsMargins(12, 6, 12, 4)
        grid.setSpacing(2)

        _to_container, self.to_edit = self._field("To:")
        grid.addWidget(_to_container)
        self.cc_container, self.cc_edit = self._field("Cc:")
        grid.addWidget(self.cc_container)
        self.cc_container.hide()
        _subj_container, self.subject_edit = self._field("Subject:")
        grid.addWidget(_subj_container)
        root.addWidget(fields)

        self.body = QTextEdit(self)
        self.body.setObjectName("composeBody")
        self.body.setAcceptRichText(True)
        self.body.setUndoRedoEnabled(True)
        root.addWidget(self.body, 1)

        bottom = QWidget()
        bottom.setObjectName("ribbon")
        b = QHBoxLayout(bottom)
        b.setContentsMargins(12, 5, 12, 5)
        self.status_label = QLabel("")
        self.status_label.setObjectName("msgMetaLabel")
        self.cc_toggle = QToolButton()
        self.cc_toggle.setObjectName("ribbonButton")
        self.cc_toggle.setText("Cc")
        self.cc_toggle.setCheckable(True)
        self.cc_toggle.setAutoRaise(True)
        self.cc_toggle.toggled.connect(self.cc_container.setVisible)
        b.addWidget(self.status_label, 1)
        b.addWidget(self.cc_toggle)
        root.addWidget(bottom)

        self.to_edit.setFocus()

    @staticmethod
    def _bold_font():
        from PyQt5.QtGui import QFont
        f = QFont()
        f.setBold(True)
        return f

    def _tool(self, text, icon_name, slot):
        btn = QToolButton()
        btn.setObjectName("ribbonButton")
        btn.setText(text)
        btn.setIcon(icons.icon(icon_name, 24))
        btn.setIconSize(QSize(24, 24))
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setAutoRaise(True)
        btn.setFixedSize(60, 54)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    def _fmt(self, text, slot):
        btn = QToolButton()
        btn.setObjectName("ribbonButton")
        btn.setText(text)
        btn.setCheckable(True)
        btn.setAutoRaise(True)
        btn.setFixedSize(28, 26)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    def _field(self, caption):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        label = QLabel(caption)
        label.setObjectName("headerCaption")
        label.setFixedWidth(64)
        edit = QLineEdit()
        edit.setObjectName("headerField")
        row.addWidget(label)
        row.addWidget(edit, 1)
        return container, edit

    # ------------------------------------------------------------ prefilling
    def prefill_reply(self, meta, raw, reply_all=False):
        self._original_meta = meta
        self._original_raw = raw
        subject = ensure_prefix(meta.get("subject") or "", "Re: ")
        self.subject_edit.setText(subject)
        self.setWindowTitle(f"{subject} - Message")

        to_values = []
        my_addr = (self.account.email if self.account else "").lower()
        for addr in getaddresses([meta.get("from_addr") or ""]):
            if addr[1]:
                to_values.append(formataddr(addr))
        if reply_all:
            for field in ("to_addr", "cc_addr"):
                for addr in getaddresses([meta.get(field) or ""]):
                    if addr[1] and addr[1].lower() != my_addr:
                        to_values.append(formataddr(addr))
        # de-duplicate
        seen, unique = set(), []
        for v in to_values:
            key = v.lower()
            if key not in seen:
                seen.add(key)
                unique.append(v)
        self.to_edit.setText(", ".join(unique))
        self.body.setPlainText(self._quote_original(raw, meta))
        self.body.moveCursor(self.body.textCursor().Start)

    def prefill_forward(self, meta, raw):
        self._original_meta = meta
        self._original_raw = raw
        subject = ensure_prefix(meta.get("subject") or "", "Fwd: ")
        self.subject_edit.setText(subject)
        self.setWindowTitle(f"{subject} - Message")
        header_lines = [
            "",
            "-----Original Message-----",
            f"From: {meta.get('from_display') or meta.get('from_addr') or ''}",
            f"Date: {self._date(meta.get('date_ts'))}",
            f"Subject: {meta.get('subject') or ''}",
            f"To: {meta.get('to_addr') or ''}",
            "",
        ]
        original = self._body_text(raw) or ""
        self.body.setPlainText("\n".join(header_lines) + original)
        self.body.moveCursor(self.body.textCursor().Start)

    def load_draft(self, raw: bytes):
        try:
            msg = message_from_bytes(raw)
        except Exception:
            return
        self.subject_edit.setText(decode_header_value(msg.get("Subject", "")))
        self.to_edit.setText(self._addr_display(msg.get("To", "")))
        cc = self._addr_display(msg.get("Cc", ""))
        if cc:
            self.cc_toggle.setChecked(True)
            self.cc_edit.setText(cc)
        plain, html_text, attachments = self._parts(msg)
        if html_text and not plain:
            self.body.setHtml(_wrap_html(html_text))
        else:
            self.body.setPlainText(plain or "")
        for filename, data, mime in attachments:
            self.attachments.append((filename, data, mime))
        self._refresh_attach_button()

    @staticmethod
    def _addr_display(value):
        if not value:
            return ""
        out = []
        for name, addr in getaddresses([decode_header_value(value)]):
            out.append(formataddr((decode_header_value(name), addr))
                       if name else addr)
        return ", ".join(out)

    @staticmethod
    def _parts(msg):
        plain = html_text = None
        attachments = []

        def handle(part, filename=None):
            nonlocal plain, html_text
            ctype = part.get_content_type()
            if filename or part.get_content_disposition() == "attachment":
                data = part.get_payload(decode=True) or b""
                attachments.append((filename or "attachment", data, ctype))
                return
            if ctype == "text/plain" and plain is None:
                payload = part.get_payload(decode=True)
                plain = (payload or b"").decode(
                    part.get_content_charset() or "utf-8", errors="replace")
            elif ctype == "text/html" and html_text is None:
                payload = part.get_payload(decode=True)
                html_text = (payload or b"").decode(
                    part.get_content_charset() or "utf-8", errors="replace")

        if msg.is_multipart():
            for part in msg.walk():
                if part.is_multipart():
                    continue
                handle(part, filename=part.get_filename())
        else:
            handle(msg, filename=msg.get_filename())
        return plain, html_text, attachments

    @staticmethod
    def _date(ts):
        if not ts:
            return ""
        return datetime.fromtimestamp(ts).strftime("%A, %d %B %Y %H:%M")

    @staticmethod
    def _body_text(raw) -> str:
        if not raw:
            return ""
        try:
            msg = message_from_bytes(raw)
            plain, html_text, _att = ComposeWindow._parts(msg)
            return plain or plain_from_html(html_text or "")
        except Exception:
            return ""

    def _quote_original(self, raw, meta) -> str:
        original = self._body_text(raw)
        who = meta.get("from_display") or meta.get("from_addr") or "someone"
        when = self._date(meta.get("date_ts"))
        head = f"On {when}, {who} wrote:" if when else f"{who} wrote:"
        quoted = "\n".join("> " + line for line in original.splitlines())
        return f"\n\n{head}\n{quoted}"

    # ------------------------------------------------------------- actions
    def _on_send(self):
        if self.sending:
            return
        if not self.to_edit.text().strip():
            self.status_label.setText("Please enter at least one recipient.")
            self.to_edit.setFocus()
            return
        self.sending = True
        self.send_button.setEnabled(False)
        self.status_label.setText("Sending…")
        self.send_requested.emit(self)

    def _on_save(self):
        self.save_draft_requested.emit(self)

    def send_finished(self, ok: bool, message: str):
        self.sending = False
        self.send_button.setEnabled(True)
        self.status_label.setText(message)
        if ok:
            self.sent = True
            self.accept()

    def _add_attachment(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Attach Files", "",
                                                "All Files (*)")
        for path in paths:
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
            except OSError as exc:
                self.status_label.setText(f"Cannot attach: {exc}")
                continue
            name = path.rsplit("/", 1)[-1]
            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
            if "/" in mime:
                maintype, subtype = mime.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"
            self.attachments.append((name, data, f"{maintype}/{subtype}"))
        self._refresh_attach_button()

    def _refresh_attach_button(self):
        if self.attachments:
            total = sum(len(d) for _n, d, _m in self.attachments)
            self.attach_button.setText(
                f"Attach ({len(self.attachments)}, {format_size(total)})")
        else:
            self.attach_button.setText("Attach")

    # ------------------------------------------------------------ build MIME
    def build_message(self) -> EmailMessage:
        acc = self.account
        msg = EmailMessage()
        display = (formataddr((acc.name, acc.email))
                   if acc and acc.name and acc.name != acc.email
                   else (acc.email if acc else ""))
        msg["From"] = display
        msg["To"] = self.to_edit.text().strip()
        cc = self.cc_edit.text().strip()
        if cc and self.cc_toggle.isChecked():
            msg["Cc"] = cc
        msg["Subject"] = self.subject_edit.text().strip()
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=(acc.email.split("@")[-1]
                                               if acc and "@" in acc.email
                                               else "localhost"))
        if self.mode in ("reply", "reply_all") and self._original_meta:
            orig_id = (self._original_meta.get("msgid") or "").strip()
            if orig_id:
                msg["In-Reply-To"] = orig_id
                msg["References"] = orig_id

        html_body = self.body.toHtml()
        m = re.search(r"(?is)<body[^>]*>(.*)</body\s*>", html_body)
        inner = m.group(1) if m else html_body
        plain = self.body.toPlainText().strip()
        msg.set_content(plain or "")
        if inner.strip():
            msg.add_alternative(_wrap_html(inner), subtype="html")

        for filename, data, mime in self.attachments:
            maintype, _, subtype = (mime or "application/octet-stream").partition("/")
            try:
                msg.add_attachment(data, maintype=maintype or "application",
                                   subtype=subtype or "octet-stream",
                                   filename=filename)
            except Exception:
                msg.add_attachment(data, maintype="application",
                                   subtype="octet-stream", filename=filename)
        return msg

    def closeEvent(self, event):
        has_content = (self.to_edit.text().strip()
                       or self.subject_edit.text().strip()
                       or self.body.toPlainText().strip())
        if has_content and not self.sending and not self.sent:
            self.save_draft_requested.emit(self)
        super().closeEvent(event)
