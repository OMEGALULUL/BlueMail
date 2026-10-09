"""Opencode assistant dialog — AI-assisted replies via the opencode CLI.

Three modes, each exposed as a button:

* **Quick answer** — short ready-to-send reply to the selected email.
* **Think for me** — a longer, well-considered response to copy & paste.
* **Power-user mode** — type what you want to say (and to whom); Opencode
  writes the email.

If the opencode CLI is not installed, the dialog instead offers a
"Download opencode" button that opens the official site.
"""

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import opencode, workers
from . import icons


class OpencodeDialog(QDialog):
    """Modal panel: choose a mode, then copy/paste the generated reply."""

    def __init__(self, message=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opencode Assistant")
        self.resize(560, 620)
        self._message = message
        self._mode = "quick"
        self._build()
        self._refresh_availability()

    # -------------------------------------------------------------- build
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Opencode Assistant")
        title.setObjectName("welcomeHeading")
        head.addWidget(title)
        head.addStretch(1)
        self.available_label = QLabel("")
        self.available_label.setObjectName("msgMetaLabel")
        head.addWidget(self.available_label)
        root.addLayout(head)

        body = QLabel(
            "Draft replies with the Opencode CLI. Pick a mode, then copy "
            "the result into a new email.")
        body.setObjectName("welcomeHint")
        body.setWordWrap(True)
        root.addWidget(body)

        # three mode cards -------------------------------------------------
        quick = QPushButton("Quick answer")
        quick.setObjectName("primary")
        quick.setToolTip("Short, ready-to-send reply to the selected email")
        think = QPushButton("Think for me")
        think.setToolTip("A longer, well-considered response — copy & paste")
        power = QPushButton("Power-user mode")
        power.setToolTip(
            "Type what you want to say (and to whom) — Opencode writes the email")
        quick.clicked.connect(lambda _c=False: self._pick("quick"))
        think.clicked.connect(lambda _c=False: self._pick("think"))
        power.clicked.connect(lambda _c=False: self._pick("power"))
        for b in (quick, think, power):
            b.setCursor(Qt.PointingHandCursor)
        self.mode_buttons = {"quick": quick, "think": think, "power": power}

        cards = QWidget()
        cl = QHBoxLayout(cards)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        cl.addWidget(quick, 1)
        cl.addWidget(think, 1)
        cl.addWidget(power, 1)
        root.addWidget(cards)
        self.cards = cards

        # power-user inputs ------------------------------------------------
        fields = QWidget()
        fl = QHBoxLayout(fields)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("To (email or domain), optional")
        self.instruction_edit = QLineEdit()
        self.instruction_edit.setPlaceholderText(
            "What to say, e.g. “thanks — I'll confirm by Friday”")
        fl.addWidget(self.target_edit, 1)
        fl.addWidget(self.instruction_edit, 2)
        self.field_row = fields
        root.addWidget(fields)
        self.field_row.setVisible(False)

        # status + generate ------------------------------------------------
        self.status = QLabel("")
        self.status.setObjectName("msgMetaLabel")
        root.addWidget(self.status)
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setObjectName("primary")
        self.generate_btn.clicked.connect(self._generate)
        root.addWidget(self.generate_btn, alignment=Qt.AlignRight)

        # result -------------------------------------------------------------
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("The generated reply will appear here…")
        root.addWidget(self.result, 1)

        bottom = QHBoxLayout()
        self.copy_btn = QPushButton("Copy to clipboard")
        self.copy_btn.clicked.connect(self._copy)
        self.copy_btn.setEnabled(False)
        bottom.addWidget(self.copy_btn)
        bottom.addStretch(1)
        self.download_btn = QPushButton("Download opencode")
        self.download_btn.setObjectName("primary")
        self.download_btn.clicked.connect(self._open_download)
        self.check_btn = QPushButton("Check again")
        self.check_btn.clicked.connect(self._refresh_availability)
        bottom.addWidget(self.check_btn)
        bottom.addWidget(self.download_btn)
        root.addLayout(bottom)

    # ------------------------------------------------------------- helpers
    def _refresh_availability(self):
        ok = opencode.is_installed()
        for b in self.mode_buttons.values():
            b.setEnabled(ok)
        self.generate_btn.setEnabled(ok)
        self.field_row.setVisible(ok and self._mode == "power")
        self.download_btn.setVisible(not ok)
        self.check_btn.setVisible(not ok)
        if ok:
            self.available_label.setText("opencode ready")
        else:
            self.available_label.setText("opencode not found")
            self.status.setText(
                "The opencode CLI isn't installed. Download it to enable "
                "AI-assisted replies.")
        if self._message and ok:
            sender = self._message.get("from_addr") or ""
            if sender:
                self.target_edit.setText(sender)

    def _pick(self, mode):
        self._mode = mode
        self.field_row.setVisible(mode == "power")
        if mode == "power":
            self.instruction_edit.setFocus()
        for name, btn in self.mode_buttons.items():
            btn.setObjectName("primary" if name == mode else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _generate(self):
        if not opencode.is_installed():
            self.status.setText("Install opencode first, then click “Check again”.")
            return
        try:
            if self._mode == "power":
                if not self.instruction_edit.text().strip():
                    self.status.setText("Type what you want to say first.")
                    return
                prompt = opencode.build_prompt(
                    "power",
                    message=self._message,
                    instruction=self.instruction_edit.text(),
                    target=self.target_edit.text())
            else:
                prompt = opencode.build_prompt(
                    self._mode, message=self._message)
        except ValueError as exc:
            self.status.setText(str(exc))
            return

        self.result.clear()
        self.status.setText("Thinking with Opencode…")
        self.generate_btn.setEnabled(False)
        self.available_label.setText("working…")

        def work():
            return opencode.run(prompt)

        def done(text):
            self.generate_btn.setEnabled(True)
            self.available_label.setText("opencode ready")
            self.result.setPlainText(text)
            self.copy_btn.setEnabled(bool(text.strip()))
            self.status.setText("Done — copy it, or edit here.")

        def failed(err):
            self.generate_btn.setEnabled(True)
            self.available_label.setText("opencode ready")
            self.status.setText(f"Error: {err}")

        workers.submit(work, on_done=done, on_failed=failed)

    def _copy(self):
        QApplication.clipboard().setText(self.result.toPlainText())
        self.status.setText("Copied to clipboard.")

    def _open_download(self):
        QDesktopServices.openUrl(QUrl(opencode.DOWNLOAD_URL))
        self.status.setText("Opened opencode.ai — install the CLI, then click "
                            "“Check again”.")