# -*- coding: utf-8 -*-
"""
Delivery section widget for Cake Memo form.

Handles:
  - Delivery venue selection (5 venues)
  - Delivery time picker (hour and minute spinboxes)
  - Confirmation subsection with status feedback
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup,
    QPushButton, QSpinBox
)
from PyQt6.QtGui import QFont


class DeliverySection(QFrame):
    """
    Encapsulates delivery venue and time selection for Cake Memo form.

    Public API:
      - get_delivery_data() -> dict: Returns {"venue": ..., "hour": ..., "minute": ...}
      - set_delivery_data(venue: str, hour: int, minute: int) -> None: Pre-fills fields
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

        # Internal state (only valid when "Add" button is clicked)
        self._delivery_venue = None
        self._delivery_hour = None
        self._delivery_minute = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title label
        title_label = QLabel("DELIVERY PROVIDED AT")
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
                background-color: #F7F7F7;
                border-left: 4px solid #f43f5e;
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

        time_add_layout.addWidget(QLabel("Time:"))

        self.delivery_hour_spin = QSpinBox()
        self.delivery_hour_spin.setRange(0, 23)
        self.delivery_hour_spin.setValue(12)
        time_add_layout.addWidget(self.delivery_hour_spin)

        time_add_layout.addWidget(QLabel(":"))

        self.delivery_minute_spin = QSpinBox()
        self.delivery_minute_spin.setRange(0, 59)
        self.delivery_minute_spin.setValue(0)
        time_add_layout.addWidget(self.delivery_minute_spin)

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

        # Extract time from spinboxes
        hour = self.delivery_hour_spin.value()
        minute = self.delivery_minute_spin.value()

        # Store internally
        self._delivery_venue = selected_venue
        self._delivery_hour = hour
        self._delivery_minute = minute

        # Show confirmation feedback
        self.delivery_status_label.setText("✓ Locked")

    def get_delivery_data(self) -> dict:
        """
        Returns the delivery data in structured dict format.

        Returns:
            {"venue": ..., "hour": ..., "minute": ...}

        If the user never clicked "Add", defaults to:
        venue='room', hour=12, minute=0.
        """
        venue = self._delivery_venue if self._delivery_venue is not None else "room"
        hour = self._delivery_hour if self._delivery_hour is not None else 12
        minute = self._delivery_minute if self._delivery_minute is not None else 0

        return {
            "venue": venue,
            "hour": hour,
            "minute": minute,
        }

    def set_delivery_data(self, venue: str, hour: int, minute: int) -> None:
        """
        Pre-fills delivery fields from structured data.

        Args:
            venue: one of the 5 venue keys (elia, ermis, ammos, il_gusto, room)
            hour: 0-23
            minute: 0-59
        """
        # Set the radio button
        if venue in self.venue_buttons:
            self.venue_buttons[venue].setChecked(True)

        # Store the internal state
        self._delivery_venue = venue
        self._delivery_hour = hour
        self._delivery_minute = minute

        # Update spinboxes
        self.delivery_hour_spin.setValue(hour)
        self.delivery_minute_spin.setValue(minute)

        # Show delivery confirmation subsection and update label
        if venue in self.venue_buttons:
            venue_label = self.venue_buttons[venue].text()
            self.delivery_label.setText(f"Provide at: {venue_label}")
            self.delivery_confirmation_frame.setVisible(True)
            # Show status to indicate this was loaded from data
            self.delivery_status_label.setText("✓ Locked")

    def reset(self) -> None:
        """Clears all fields back to defaults."""
        # Clear selection and internal state
        self.venue_group.setExclusive(False)
        for btn in self.venue_buttons.values():
            btn.setChecked(False)
        self.venue_group.setExclusive(True)
        self._delivery_venue = None
        self._delivery_hour = None
        self._delivery_minute = None
        self.delivery_confirmation_frame.setVisible(False)
        self.delivery_hour_spin.setValue(12)
        self.delivery_minute_spin.setValue(0)
        self.delivery_status_label.setText("")
