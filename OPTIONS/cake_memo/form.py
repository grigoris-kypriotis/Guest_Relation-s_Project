# -*- coding: utf-8 -*-
"""
Structured Create/Update form widget for Cake Memo entries.

CakeMemoForm provides a complete UI for collecting cake memo data with:
  - Delivery venue selection + time picker with confirmation
  - Room number input
  - Cake flavor, written text, pax, qty
  - Charge state (Paid/Pending/Complimentary with optional authorizer name)

The form's get_form_data() and set_form_data() methods produce/consume the exact
structured dict shape used by MODULES/cake_memo/document.py and parser.py.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from MODULES.cake_memo.field_format import (
    FLAVOR_DISPLAY,
    CHARGE_PAID,
)

from OPTIONS.cake_memo.delivery_section import DeliverySection
from OPTIONS.cake_memo.charge_section import ChargeSection


class CakeMemoForm(QWidget):
    """
    Structured form for creating/updating cake memo entries.

    Provides three public methods:
      - get_form_data() -> dict: Returns the collected form data in the structured shape
      - set_form_data(data: dict) -> None: Pre-fills form from a data dict
      - reset() -> None: Clears all fields to defaults
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #FAFAFA;")

        # Build the form layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # === DELIVERY SECTION ===
        self.delivery_section = DeliverySection()
        main_layout.addWidget(self.delivery_section)

        # === ROOM NUMBER SECTION ===
        room_frame = self._build_room_section()
        main_layout.addWidget(room_frame)

        # === CAKE DESCRIPTION SECTION ===
        cake_frame = self._build_cake_section()
        main_layout.addWidget(cake_frame, stretch=1)


    def _build_room_section(self) -> QFrame:
        """Builds the Room Number section."""
        frame = self._create_section_frame("ROOM NUMBER")
        layout = frame.layout()

        row = QHBoxLayout()
        row.addWidget(QLabel("Room:"))
        self.room_number_edit = QLineEdit()
        self.room_number_edit.setPlaceholderText("e.g., 0412")
        row.addWidget(self.room_number_edit)
        row.addStretch()

        layout.addLayout(row)
        return frame

    def _build_cake_section(self) -> QFrame:
        """Builds the Cake Description section (largest section)."""
        frame = self._create_section_frame("CAKE DESCRIPTION", title_point_size=13)
        layout = frame.layout()

        # === Flavor ===
        flavor_row = QHBoxLayout()
        flavor_row.addWidget(QLabel("Flavor:"))
        self.flavor_combo = QComboBox()
        self.flavor_combo.setEditable(False)

        # Add 6 flavor options with emoji
        flavors_with_emoji = [
            ("🍓 Strawberry", "strawberry"),
            ("🍫 Chocolate", "chocolate"),
            ("🍦 Vanilla", "vanilla"),
            ("🍓🍦 Strawberry+Vanilla", "strawberry_vanilla"),
            ("🍫🍦 Chocolate+Vanilla", "chocolate_vanilla"),
            ("🍫🍓 Chocolate+Strawberry", "chocolate_strawberry"),
        ]

        for display_text, flavor_key in flavors_with_emoji:
            self.flavor_combo.addItem(display_text, userData=flavor_key)

        flavor_row.addWidget(self.flavor_combo)
        flavor_row.addStretch()
        layout.addLayout(flavor_row)

        # === Written text ===
        written_row = QHBoxLayout()
        written_row.addWidget(QLabel("Anything to be written?:"))
        self.written_text_edit = QLineEdit()
        self.written_text_edit.setPlaceholderText("e.g., Happy Birthday")
        written_row.addWidget(self.written_text_edit)
        layout.addLayout(written_row)

        # === Pax and Qty (side by side) ===
        pax_qty_row = QHBoxLayout()
        pax_qty_row.setSpacing(20)

        # Pax (non-editable combo)
        pax_qty_row.addWidget(QLabel("Guest count (Pax):"))
        self.pax_combo = QComboBox()
        self.pax_combo.setEditable(False)
        for i in range(1, 51):
            self.pax_combo.addItem(str(i), userData=i)
        self.pax_combo.setCurrentIndex(0)  # default value 1
        pax_qty_row.addWidget(self.pax_combo)

        pax_qty_row.addSpacing(20)

        # Qty (fully typable)
        pax_qty_row.addWidget(QLabel("Quantity (QTY):"))
        self.qty_spinbox = QSpinBox()
        self.qty_spinbox.setRange(1, 999)
        self.qty_spinbox.setValue(1)
        pax_qty_row.addWidget(self.qty_spinbox)

        pax_qty_row.addStretch()
        layout.addLayout(pax_qty_row)

        # === Charge section ===
        self.charge_section = ChargeSection()
        layout.addWidget(self.charge_section)

        return frame

    def _create_section_frame(self, title: str, title_point_size: int = 11) -> QFrame:
        """Creates a styled section frame with a title."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title label
        title_label = QLabel(title)
        font = title_label.font()
        font.setPointSize(title_point_size)
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

        return frame


    def get_form_data(self) -> dict:
        """
        Returns the structured field dict matching MODULES/cake_memo's expected shape.

        Keys: flavor, written_text, pax, qty, venue, hour, minute,
              charge_state, complimentary_by, room_number

        If the user never clicked "Add" in the Delivery section, defaults to:
        venue='room', hour=12, minute=0.
        """
        # Delivery data
        delivery_data = self.delivery_section.get_delivery_data()

        # Flavor: get the userData from the currently selected item
        flavor_key = self.flavor_combo.currentData()

        # Written text
        written_text = self.written_text_edit.text().strip()

        # Pax
        pax = self.pax_combo.currentData()

        # Qty
        qty = self.qty_spinbox.value()

        # Charge data
        charge_data = self.charge_section.get_charge_data()

        # Room number
        room_number = self.room_number_edit.text().strip()

        return {
            "flavor": flavor_key,
            "written_text": written_text,
            "pax": pax,
            "qty": qty,
            "venue": delivery_data["venue"],
            "hour": delivery_data["hour"],
            "minute": delivery_data["minute"],
            "charge_state": charge_data["charge_state"],
            "complimentary_by": charge_data["complimentary_by"],
            "room_number": room_number,
        }

    def set_form_data(self, data: dict) -> None:
        """
        Pre-fills every control from a dict in the same shape as get_form_data().

        Also correctly re-derives which radio buttons should be checked and which
        conditional sub-fields (delivery confirmation, complimentary_by) should be visible.
        """
        # Flavor
        flavor_key = data.get("flavor", "strawberry")
        for idx in range(self.flavor_combo.count()):
            if self.flavor_combo.itemData(idx) == flavor_key:
                self.flavor_combo.setCurrentIndex(idx)
                break

        # Written text
        self.written_text_edit.setText(data.get("written_text", ""))

        # Pax: find and select by itemData
        pax_value = data.get("pax", 1)
        for idx in range(self.pax_combo.count()):
            if self.pax_combo.itemData(idx) == pax_value:
                self.pax_combo.setCurrentIndex(idx)
                break

        # Qty
        self.qty_spinbox.setValue(data.get("qty", 1))

        # Delivery
        venue = data.get("venue", "room")
        hour = data.get("hour", 12)
        minute = data.get("minute", 0)
        self.delivery_section.set_delivery_data(venue, hour, minute)

        # Charge state and complimentary_by
        charge_state = data.get("charge_state", CHARGE_PAID)
        complimentary_by = data.get("complimentary_by", "")
        self.charge_section.set_charge_data(charge_state, complimentary_by)

        # Room number
        self.room_number_edit.setText(data.get("room_number", ""))

    def reset(self) -> None:
        """Clears all fields back to defaults."""
        # Delivery
        self.delivery_section.reset()

        # Room number
        self.room_number_edit.setText("")

        # Cake description
        self.flavor_combo.setCurrentIndex(0)  # First flavor (strawberry)
        self.written_text_edit.setText("")
        self.pax_combo.setCurrentIndex(0)  # First pax (1)
        self.qty_spinbox.setValue(1)

        # Charge
        self.charge_section.reset()
