"""
Shared UI Widgets: Infrastructure-level components used across multiple option modules.
=====================================================================================
Extracted from the original monolithic app.py to enable reuse across the options/ package.
Contains no business logic — only UI structure and COM/Office integration.
"""

import os
import win32gui
import win32con
import win32com.client

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QSizePolicy, QMenu, QScrollArea, QFrame,
    QDialog, QTextBrowser
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize


# =============================================================================
# HamburgerButton: Styled sidebar menu trigger
# =============================================================================

class HamburgerButton(QPushButton):
    hovered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("☰", parent)
        self.setObjectName("btn_hamburger")
        self.setToolTip("Options Menu")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(36, 32)
        self.setStyleSheet("""
            QPushButton#btn_hamburger {
                background-color: #FFC0CB;
                border: 1px solid #FF69B4;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                color: #800020;
                padding: 0px;
                text-align: center;
            }
            QPushButton#btn_hamburger:hover {
                background-color: #FF69B4;
                color: white;
            }
            QPushButton#btn_hamburger[active="true"] {
                background-color: #FF69B4;
                color: white;
            }
        """)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.hovered.emit()


# =============================================================================
# Sidebar: Left-hand navigation panel with scrollable button area
# =============================================================================

class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(180)
        self.setObjectName("sidebar_root")
        self.setStyleSheet("""
            QWidget#sidebar_root { background-color: #FFB6C1; }
            QScrollArea { background-color: #FFB6C1; border: none; }
            QWidget#sidebar_container { background-color: #FFB6C1; }
            QPushButton {
                background-color: #FFC0CB;
                border: 1px solid #FF69B4;
                padding: 10px;
                text-align: left;
                font-weight: bold;
                color: black;
            }
            QPushButton:hover { background-color: #FF69B4; color: white; }
            QPushButton[active="true"] { background-color: #FF69B4; color: white; }
            QLabel { font-weight: bold; padding: 10px; color: #B03060; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.container.setObjectName("sidebar_container")
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Bottom-left container for hamburger button
        self.bottom_bar = QWidget()
        self.bottom_bar.setObjectName("sidebar_bottom_bar")
        self.bottom_bar.setStyleSheet("background-color: #FFB6C1;")
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(12, 6, 12, 12)
        bottom_layout.setSpacing(0)
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.btn_hamburger = HamburgerButton()
        bottom_layout.addWidget(self.btn_hamburger)
        layout.addWidget(self.bottom_bar, stretch=0)


# =============================================================================
# TaskWidget: Individual To-Do item with status cycling
# =============================================================================

class TaskWidget(QWidget):
    def __init__(self, description: str, task_id: str, state_change_callback=None):
        super().__init__()
        self.task_id = task_id
        self.state_change_callback = state_change_callback
        self.states = ["⏳", "❌", "✅", "➖"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.lbl_desc = QLabel(description)
        self.btn_state = QPushButton(self.states[0])
        self.btn_state.setFixedWidth(40)
        self.btn_state.clicked.connect(self.show_status_menu)

        layout.addWidget(self.lbl_desc)
        layout.addStretch()
        layout.addWidget(self.btn_state)

    def show_status_menu(self):
        menu = QMenu(self)
        for state in self.states:
            action = menu.addAction(state)
            action.triggered.connect(lambda checked=False, s=state: self.set_state(s))
        menu.exec(self.btn_state.mapToGlobal(self.btn_state.rect().bottomLeft()))

    def set_state(self, state: str):
        from MODULES.offers_module import log_task
        self.btn_state.setText(state)
        log_task(f"{state} {self.lbl_desc.text()}", "STATE_CHANGED")
        if self.state_change_callback:
            self.state_change_callback(state, self.task_id, self.lbl_desc.text())


# =============================================================================
# OfficeViewer: Embedded Word/Excel COM automation viewer
# =============================================================================

class OfficeViewer(QWidget):
    file_saved_and_closed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.office_app = None
        self.doc = None
        self.office_hwnd = None
        self.current_filepath = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hide()

    def open_file(self, filepath: str) -> None:
        self.close_file()
        self.current_filepath = os.path.abspath(filepath)
        ext = os.path.splitext(filepath)[1].lower()

        try:
            if ext in ['.doc', '.docx']:
                self.office_app = win32com.client.DispatchEx("Word.Application")
                self.office_app.WindowState = 0
                self.office_app.Visible = True
                self.doc = self.office_app.Documents.Open(self.current_filepath)
                try:
                    self.office_app.ActiveWindow.ActivePane.View.Zoom.Percentage = 70
                except Exception:
                    pass
                self.office_hwnd = self.office_app.ActiveWindow.Hwnd
            elif ext in ['.csv', '.xls', '.xlsx']:
                self.office_app = win32com.client.DispatchEx("Excel.Application")
                self.office_app.WindowState = -4143
                self.office_app.Visible = True
                self.doc = self.office_app.Workbooks.Open(self.current_filepath)
                self.office_hwnd = self.office_app.Hwnd

            if self.office_hwnd:
                win32gui.SetParent(self.office_hwnd, int(self.winId()))
                style = win32gui.GetWindowLong(self.office_hwnd, win32con.GWL_STYLE)
                style = style & ~win32con.WS_CAPTION & ~win32con.WS_THICKFRAME & ~win32con.WS_SYSMENU
                win32gui.SetWindowLong(self.office_hwnd, win32con.GWL_STYLE, style)
                QTimer.singleShot(500, self.resize_office_window)
            self.show()
        except Exception as e:
            print(f"System Error (open_file): {e}")

    def save_file(self) -> None:
        if self.doc:
            try:
                self.doc.Save()
            except:
                pass

    def close_file(self) -> None:
        if self.doc:
            try:
                self.doc.Close(False)
            except:
                pass
            self.doc = None

        if self.office_app:
            try:
                self.office_app.Quit()
            except:
                pass
            self.office_app = None

        self.office_hwnd = None
        self.hide()

    def save_and_close(self) -> None:
        fp = self.current_filepath
        self.save_file()
        self.close_file()
        if fp:
            self.file_saved_and_closed.emit(fp)

    def resize_office_window(self) -> None:
        if self.office_hwnd:
            ratio = self.devicePixelRatioF()
            w = int(self.width() * ratio)
            h = int(self.height() * ratio)
            win32gui.SetWindowPos(
                self.office_hwnd,
                win32con.HWND_TOP,
                0, 0, w, h,
                win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_office_window()


# =============================================================================
# WorkspaceViewerDialog: Full-size document viewer dialog
# =============================================================================

class WorkspaceViewerDialog(QDialog):
    """
    Dedicated document viewer dialog covering 99% of the parent window's bounds.
    An explicit outer padding of 6 pixels leaves the discrete pink boundary visible framing the active viewer.
    """
    def __init__(self, title: str, content_html: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
            }
            #OuterContainer {
                background-color: #ffffff;
                border: 2px solid #f43f5e; /* Discrete Pink Border */
                border-radius: 8px;
            }
        """)

        # Main Layout taking 99% scale of the workspace
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)  # Leaves discrete 1% pink backdrop visible

        container = QFrame()
        container.setObjectName("OuterContainer")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(12, 12, 12, 12)

        # Content display
        self.browser = QTextBrowser()
        if content_html:
            self.browser.setHtml(content_html)
        self.browser.setStyleSheet("border: none; background: #ffffff;")
        c_layout.addWidget(self.browser)

        # Bottom Controls
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #e11d48;
                color: white;
                font-weight: bold;
                padding: 6px 18px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #be123c;
            }
        """)
        close_btn.clicked.connect(self.close)
        btn_bar.addWidget(close_btn)
        c_layout.addLayout(btn_bar)

        root_layout.addWidget(container)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            # Calculate 99% geometry of parent workspace
            p_geom = self.parent().geometry()
            w = int(p_geom.width() * 0.99)
            h = int(p_geom.height() * 0.99)
            x = p_geom.x() + (p_geom.width() - w) // 2
            y = p_geom.y() + (p_geom.height() - h) // 2
            self.setGeometry(x, y, w, h)
