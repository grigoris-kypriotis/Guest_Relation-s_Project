"""
Booking Calls Option: Thin wrapper around BookingCallsWidget from booking_calls.py.
====================================================================================
Provides BookingCallsOptionWidget that wraps the existing CRM interface
and exposes the standardized activate() interface.
"""

from typing import Optional, Callable

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

from MODULES.booking_calls import BookingCallsWidget


class BookingCallsOptionWidget(QWidget):
    """
    Booking Calls CRM view: wraps the existing BookingCallsWidget
    from booking_calls.py and relays the feedback_submitted signal.
    """
    feedback_submitted = pyqtSignal(str, str)

    def __init__(self, log_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.log_callback = log_callback
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.booking_widget = BookingCallsWidget()
        self.booking_widget.feedback_submitted.connect(self._relay_feedback)
        layout.addWidget(self.booking_widget)

    def _relay_feedback(self, room: str, comment: str) -> None:
        """Relay the feedback signal to the parent application."""
        self.feedback_submitted.emit(room, comment)

    def refresh_calls(self) -> None:
        """Refresh the booking calls data."""
        try:
            self.booking_widget.refresh_calls()
        except Exception as e:
            print(f"[BookingCalls] Refresh error: {e}")

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        try:
            self.booking_widget.refresh_calls()
        except Exception as e:
            print(f"[BookingCalls] Activation error: {e}")
