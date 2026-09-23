"""
Navigation Components: Hamburger button and sidebar panel.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal


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
