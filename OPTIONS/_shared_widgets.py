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
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QEvent, QObject
from PyQt6.QtGui import QColor


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
    def __init__(self, description: str, task_id: str, state_change_callback=None, payload: dict = None):
        super().__init__()
        self.task_id = task_id
        self.state_change_callback = state_change_callback
        self.payload = payload or {}
        self.states = ["⏳", "❌", "✅", "➖"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.lbl_desc = QLabel(description)
        self.btn_state = QPushButton(self.states[0])
        self.btn_state.setFixedWidth(40)
        self.btn_state.clicked.connect(self.show_status_menu)

        layout.addWidget(self.lbl_desc)

        if self.payload.get("type") == "outlook_draft":
            self.btn_outlook = QPushButton("✉️ Manual Draft")
            self.btn_outlook.setStyleSheet("background-color: #2563EB; color: white; border-radius: 4px; padding: 2px 8px; font-weight: bold;")
            self.btn_outlook.clicked.connect(self.manual_draft_outlook)
            layout.addWidget(self.btn_outlook)

        layout.addStretch()
        layout.addWidget(self.btn_state)

    def manual_draft_outlook(self):
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            data = self.payload.get("data", {})
            mail.To = data.get("To", "")
            mail.CC = data.get("CC", "")
            mail.Subject = data.get("Subject", "")
            mail.HTMLBody = data.get("HTMLBody", "")
            
            attachment = data.get("Attachment")
            if attachment:
                import os
                mail.Attachments.Add(os.path.abspath(attachment))
                
            mail.Display()
        except Exception as e:
            print(f"Failed to draft outlook email: {e}")

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


# =============================================================================
# ChartCardWidget: Modular, standalone card for visual analytics charts
# =============================================================================

def _with_alpha(hex_color: str, alpha: int) -> str:
    """alpha: 0-255"""
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c.name(QColor.NameFormat.HexArgb)


class ChartCardWidget(QFrame):
    """
    Standalone visual analytics card with:
      - Title and icon
      - Subtitle/description
      - Metric summary badge pills
      - Embedded chart canvas slot (min height 380px-450px)
      - Descriptive legend / summary footer
    """
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        icon: str = "📊",
        min_canvas_height: int = 300,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.min_canvas_height = min_canvas_height
        self._init_ui(title, subtitle, icon)

    def _init_ui(self, title: str, subtitle: str, icon: str) -> None:
        self.setStyleSheet("""
            ChartCardWidget {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header bar
        header_bar = QHBoxLayout()
        header_bar.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel(f"{icon}  {title}")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B;")
        lbl_title.setWordWrap(True)
        title_col.addWidget(lbl_title)

        if subtitle:
            lbl_sub = QLabel(subtitle)
            lbl_sub.setStyleSheet("font-size: 11px; color: #64748B;")
            lbl_sub.setWordWrap(True)
            title_col.addWidget(lbl_sub)

        header_bar.addLayout(title_col, stretch=1)

        # Badge pills container
        self.badge_box = QHBoxLayout()
        self.badge_box.setSpacing(6)
        header_bar.addLayout(self.badge_box)

        layout.addLayout(header_bar)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("color: #E2E8F0; background-color: #E2E8F0; max-height: 1px;")
        layout.addWidget(divider)

        # Body / Canvas Slot
        self.body_layout = QVBoxLayout()
        self.body_layout.setContentsMargins(0, 4, 0, 4)
        layout.addLayout(self.body_layout)

    def set_badges(self, badges: list) -> None:
        """
        Updates the badge pills in the header.
        badges: list of (label, value, hex_color)
        """
        while self.badge_box.count():
            item = self.badge_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for label, val, color in badges:
            pill = QFrame()
            pill.setStyleSheet(f"""
                QFrame {{
                    background-color: {_with_alpha(color, 21)};
                    border: 1px solid {_with_alpha(color, 80)};
                    border-radius: 4px;
                    padding: 2px 8px;
                }}
            """)
            p_layout = QHBoxLayout(pill)
            p_layout.setContentsMargins(6, 2, 6, 2)
            p_layout.setSpacing(4)

            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("font-size: 10px; color: #475569; font-weight: bold;")
            v_lbl = QLabel(str(val))
            v_lbl.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: 800;")

            p_layout.addWidget(lbl)
            p_layout.addWidget(v_lbl)
            self.badge_box.addWidget(pill)

    def set_canvas(self, canvas: QWidget) -> None:
        """Sets the chart canvas inside the card with explicit minimum height and wheel event forwarding."""
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        canvas.setMinimumWidth(0)
        canvas.setMinimumHeight(self.min_canvas_height)
        # Fix #6a: Disable focus/wheel capture on canvas so QScrollArea receives wheel events
        canvas.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._wheel_filter = WheelPassThroughFilter(canvas)
        canvas.installEventFilter(self._wheel_filter)
        self.body_layout.addWidget(canvas)


# =============================================================================
# WheelPassThroughFilter & NonScrollableFigureCanvas
# =============================================================================

class WheelPassThroughFilter(QObject):
    """
    Event filter for FigureCanvas widgets inside scrollable cards.
    Intercepts wheel events that Matplotlib's Qt backend would normally capture/consume,
    and forwards them up to the ancestor QScrollArea viewport so the dashboard scrolls smoothly.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            p = obj.parent()
            while p is not None:
                if isinstance(p, QScrollArea):
                    viewport = p.viewport()
                    if viewport is not None:
                        viewport.event(event)
                    else:
                        p.wheelEvent(event)
                    return True
                p = p.parent()
            event.ignore()
            return False
        return False


try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
except ImportError:
    FigureCanvasQTAgg = QWidget


class NonScrollableFigureCanvas(FigureCanvasQTAgg):
    """FigureCanvas that ignores mouse wheel events, provides zero minimum width, and passes wheel to ancestor QScrollArea."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def sizeHint(self) -> QSize:
        return QSize(400, 260)

    def wheelEvent(self, event):
        p = self.parent()
        while p is not None:
            if isinstance(p, QScrollArea):
                viewport = p.viewport()
                if viewport is not None:
                    viewport.event(event)
                else:
                    p.wheelEvent(event)
                event.accept()
                return
            p = p.parent()
        event.ignore()

