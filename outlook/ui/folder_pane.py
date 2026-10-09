"""Folder tree (accounts + folders) with unread counts and context menu."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem

from ..protocols.common import ROLE_LABELS, ROLE_ORDER
from . import icons

ROLE_ICONS = {
    "inbox": "folder_inbox",
    "drafts": "folder_drafts",
    "sent": "folder_sent",
    "junk": "folder_junk",
    "trash": "trash",
    "archive": "archive",
    "custom": "folder",
}

ITEM_KIND = Qt.UserRole + 1
ITEM_ACCOUNT = Qt.UserRole + 2
ITEM_PATH = Qt.UserRole + 3


class FolderPane(QTreeWidget):
    folder_selected = pyqtSignal(str, str)            # account_id, path
    context_action = pyqtSignal(str, str, str)        # action, account_id, path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("folderTree")
        self.setHeaderHidden(True)
        self.setIndentation(18)
        self.setRootIsDecorated(True)
        self.setAnimated(True)
        self.setExpandsOnDoubleClick(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemSelectionChanged.connect(self._on_selection)
        self._current = None  # (account_id, path)

    # -------------------------------------------------------------- populate
    def populate(self, accounts, folders_by_account, counts_by_account):
        expanded = {}
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            expanded[item.data(0, ITEM_ACCOUNT)] = item.isExpanded()

        self.clear()
        first_select = None
        for account in accounts:
            acc_item = QTreeWidgetItem()
            acc_item.setText(0, account.email)
            acc_item.setIcon(0, icons.icon("account", 16))
            f = acc_item.font(0)
            f.setBold(True)
            acc_item.setFont(0, f)
            acc_item.setData(0, ITEM_KIND, "account")
            acc_item.setData(0, ITEM_ACCOUNT, account.id)
            acc_item.setData(0, ITEM_PATH, "")
            acc_item.setFlags(Qt.ItemIsEnabled)
            self.addTopLevelItem(acc_item)

            folders = folders_by_account.get(account.id, [])
            counts = counts_by_account.get(account.id, {})
            folders = sorted(
                folders,
                key=lambda r: (ROLE_ORDER.index(r.get("role", "custom"))
                               if r.get("role", "custom") in ROLE_ORDER else 99,
                               (r.get("name") or "").lower()),
            )
            for folder in folders:
                role = folder.get("role", "custom")
                child = QTreeWidgetItem()
                label = folder.get("name") or folder.get("path") or role
                unread = counts.get(folder.get("path"), 0)
                if unread:
                    label = f"{label} ({unread})"
                child.setText(0, label)
                child.setIcon(0, icons.icon(ROLE_ICONS.get(role, "folder"), 16))
                if unread:
                    cf = child.font(0)
                    cf.setBold(True)
                    child.setFont(0, cf)
                child.setData(0, ITEM_KIND, "folder")
                child.setData(0, ITEM_ACCOUNT, account.id)
                child.setData(0, ITEM_PATH, folder.get("path"))
                acc_item.addChild(child)
                if first_select is None and role == "inbox":
                    first_select = (account.id, folder.get("path"))
            acc_item.setExpanded(expanded.get(account.id, True))

        if self._current:
            self.select_folder(*self._current)
        elif first_select:
            self.select_folder(*first_select)

    # ------------------------------------------------------------- selection
    def select_folder(self, account_id, path):
        for i in range(self.topLevelItemCount()):
            acc_item = self.topLevelItem(i)
            for j in range(acc_item.childCount()):
                child = acc_item.child(j)
                if (child.data(0, ITEM_ACCOUNT) == account_id
                        and child.data(0, ITEM_PATH) == path):
                    self.setCurrentItem(child)
                    return True
        return False

    def current_folder(self):
        item = self.currentItem()
        if item is None:
            return None
        if item.data(0, ITEM_KIND) != "folder":
            return None
        return item.data(0, ITEM_ACCOUNT), item.data(0, ITEM_PATH)

    def _on_selection(self):
        sel = self.current_folder()
        if sel and sel != self._current:
            self._current = sel
            self.folder_selected.emit(*sel)

    # ---------------------------------------------------------- context menu
    def _context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        kind = item.data(0, ITEM_KIND)
        account_id = item.data(0, ITEM_ACCOUNT)
        path = item.data(0, ITEM_PATH)
        menu = QMenu(self)
        if kind == "account":
            act_refresh = menu.addAction(icons.icon("refresh", 16), "Sync Now")
            menu.addSeparator()
            act_settings = menu.addAction(icons.icon("account", 16),
                                          "Account Settings…")
            chosen = menu.exec_(self.viewport().mapToGlobal(pos))
            if chosen is act_refresh:
                self.context_action.emit("sync_account", account_id, "")
            elif chosen is act_settings:
                self.context_action.emit("account_settings", account_id, "")
            return

        act_new = menu.addAction(icons.icon("new_folder", 16), "New Folder…")
        act_rename = menu.addAction(icons.icon("folder", 16), "Rename…")
        act_delete = menu.addAction(icons.icon("delete", 16), "Delete")
        menu.addSeparator()
        act_read = menu.addAction(icons.icon("open_mail", 16),
                                  "Mark All as Read")
        act_empty = menu.addAction(icons.icon("trash", 16), "Empty Folder")
        act_refresh = menu.addAction(icons.icon("refresh", 16), "Sync Now")
        chosen = menu.exec_(self.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        mapping = {
            act_new: "new_folder",
            act_rename: "rename_folder",
            act_delete: "delete_folder",
            act_read: "mark_all_read",
            act_empty: "empty_folder",
            act_refresh: "sync_folder",
        }
        action = mapping.get(chosen)
        if action:
            self.context_action.emit(action, account_id, path)
