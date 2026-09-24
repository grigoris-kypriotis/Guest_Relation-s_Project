"""
ChartCardWidget: Modular, standalone card for visual analytics charts.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from OPTIONS._shared.mpl_helpers import WheelPassThroughFilter


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
