"""Outlook-style message list: table model + proxy + view."""

import datetime

from PyQt5.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableView,
)

from ..protocols.common import format_size
from . import animations, avatars, icons, theme

COL_IMPORTANCE = 0
COL_ATTACH = 1
COL_FROM = 2
COL_SUBJECT = 3
COL_RECEIVED = 4
COL_SIZE = 5

DATE_ROLE = Qt.UserRole + 1
SIZE_ROLE = Qt.UserRole + 2


def _fmt_datetime(ts):
    if not ts:
        return ""
    dt = datetime.datetime.fromtimestamp(ts)
    now = datetime.datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    if dt.year == now.year:
        return dt.strftime("%d %b %H:%M")
    return dt.strftime("%d %b %Y")


class MessageTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    # ------------------------------------------------------------- plumbing
    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rows(self):
        return list(self._rows)

    def row_at(self, uid):
        for i, r in enumerate(self._rows):
            if str(r.get("uid")) == str(uid):
                return i, r
        return -1, None

    def update_row(self, uid):
        i, _row = self.row_at(uid)
        if i >= 0:
            self.dataChanged.emit(
                self.index(i, 0), self.index(i, self.columnCount() - 1)
            )

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 6

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        return ["", "", "From", "Subject", "Received", "Size"][section]

    # ----------------------------------------------------------------- data
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == COL_FROM:
                return row.get("from_display") or row.get("from_addr") or ""
            if col == COL_SUBJECT:
                subj = row.get("subject") or ""
                return subj if subj else "(no subject)"
            if col == COL_RECEIVED:
                return _fmt_datetime(row.get("date_ts") or 0)
            if col == COL_SIZE:
                return format_size(row.get("size") or 0)
            return ""

        if role == Qt.DecorationRole:
            if col == COL_IMPORTANCE:
                if row.get("is_flagged"):
                    return icons.icon("flag", 20)
                if row.get("importance") == "high":
                    return icons.icon("importance_high", 20)
                if row.get("importance") == "low":
                    return icons.icon("importance_low", 20)
                if not row.get("is_read"):
                    return avatars.unread_dot(20)
                return None
            if col == COL_ATTACH and row.get("has_attachment"):
                return icons.icon("attach", 20)
            if col == COL_FROM:
                return avatars.avatar_pixmap(
                    row.get("from_display") or "",
                    row.get("from_addr") or "",
                    20,
                )
            return None

        if role == Qt.FontRole:
            font = QFont()
            if not row.get("is_read"):
                font.setBold(True)
            return font

        if role == Qt.ForegroundRole:
            if not row.get("is_read"):
                return QColor(theme.UNREAD)
            if row.get("is_flagged"):
                return QColor("#a4262c")
            return QColor(theme.TEXT)

        if role == Qt.TextAlignmentRole and col == COL_SIZE:
            return int(Qt.AlignRight | Qt.AlignVCenter)

        if role == DATE_ROLE:
            return int(row.get("date_ts") or 0)

        if role == SIZE_ROLE:
            return int(row.get("size") or 0)

        if role == Qt.ToolTipRole:
            lines = [
                row.get("from_display") or "",
                ("To: " + (row.get("to_addr") or "")) if row.get("to_addr") else "",
                ("Cc: " + (row.get("cc_addr") or "")) if row.get("cc_addr") else "",
                row.get("subject") or "",
            ]
            return "\n".join(l for l in lines if l)

        return None

    def sort(self, column, order=Qt.AscendingOrder):
        reverse = order == Qt.DescendingOrder
        self.layoutAboutToBeChanged.emit()

        def key(row):
            if column == COL_RECEIVED:
                return row.get("date_ts") or 0
            if column == COL_SIZE:
                return row.get("size") or 0
            if column == COL_FROM:
                return (row.get("from_display") or row.get("from_addr") or "").lower()
            if column == COL_SUBJECT:
                return (row.get("subject") or "").lower()
            return row.get("uid") or ""

        self._rows.sort(key=key, reverse=reverse)
        self.layoutChanged.emit()


class MessageProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search = ""
        self.setSortRole(Qt.DisplayRole)
        self.setDynamicSortFilter(True)

    def set_search(self, text):
        text = (text or "").strip().lower()
        if text == self._search:
            return
        self._search = text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._search:
            return True
        model = self.sourceModel()
        idx = model.index(source_row, 0, source_parent)
        row = model.rows()[source_row]
        haystack = " ".join([
            row.get("subject") or "",
            row.get("from_display") or "",
            row.get("from_addr") or "",
            row.get("to_addr") or "",
        ]).lower()
        del idx
        return self._search in haystack

    def lessThan(self, left, right):
        col = left.column()
        if col == COL_RECEIVED:
            lv = self.sourceModel().data(left, DATE_ROLE) or 0
            rv = self.sourceModel().data(right, DATE_ROLE) or 0
            return lv < rv
        if col == COL_SIZE:
            lv = self.sourceModel().data(left, SIZE_ROLE) or 0
            rv = self.sourceModel().data(right, SIZE_ROLE) or 0
            return lv < rv
        if col in (COL_FROM, COL_SUBJECT):
            ls = self.sourceModel().data(left, Qt.DisplayRole) or ""
            rs = self.sourceModel().data(right, Qt.DisplayRole) or ""
            return ls.lower() < rs.lower()
        return super().lessThan(left, right)


class MessageList(QTableView):
    action_requested = pyqtSignal(str, list)
    selection_made = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("messageList")
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(34)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setIconSize(QSize(20, 20))

        self._model = MessageTableModel(self)
        self._proxy = MessageProxy(self)
        self._proxy.setSourceModel(self._model)
        self.setModel(self._proxy)

        header = self.horizontalHeader()
        header.setObjectName("messageHeader")
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(COL_IMPORTANCE, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_ATTACH, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_FROM, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_SUBJECT, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_RECEIVED, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_SIZE, QHeaderView.Fixed)
        header.resizeSection(COL_IMPORTANCE, 24)
        header.resizeSection(COL_ATTACH, 24)
        header.resizeSection(COL_FROM, 175)
        header.resizeSection(COL_RECEIVED, 120)
        header.resizeSection(COL_SIZE, 64)

        self.setSortingEnabled(True)
        self.sortByColumn(COL_RECEIVED, Qt.DescendingOrder)

        self.selectionModel().selectionChanged.connect(self._on_selection)
        self.doubleClicked.connect(lambda _i: self.emit_action("open"))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    # ---------------------------------------------------------------- data
    def set_rows(self, rows):
        animations.stop(self)   # repaint storm guard (sync/flag updates)
        self._model.set_rows(rows)
        self._proxy.sort(self.horizontalHeader().sortIndicatorSection(),
                         self.horizontalHeader().sortIndicatorOrder())

    def model_rows(self):
        return self._model.rows()

    def set_search(self, text):
        self._proxy.set_search(text)

    def selected_rows(self):
        rows = []
        seen = set()
        for idx in self.selectionModel().selectedRows():
            src = self._proxy.mapToSource(idx)
            uid = str(self._model.rows()[src.row()].get("uid"))
            if uid in seen:
                continue
            seen.add(uid)
            rows.append(self._model.rows()[src.row()])
        return rows

    def first_selected(self):
        rows = self.selected_rows()
        return rows[0] if rows else None

    def select_uid(self, uid):
        for r in range(self._proxy.rowCount()):
            src = self._proxy.mapToSource(self._proxy.index(r, 0))
            row = self._model.rows()[src.row()]
            if str(row.get("uid")) == str(uid):
                proxy_index = self._proxy.index(r, 0)
                self.selectRow(r)
                self.scrollTo(proxy_index)
                return True
        return False

    def update_row(self, uid):
        self._model.update_row(uid)

    # -------------------------------------------------------------- events
    def _on_selection(self, _selected, _deselected):
        self.selection_made.emit(self.first_selected())

    def emit_action(self, action):
        rows = self.selected_rows()
        if rows or action in ("new",):
            self.action_requested.emit(action, rows)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.emit_action("open")
            return
        if key == Qt.Key_Delete:
            self.emit_action("delete")
            return
        if key == Qt.Key_Space:
            self.emit_action("open")
            return
        super().keyPressEvent(event)

    def _context_menu(self, pos):
        rows = self.selected_rows()
        menu = QMenu(self)
        act_open = menu.addAction(icons.icon("open_mail", 16), "Open")
        act_reply = menu.addAction(icons.icon("reply", 16), "Reply")
        act_reply_all = menu.addAction(icons.icon("reply_all", 16), "Reply All")
        act_forward = menu.addAction(icons.icon("forward", 16), "Forward")
        menu.addSeparator()
        act_read = menu.addAction(
            icons.icon("open_mail", 16),
            "Mark as Read" if rows and all(r.get("is_read") for r in rows)
            else "Mark as Unread",
        )
        if rows and any(not r.get("is_flagged") for r in rows):
            act_flag = menu.addAction(icons.icon("flag", 16), "Flag")
        else:
            act_flag = menu.addAction(icons.icon("unflag", 16), "Clear Flag")
        menu.addSeparator()
        act_delete = menu.addAction(icons.icon("delete", 16), "Delete\tDel")

        if not rows:
            for a in (act_open, act_reply, act_reply_all, act_forward,
                      act_read, act_flag, act_delete):
                a.setEnabled(False)
        chosen = menu.exec_(self.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        mapping = {
            act_open: "open",
            act_reply: "reply",
            act_reply_all: "reply_all",
            act_forward: "forward",
            act_read: "toggle_read",
            act_flag: "toggle_flag",
            act_delete: "delete",
        }
        action = mapping.get(chosen)
        if action:
            self.emit_action(action)
