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
    QSpinBox, QRadioButton, QButtonGroup, QTimeEdit, QPushButton,
    QFrame, QGridLayout, QAbstractSpinBox
)
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QFont

from MODULES.cake_memo.field_format import (
    FLAVOR_DISPLAY,
    VENUE_DISPLAY,
    CHARGE_PAID,
    CHARGE_PENDING,
    CHARGE_COMPLIMENTARY,
)


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

        # Internal state for delivery section (only valid when "Add" button is clicked)
        self._delivery_venue = None
        self._delivery_hour = None
        self._delivery_minute = None
        self._delivery_is_pm = None

        # Build the form layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # === DELIVERY SECTION ===
        delivery_frame = self._build_delivery_section()
        main_layout.addWidget(delivery_frame)

        # === ROOM NUMBER SECTION ===
        room_frame = self._build_room_section()
        main_layout.addWidget(room_frame)

        # === CAKE DESCRIPTION SECTION ===
        cake_frame = self._build_cake_section()
        main_layout.addWidget(cake_frame)

        main_layout.addStretch()

    def _build_delivery_section(self) -> QFrame:
        """Builds the Delivery Provided At section."""
        frame = self._create_section_frame("DELIVERY PROVIDED AT")
        layout = frame.layout()

        # Venue selection: 5 radio buttons
        venue_layout = QHBoxLayout()
        venue_layout.setSpacing(12)

        self.venue_group = QButtonGroup()
        self.venue_buttons = {}

        venue_options = [
            ("elia", "Elia"),
            ("ermis", "Ermis"),
            ("ammos", "Ammos"),
            ("il_gusto", "Il Gusto"),
            ("room", "Room"),
        ]

        for venue_key, venue_label in venue_options:
            btn = QRadioButton(venue_label)
            self.venue_buttons[venue_key] = btn
            self.venue_group.addButton(btn, len(self.venue_buttons) - 1)
            btn.toggled.connect(self._on_venue_selection_changed)
            venue_layout.addWidget(btn)

        layout.addLayout(venue_layout)

        # Confirmation subsection (hidden by default)
        self.delivery_confirmation_frame = QFrame()
        self.delivery_confirmation_frame.setStyleSheet("""
            QFrame {
                background-color: #FFF8F0;
                border: 1px solid #FFDDAA;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.delivery_confirmation_frame.setVisible(False)

        conf_layout = QVBoxLayout(self.delivery_confirmation_frame)
        conf_layout.setSpacing(8)
        conf_layout.setContentsMargins(8, 8, 8, 8)

        # Label showing selected venue
        self.delivery_label = QLabel("Provide at: ")
        font = self.delivery_label.font()
        font.setPointSize(10)
        font.setBold(True)
        self.delivery_label.setFont(font)
        conf_layout.addWidget(self.delivery_label)

        # Time picker and Add button
        time_add_layout = QHBoxLayout()

        self.delivery_time_edit = QTimeEdit()
        self.delivery_time_edit.setDisplayFormat("hh:mm AP")
        self.delivery_time_edit.setTime(QTime(12, 0))
        time_add_layout.addWidget(QLabel("Time:"))
        time_add_layout.addWidget(self.delivery_time_edit)

        self.delivery_add_button = QPushButton("Add")
        self.delivery_add_button.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.delivery_add_button.clicked.connect(self._on_delivery_add_clicked)
        time_add_layout.addWidget(self.delivery_add_button)

        self.delivery_status_label = QLabel("")
        self.delivery_status_label.setStyleSheet("color: #059669; font-weight: bold;")
        time_add_layout.addWidget(self.delivery_status_label)

        time_add_layout.addStretch()
        conf_layout.addLayout(time_add_layout)

        layout.addWidget(self.delivery_confirmation_frame)

        return frame

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
        frame = self._create_section_frame("CAKE DESCRIPTION")
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

        # Pax (read-only but scrollable)
        pax_qty_row.addWidget(QLabel("Guest count (Pax):"))
        self.pax_spinbox = QSpinBox()
        self.pax_spinbox.setRange(1, 50)
        self.pax_spinbox.setValue(1)
        self.pax_spinbox.setReadOnly(True)
        pax_qty_row.addWidget(self.pax_spinbox)

        pax_qty_row.addSpacing(20)

        # Qty (fully typable)
        pax_qty_row.addWidget(QLabel("Quantity (QTY):"))
        self.qty_spinbox = QSpinBox()
        self.qty_spinbox.setRange(1, 999)
        self.qty_spinbox.setValue(1)
        pax_qty_row.addWidget(self.qty_spinbox)

        pax_qty_row.addStretch()
        layout.addLayout(pax_qty_row)

        # === Charge state ===
        charge_row = QHBoxLayout()
        charge_row.addWidget(QLabel("Charge:"))

        # Complimentary-by field must exist BEFORE the charge radio buttons are wired up and
        # default-checked below: setChecked(True) fires `toggled` synchronously, which invokes
        # _on_charge_selection_changed, which references self.complimentary_by_frame. Creating
        # it first avoids a construction-order crash (accessing a not-yet-created attribute from
        # inside a signal handler triggered mid-construction).
        self.complimentary_by_frame = QFrame()
        self.complimentary_by_frame.setStyleSheet("""
            QFrame {
                background-color: #FFF8F0;
                border: 1px solid #FFDDAA;
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

        # Default to "Paid"
        self.charge_buttons[CHARGE_PAID].setChecked(True)

        charge_row.addStretch()
        layout.addLayout(charge_row)
        layout.addWidget(self.complimentary_by_frame)

        return frame

    def _create_section_frame(self, title: str) -> QFrame:
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

        return frame

    def _on_venue_selection_changed(self, checked: bool) -> None:
        """Shows/hides the delivery confirmation subsection."""
        if checked:
            self.delivery_confirmation_frame.setVisible(True)
            # Update the label to show the selected venue
            for venue_key, btn in self.venue_buttons.items():
                if btn.isChecked():
                    venue_label = btn.text()
                    self.delivery_label.setText(f"Provide at: {venue_label}")
                    break
            # Reset the status label
            self.delivery_status_label.setText("")
        else:
            # Check if ANY radio button is now checked
            any_checked = any(btn.isChecked() for btn in self.venue_buttons.values())
            if not any_checked:
                self.delivery_confirmation_frame.setVisible(False)

    def _on_delivery_add_clicked(self) -> None:
        """Locks in the delivery venue and time selection."""
        # Find which venue is selected
        selected_venue = None
        for venue_key, btn in self.venue_buttons.items():
            if btn.isChecked():
                selected_venue = venue_key
                break

        if selected_venue is None:
            return

        # Extract time from QTimeEdit
        qtime = self.delivery_time_edit.time()
        hour = qtime.hour()  # 0-23
        minute = qtime.minute()  # 0-59
        is_pm = hour >= 12

        # Store internally
        self._delivery_venue = selected_venue
        self._delivery_hour = hour
        self._delivery_minute = minute
        self._delivery_is_pm = is_pm

        # Show confirmation feedback
        self.delivery_status_label.setText("✓ Locked")

    def _on_charge_selection_changed(self, checked: bool) -> None:
        """Shows/hides the complimentary_by field based on charge selection."""
        if self.charge_buttons[CHARGE_COMPLIMENTARY].isChecked():
            self.complimentary_by_frame.setVisible(True)
        else:
            self.complimentary_by_frame.setVisible(False)

    def get_form_data(self) -> dict:
        """
        Returns the structured field dict matching MODULES/cake_memo's expected shape.

        Keys: flavor, written_text, pax, qty, venue, hour, minute, is_pm,
              charge_state, complimentary_by, room_number

        If the user never clicked "Add" in the Delivery section, defaults to:
        venue='room', hour=12, minute=0, is_pm=True (12:00 PM).
        """
        # Delivery: use stored values if "Add" was clicked, else default
        venue = self._delivery_venue if self._delivery_venue is not None else "room"
        hour = self._delivery_hour if self._delivery_hour is not None else 12
        minute = self._delivery_minute if self._delivery_minute is not None else 0
        is_pm = self._delivery_is_pm if self._delivery_is_pm is not None else True

        # Flavor: get the userData from the currently selected item
        flavor_key = self.flavor_combo.currentData()

        # Written text
        written_text = self.written_text_edit.text().strip()

        # Pax and Qty
        pax = self.pax_spinbox.value()
        qty = self.qty_spinbox.value()

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

        # Room number
        room_number = self.room_number_edit.text().strip()

        return {
            "flavor": flavor_key,
            "written_text": written_text,
            "pax": pax,
            "qty": qty,
            "venue": venue,
            "hour": hour,
            "minute": minute,
            "is_pm": is_pm,
            "charge_state": charge_state,
            "complimentary_by": complimentary_by,
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

        # Pax
        self.pax_spinbox.setValue(data.get("pax", 1))

        # Qty
        self.qty_spinbox.setValue(data.get("qty", 1))

        # Delivery: set the radio button AND store the internal state
        venue = data.get("venue", "room")
        if venue in self.venue_buttons:
            self.venue_buttons[venue].setChecked(True)
        self._delivery_venue = venue
        self._delivery_hour = data.get("hour", 12)
        self._delivery_minute = data.get("minute", 0)
        self._delivery_is_pm = data.get("is_pm", True)

        # Also update the QTimeEdit to reflect stored time
        hour_display = self._delivery_hour
        self.delivery_time_edit.setTime(QTime(hour_display, self._delivery_minute))

        # Charge state
        charge_state = data.get("charge_state", CHARGE_PAID)
        if charge_state in self.charge_buttons:
            self.charge_buttons[charge_state].setChecked(True)

        # Complimentary by
        complimentary_by = data.get("complimentary_by", "")
        self.complimentary_by_edit.setText(complimentary_by)

        # Room number
        self.room_number_edit.setText(data.get("room_number", ""))

        # Show delivery confirmation subsection and update label
        if venue in self.venue_buttons:
            venue_label = self.venue_buttons[venue].text()
            self.delivery_label.setText(f"Provide at: {venue_label}")
            self.delivery_confirmation_frame.setVisible(True)
            # Show status to indicate this was loaded from data
            self.delivery_status_label.setText("✓ Locked")

        # Show complimentary_by frame if complimentary is selected
        if charge_state == CHARGE_COMPLIMENTARY:
            self.complimentary_by_frame.setVisible(True)

    def reset(self) -> None:
        """Clears all fields back to defaults."""
        # Delivery: clear selection and internal state
        self.venue_group.setExclusive(False)
        for btn in self.venue_buttons.values():
            btn.setChecked(False)
        self.venue_group.setExclusive(True)
        self._delivery_venue = None
        self._delivery_hour = None
        self._delivery_minute = None
        self._delivery_is_pm = None
        self.delivery_confirmation_frame.setVisible(False)
        self.delivery_time_edit.setTime(QTime(12, 0))
        self.delivery_status_label.setText("")

        # Room number
        self.room_number_edit.setText("")

        # Cake description
        self.flavor_combo.setCurrentIndex(0)  # First flavor (strawberry)
        self.written_text_edit.setText("")
        self.pax_spinbox.setValue(1)
        self.qty_spinbox.setValue(1)

        # Charge: default to Paid
        self.charge_buttons[CHARGE_PAID].setChecked(True)
        self.complimentary_by_edit.setText("")
        self.complimentary_by_frame.setVisible(False)
