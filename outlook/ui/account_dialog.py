"""Account settings dialog: add/edit/remove IMAP & POP3 accounts."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import Account
from .. import providers
from ..protocols.imap_client import ImapClient
from ..protocols.pop3_client import PopClient
from ..protocols.smtp_client import send_message as smtp_ping
from .. import workers
from . import icons


class AccountDialog(QDialog):
    accounts_changed = pyqtSignal()

    def __init__(self, config, parent=None, provider=None):
        super().__init__(parent)
        self.setWindowTitle("Add / Manage Accounts")
        self.resize(920, 580)
        self.config = config
        self._accounts = {a.id: a for a in config.accounts}
        self._current_id = None
        self._dirty = False
        self._build()
        if self._accounts:
            first = config.accounts[0]
            self._select(first.id)
        else:
            self._new_account(provider=provider)
        if provider:
            self._select_provider(provider)

    def _build(self):
        root = QVBoxLayout(self)

        split = QHBoxLayout()
        # --------------------------------------------------------- list side
        left = QVBoxLayout()
        left.addWidget(QLabel("Accounts:"))
        self.listw = QListWidget()
        self.listw.setObjectName("accountList")
        self.listw.currentItemChanged.connect(self._on_list_changed)
        left.addWidget(self.listw, 1)
        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("New…")
        self.new_btn.clicked.connect(self._new_account)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_account)
        btn_row.addWidget(self.new_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch(1)
        left.addLayout(btn_row)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(240)
        split.addWidget(left_widget)

        # ---------------------------------------------------------- form side
        right = QVBoxLayout()
        general = QGroupBox("General")
        form = QFormLayout(general)
        self.provider_combo = QComboBox()
        for pid in ("gmail", "outlook", "yahoo", "icloud", "aol", "custom"):
            self.provider_combo.addItem(providers.PROVIDERS[pid]["label"], pid)
        self.provider_note = QLabel("")
        self.provider_note.setObjectName("msgMetaLabel")
        self.provider_note.setWordWrap(True)
        self.provider_combo.currentIndexChanged.connect(self._provider_changed)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Display name, e.g. Alex Morgan")
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("alex@gmail.com")
        self.email_edit.textChanged.connect(self._email_changed)
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["IMAP", "POP3"])
        self.protocol_combo.currentTextChanged.connect(self._protocol_changed)
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Provider:", self.provider_combo)
        form.addRow("", self.provider_note)
        form.addRow("Your name:", self.name_edit)
        form.addRow("Email address:", self.email_edit)
        form.addRow("Account type:", self.protocol_combo)
        form.addRow("User name:", self.user_edit)
        form.addRow("Password:", self.pass_edit)
        right.addWidget(general)

        self.incoming_group = QGroupBox("Incoming server")
        in_form = QFormLayout(self.incoming_group)
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.ssl_check = QCheckBox("Use SSL/TLS")
        self.ssl_check.setChecked(True)
        in_form.addRow("Server:", self.host_edit)
        in_form.addRow("Port:", self.port_spin)
        in_form.addRow("", self.ssl_check)
        right.addWidget(self.incoming_group)

        smtp_group = QGroupBox("Outgoing server (SMTP)")
        out_form = QFormLayout(smtp_group)
        self.smtp_host = QLineEdit()
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(587)
        self.smtp_security = QComboBox()
        self.smtp_security.addItems(["STARTTLS", "SSL/TLS", "None"])
        self.smtp_user = QLineEdit()
        self.smtp_pass = QLineEdit()
        self.smtp_pass.setEchoMode(QLineEdit.Password)
        out_form.addRow("Server:", self.smtp_host)
        out_form.addRow("Port:", self.smtp_port)
        out_form.addRow("Security:", self.smtp_security)
        out_form.addRow("User name:", self.smtp_user)
        out_form.addRow("Password:", self.smtp_pass)
        right.addWidget(smtp_group)

        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test incoming settings")
        self.test_btn.clicked.connect(self._test)
        self.test_status = QLabel("")
        self.test_status.setObjectName("msgMetaLabel")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status, 1)
        right.addLayout(test_row)
        right.addStretch(1)
        right_widget = QWidget()
        right_widget.setLayout(right)
        split.addWidget(right_widget, 1)

        root.addLayout(split, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        ok_btn = self.buttons.button(QDialogButtonBox.Ok)
        if ok_btn is not None:
            ok_btn.setObjectName("primary")
        root.addWidget(self.buttons)
        self._refresh_list()

    # ----------------------------------------------------------------- list
    def _refresh_list(self, keep=None):
        self.listw.blockSignals(True)
        self.listw.clear()
        for acc in self.config.accounts:
            item = QListWidgetItem(
                icons.icon("account", 16),
                f"{acc.name or acc.email}\n{acc.email}")
            item.setData(Qt.UserRole, acc.id)
            self.listw.addItem(item)
        self.listw.blockSignals(False)
        target = keep or self._current_id
        if target:
            for i in range(self.listw.count()):
                if self.listw.item(i).data(Qt.UserRole) == target:
                    self.listw.setCurrentRow(i)
                    return

    def _on_list_changed(self, current, _previous):
        if current is None:
            return
        acc_id = current.data(Qt.UserRole)
        if acc_id != self._current_id:
            self._commit_current()
            self._select(acc_id)

    def _select(self, acc_id):
        acc = self._accounts.get(acc_id)
        if acc is None:
            return
        self._current_id = acc_id
        self.name_edit.setText(acc.name or "")
        self.email_edit.setText(acc.email or "")
        detected = providers.detect_provider(acc.email)
        self.provider_combo.blockSignals(True)
        self.provider_combo.setCurrentIndex(
            self.provider_combo.findData(detected))
        self.provider_combo.blockSignals(False)
        self._update_provider_note(detected)
        self._load_server_fields()
        self._protocol_changed(self.protocol_combo.currentText())

    def _load_server_fields(self):
        acc = self._accounts.get(self._current_id)
        if acc is None:
            return
        if acc.protocol == "imap":
            self.host_edit.setText(acc.imap_host or "")
            self.port_spin.setValue(acc.imap_port or 993)
            self.ssl_check.setChecked(acc.imap_ssl)
        else:
            self.host_edit.setText(acc.pop_host or "")
            self.port_spin.setValue(acc.pop_port or 995)
            self.ssl_check.setChecked(acc.pop_ssl)
        self.smtp_host.setText(acc.smtp_host or "")
        self.smtp_port.setValue(acc.smtp_port or 587)
        self.smtp_security.setCurrentText(
            {"starttls": "STARTTLS", "ssl": "SSL/TLS",
             "none": "None"}.get(acc.smtp_security, "STARTTLS"))
        self.smtp_user.setText(acc.username or "")
        self.smtp_pass.setText(acc.password or "")
        self.test_status.setText("")

    def _current_provider(self):
        return self.provider_combo.currentData() or "custom"

    def _update_provider_note(self, provider_id=None):
        note = providers.PROVIDERS.get(
            provider_id or self._current_provider(), {}).get("note", "")
        self.provider_note.setText(note)
        self.provider_note.setVisible(bool(note))

    def _select_provider(self, provider_id):
        if provider_id and provider_id in providers.PROVIDERS:
            self.provider_combo.setCurrentIndex(
                self.provider_combo.findData(provider_id))

    def _provider_changed(self, _index):
        acc = self._accounts.get(self._current_id)
        if acc is None:
            self._update_provider_note()
            return
        providers.apply_provider(
            acc, self._current_provider(),
            protocol=self.protocol_combo.currentText())
        self._update_provider_note()
        self._load_server_fields()

    def _email_changed(self, text):
        detected = providers.detect_provider(text)
        if detected != "custom" and detected != self._current_provider():
            self._select_provider(detected)

    def _protocol_changed(self, text):
        if text == "IMAP":
            self.incoming_group.setTitle("Incoming server (IMAP)")
            self.port_spin.setValue(self.port_spin.value()
                                    if self.port_spin.value() in (993, 143)
                                    else 993)
        else:
            self.incoming_group.setTitle("Incoming server (POP3)")
            if self.port_spin.value() not in (995, 110):
                self.port_spin.setValue(995)

    def _commit_current(self):
        if not self._current_id:
            return
        acc = self._accounts.get(self._current_id)
        if acc is None:
            return
        acc.name = self.name_edit.text().strip()
        acc.email = self.email_edit.text().strip()
        acc.protocol = "imap" if self.protocol_combo.currentText() == "IMAP" else "pop3"
        acc.username = self.user_edit.text().strip() or acc.email
        acc.password = self.pass_edit.text()
        if acc.protocol == "imap":
            acc.imap_host = self.host_edit.text().strip()
            acc.imap_port = int(self.port_spin.value())
            acc.imap_ssl = self.ssl_check.isChecked()
        else:
            acc.pop_host = self.host_edit.text().strip()
            acc.pop_port = int(self.port_spin.value())
            acc.pop_ssl = self.ssl_check.isChecked()
        acc.smtp_host = self.smtp_host.text().strip()
        acc.smtp_port = int(self.smtp_port.value())
        acc.smtp_security = {
            "STARTTLS": "starttls", "SSL/TLS": "ssl", "None": "none",
        }.get(self.smtp_security.currentText(), "starttls")
        if self.smtp_user.text().strip():
            acc.username = self.smtp_user.text().strip()
        acc.smtp_user = acc.username  # kept for clarity
        if self.smtp_pass.text():
            acc.password = self.smtp_pass.text()
            self.pass_edit.setText(acc.password)

    def _new_account(self, provider=None):
        self._commit_current()
        acc = Account.new(name="", email="", protocol="imap",
                          username="", password="", smtp_port=587,
                          smtp_security="starttls", imap_port=993,
                          pop_port=995)
        providers.apply_provider(acc, provider or "custom")
        self._accounts[acc.id] = acc
        self._refresh_list(keep=acc.id)
        self._select(acc.id)
        self.email_edit.setFocus()

    def _remove_account(self):
        acc_id = self._current_id
        if not acc_id:
            return
        acc = self._accounts.get(acc_id)
        answer = QMessageBox.question(
            self, "Remove account",
            f"Remove account {acc.email if acc else ''}?\n"
            "Its locally cached mail will also be removed.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        self._accounts.pop(acc_id, None)
        self._current_id = None
        self._refresh_list()
        if self._accounts:
            self._select(next(iter(self._accounts)))
        else:
            self._new_account()

    # ----------------------------------------------------------------- test
    def _test(self):
        self._commit_current()
        acc = self._accounts.get(self._current_id)
        if acc is None:
            return
        if not acc.inbound_host:
            self.test_status.setText("Enter the incoming server first.")
            return
        self.test_btn.setEnabled(False)
        self.test_status.setText("Testing…")

        def run():
            if acc.protocol == "imap":
                with ImapClient(acc, timeout=15) as client:
                    client.list_folders()
                return "IMAP login OK"
            with PopClient(acc, timeout=15) as client:
                client.uidl_list()
            return "POP3 login OK"

        def done(result):
            self.test_btn.setEnabled(True)
            self.test_status.setStyleSheet(f"color:{theme_green()};")
            self.test_status.setText(str(result))

        def failed(err):
            self.test_btn.setEnabled(True)
            self.test_status.setStyleSheet("color:#d13438;")
            self.test_status.setText(err)

        workers.submit(run, on_done=done, on_failed=failed)

    # ---------------------------------------------------------------- accept
    def _accept(self):
        self._commit_current()
        missing = [a for a in self._accounts.values()
                   if not a.email or not a.inbound_host]
        if missing:
            answer = QMessageBox.question(
                self, "Incomplete accounts",
                "Some accounts are missing an email address or incoming "
                "server. Save anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        # replace config contents
        for acc_id in list(self.config.accounts):
            if acc_id.id not in self._accounts:
                self.config.remove(acc_id.id)
        for acc in self._accounts.values():
            existing = self.config.get(acc.id)
            if existing is None:
                self.config.add(acc)
            else:
                self.config.update(acc)
        self.accounts_changed.emit()
        self.accept()


def theme_green():
    return "#107c10"
