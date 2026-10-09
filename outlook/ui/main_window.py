"""Main window: ribbon, folder pane, message list, reading pane, sync."""

import uuid
from datetime import datetime

from PyQt5.QtCore import QSignalBlocker, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QShortcut,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from .. import workers
from ..config import Account
from ..protocols.common import (
    ROLE_LABELS,
    MessageMeta,
    folder_role,
    format_size,
    parse_address_field,
)
from ..protocols.imap_client import ImapClient
from ..protocols.pop3_client import PopClient
from ..protocols.smtp_client import send_message as smtp_send
from . import animations, icons, theme
from .account_dialog import AccountDialog
from .compose import ComposeWindow
from .folder_pane import FolderPane
from .message_list import MessageList
from .reading_pane import ReadingPane
from .ribbon import Ribbon, RibbonPanel, mini_button, ribbon_button


class MessageWindow(QDialog):
    action = pyqtSignal(str, object)

    def __init__(self, row, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle((row.get("subject") or "Message")
                            + " - Message")
        self.resize(760, 640)
        self.row = row
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QWidget()
        bar.setObjectName("ribbon")
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(8, 5, 8, 5)
        row1 = __import__("PyQt5.QtWidgets", fromlist=["QHBoxLayout"]).QHBoxLayout()
        for text, icon_name, action in (
            ("Reply", "reply", "reply"),
            ("Reply All", "reply_all", "reply_all"),
            ("Forward", "forward", "forward"),
            ("Delete", "delete", "delete"),
            ("Mark Unread", "open_mail", "toggle_read"),
            ("Flag", "flag", "toggle_flag"),
        ):
            btn = QToolButton()
            btn.setObjectName("ribbonButton")
            btn.setText(text)
            btn.setIcon(icons.icon(icon_name, 24))
            from PyQt5.QtCore import QSize
            btn.setIconSize(QSize(24, 24))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setAutoRaise(True)
            btn.setFixedSize(70, 54)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _c, a=action: self.action.emit(a, self.row))
            row1.addWidget(btn)
        row1.addStretch(1)
        lay.addLayout(row1)
        root.addWidget(bar)

        self.reading = ReadingPane(self)
        root.addWidget(self.reading, 1)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: animations.fade_window(self, 220))

    def show_raw(self, row, raw):
        self.row = row
        self.reading.show_message(row, raw)


class MainWindow(QMainWindow):
    def __init__(self, config, store, demo=False, parent=None,
                 auto_sync=True):
        super().__init__(parent)
        self.config = config
        self.store = store
        self.demo = demo
        self._current = None
        self._preview = None
        self._syncing = set()
        self._active = 0
        self._pending_body = None
        self._compose_windows = []
        self._message_windows = []
        self._pane_pos = config.get_setting("reading_pane", "bottom")
        if self._pane_pos not in ("bottom", "right"):
            self._pane_pos = "bottom"

        self.setWindowTitle("BlueMail")
        self.setWindowIcon(icons.icon("new_mail", 64))
        self.resize(1280, 800)

        self._build_ribbon()
        self._build_central()
        self._build_statusbar()
        self._build_shortcuts()

        self.refresh_folder_pane()
        self._last_entrance = -1
        if not self.config.accounts:
            self.stack.setCurrentIndex(1)
            self._enter_welcome()
        else:
            self.stack.setCurrentIndex(0)
            self._enter_main()
            if not self.demo and auto_sync:
                QTimer.singleShot(300, self.send_receive_all)

    # ------------------------------------------------------------------ UI
    def _build_ribbon(self):
        self.ribbon = Ribbon()
        home = RibbonPanel()
        home.add_group("New", [ribbon_button(
            "New Email", "new_mail", self.new_message, tooltip="New message (Ctrl+N)")])
        home.add_group("Delete", [ribbon_button(
            "Delete", "delete", lambda: self.message_list.emit_action("delete"),
            tooltip="Delete selected (Del)")])
        home.add_group("Respond", [
            ribbon_button("Reply", "reply",
                          lambda: self.message_list.emit_action("reply"),
                          tooltip="Reply (Ctrl+R)"),
            ribbon_button("Reply All", "reply_all",
                          lambda: self.message_list.emit_action("reply_all"),
                          tooltip="Reply All (Ctrl+Shift+R)"),
            ribbon_button("Forward", "forward",
                          lambda: self.message_list.emit_action("forward"),
                          tooltip="Forward (Ctrl+Alt+F)"),
        ])
        home.add_group("All", [
            ribbon_button("Mark Read", "open_mail",
                          lambda: self._set_read_for_selection(True)),
            ribbon_button("Mark Unread", "new_mail",
                          lambda: self._set_read_for_selection(False)),
            ribbon_button("Flag", "flag",
                          lambda: self.message_list.emit_action("toggle_flag")),
        ])
        home.add_group("Smart", [
            ribbon_button("Opencode", "opencode", self.open_opencode,
                          tooltip="AI-assisted replies via the opencode CLI"),
        ])
        home.add_stretch()

        sr = RibbonPanel()
        sr.add_group("Send and Receive", [
            ribbon_button("Send/Receive All", "send_recv",
                          self.send_receive_all,
                          tooltip="Send/Receive all folders (F9)"),
            ribbon_button("Sync Folder", "refresh",
                          lambda: self.sync_current(background=False),
                          tooltip="Sync the current folder"),
        ])
        sr.add_group("Preferences", [
            ribbon_button("Accounts", "account",
                          lambda: self.open_account_settings(None)),
        ])
        sr.add_stretch()

        folders = RibbonPanel()
        folders.add_group("New", [
            ribbon_button("New Folder", "new_folder",
                          lambda: self._folder_action("new_folder"))])
        folders.add_group("Manage", [
            ribbon_button("Rename", "folder",
                          lambda: self._folder_action("rename_folder")),
            ribbon_button("Delete", "delete",
                          lambda: self._folder_action("delete_folder")),
        ])
        folders.add_group("Clean Up", [
            ribbon_button("Empty", "trash",
                          lambda: self._folder_action("empty_folder")),
            ribbon_button("Mark All Read", "open_mail",
                          lambda: self._folder_action("mark_all_read")),
        ])
        folders.add_stretch()

        view = RibbonPanel()
        bottom_btn = ribbon_button("Bottom", "pane_bottom",
                                   lambda: self.set_reading_pane("bottom"))
        right_btn = ribbon_button("Right", "pane_right",
                                  lambda: self.set_reading_pane("right"))
        bottom_btn.setCheckable(True)
        right_btn.setCheckable(True)
        self._pane_buttons = {"bottom": bottom_btn, "right": right_btn}
        view.add_group("Reading Pane", [bottom_btn, right_btn])
        self._folder_pane_btn = ribbon_button(
            "Folder Pane", "folder_pane", self._toggle_folder_pane)
        self._folder_pane_btn.setCheckable(True)
        self._folder_pane_btn.setChecked(
            bool(self.config.get_setting("folder_pane_visible", True)))
        view.add_group("Layout", [self._folder_pane_btn])
        view.add_group("Find", [
            ribbon_button("Search", "search", self._focus_search)])
        view.add_stretch()

        self.ribbon.add_tab("Home", home)
        self.ribbon.add_tab("Send/Receive", sr)
        self.ribbon.add_tab("Folder", folders)
        self.ribbon.add_tab("View", view)
        self.ribbon.file_clicked.connect(self._file_menu)
        self._update_pane_buttons()

    def _build_central(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # page 0: mail UI
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.ribbon)

        self.folder_pane = FolderPane()
        self.folder_pane.folder_selected.connect(self.open_folder)
        self.folder_pane.context_action.connect(self._folder_action_named)

        self.message_list = MessageList()
        self.message_list.action_requested.connect(self._list_action)
        self.message_list.selection_made.connect(self._on_selection)
        self.reading_pane = ReadingPane()
        self.reading_pane.attachment_clicked.connect(self._save_attachment)
        self.reading_pane.action_requested.connect(self._reading_action)

        # list area: search row + list
        list_area = QWidget()
        lv = QVBoxLayout(list_area)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        search_row = QWidget()
        sr = QVBoxLayout(search_row)
        sr.setContentsMargins(8, 5, 8, 5)
        sr.setSpacing(0)
        wrap = QWidget()
        wrap.setObjectName("searchWrap")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchBox")
        self.search_edit.setPlaceholderText("Search Current Mailbox  (Ctrl+F)")
        self.search_edit.setClearButtonEnabled(True)
        search_action = QAction(icons.icon("search", 14), "", self.search_edit)
        self.search_edit.addAction(search_action, QLineEdit.LeadingPosition)
        self.search_edit.textChanged.connect(self.message_list.set_search)
        wl.addWidget(self.search_edit)
        wrap.setFixedHeight(30)
        sr.addWidget(wrap)
        lv.addWidget(search_row)
        lv.addWidget(self.message_list, 1)
        self.list_area = list_area

        self.splitter_v = QSplitter(Qt.Vertical)
        self.splitter_v.addWidget(list_area)
        self.splitter_v.addWidget(self.reading_pane)
        self.splitter_v.setStretchFactor(0, 3)
        self.splitter_v.setStretchFactor(1, 2)
        self.splitter_v.setSizes([420, 300])

        self.splitter_h = QSplitter(Qt.Horizontal)
        self.splitter_h.addWidget(self.folder_pane)
        self.splitter_h.addWidget(self.splitter_v)
        self.splitter_h.setStretchFactor(0, 0)
        self.splitter_h.setStretchFactor(1, 1)
        self.splitter_h.setSizes([210, 1000])
        self.folder_pane.setMinimumWidth(160)
        layout.addWidget(self.splitter_h, 1)

        # page 1: welcome — blue identity band, heading, primary CTA, footer
        welcome = QWidget()
        welcome.setObjectName("welcomePage")
        wv = QVBoxLayout(welcome)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(0)

        band = QWidget()
        band.setObjectName("welcomeBand")
        self.welcome_band = band
        band.setFixedHeight(96)
        bh = QHBoxLayout(band)
        bh.setContentsMargins(44, 0, 0, 0)
        bh.setSpacing(18)
        logo_img = icons.icon("open_mail", 48).pixmap(48, 48).toImage()
        for y in range(logo_img.height()):
            for x in range(logo_img.width()):
                c = logo_img.pixelColor(x, y)
                if c.alpha():
                    c.setRgb(255, 255, 255)
                    logo_img.setPixelColor(x, y, c)
        logo = QLabel()
        logo.setPixmap(QPixmap.fromImage(logo_img))
        logo.setFixedSize(48, 48)
        btitles = QVBoxLayout()
        btitles.setSpacing(1)
        app_name = QLabel("BlueMail")
        app_name.setObjectName("welcomeTitle")
        app_tag = QLabel("Free desktop mail  ·  IMAP  ·  POP3  ·  SMTP")
        app_tag.setObjectName("welcomeSubtitle")
        btitles.addWidget(app_name)
        btitles.addWidget(app_tag)
        bh.addWidget(logo)
        bh.addLayout(btitles)
        bh.addStretch(1)
        wv.addWidget(band)

        wv.addStretch(1)
        heading = QLabel("Set up your mail")
        heading.setObjectName("welcomeHeading")
        self.welcome_heading = heading
        heading.setAlignment(Qt.AlignCenter)
        hint = QLabel(
            "Add an IMAP or POP3 account to get started.\n"
            "All mail is stored locally on this computer.")
        hint.setObjectName("welcomeHint")
        self.welcome_hint = hint
        hint.setAlignment(Qt.AlignCenter)
        add_btn = QPushButton("Add Account…")
        add_btn.setObjectName("primary")
        add_btn.setIcon(icons.icon("account", 20))
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setFixedSize(210, 42)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(
            lambda _c=False: self.open_account_settings(None))
        self.welcome_cta = add_btn
        btn_wrap = QWidget()
        bwl = QVBoxLayout(btn_wrap)
        bwl.setContentsMargins(0, 0, 0, 0)
        bwl.addWidget(add_btn)              # addWidget first…
        bwl.setAlignment(add_btn, Qt.AlignHCenter)  # …then alignment (no-op reverse)
        wv.addWidget(heading)
        wv.addSpacing(10)
        wv.addWidget(hint)
        wv.addSpacing(26)
        wv.addWidget(btn_wrap)

        providers_block = QWidget()
        pbl = QVBoxLayout(providers_block)
        pbl.setContentsMargins(0, 0, 0, 0)
        pbl.setSpacing(8)
        providers_label = QLabel("Or quick sign-in with")
        providers_label.setObjectName("welcomeProvidersLabel")
        providers_label.setAlignment(Qt.AlignCenter)
        pbl.addWidget(providers_label)
        chips = QWidget()
        chips.setObjectName("providerChips")
        cl = QHBoxLayout(chips)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        from .. import providers as provider_presets
        for pid, label in provider_presets.WELCOME_ROWS:
            chip = QPushButton(label)
            chip.setObjectName("providerChip")
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(
                lambda _c=False, k=pid: self.open_account_settings(k))
            cl.addWidget(chip)
        pbl.addWidget(chips, alignment=Qt.AlignHCenter)
        self.welcome_provider_row = providers_block
        wv.addSpacing(16)
        wv.addWidget(providers_block)
        wv.addStretch(1)

        footer = QLabel(
            "BlueMail  ·  free & open-source  ·  "
            "your mail never leaves this machine")
        footer.setObjectName("welcomeFooter")
        self.welcome_footer = footer
        footer.setFixedHeight(30)
        footer.setAlignment(Qt.AlignCenter)
        wv.addWidget(footer)

        self.stack.addWidget(page)
        self.stack.addWidget(welcome)

        if self._pane_pos == "right":
            self._apply_pane_right()
        visible = bool(self.config.get_setting("folder_pane_visible", True))
        self.folder_pane.setVisible(visible)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.status_label = QLabel("Ready")
        sb.addWidget(self.status_label, 1)
        self.progress = QProgressBar()
        self.progress.setObjectName("syncBar")
        self.progress.setRange(0, 0)
        self.progress.hide()
        sb.addPermanentWidget(self.progress)
        self.unread_label = QLabel("")
        sb.addPermanentWidget(self.unread_label)
        self.account_label = QLabel("")
        sb.addPermanentWidget(self.account_label)

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_message)
        QShortcut(QKeySequence("Ctrl+R"), self,
                  lambda: self.message_list.emit_action("reply"))
        QShortcut(QKeySequence("Ctrl+Shift+R"), self,
                  lambda: self.message_list.emit_action("reply_all"))
        QShortcut(QKeySequence("Ctrl+Alt+F"), self,
                  lambda: self.message_list.emit_action("forward"))
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("F9"), self, self.send_receive_all)
        QShortcut(QKeySequence("Ctrl+Q"), self,
                  lambda: self._set_read_for_selection(True))
        QShortcut(QKeySequence("Esc"), self, self.search_edit.clear)

    # ------------------------------------------------------------ task help
    def _submit(self, fn, on_done, on_fail=None, label=None):
        self._active += 1
        self._update_busy()
        if label:
            self.set_status(label)

        def finished():
            self._active -= 1
            self._update_busy()

        return workers.submit(
            fn,
            on_done=on_done,
            on_failed=on_fail or self._show_error,
            on_finished=finished,
        )

    def _update_busy(self):
        self.progress.setVisible(self._active > 0)

    def set_status(self, text, error=False):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color:{theme.RED};" if error else "")

    def _show_error(self, message):
        self.set_status(f"Error: {message}", error=True)

    def _silent_error(self, _message):
        pass

    # ----------------------------------------------------------- folder pane
    def refresh_folder_pane(self):
        animations.stop(self.folder_pane)   # repaint storm guard
        accounts = self.config.accounts
        folders_by = {}
        counts_by = {}
        for acc in accounts:
            self._ensure_local_folders(acc)
            folders_by[acc.id] = self.store.list_folders(acc.id)
            counts_by[acc.id] = self.store.counts(acc.id)
        self.folder_pane.populate(accounts, folders_by, counts_by)
        self._update_unread_label()

    def _ensure_local_folders(self, account):
        if account.protocol == "imap":
            if not self.store.folder_path_exists(account.id, "INBOX"):
                self.store.upsert_folder(account.id, "INBOX", "Inbox", "inbox")
            return
        for path, role in (("INBOX", "inbox"), ("Drafts", "drafts"),
                           ("Sent", "sent"), ("Trash", "trash"),
                           ("Junk", "junk")):
            if not self.store.folder_path_exists(account.id, path):
                self.store.upsert_folder(account.id, path,
                                         ROLE_LABELS[role], role)

    def _update_unread_label(self):
        if not self._current:
            self.unread_label.setText("")
            return
        acc_id, folder = self._current
        counts = self.store.counts(acc_id, folder)
        unread = counts.get(folder, 0)
        self.unread_label.setText(f"Unread: {unread}" if unread else "Unread: 0")

    def _toggle_folder_pane(self, checked):
        self.folder_pane.setVisible(checked)
        self.config.set_setting("folder_pane_visible", checked)

    # ------------------------------------------------------------- folders
    def open_folder(self, account_id, path):
        self._current = (account_id, path)
        acc = self.config.get(account_id)
        if acc:
            name = self._folder_display(account_id, path)
            self.setWindowTitle(
                f"{name} - {acc.email} - BlueMail")
            self.account_label.setText(acc.email)
        self.reload_list()
        self.reading_pane.clear()
        animations.fade_in(self.message_list, 260)
        self._preview = None
        if not self.demo:
            self.sync_folder(account_id, path)

    def _folder_display(self, account_id, path):
        for row in self.store.list_folders(account_id):
            if row["path"] == path:
                return row.get("name") or path
        return path

    def _folder_role(self, account_id, path):
        for row in self.store.list_folders(account_id):
            if row["path"] == path:
                return row.get("role") or "custom"
        return folder_role(path, path)

    def reload_list(self, keep_uid=None):
        animations.stop(self.message_list)  # repaint storm guard
        if not self._current:
            self.message_list.set_rows([])
            return
        acc_id, folder = self._current
        rows = self.store.list_messages(acc_id, folder)
        self.message_list.set_rows(rows)
        if keep_uid is not None:
            self.message_list.select_uid(keep_uid)
        self._update_unread_label()

    def sync_folder(self, account_id, path, background=True):
        if self.demo:
            return
        key = (account_id, path)
        if key in self._syncing:
            return
        acc = self.config.get(account_id)
        if acc is None or not acc.enabled:
            return
        self._syncing.add(key)
        if not background:
            self.set_status(f"Syncing {self._folder_display(account_id, path)}…")

        def run():
            if acc.protocol == "imap":
                with ImapClient(acc) as client:
                    client.select(path)
                    uv = client.uidvalidity()
                    metas = client.fetch_summaries()
                return {"folder": path, "metas": metas, "uidvalidity": uv,
                        "server_uids": [m.uid for m in metas]}
            existing = self.store.uid_set(acc.id, path)
            with PopClient(acc) as client:
                new, all_uidls = client.fetch_summaries(existing=existing)
            return {"folder": path, "metas": new, "server_uids": all_uidls,
                    "uidvalidity": 0}

        def done(payload):
            self._syncing.discard(key)
            self._apply_sync(acc, payload)

        def failed(err):
            self._syncing.discard(key)
            self._show_error(err)

        self._submit(run, done, failed,
                     None if background else "Syncing…")

    def _apply_sync(self, account, payload):
        folder = payload["folder"]
        existed = self.store.folder_path_exists(account.id, folder)
        if not existed:
            name = folder.split("/")[-1]
            if folder.upper() == "INBOX":
                name = "Inbox"
            self.store.upsert_folder(account.id, folder, name,
                                     folder_role(folder, name))
        local_uids = self.store.uid_set(account.id, folder)
        server_uids = {str(u) for u in payload["server_uids"]}
        removed = local_uids - server_uids

        new_uv = int(payload.get("uidvalidity") or 0)
        prev_uv = 0
        for row in self.store.list_folders(account.id):
            if row["path"] == folder:
                prev_uv = int(row.get("uidvalidity") or 0)
                break
        if new_uv and prev_uv and new_uv != prev_uv:
            removed = set(local_uids)

        self.store.apply_sync(account.id, folder, payload["metas"],
                              removed_uids=removed)
        self.store.mark_folder_synced(
            account.id, folder, new_uv or None)

        if not existed or self._current == (account.id, folder):
            keep = None
            if self._preview and self._current == (account.id, folder):
                keep = self._preview.get("uid")
            self.reload_list(keep_uid=keep)
        self.refresh_folder_pane()
        if self._current == (account.id, folder):
            self.set_status("Up to date")
            self._refresh_preview_row()
        else:
            self.set_status("Up to date")

    def sync_folder_list(self, account, then_inbox=True):
        if self.demo or account.protocol != "imap":
            return

        def run():
            with ImapClient(account) as client:
                return client.list_folders()

        def done(folders):
            server_paths = set()
            for info in folders:
                server_paths.add(info.path)
                name = "Inbox" if info.path.upper() == "INBOX" else info.name
                role = folder_role(info.path, info.name)
                self.store.upsert_folder(account.id, info.path, name, role)
            for path in self.store.all_folder_paths(account.id):
                if path not in server_paths:
                    self.store.remove_folder(account.id, path)
            if not self.store.folder_path_exists(account.id, "INBOX"):
                self.store.upsert_folder(account.id, "INBOX", "Inbox", "inbox")
            self.refresh_folder_pane()
            if then_inbox:
                self.sync_folder(account.id, "INBOX")
                if self._current and self._current[0] == account.id:
                    self.sync_folder(*self._current)

        self._submit(run, done)

    def sync_current(self, background=False):
        if self._current:
            self.sync_folder(*self._current, background=background)

    def send_receive_all(self):
        if self.demo:
            self.set_status("Demo mode — no server to sync")
            return
        accounts = self.config.accounts
        if not accounts:
            self.open_account_settings()
            return
        self.set_status("Sending/Receiving…")
        for acc in accounts:
            self._ensure_local_folders(acc)
            if acc.protocol == "imap":
                self.sync_folder_list(acc, then_inbox=True)
            else:
                self.sync_folder(acc.id, "INBOX")
        if self._current and self.config.get(self._current[0]) and \
                self.config.get(self._current[0]).protocol == "pop3":
            self.sync_folder(*self._current)
        QTimer.singleShot(1500, self._idle_status)

    def _idle_status(self):
        if self._active == 0:
            self.set_status("Ready")

    # ------------------------------------------------------------- actions
    def _list_action(self, action, rows):
        if action == "open":
            self._open_messages(rows)
        elif action == "reply":
            self._reply(rows, reply_all=False)
        elif action == "reply_all":
            self._reply(rows, reply_all=True)
        elif action == "forward":
            self._forward(rows)
        elif action == "delete":
            self._delete_rows(rows)
        elif action == "toggle_read":
            if rows:
                self._set_read(not all(r.get("is_read") for r in rows), rows)
        elif action == "toggle_flag":
            if rows:
                self._set_flag(not any(r.get("is_flagged") for r in rows), rows)

    def _reading_action(self, action):
        """Quick-action buttons in the reading pane header."""
        row = self.reading_pane.current_row()
        if not row:
            return
        self._list_action(action, [row])

    def _set_read_for_selection(self, read):
        rows = self.message_list.selected_rows()
        if rows:
            self._set_read(read, rows)

    def _set_read(self, read, rows):
        if not self._current or not rows:
            return
        acc_id, folder = self._current
        uids = [str(r["uid"]) for r in rows]
        for row in rows:
            row["is_read"] = bool(read)
            self.message_list.update_row(row["uid"])
        self.store.set_flags(acc_id, folder, uids, is_read=read)
        self.refresh_folder_pane()
        acc = self.config.get(acc_id)
        if acc and acc.protocol == "imap" and not self.demo:
            def run():
                with ImapClient(acc) as client:
                    client.select(folder)
                    for uid in uids:
                        client.set_seen(uid, read)
                return True
            self._submit(run, lambda _r: None, self._silent_error)

    def _set_flag(self, flagged, rows):
        if not self._current or not rows:
            return
        acc_id, folder = self._current
        uids = [str(r["uid"]) for r in rows]
        for row in rows:
            row["is_flagged"] = bool(flagged)
            self.message_list.update_row(row["uid"])
        self.store.set_flags(acc_id, folder, uids, is_flagged=flagged)
        acc = self.config.get(acc_id)
        if acc and acc.protocol == "imap" and not self.demo:
            def run():
                with ImapClient(acc) as client:
                    client.select(folder)
                    for uid in uids:
                        client.set_flagged(uid, flagged)
                return True
            self._submit(run, lambda _r: None, self._silent_error)

    def _delete_rows(self, rows):
        if not self._current or not rows:
            return
        acc_id, folder = self._current
        acc = self.config.get(acc_id)
        if acc is None:
            return
        uids = [str(r["uid"]) for r in rows]
        role = self._folder_role(acc_id, folder)
        trash_path = None
        if role != "trash":
            for row in self.store.list_folders(acc_id):
                if row.get("role") == "trash" and row["path"] != folder:
                    trash_path = row["path"]
                    break

        if acc.protocol != "imap" or self.demo:
            target = trash_path or ("Trash" if role != "trash" else None)
            if target is None:
                self.store.delete_messages(acc_id, folder, uids)
                label = "Deleted"
            else:
                if not self.store.folder_path_exists(acc_id, target):
                    self.store.upsert_folder(acc_id, target, "Deleted Items",
                                             "trash")
                self.store.move_messages(acc_id, folder, target, uids)
                label = f"Moved to {self._folder_display(acc_id, target)}"
            self._after_delete(rows, label)
            return

        src = folder
        dst = trash_path

        def run():
            with ImapClient(acc) as client:
                client.select(src)
                if dst:
                    client.move(uids, dst)
                else:
                    client.store_deleted(uids)
                    client.expunge()
            return True

        def done(_r):
            if dst:
                self.store.move_messages(acc_id, src, dst, uids)
                label = f"Moved to {self._folder_display(acc_id, dst)}"
            else:
                self.store.delete_messages(acc_id, src, uids)
                label = "Deleted"
            self._after_delete(rows, label)

        self._submit(run, done)

    def _after_delete(self, rows, label):
        keep_next = None
        if self._preview and any(
                str(r["uid"]) == str(self._preview.get("uid"))
                for r in rows):
            self.reading_pane.clear()
            self._preview = None
        self.reload_list(keep_uid=keep_next)
        self.refresh_folder_pane()
        self.set_status(label)

    # ------------------------------------------------------- preview & body
    def _on_selection(self, row):
        if row is None:
            return
        if not self._current:
            return
        self._preview = row
        acc_id, folder = self._current
        raw = self.store.get_raw(acc_id, folder, row["uid"])
        self.reading_pane.show_message(row, raw)
        if raw is None and not self.demo:
            self._fetch_body(acc_id, folder, row)
        if not row.get("is_read"):
            self._set_read(True, [row])

    def _fetch_body(self, acc_id, folder, row):
        acc = self.config.get(acc_id)
        if acc is None:
            return
        uid = str(row["uid"])
        self._pending_body = uid

        def run():
            if acc.protocol == "imap":
                with ImapClient(acc) as client:
                    client.select(folder)
                    return client.fetch_full(uid)
            with PopClient(acc) as client:
                entries = {str(u): n for n, u in client.uidl_list()}
                num = entries.get(uid)
                if num is None:
                    raise RuntimeError("Message no longer on server")
                return client.fetch_full(num)

        def done(raw):
            self.store.set_raw(acc_id, folder, uid, raw)
            if self._pending_body == uid:
                self.reading_pane.show_body(uid, raw)
                for win in self._message_windows:
                    if str(win.row.get("uid")) == uid:
                        win.show_raw(win.row, raw)
                for compose in self._compose_windows:
                    if (getattr(compose, "mode", "") == "draft"
                            and getattr(compose, "draft_uid", None) == uid):
                        compose.load_draft(raw)
            self._pending_body = None

        self._submit(run, done)

    def _refresh_preview_row(self):
        if not self._preview or not self._current:
            return
        acc_id, folder = self._current
        fresh = self.store.get_message(acc_id, folder,
                                       self._preview.get("uid"))
        if fresh is None:
            self.reading_pane.clear()
            self._preview = None
            return
        self._preview = fresh

    def _save_attachment(self, data, filename):
        path, _ = QFileDialog.getSaveFileName(self, "Save Attachment",
                                              filename or "attachment.bin")
        if not path:
            return
        try:
            with open(path, "wb") as fh:
                fh.write(data)
            self.set_status(f"Saved {path.rsplit('/', 1)[-1]}")
        except OSError as exc:
            self._show_error(str(exc))

    # ------------------------------------------------------- open / compose
    def _open_messages(self, rows):
        if not rows:
            return
        row = rows[0]
        if not self._current:
            return
        acc_id, folder = self._current
        role = self._folder_role(acc_id, folder)
        raw = self.store.get_raw(acc_id, folder, row["uid"])
        if role == "drafts":
            if raw is None:
                self._preview = row
                self.reading_pane.show_message(row, None)
                self._fetch_body(acc_id, folder, row)
                self.set_status("Opening draft…")
                return
            self._open_draft(acc_id, row, raw)
            return
        win = MessageWindow(row)
        win.action.connect(self._window_action)
        self._message_windows.append(win)
        win.show()
        if raw is not None:
            win.show_raw(row, raw)
        else:
            win.reading.show_message(row, None)
            self._fetch_body(acc_id, folder, row)

    def _window_action(self, action, row):
        rows = [row]
        if action == "delete":
            self._delete_rows(rows)
            for win in list(self._message_windows):
                if win.row is row:
                    win.close()
            return
        self._list_action(action, rows)

    def _open_draft(self, acc_id, row, raw):
        acc = self.config.get(acc_id)
        compose = ComposeWindow(acc, mode="draft")
        compose.draft_uid = str(row.get("uid"))
        compose.draft_account = acc_id
        compose.send_requested.connect(self._send_compose)
        compose.save_draft_requested.connect(self._save_draft)
        compose.load_draft(raw)
        self._compose_windows.append(compose)
        compose.show()

    def new_message(self, account=None, *_):
        if not isinstance(account, Account):
            account = None          # QAbstractButton.clicked passes (checked,)
        acc = account
        if acc is None and self._current:
            acc = self.config.get(self._current[0])
        if acc is None:
            acc = self.config.accounts[0] if self.config.accounts else None
        compose = ComposeWindow(acc, mode="new")
        compose.send_requested.connect(self._send_compose)
        compose.save_draft_requested.connect(self._save_draft)
        self._compose_windows.append(compose)
        compose.show()
        compose.raise_()
        compose.activateWindow()

    def _reply(self, rows, reply_all=False):
        if not rows or not self._current:
            return
        row = rows[0]
        acc_id, folder = self._current
        acc = self.config.get(acc_id)
        raw = self.store.get_raw(acc_id, folder, row["uid"])

        def open_with(raw_data):
            compose = ComposeWindow(acc, mode="reply_all" if reply_all
                                    else "reply")
            compose.send_requested.connect(self._send_compose)
            compose.save_draft_requested.connect(self._save_draft)
            compose.prefill_reply(row, raw_data, reply_all=reply_all)
            self._compose_windows.append(compose)
            compose.show()

        if raw is not None:
            open_with(raw)
        else:
            def run():
                if acc.protocol == "imap":
                    with ImapClient(acc) as client:
                        client.select(folder)
                        return client.fetch_full(str(row["uid"]))
                with PopClient(acc) as client:
                    entries = {str(u): n for n, u in client.uidl_list()}
                    num = entries.get(str(row["uid"]))
                    if num is None:
                        raise RuntimeError("Message no longer on server")
                    return client.fetch_full(num)

            def done(raw_data):
                self.store.set_raw(acc_id, folder, row["uid"], raw_data)
                open_with(raw_data)

            self._submit(run, done, label="Preparing reply…")

    def _forward(self, rows):
        if not rows or not self._current:
            return
        row = rows[0]
        acc_id, folder = self._current
        acc = self.config.get(acc_id)
        raw = self.store.get_raw(acc_id, folder, row["uid"])

        def open_with(raw_data):
            compose = ComposeWindow(acc, mode="forward")
            compose.send_requested.connect(self._send_compose)
            compose.save_draft_requested.connect(self._save_draft)
            compose.prefill_forward(row, raw_data)
            self._compose_windows.append(compose)
            compose.show()

        if raw is not None:
            open_with(raw)
        else:
            def run():
                if acc.protocol == "imap":
                    with ImapClient(acc) as client:
                        client.select(folder)
                        return client.fetch_full(str(row["uid"]))
                with PopClient(acc) as client:
                    entries = {str(u): n for n, u in client.uidl_list()}
                    num = entries.get(str(row["uid"]))
                    if num is None:
                        raise RuntimeError("Message no longer on server")
                    return client.fetch_full(num)

            def done(raw_data):
                self.store.set_raw(acc_id, folder, row["uid"], raw_data)
                open_with(raw_data)

            self._submit(run, done, label="Preparing forward…")

    # ------------------------------------------------------- send & drafts
    def _send_compose(self, compose):
        acc = compose.account
        if acc is None:
            compose.send_finished(False, "No account selected")
            return
        try:
            msg = compose.build_message()
        except Exception as exc:  # noqa: BLE001
            compose.send_finished(False, str(exc))
            return
        if not (msg["To"] or msg["Cc"]):
            compose.send_finished(False, "Please enter at least one recipient")
            return

        sent_folder = self._resolve_role_folder(acc, "sent")
        if acc.protocol == "imap" and not sent_folder:
            sent_folder = "Sent"

        def run():
            if self.demo:
                return {"appended": False, "raw": msg.as_bytes()}
            smtp_send(acc, msg)
            appended = False
            if acc.protocol == "imap":
                try:
                    with ImapClient(acc) as client:
                        client.append(sent_folder, msg.as_bytes())
                    appended = True
                except Exception:
                    appended = False
            return {"appended": appended, "raw": msg.as_bytes()}

        def done(result):
            if compose in self._compose_windows:
                self._compose_windows.remove(compose)
            appended = result["appended"]
            raw = result["raw"]
            folder_for_copy = sent_folder or "Sent"
            if acc.protocol != "imap" or self.demo:
                if not self.store.folder_path_exists(acc.id, folder_for_copy):
                    self.store.upsert_folder(acc.id, folder_for_copy,
                                             ROLE_LABELS["sent"], "sent")
                self._store_local_message(acc, folder_for_copy, msg, raw)
                compose.send_finished(True, "Message sent")
                self.set_status("Message sent")
            elif appended:
                compose.send_finished(True, "Message sent")
                self.set_status("Message sent")
                self.sync_folder(acc.id, folder_for_copy)
            else:
                compose.send_finished(
                    True, "Sent, but could not save to Sent Items")
                self.set_status(
                    "Message sent (not saved to server Sent Items)",
                    error=True)
            compose.close()
            if self._current and self._current[0] == acc.id:
                self.reload_list(
                    keep_uid=self._preview.get("uid")
                    if self._preview else None)
            self.refresh_folder_pane()

        def failed(err):
            compose.send_finished(False, err)
            self._show_error(err)

        self._submit(run, done, failed, label="Sending…")

    def _store_local_message(self, acc, folder, msg, raw, is_read=True):
        uid = "L" + uuid.uuid4().hex[:12]
        date_hdr = msg["Date"]
        from email.utils import parsedate_to_datetime
        date_ts = int(datetime.now().timestamp())
        if date_hdr:
            try:
                date_ts = int(parsedate_to_datetime(str(date_hdr)).timestamp())
            except Exception:
                pass
        meta = MessageMeta(
            uid=uid,
            msgid=str(msg["Message-ID"] or ""),
            from_name=acc.name or "",
            from_addr=acc.email,
            to_addr=parse_address_field(str(msg["To"] or "")),
            cc_addr=parse_address_field(str(msg["Cc"] or "")),
            subject=str(msg["Subject"] or ""),
            date_ts=date_ts,
            size=len(raw),
            is_read=is_read,
            importance="",
        )
        self.store.insert_message(acc.id, folder, meta, raw)

    def _save_draft(self, compose):
        acc = compose.account
        if acc is None:
            compose.status_label.setText("No account selected")
            return
        try:
            msg = compose.build_message()
        except Exception as exc:  # noqa: BLE001
            compose.status_label.setText(f"Cannot save draft: {exc}")
            return
        raw = msg.as_bytes()
        folder = self._resolve_role_folder(acc, "drafts") or "Drafts"
        if not self.store.folder_path_exists(acc.id, folder):
            self.store.upsert_folder(acc.id, folder, "Drafts", "drafts")

        if getattr(compose, "draft_uid", None) and compose.draft_account == acc.id:
            uid = compose.draft_uid
            meta = MessageMeta(
                uid=uid, msgid=str(msg["Message-ID"] or ""),
                from_addr=acc.email,
                to_addr=parse_address_field(str(msg["To"] or "")),
                cc_addr=parse_address_field(str(msg["Cc"] or "")),
                subject=str(msg["Subject"] or ""),
                date_ts=int(datetime.now().timestamp()), size=len(raw),
                is_read=True)
            self.store.insert_message(acc.id, folder, meta, raw)
            if self._current and self._current[0] == acc.id and \
                    self._current[1] != folder:
                pass
        else:
            self._store_local_message(acc, folder, msg, raw)
            compose.draft_uid = None
        compose.status_label.setText("Draft saved")
        self.refresh_folder_pane()
        if self._current and self._current[0] == acc.id:
            self.reload_list(
                keep_uid=self._preview.get("uid") if self._preview else None)
        self.set_status("Draft saved")

        if acc.protocol == "imap" and not self.demo:
            def run():
                try:
                    with ImapClient(acc) as client:
                        client.append(folder, raw, flags="")
                    return True
                except Exception:
                    return False

            def done(ok):
                if ok:
                    self.sync_folder(acc.id, folder)

            self._submit(run, done, self._silent_error)

    def _resolve_role_folder(self, account, role):
        for row in self.store.list_folders(account.id):
            if row.get("role") == role:
                return row["path"]
        return None

    # --------------------------------------------------------- folder menu
    def _folder_action(self, action):
        sel = self.folder_pane.current_folder()
        if not sel:
            return
        self._folder_action_named(action, sel[0], sel[1])

    def _folder_action_named(self, action, account_id, path):
        acc = self.config.get(account_id)
        if action == "account_settings":
            self.open_account_settings()
            return
        if action == "sync_account":
            if acc and acc.protocol == "imap":
                self.sync_folder_list(acc, then_inbox=True)
            else:
                self.sync_folder(account_id, "INBOX")
            return
        if acc is None or not path:
            return

        if action == "sync_folder":
            self.sync_folder(account_id, path, background=False)
            return

        if action == "new_folder":
            parent_path = path
            name, ok = QInputDialog.getText(
                self, "New Folder", "Folder name:", QLineEdit.Normal, "")
            if not ok or not name.strip():
                return
            new_path = f"{parent_path}/{name.strip()}"
            if acc.protocol == "imap" and not self.demo:
                def run():
                    with ImapClient(acc) as client:
                        client.create_folder(new_path)
                    return True

                def done(_r):
                    self.store.upsert_folder(account_id, new_path,
                                             name.strip(), "custom")
                    self.refresh_folder_pane()
                    self.set_status(f"Created folder {name.strip()}")
                self._submit(run, done)
            else:
                self.store.upsert_folder(account_id, new_path, name.strip(),
                                         "custom")
                self.refresh_folder_pane()
            return

        if action == "rename_folder":
            current = self._folder_display(account_id, path)
            name, ok = QInputDialog.getText(
                self, "Rename Folder", "New name:", QLineEdit.Normal, current)
            if not ok or not name.strip() or name.strip() == current:
                return
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            new_path = f"{parent}/{name.strip()}" if parent else name.strip()
            if acc.protocol == "imap" and not self.demo:
                def run():
                    with ImapClient(acc) as client:
                        client.rename_folder(path, new_path)
                    return True

                def done(_r):
                    self.store.remove_folder(account_id, path)
                    self.store.upsert_folder(account_id, new_path,
                                             name.strip(),
                                             folder_role(new_path, name))
                    if self._current == (account_id, path):
                        self._current = None
                        self.folder_pane.select_folder(account_id, new_path)
                    self.refresh_folder_pane()
                self._submit(run, done)
            else:
                self.store.remove_folder(account_id, path)
                self.store.upsert_folder(account_id, new_path, name.strip(),
                                         folder_role(new_path, name))
                self.refresh_folder_pane()
            return

        if action == "delete_folder":
            role = self._folder_role(account_id, path)
            if role in ("inbox", "trash", "drafts", "sent"):
                self.set_status("Built-in folders cannot be deleted",
                                error=True)
                return
            answer = QMessageBox.question(
                self, "Delete Folder",
                f"Delete folder “{self._folder_display(account_id, path)}” "
                "and all messages in it?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            if acc.protocol == "imap" and not self.demo:
                def run():
                    with ImapClient(acc) as client:
                        client.select(path)
                        uids = client.search_all()
                        if uids:
                            client.store_deleted(uids)
                            client.expunge()
                        client.delete_folder(path)
                    return True

                def done(_r):
                    self.store.remove_folder(account_id, path)
                    if self._current == (account_id, path):
                        self._current = None
                        self.folder_pane.select_folder(account_id, "INBOX")
                    self.refresh_folder_pane()
                self._submit(run, done)
            else:
                self.store.remove_folder(account_id, path)
                self.refresh_folder_pane()
            return

        if action == "empty_folder":
            role = self._folder_role(account_id, path)
            if role not in ("trash", "junk"):
                answer = QMessageBox.question(
                    self, "Empty Folder",
                    "Permanently delete ALL messages in this folder?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    return
            uids = sorted(self.store.uid_set(account_id, path))
            if not uids:
                self.set_status("Folder is already empty")
                return
            if acc.protocol == "imap" and not self.demo:
                def run():
                    with ImapClient(acc) as client:
                        client.select(path)
                        client.store_deleted(uids)
                        client.expunge()
                    return True

                def done(_r):
                    self.store.delete_messages(account_id, path, uids)
                    self.reload_list()
                    self.reading_pane.clear()
                    self.refresh_folder_pane()
                    self.set_status("Folder emptied")
                self._submit(run, done)
            else:
                self.store.delete_messages(account_id, path, uids)
                self.reload_list()
                self.reading_pane.clear()
                self.refresh_folder_pane()
                self.set_status("Folder emptied")
            return

        if action == "mark_all_read":
            unread = [u for u, r in
                      ((m["uid"], m) for m in
                       self.store.list_messages(account_id, path))
                      if not r.get("is_read")]
            if not unread:
                return
            self.store.set_flags(account_id, path, unread, is_read=True)
            if acc.protocol == "imap" and not self.demo:
                def run():
                    with ImapClient(acc) as client:
                        client.select(path)
                        for i in range(0, len(unread), 100):
                            chunk = unread[i:i + 100]
                            for uid in chunk:
                                client.set_seen(uid, True)
                    return True
                self._submit(run, lambda _r: None, self._silent_error)
            self.reload_list(
                keep_uid=self._preview.get("uid") if self._preview else None)
            self.refresh_folder_pane()
            self.set_status("All messages marked as read")

    # ------------------------------------------------------------ settings
    def open_account_settings(self, provider=None):
        before = {a.id for a in self.config.accounts}
        dialog = AccountDialog(self.config, self, provider=provider)
        dialog.accounts_changed.connect(self._accounts_changed)
        dialog.exec_()
        after = {a.id for a in self.config.accounts}
        removed = before - after
        for acc_id in removed:
            self.store.clear_account(acc_id)
        if removed:
            self._current = None
            self.reading_pane.clear()

    # ---------------------------------------------------------------- smart
    def open_opencode(self):
        """Open the Opencode assistant for the currently selected email."""
        from .opencode_dialog import OpencodeDialog
        row = self.message_list.first_selected()
        dialog = OpencodeDialog(row, self)
        dialog.exec_()

    def _accounts_changed(self):
        self.refresh_folder_pane()
        target = 0 if self.config.accounts else 1
        changed = target != self._last_entrance
        if self.config.accounts:
            self.stack.setCurrentIndex(0)
            self._enter_main()
        else:
            self.stack.setCurrentIndex(1)
            self._enter_welcome()
        if changed:
            animations.fade_window(self, 320, start=0.92)
        if not self.demo:
            for acc in self.config.accounts:
                self._ensure_local_folders(acc)
                if acc.protocol == "imap":
                    self.sync_folder_list(acc, then_inbox=True)
                else:
                    self.sync_folder(acc.id, "INBOX")
            self.refresh_folder_pane()

    # ---------------------------------------------------------- entrances
    def _enter_welcome(self):
        """Staggered reveal of the welcome page (runs once per page switch)."""
        if self._last_entrance == 1:
            return
        self._last_entrance = 1
        animations.stagger([
            (self.welcome_band, 0, 340),
            (self.welcome_heading, 150, 300),
            (self.welcome_hint, 220, 300),
            (self.welcome_cta, 300, 320),
            (self.welcome_provider_row, 360, 300),
            (self.welcome_footer, 430, 260),
        ])
        QTimer.singleShot(1000, lambda: animations.pulse(self.welcome_cta))

    def _enter_main(self):
        """Staggered reveal of the mail UI (runs once per page switch)."""
        if self._last_entrance == 0:
            return
        self._last_entrance = 0
        animations.stagger([
            (self.ribbon, 0, 300),
            (self.folder_pane, 70, 300),
            (self.message_list, 140, 300),
            (self.reading_pane, 210, 300),
        ])

    def _file_menu(self):
        menu = QMenu(self)
        menu.addAction(icons.icon("account", 16), "Account Settings…",
                       self.open_account_settings)
        menu.addAction(icons.icon("send_recv", 16), "Send/Receive All (F9)",
                       self.send_receive_all)
        menu.addSeparator()
        menu.addAction(icons.icon("exit", 16), "Exit", self.close)
        pos = self.ribbon.file_button.mapToGlobal(
            self.ribbon.file_button.rect().bottomLeft())
        menu.exec_(pos)

    # -------------------------------------------------------- reading pane
    def set_reading_pane(self, position):
        if position == self._pane_pos:
            return
        if position == "right":
            self.splitter_h.addWidget(self.list_area)
            self.splitter_h.addWidget(self.reading_pane)
            self.splitter_v.setParent(None)
            self.splitter_h.setSizes([200, 560, 420])
        else:
            self.splitter_v.addWidget(self.list_area)
            self.splitter_v.addWidget(self.reading_pane)
            self.splitter_h.addWidget(self.splitter_v)
            self.splitter_h.setSizes([200, 980])
            self.splitter_v.setSizes([430, 300])
        self._pane_pos = position
        self.config.set_setting("reading_pane", position)
        self._update_pane_buttons()

    def _apply_pane_right(self):
        self.splitter_h.addWidget(self.list_area)
        self.splitter_h.addWidget(self.reading_pane)
        self.splitter_v.setParent(None)
        self.splitter_h.setSizes([200, 560, 420])

    def _update_pane_buttons(self):
        for pos, btn in self._pane_buttons.items():
            btn.setChecked(pos == self._pane_pos)

    def _focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    # ------------------------------------------------------------- closing
    def closeEvent(self, event):
        self.config.save()
        for win in list(self._compose_windows):
            win.close()
        for win in list(self._message_windows):
            win.close()
        try:
            self.store.close()
        except Exception:
            pass
        super().closeEvent(event)



