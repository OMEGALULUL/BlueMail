"""Outlook 2016 look-and-feel: palette, fonts, stylesheets."""

from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import QApplication

BLUE = "#0078d4"
BLUE_HOVER = "#106ebe"
BLUE_PRESSED = "#005a9e"
BLUE_DARK = "#2b579a"
BLUE_LIGHT = "#cfe4f7"
BLUE_LIGHTER = "#e5f1fb"
HOVER_GRAY = "#edebe9"
CHROME = "#f3f2f1"
BORDER = "#d0d0d0"
BORDER_SOFT = "#e1dfdd"
TEXT = "#201f1e"
MUTED = "#605e5c"
WHITE = "#ffffff"
UNREAD = "#0563c1"
SELECT_BG = "#cfe4f7"
SELECT_BORDER = "#9dc9ef"
RED = "#d13438"
GREEN = "#107c10"

FONT_FAMILIES = ["Segoe UI", "Noto Sans", "DejaVu Sans", "sans-serif"]


def app_font() -> QFont:
    font = QFont()
    try:
        font.setFamilies(FONT_FAMILIES)
    except AttributeError:
        font = QFont(FONT_FAMILIES[0])
    font.setPointSize(10)
    return font


def apply_application_style(app: QApplication):
    app.setFont(app_font())
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f0f0f0"))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Base, QColor(WHITE))
    pal.setColor(QPalette.AlternateBase, QColor("#faf9f8"))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(CHROME))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor(SELECT_BG))
    pal.setColor(QPalette.HighlightedText, QColor(TEXT))
    pal.setColor(QPalette.ToolTipBase, QColor(WHITE))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.PlaceholderText, QColor("#8a8886"))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)


STYLESHEET = f"""
/* ---------------------------------------------------------- main window */
QMainWindow, QDialog {{
    background: {WHITE};
}}
QLabel {{
    background: transparent;
    color: {TEXT};
}}
QToolTip {{
    background: {WHITE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 3px 6px;
    font-size: 11px;
}}

/* ---------------------------------------------------------------- ribbon */
QWidget#ribbon {{
    background: {CHROME};
    border-bottom: 1px solid {BORDER};
}}
QToolButton#fileTab {{
    background: {BLUE_DARK};
    color: {WHITE};
    border: none;
    padding: 5px 16px;
    font-weight: bold;
    font-size: 12px;
}}
QToolButton#fileTab:hover {{
    background: {BLUE};
}}
QTabBar#ribbonTabs {{
    background: {CHROME};
    border: none;
    selection-background-color: {WHITE};
}}
QTabBar#ribbonTabs::tab {{
    background: transparent;
    color: #444;
    border: none;
    padding: 7px 16px 6px 16px;
    margin: 0;
    font-size: 12px;
    min-width: 40px;
}}
QTabBar#ribbonTabs::tab:hover {{
    background: #e1dfdd;
    color: {TEXT};
}}
QTabBar#ribbonTabs::tab:selected {{
    background: {WHITE};
    color: {BLUE};
    font-weight: bold;
    border-bottom: 2px solid {BLUE};
}}
QToolButton#ribbonButton {{
    background: transparent;
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 4px 6px;
    font-size: 11px;
}}
QToolButton#ribbonButton:hover {{
    background: {BLUE_LIGHT};
    border: 1px solid {SELECT_BORDER};
}}
QToolButton#ribbonButton:pressed {{
    background: #a6d4f2;
    border: 1px solid #7bb8e8;
}}
QToolButton#ribbonButton:checked {{
    background: {BLUE_LIGHT};
    border: 1px solid {SELECT_BORDER};
}}
QToolButton#ribbonButton:disabled {{
    color: #a19f9d;
}}
QToolButton#sendTool {{
    background: {BLUE_LIGHTER};
    color: {TEXT};
    border: 1px solid {SELECT_BORDER};
    border-radius: 3px;
    padding: 4px 6px;
    font-size: 11px;
}}
QToolButton#sendTool:hover {{
    background: {BLUE_LIGHT};
    border: 1px solid #7bb8e8;
}}
QToolButton#sendTool:pressed {{
    background: #a6d4f2;
    border: 1px solid #7bb8e8;
}}
QWidget#ribbonPanel {{
    background: {WHITE};
}}
QLabel#groupTitle {{
    color: {MUTED};
    font-size: 10px;
    padding-top: 2px;
    qproperty-alignment: AlignHCenter;
}}
QFrame#groupSep {{
    background: {BORDER_SOFT};
    max-width: 1px;
    min-width: 1px;
}}
QFrame#ribbonFrame {{
    background: {WHITE};
    border-bottom: 1px solid {BORDER};
}}

/* ------------------------------------------------------------ welcome */
QWidget#welcomePage {{
    background: {WHITE};
}}
QWidget#welcomeBand {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #2b579a, stop:1 #1f427a);
}}
QLabel#welcomeTitle {{
    color: {WHITE};
    font-size: 21px;
    font-weight: bold;
}}
QLabel#welcomeSubtitle {{
    color: #b9c7e8;
    font-size: 12px;
}}
QLabel#welcomeHeading {{
    color: {TEXT};
    font-size: 26px;
}}
QLabel#welcomeHint {{
    color: {MUTED};
    font-size: 13px;
}}
QLabel#welcomeFooter {{
    background: {CHROME};
    color: {MUTED};
    font-size: 11px;
    border-top: 1px solid {BORDER_SOFT};
}}
QLabel#welcomeProvidersLabel {{
    color: {MUTED};
    font-size: 12px;
}}
QPushButton#providerChip {{
    background: {WHITE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 15px;
    padding: 7px 18px;
    font-size: 13px;
}}
QPushButton#providerChip:hover {{
    background: {BLUE_LIGHTER};
    border: 1px solid {BLUE};
    color: {BLUE_HOVER};
}}
QPushButton#providerChip:pressed {{
    background: {SELECT_BG};
}}
QWidget#welcomePage QPushButton {{
    font-size: 13px;
}}

/* ---------------------------------------------------------- folder pane */
QTreeWidget#folderTree {{
    background: {WHITE};
    border: none;
    alternate-background-color: {WHITE};
    font-size: 12px;
    outline: 0;
}}
QTreeWidget#folderTree::item {{
    height: 26px;
    padding: 1px 7px;
    border: none;
    border-radius: 0;
}}
QTreeWidget#folderTree::item:hover {{
    background: {BLUE_LIGHTER};
}}
QTreeWidget#folderTree::item:selected {{
    background: {SELECT_BG};
    color: {TEXT};
    border: none;
}}
QTreeWidget#folderTree::branch {{ background: transparent; }}

/* --------------------------------------------------------- message list */
QLabel#searchWrap {{
    background: {WHITE};
    border: 1px solid {BORDER_SOFT};
    border-radius: 3px;
    padding: 1px 4px;
}}
QLineEdit#searchBox {{
    background: transparent;
    border: none;
    padding: 3px 2px;
    font-size: 12px;
    color: {TEXT};
}}
QTableView#messageList {{
    background: {WHITE};
    alternate-background-color: #faf9f8;
    border: none;
    gridline-color: transparent;
    selection-background-color: {SELECT_BG};
    selection-color: {TEXT};
    font-size: 12px;
}}
QTableView#messageList::item {{
    padding: 3px 6px;
    border: none;
}}
QTableView#messageList::item:hover {{
    background: #e9f3fc;
}}
QTableView#messageList::item:selected {{
    background: {SELECT_BG};
    color: {TEXT};
}}
QHeaderView#messageHeader {{
    background: {CHROME};
    border: none;
    border-bottom: 1px solid {BORDER};
}}
QHeaderView::section#messageHeader {{
    background: {CHROME};
    color: #444;
    border: none;
    border-right: none;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: normal;
}}
QHeaderView::section#messageHeader:hover {{
    background: #e1dfdd;
}}
QTableView#messageList QAbstractItemView::indicator {{
    width: 0px;
    height: 0px;
}}

/* --------------------------------------------------------- reading pane */
QFrame#readingPane {{
    background: {WHITE};
    border: none;
}}
QFrame#msgHeadCard {{
    background: transparent;
}}
QLabel#msgAvatar {{
    background: transparent;
    border: none;
}}
QLabel#msgSenderName {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#msgSenderMail {{
    font-size: 12px;
    color: {MUTED};
}}
QLabel#msgDateTop {{
    font-size: 11px;
    color: {MUTED};
}}
QToolButton#readingAction {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px;
}}
QToolButton#readingAction:hover {{
    background: #f3f2f1;
    border-color: {BORDER_SOFT};
}}
QToolButton#readingAction:pressed {{
    background: {BLUE_LIGHT};
    border-color: {SELECT_BORDER};
}}
QToolButton#readingAction:disabled {{
    border-color: transparent;
    background: transparent;
}}
QLabel#msgSubject {{
    font-size: 18px;
    font-weight: bold;
    color: {TEXT};
    padding-top: 6px;
    padding-bottom: 4px;
}}
QFrame#msgHeaderSep {{
    background: {BORDER_SOFT};
    max-height: 1px;
    min-height: 1px;
}}
QLabel#msgMetaLabel {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#msgMetaValue {{
    color: {TEXT};
    font-size: 12px;
}}
QLabel#msgDateTime {{
    color: {MUTED};
    font-size: 11px;
}}
QTextBrowser#msgBody {{
    background: {WHITE};
    border: none;
    color: {TEXT};
    font-size: 13px;
    padding: 4px 18px 18px 18px;
}}
QFrame#attachmentBar {{
    background: #f8f8f8;
    border-top: 1px solid {BORDER_SOFT};
    border-bottom: 1px solid {BORDER_SOFT};
}}
QToolButton#attachmentButton {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 11px;
    color: {TEXT};
}}
QToolButton#attachmentButton:hover {{
    background: {BLUE_LIGHT};
    border-color: {SELECT_BORDER};
}}
QLabel#readPlaceholder {{
    color: {MUTED};
    font-size: 13px;
}}

/* ------------------------------------------------------- search & tools */
QLineEdit#headerField {{
    background: {WHITE};
    border: none;
    border-bottom: 1px solid {BORDER_SOFT};
    padding: 6px 4px;
    font-size: 12px;
}}
QLineEdit#headerField:focus {{
    border-bottom: 1px solid {BLUE};
}}
QLabel#headerCaption {{
    color: {MUTED};
    font-size: 11px;
    padding-right: 6px;
}}
QTextEdit#composeBody {{
    background: {WHITE};
    border: none;
    font-size: 13px;
    padding: 8px;
    selection-background-color: {SELECT_BG};
    selection-color: {TEXT};
}}

/* -------------------------------------------------------------- buttons */
QPushButton {{
    background: {WHITE};
    color: {TEXT};
    border: 1px solid #8a8886;
    border-radius: 2px;
    padding: 5px 16px;
    font-size: 12px;
}}
QPushButton:hover {{
    background: {HOVER_GRAY};
    border-color: {MUTED};
}}
QPushButton:pressed {{
    background: #e1dfdd;
}}
QPushButton:disabled {{
    color: #a19f9d;
    border-color: {BORDER};
    background: {CHROME};
}}
QPushButton:focus {{
    border-color: {BLUE};
}}
QPushButton#primary {{
    background: {BLUE};
    color: {WHITE};
    border: 1px solid {BLUE};
    font-weight: bold;
    padding: 6px 20px;
}}
QPushButton#primary:hover {{
    background: {BLUE_HOVER};
    border-color: {BLUE_HOVER};
}}
QPushButton#primary:pressed {{
    background: {BLUE_PRESSED};
}}
QPushButton#primary:disabled {{
    background: #a6d4f2;
    border-color: #a6d4f2;
    color: {WHITE};
}}

/* --------------------------------------------------------------- inputs */
QLineEdit, QComboBox, QSpinBox {{
    background: {WHITE};
    border: 1px solid #8a8886;
    border-radius: 2px;
    padding: 4px 6px;
    font-size: 12px;
    color: {TEXT};
    selection-background-color: {SELECT_BG};
    selection-color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {BLUE};
    padding: 3px 5px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {WHITE};
    border: 1px solid {BORDER};
    selection-background-color: {BLUE_LIGHT};
    selection-color: {TEXT};
    font-size: 12px;
}}
QCheckBox {{
    font-size: 12px;
    color: {TEXT};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #8a8886;
    background: {WHITE};
    border-radius: 2px;
}}
QCheckBox::indicator:checked {{
    background: {BLUE};
    border-color: {BLUE};
}}
QListWidget#accountList {{
    background: {WHITE};
    border: 1px solid {BORDER};
    font-size: 12px;
}}
QListWidget#accountList::item {{
    padding: 7px 8px;
    border-bottom: 1px solid #f3f2f1;
}}
QListWidget#accountList::item:selected {{
    background: {SELECT_BG};
    color: {TEXT};
}}

/* -------------------------------------------------------------- menus */
QMenuBar {{
    background: {CHROME};
    color: {TEXT};
    border-bottom: 1px solid {BORDER};
    font-size: 12px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {BLUE_LIGHT};
}}
QMenu {{
    background: {WHITE};
    border: 1px solid {BORDER};
    padding: 4px;
    font-size: 12px;
}}
QMenu::item {{
    padding: 5px 26px 5px 24px;
    border-radius: 2px;
}}
QMenu::item:selected {{
    background: {BLUE_LIGHT};
    color: {TEXT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER_SOFT};
    margin: 4px 8px;
}}
QMenu::indicator {{
    width: 14px;
    height: 14px;
}}

/* ---------------------------------------------------------- status bar */
QStatusBar {{
    background: {CHROME};
    border-top: 1px solid {BORDER};
    color: {MUTED};
    font-size: 11px;
}}
QStatusBar::item {{
    border: none;
}}
QStatusBar QLabel {{
    color: {MUTED};
    font-size: 11px;
    padding: 0 6px;
}}
QProgressBar#syncBar {{
    background: transparent;
    border: none;
    max-height: 12px;
    min-width: 90px;
    max-width: 90px;
    text-align: center;
    font-size: 10px;
    color: {MUTED};
}}
QProgressBar#syncBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #0078d4, stop:0.5 #1f8fd4,
                                stop:1 #0078d4);
    border-radius: 2px;
}}

/* ------------------------------------------------------------ splitter */
QSplitter::handle {{
    background: {WHITE};
}}
QSplitter::handle:horizontal {{
    width: 5px;
    border-left: 1px solid #ececec;
    border-right: 1px solid #ececec;
}}
QSplitter::handle:horizontal:hover {{
    background: {BLUE_LIGHT};
}}
QSplitter::handle:vertical {{
    height: 5px;
    border-top: 1px solid #ececec;
    border-bottom: 1px solid #ececec;
}}
QSplitter::handle:vertical:hover {{
    background: {BLUE_LIGHT};
}}

/* ---------------------------------------------------------- scrollbars */
QScrollBar:vertical {{
    background: {WHITE};
    width: 14px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: #c8c6c4;
    min-height: 32px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {MUTED};
}}
QScrollBar:horizontal {{
    background: {WHITE};
    height: 14px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: #c8c6c4;
    min-width: 32px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {MUTED};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QScrollBar::corner {{
    background: {WHITE};
}}
"""
