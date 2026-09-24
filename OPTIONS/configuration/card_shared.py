"""
Card Shared: Common utilities for configuration card building.
==============================================================
Provides the shared create_card() function and button styling constants.
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel

# Shared button browse style used across all card builders
btn_browse_style = """
    QPushButton {
        background-color: #F1F5F9;
        color: #0F172A;
        font-weight: bold;
        padding: 5px 12px;
        border: 1px solid #CBD5E1;
        border-radius: 4px;
    }
    QPushButton:hover { background-color: #E2E8F0; }
"""


def create_card(title: str, accent_color: str = "#800020") -> QFrame:
    """
    Creates a styled configuration card frame.

    Args:
        title: Card title string
        accent_color: Hex color for the left border and title

    Returns:
        QFrame with title label and empty vertical layout ready for content
    """
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left: 4px solid {accent_color};
            border-radius: 6px;
            padding: 12px;
        }}
    """)
    c_layout = QVBoxLayout(frame)
    c_layout.setSpacing(8)
    t_lbl = QLabel(title)
    t_lbl.setStyleSheet(f"color: {accent_color}; font-size: 13px; font-weight: 800; border: none;")
    c_layout.addWidget(t_lbl)
    return frame
