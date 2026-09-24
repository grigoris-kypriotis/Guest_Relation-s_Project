"""
Card Properties & Locations: Property configuration and data paths.
===================================================================
Provides builders for Properties & Room Capacity (Card 2), Data Locations (Card 3),
and LocationsMixin for directory browsing.
"""

import os

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QLineEdit, QSpinBox,
    QFileDialog
)

from MODULES.data_manager import (
    DATABASE_DIR, TEMPLATES_DIR, BOOKING_CALLS_DIR, HOTEL_DATASET_PATH
)
from OPTIONS.configuration.card_shared import create_card, btn_browse_style


def build_properties_card(widget) -> QFrame:
    """
    Builds the Properties & Room Capacity card (Card 2).

    Args:
        widget: The ConfigurationWidget instance. Assigns:
            - widget.spin_beach_rooms (QSpinBox)

    Returns:
        QFrame containing the properties card layout
    """
    card_prop = create_card("\U0001f3e8 PROPERTIES & ROOM CAPACITY")
    prop_layout = card_prop.layout()

    prop_desc = QLabel("Define total physical room capacity for each resort section to calibrate occupancy metrics across Dashboard and Blocks.")
    prop_desc.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
    prop_desc.setWordWrap(True)
    prop_layout.addWidget(prop_desc)

    row_beach = QHBoxLayout()
    lbl_beach = QLabel("Total Rooms — SANDY BEACH:")
    lbl_beach.setFixedWidth(230)
    lbl_beach.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.spin_beach_rooms = QSpinBox()
    widget.spin_beach_rooms.setRange(1, 5000)
    widget.spin_beach_rooms.setValue(660)
    widget.spin_beach_rooms.setFixedWidth(120)
    widget.spin_beach_rooms.setStyleSheet("padding: 4px; border: 1px solid #CBD5E1; border-radius: 4px; background: white;")
    row_beach.addWidget(lbl_beach)
    row_beach.addWidget(widget.spin_beach_rooms)
    row_beach.addStretch()
    prop_layout.addLayout(row_beach)

    return card_prop


def build_data_locations_card(widget) -> QFrame:
    """
    Builds the Data Locations & Directory Routing card (Card 3).

    Args:
        widget: The ConfigurationWidget instance. Assigns:
            - widget.txt_database_dir (QLineEdit)
            - widget.txt_templates_dir (QLineEdit)
            - widget.txt_booking_calls_path (QLineEdit)
            - widget.txt_json (QLineEdit, read-only)

    Returns:
        QFrame containing the data locations card layout
    """
    card_routing = create_card("\U0001f4c1 DATA LOCATIONS & DIRECTORY ROUTING")
    r_layout = card_routing.layout()

    # Database Directory
    row_db = QHBoxLayout()
    lbl_db = QLabel("Database Root Directory:")
    lbl_db.setFixedWidth(230)
    lbl_db.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_database_dir = QLineEdit(DATABASE_DIR)
    widget.txt_database_dir.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
    btn_browse_db = QPushButton("Browse…")
    btn_browse_db.setStyleSheet(btn_browse_style)
    btn_browse_db.clicked.connect(widget._browse_database_dir)
    row_db.addWidget(lbl_db)
    row_db.addWidget(widget.txt_database_dir)
    row_db.addWidget(btn_browse_db)
    r_layout.addLayout(row_db)

    # Templates Directory
    row_tpl = QHBoxLayout()
    lbl_tpl = QLabel("Document Templates Directory:")
    lbl_tpl.setFixedWidth(230)
    lbl_tpl.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_templates_dir = QLineEdit(TEMPLATES_DIR)
    widget.txt_templates_dir.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
    btn_browse_tpl = QPushButton("Browse…")
    btn_browse_tpl.setStyleSheet(btn_browse_style)
    btn_browse_tpl.clicked.connect(widget._browse_templates_dir)
    row_tpl.addWidget(lbl_tpl)
    row_tpl.addWidget(widget.txt_templates_dir)
    row_tpl.addWidget(btn_browse_tpl)
    r_layout.addLayout(row_tpl)

    # Booking Calls Workbook
    row_bk = QHBoxLayout()
    lbl_bk = QLabel("Booking Calls Workbook (.xlsx):")
    lbl_bk.setFixedWidth(230)
    lbl_bk.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_booking_calls_path = QLineEdit(os.path.join(BOOKING_CALLS_DIR, "BOOKING CALLS.xlsx"))
    widget.txt_booking_calls_path.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
    btn_browse_bk = QPushButton("Browse…")
    btn_browse_bk.setStyleSheet(btn_browse_style)
    btn_browse_bk.clicked.connect(widget._browse_booking_calls_file)
    row_bk.addWidget(lbl_bk)
    row_bk.addWidget(widget.txt_booking_calls_path)
    row_bk.addWidget(btn_browse_bk)
    r_layout.addLayout(row_bk)

    # Primary Hotel Data Set
    row_json = QHBoxLayout()
    lbl_json = QLabel("Primary Hotel Data Set (JSON):")
    lbl_json.setFixedWidth(230)
    lbl_json.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.txt_json = QLineEdit(str(HOTEL_DATASET_PATH))
    widget.txt_json.setReadOnly(True)
    widget.txt_json.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
    row_json.addWidget(lbl_json)
    row_json.addWidget(widget.txt_json)
    r_layout.addLayout(row_json)

    return card_routing


class LocationsMixin:
    """
    Mixin providing directory browsing methods.

    Expected to be mixed into ConfigurationWidget. Requires:
        - self.txt_database_dir, self.txt_templates_dir, self.txt_booking_calls_path
          (from build_data_locations_card)
    """

    def _browse_database_dir(self) -> None:
        """Opens directory chooser for database directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Database Directory", self.txt_database_dir.text())
        if folder:
            self.txt_database_dir.setText(folder)

    def _browse_templates_dir(self) -> None:
        """Opens directory chooser for templates directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Document Templates Directory", self.txt_templates_dir.text())
        if folder:
            self.txt_templates_dir.setText(folder)

    def _browse_booking_calls_file(self) -> None:
        """Opens file chooser for booking calls workbook."""
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Booking Calls Excel Workbook",
            os.path.dirname(self.txt_booking_calls_path.text()),
            "Excel Files (*.xlsx *.xls);;All Files (*.*)"
        )
        if fpath:
            self.txt_booking_calls_path.setText(fpath)
