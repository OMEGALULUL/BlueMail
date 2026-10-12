"""Outlook-style ribbon: File button, tabs, button panels with group labels."""

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme


def ribbon_button(text, icon_name, slot=None, checkable=False, tooltip=""):
    btn = QToolButton()
    btn.setObjectName("ribbonButton")
    btn.setText(text)
    btn.setIcon(icons.icon(icon_name, 32))
    btn.setIconSize(QSize(28, 28))
    btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    btn.setAutoRaise(True)
    btn.setCheckable(checkable)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedSize(78, 70)
    btn.setToolTip(tooltip or text)
    if slot is not None:
        btn.clicked.connect(slot)
    return btn


def mini_button(text, icon_name, slot=None, checkable=False, tooltip=""):
    btn = QToolButton()
    btn.setObjectName("ribbonButton")
    btn.setText(text)
    btn.setIcon(icons.icon(icon_name, 16))
    from PyQt5.QtCore import QSize
    btn.setIconSize(QSize(16, 16))
    btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    btn.setAutoRaise(True)
    btn.setCheckable(checkable)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedHeight(26)
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    btn.setToolTip(tooltip or text)
    if slot is not None:
        btn.clicked.connect(slot)
    return btn


class RibbonPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ribbonPanel")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 4, 6, 2)
        self._layout.setSpacing(2)

    def add_group(self, title, widgets):
        if self._layout.count() > 0:
            sep = QFrame()
            sep.setObjectName("groupSep")
            sep.setFrameShape(QFrame.VLine)
            sep.setFixedWidth(1)
            sep.setContentsMargins(4, 4, 4, 4)
            self._layout.addWidget(sep)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        for w in widgets:
            row.addWidget(w)
        col.addLayout(row)
        col.addStretch(1)
        label = QLabel(title)
        label.setObjectName("groupTitle")
        col.addWidget(label)
        holder = QWidget()
        holder.setLayout(col)
        self._layout.addWidget(holder)
        return self

    def add_stretch(self):
        self._layout.addStretch(1)


class Ribbon(QWidget):
    file_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ribbon")
        self.setFixedHeight(104)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(4, 3, 4, 0)
        tab_row.setSpacing(0)
        self.file_button = QToolButton()
        self.file_button.setObjectName("fileTab")
        self.file_button.setText("File")
        self.file_button.setCursor(Qt.PointingHandCursor)
        self.file_button.setFixedHeight(26)
        self.file_button.clicked.connect(self.file_clicked)
        tab_row.addWidget(self.file_button)
        self.tabs = QTabBar()
        self.tabs.setObjectName("ribbonTabs")
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.setDocumentMode(True)
        self.tabs.setFixedHeight(27)
        tab_row.addWidget(self.tabs)
        tab_row.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(tab_row)
        wrap.setObjectName("ribbon")
        root.addWidget(wrap)

        frame = QFrame()
        frame.setObjectName("ribbonFrame")
        self.panel_layout = QHBoxLayout(frame)
        self.panel_layout.setContentsMargins(0, 0, 0, 0)
        self.panel_layout.setSpacing(0)
        root.addWidget(frame, 1)

        self._panels = []
        self.tabs.currentChanged.connect(self._show_panel)

    def add_tab(self, title: str, panel: RibbonPanel) -> int:
        idx = self.tabs.addTab(title)
        panel.hide()
        self.panel_layout.addWidget(panel)
        self._panels.append(panel)
        if len(self._panels) == 1:
            self.tabs.setCurrentIndex(0)
            self._show_panel(0)
        return idx

    def _show_panel(self, idx: int):
        for i, panel in enumerate(self._panels):
            panel.setVisible(i == idx)

    def set_tab_enabled(self, idx, enabled):
        self.tabs.setTabEnabled(idx, enabled)
