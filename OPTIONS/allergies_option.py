"""
Allergies Option: Allergies processor placeholder.
====================================================
Minimal module ready for future expansion.
Currently displays a centered placeholder label.
"""

from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class AllergiesWidget(QWidget):
    """Allergies Processor — placeholder view for future implementation."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("ALLERGIES PROCESSOR")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #800020;")
        layout.addWidget(lbl)

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        pass  # Placeholder — no action needed
