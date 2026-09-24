"""
Card Booking & Exclusivi: Booking Calls and Exclusivi API configuration.
=========================================================================
Provides builders for Booking Calls (Card 4) and Exclusivi API (Card 5),
and ExclusiviMixin for API integration methods.
"""

import threading
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox,
    QMessageBox
)
from PyQt6.QtCore import QTimer

from MODULES.data_manager import BOOKING_CALLS_DIR
import os
from OPTIONS.configuration.card_shared import create_card, btn_browse_style


def build_booking_calls_card(widget) -> QFrame:
    """
    Builds the Booking Calls Workbook Configuration card (Card 4).

    Args:
        widget: The ConfigurationWidget instance. Assigns:
            - widget.txt_sheet_name (QLineEdit)
            - widget.chk_mirror_sheet (QCheckBox)

    Returns:
        QFrame containing the booking calls card layout
    """
    card_booking = create_card("\U0001f4de BOOKING CALLS WORKBOOK CONFIGURATION")
    b_layout = card_booking.layout()

    row_sheet = QHBoxLayout()
    lbl_sheet = QLabel("Target Follow-Up Sheet:")
    lbl_sheet.setFixedWidth(230)
    lbl_sheet.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_sheet_name = QLineEdit("FOLLOW UP")
    widget.txt_sheet_name.setFixedWidth(160)
    widget.txt_sheet_name.setStyleSheet("padding: 4px 8px; border: 1px solid #CBD5E1; border-radius: 4px; background: white;")
    row_sheet.addWidget(lbl_sheet)
    row_sheet.addWidget(widget.txt_sheet_name)
    row_sheet.addStretch()
    b_layout.addLayout(row_sheet)

    widget.chk_mirror_sheet = QCheckBox("Also mirror logs to 'FOLLOW UP 1' (Strict adherence to standard follow-up sheets)")
    widget.chk_mirror_sheet.setChecked(True)
    widget.chk_mirror_sheet.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    b_layout.addWidget(widget.chk_mirror_sheet)

    return card_booking


def build_exclusivi_card(widget) -> QFrame:
    """
    Builds the Exclusivi API Integration card (Card 5).

    Args:
        widget: The ConfigurationWidget instance. Assigns:
            - widget.chk_exclusivi_enabled (QCheckBox)
            - widget.txt_exclusivi_url (QLineEdit)
            - widget.txt_exclusivi_key (QLineEdit)
            - widget.btn_toggle_key (QPushButton)
            - widget.btn_test_connection (QPushButton)
            - widget.lbl_connection_status (QLabel)

    Returns:
        QFrame containing the exclusivi card layout
    """
    card_exclusivi = create_card("\U0001f50c EXCLUSIVI API INTEGRATION", accent_color="#7C3AED")
    ex_layout = card_exclusivi.layout()

    ex_desc = QLabel("Connect to Exclusivi applications for guest service management, amenity requests, and reservation synchronization.")
    ex_desc.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
    ex_desc.setWordWrap(True)
    ex_layout.addWidget(ex_desc)

    # Enable toggle
    widget.chk_exclusivi_enabled = QCheckBox("Enable Exclusivi API Integration")
    widget.chk_exclusivi_enabled.setStyleSheet("font-weight: bold; color: #1E293B; font-size: 12px; border: none;")
    widget.chk_exclusivi_enabled.toggled.connect(widget._toggle_exclusivi_fields)
    ex_layout.addWidget(widget.chk_exclusivi_enabled)

    # API Base URL
    row_api_url = QHBoxLayout()
    lbl_api_url = QLabel("API Base URL:")
    lbl_api_url.setFixedWidth(230)
    lbl_api_url.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_exclusivi_url = QLineEdit()
    widget.txt_exclusivi_url.setPlaceholderText("https://api.exclusivi.com/v1")
    widget.txt_exclusivi_url.setStyleSheet("padding: 6px 10px; border: 1px solid #C4B5FD; border-radius: 4px; background: white;")
    row_api_url.addWidget(lbl_api_url)
    row_api_url.addWidget(widget.txt_exclusivi_url)
    ex_layout.addLayout(row_api_url)

    # API Key
    row_api_key = QHBoxLayout()
    lbl_api_key = QLabel("API Key / Bearer Token:")
    lbl_api_key.setFixedWidth(230)
    lbl_api_key.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_exclusivi_key = QLineEdit()
    widget.txt_exclusivi_key.setPlaceholderText("Enter your Exclusivi API key...")
    widget.txt_exclusivi_key.setEchoMode(QLineEdit.EchoMode.Password)
    widget.txt_exclusivi_key.setStyleSheet("padding: 6px 10px; border: 1px solid #C4B5FD; border-radius: 4px; background: white;")

    widget.btn_toggle_key = QPushButton("\U0001f441")
    widget.btn_toggle_key.setFixedWidth(36)
    widget.btn_toggle_key.setStyleSheet("""
        QPushButton {
            background: #F5F3FF;
            border: 1px solid #C4B5FD;
            border-radius: 4px;
            padding: 4px;
            font-size: 14px;
        }
        QPushButton:hover { background: #EDE9FE; }
    """)
    widget.btn_toggle_key.clicked.connect(widget._toggle_api_key_visibility)

    row_api_key.addWidget(lbl_api_key)
    row_api_key.addWidget(widget.txt_exclusivi_key)
    row_api_key.addWidget(widget.btn_toggle_key)
    ex_layout.addLayout(row_api_key)

    # Test Connection row
    row_test = QHBoxLayout()
    widget.btn_test_connection = QPushButton("\U0001f517 Test Connection")
    widget.btn_test_connection.setStyleSheet("""
        QPushButton {
            background-color: #7C3AED;
            color: white;
            font-weight: bold;
            padding: 7px 18px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover { background-color: #6D28D9; }
        QPushButton:disabled { background-color: #CBD5E1; color: #64748B; }
    """)
    widget.btn_test_connection.clicked.connect(widget._test_exclusivi_connection)

    widget.lbl_connection_status = QLabel("● Not configured")
    widget.lbl_connection_status.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")

    row_test.addWidget(widget.btn_test_connection)
    row_test.addWidget(widget.lbl_connection_status)
    row_test.addStretch()
    ex_layout.addLayout(row_test)

    return card_exclusivi


class ExclusiviMixin:
    """
    Mixin providing Exclusivi API integration methods.

    Expected to be mixed into ConfigurationWidget. Requires:
        - self.txt_exclusivi_url, self.txt_exclusivi_key, self.btn_test_connection, etc.
          (from build_exclusivi_card)
        - self.current_settings (dict)
    """

    def _toggle_exclusivi_fields(self, enabled: bool) -> None:
        """Enable/disable Exclusivi API fields based on the toggle."""
        self.txt_exclusivi_url.setEnabled(enabled)
        self.txt_exclusivi_key.setEnabled(enabled)
        self.btn_test_connection.setEnabled(enabled)
        self.btn_toggle_key.setEnabled(enabled)
        if not enabled:
            self.lbl_connection_status.setText("● Disabled")
            self.lbl_connection_status.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")

    def _toggle_api_key_visibility(self) -> None:
        """Toggle password visibility for the API key field."""
        if self.txt_exclusivi_key.echoMode() == QLineEdit.EchoMode.Password:
            self.txt_exclusivi_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_key.setText("\U0001f512")
        else:
            self.txt_exclusivi_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_key.setText("\U0001f441")

    def _test_exclusivi_connection(self) -> None:
        """Tests the Exclusivi API connection in a background thread."""
        url = self.txt_exclusivi_url.text().strip()
        key = self.txt_exclusivi_key.text().strip()

        if not url:
            self.lbl_connection_status.setText("⚠️ URL is required")
            self.lbl_connection_status.setStyleSheet("color: #D97706; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")
            return

        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL")
        except Exception:
            self.lbl_connection_status.setText("❌ Invalid URL format")
            self.lbl_connection_status.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")
            return

        self.btn_test_connection.setEnabled(False)
        self.lbl_connection_status.setText("⏳ Testing connection...")
        self.lbl_connection_status.setStyleSheet("color: #D97706; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")

        def _do_test():
            status = "failed"
            try:
                import urllib.request
                req = urllib.request.Request(
                    url.rstrip("/") + "/health",
                    headers={"Authorization": f"Bearer {key}"} if key else {},
                    method="GET"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        status = "connected"
                    else:
                        status = f"error_{resp.status}"
            except Exception as e:
                status = f"failed: {str(e)[:60]}"

            QTimer.singleShot(0, lambda: self._on_test_complete(status))

        t = threading.Thread(target=_do_test, daemon=True)
        t.start()

    def _on_test_complete(self, status: str) -> None:
        """Handle test connection result on the main thread."""
        self.btn_test_connection.setEnabled(True)
        ts = datetime.now().strftime("%H:%M:%S")

        if status == "connected":
            self.lbl_connection_status.setText(f"✅ Connected ({ts})")
            self.lbl_connection_status.setStyleSheet("color: #1D4ED8; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")
        else:
            display = status[:80] if len(status) > 80 else status
            self.lbl_connection_status.setText(f"❌ {display} ({ts})")
            self.lbl_connection_status.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")

        # Store the test result
        self.current_settings.setdefault("exclusivi", {})["last_test_status"] = status.split(":")[0] if ":" in status else status
        self.current_settings["exclusivi"]["last_test_timestamp"] = ts
