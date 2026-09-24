# -*- coding: utf-8 -*-
"""
Charge section widget for Cake Memo form.

Handles:
  - Charge state selection (Paid/Pending/Complimentary)
  - Conditional "Complimentary by" field for authorizer name
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QRadioButton, QButtonGroup
)
from PyQt6.QtGui import QFont

from MODULES.cake_memo.field_format import (
    CHARGE_PAID,
    CHARGE_PENDING,
    CHARGE_COMPLIMENTARY,
)


class ChargeSection(QFrame):
    """
    Encapsulates charge state and complimentary_by field for Cake Memo form.

    Public API:
      - get_charge_data() -> dict: Returns {"charge_state": ..., "complimentary_by": ...}
      - set_charge_data(charge_state: str, complimentary_by: str) -> None: Pre-fills fields
      - reset() -> None: Clears to defaults
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title label
        title_label = QLabel("CHARGE STATE")
        font = title_label.font()
        font.setPointSize(11)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setStyleSheet("color: #1F2937; padding-bottom: 4px;")
        layout.addWidget(title_label)

        # Divider
        divider = QFrame()
        divider.setStyleSheet("background-color: #E5E7EB;")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        layout.addSpacing(4)

        # CRITICAL: Build complimentary_by_frame BEFORE wiring charge buttons.
        # setChecked(True) fires `toggled` synchronously, which invokes _on_charge_selection_changed,
        # which references self.complimentary_by_frame. Creating it first avoids a construction-order
        # crash (native interpreter death, not catchable as Python exception).

        self.complimentary_by_frame = QFrame()
        self.complimentary_by_frame.setStyleSheet("""
            QFrame {
                background-color: #F7F7F7;
                border-left: 4px solid #f43f5e;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.complimentary_by_frame.setVisible(False)

        comp_layout = QHBoxLayout(self.complimentary_by_frame)
        comp_layout.addWidget(QLabel("Complimentary by:"))
        self.complimentary_by_edit = QLineEdit()
        self.complimentary_by_edit.setPlaceholderText("e.g., Manager Name")
        comp_layout.addWidget(self.complimentary_by_edit)
        comp_layout.addStretch()

        # NOW wire up the charge radio buttons (which may trigger _on_charge_selection_changed)
        charge_row = QHBoxLayout()
        charge_row.addWidget(QLabel("Charge:"))

        self.charge_group = QButtonGroup()
        self.charge_buttons = {}

        charge_options = [
            (CHARGE_PAID, "Paid"),
            (CHARGE_PENDING, "Pending"),
            (CHARGE_COMPLIMENTARY, "Complimentary"),
        ]

        for idx, (charge_key, charge_label) in enumerate(charge_options):
            btn = QRadioButton(charge_label)
            self.charge_buttons[charge_key] = btn
            self.charge_group.addButton(btn, idx)
            btn.toggled.connect(self._on_charge_selection_changed)
            charge_row.addWidget(btn)

        # Default to "Paid" (this triggers _on_charge_selection_changed, which now safely accesses self.complimentary_by_frame)
        self.charge_buttons[CHARGE_PAID].setChecked(True)

        charge_row.addStretch()
        layout.addLayout(charge_row)
        layout.addWidget(self.complimentary_by_frame)

    def _on_charge_selection_changed(self, checked: bool) -> None:
        """Shows/hides the complimentary_by field based on charge selection."""
        if self.charge_buttons[CHARGE_COMPLIMENTARY].isChecked():
            self.complimentary_by_frame.setVisible(True)
        else:
            self.complimentary_by_frame.setVisible(False)

    def get_charge_data(self) -> dict:
        """
        Returns the charge data in structured dict format.

        Returns:
            {"charge_state": ..., "complimentary_by": ...}
        """
        # Charge state
        charge_state = CHARGE_PAID
        for key, btn in self.charge_buttons.items():
            if btn.isChecked():
                charge_state = key
                break

        # Complimentary by
        complimentary_by = ""
        if charge_state == CHARGE_COMPLIMENTARY:
            complimentary_by = self.complimentary_by_edit.text().strip()

        return {
            "charge_state": charge_state,
            "complimentary_by": complimentary_by,
        }

    def set_charge_data(self, charge_state: str, complimentary_by: str) -> None:
        """
        Pre-fills charge fields from structured data.

        Args:
            charge_state: one of CHARGE_PAID, CHARGE_PENDING, CHARGE_COMPLIMENTARY
            complimentary_by: name of complimentary authorizer (if applicable)
        """
        # Charge state
        if charge_state in self.charge_buttons:
            self.charge_buttons[charge_state].setChecked(True)

        # Complimentary by
        self.complimentary_by_edit.setText(complimentary_by)

        # Show complimentary_by frame if complimentary is selected
        if charge_state == CHARGE_COMPLIMENTARY:
            self.complimentary_by_frame.setVisible(True)

    def reset(self) -> None:
        """Clears all fields back to defaults."""
        # Charge: default to Paid
        self.charge_buttons[CHARGE_PAID].setChecked(True)
        self.complimentary_by_edit.setText("")
        self.complimentary_by_frame.setVisible(False)
