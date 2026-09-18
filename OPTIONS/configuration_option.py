"""
Configuration Option: System configuration, directory routing, and database maintenance.
========================================================================================
Provides the ConfigurationWidget with enhanced sections:
  1. IN-HOUSE LIST INGESTION (Promoted — quick-access manifest loading)
  2. PROPERTIES & ROOM COUNTS (Calibrates resort occupancy calculations)
  3. DATA SOURCE LOCATIONS & BROWSING (Centralized database & template paths)
  4. BOOKING CALLS CONFIGURATION (Sheet target & mirror options)
  5. EXCLUSIVI API INTEGRATION (External application API connection)
  6. DOCUMENT STORAGE LOCATIONS (Offer Lists & Cake Memos output directories)
  7. GATEKEEPER & DATE OVERRIDE (Operational date control)
  8. WORKSPACE PREFERENCES (Map defaults & operational modes)
  9. ACTIONS & SETTINGS PERSISTENCE (Saves to DATABASE/app_settings.json)
 10. DATABASE PURGE & RESET (System reset and block refresh)
"""

import os
import json
import subprocess
import threading
from datetime import date, datetime
from typing import Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QScrollArea, QFrame,
    QFileDialog, QMessageBox, QSpinBox, QDateEdit, QSizePolicy,
    QDialog, QDialogButtonBox
)
from PyQt6.QtCore import pyqtSignal, QDate, Qt, QTimer

from MODULES.data_manager import (
    InHouseDataManager, MASTER_STATE_PATH, STATE_META_PATH,
    CHECKOUTS_JSON, ROOM_MOVES_JSON, ARRIVALS_BEACH_PATH,
    DATABASE_DIR, TEMPLATES_DIR, OUTPUT_DIR, BASE_DIR, PLOT_DIR,
    BOOKING_CALLS_DIR, HOTEL_DATASET_PATH, BOOKING_CALLS_TODAY_JSON,
    validate_inhouse_file_date, extract_inhouse_report_date
)

APP_SETTINGS_PATH = os.path.join(DATABASE_DIR, "app_settings.json")

DEFAULT_APP_SETTINGS: Dict[str, Any] = {
    "properties": {
        "sandy_beach_rooms": 660,
        "sandy_villas_rooms": 40,
    },
    "paths": {
        "database_dir": DATABASE_DIR,
        "templates_dir": TEMPLATES_DIR,
        "booking_calls_workbook": os.path.join(BOOKING_CALLS_DIR, "BOOKING CALLS.xlsx"),
    },
    "booking_calls": {
        "sheet_name": "FOLLOW UP",
        "mirror_follow_up_1": True,
    },
    "exclusivi": {
        "enabled": False,
        "api_base_url": "",
        "api_key": "",
        "last_test_status": None,
        "last_test_timestamp": None,
    },
    "storage": {
        "offer_lists_dir": os.path.join(OUTPUT_DIR, "OFFERS"),
        "cake_memos_dir": os.path.join(OUTPUT_DIR, "CAKE_MEMOS"),
    },
    "preferences": {
        "default_fit_view": True,
        "active_property": "Sandy Beach (Exclusive Active Property)",
        "operational_mode": "Production (Standard Gatekeeper & Centralized Database)",
    },
    "last_saved": None,
}


def load_app_settings() -> Dict[str, Any]:
    """Safely loads app settings from DATABASE/app_settings.json with defaults fallback."""
    if os.path.exists(APP_SETTINGS_PATH):
        try:
            with open(APP_SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings = json.loads(json.dumps(DEFAULT_APP_SETTINGS))
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(settings.get(k), dict):
                    settings[k].update(v)
                else:
                    settings[k] = v
            return settings
        except Exception as e:
            print(f"[Configuration] Error loading settings: {e}")
    return json.loads(json.dumps(DEFAULT_APP_SETTINGS))


def save_app_settings(settings: Dict[str, Any]) -> bool:
    """Persists app settings to DATABASE/app_settings.json."""
    try:
        os.makedirs(os.path.dirname(APP_SETTINGS_PATH), exist_ok=True)
        settings["last_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(APP_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Configuration] Error saving settings: {e}")
        return False


class ConfigurationWidget(QWidget):
    """
    Configuration Page: system configuration inputs, directory path settings,
    workspace calibration, API integration, storage routing, and database maintenance controls.
    """
    data_updated = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self.current_settings = load_app_settings()
        self._init_ui()
        self.populate_settings_ui()
        self.refresh_timestamp_display()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        lbl_title = QLabel("\u2699\ufe0f SYSTEM CONFIGURATION & WORKSPACE PREFERENCES")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Configure resort capacity, data routing, API integrations, document storage, and operational settings.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #555555;")
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # Scroll area for clean card display
        cfg_scroll = QScrollArea()
        cfg_scroll.setWidgetResizable(True)
        cfg_scroll.setFrameShape(QFrame.Shape.NoFrame)
        cfg_content = QWidget()
        scroll_layout = QVBoxLayout(cfg_content)
        scroll_layout.setSpacing(14)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

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

        # -----------------------------------------------------------------
        # Card 1: IN-HOUSE LIST INGESTION (Promoted — Top Card)
        # -----------------------------------------------------------------
        card_inhouse = self._create_card("\U0001f4c2 IN-HOUSE LIST INGESTION", accent_color="#1E3A8A")
        ih_layout = card_inhouse.layout()

        ih_desc = QLabel("Load today's In-House List from your PMS export. This is the primary data source for all Stats, Occupancy, and Guest Manifest views.")
        ih_desc.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
        ih_desc.setWordWrap(True)
        ih_layout.addWidget(ih_desc)

        # Status display
        self.txt_timestamp = QLineEdit("No In-House List Loaded")
        self.txt_timestamp.setReadOnly(True)
        self.txt_timestamp.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 8px 12px; border: 1px solid #FECACA; border-radius: 6px;")
        ih_layout.addWidget(self.txt_timestamp)

        # Load button row
        row_load = QHBoxLayout()
        self.btn_load_inhouse = QPushButton("\U0001f4c2 Load In-House List (.xlsx / .xls / .csv)")
        self.btn_load_inhouse.setStyleSheet("""
            QPushButton {
                background-color: #1E3A8A;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 22px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        self.btn_load_inhouse.clicked.connect(self.load_inhouse_list)
        row_load.addWidget(self.btn_load_inhouse)
        row_load.addStretch()
        ih_layout.addLayout(row_load)

        # Gatekeeper Override (compact, inline)
        row_override = QHBoxLayout()
        lbl_override = QLabel("Manual Date Override:")
        lbl_override.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px; border: none;")
        self.date_override = QDateEdit()
        self.date_override.setCalendarPopup(True)
        self.date_override.setDate(QDate.currentDate())
        self.date_override.setDisplayFormat("dd/MM/yyyy")
        self.date_override.setFixedWidth(130)
        self.date_override.setStyleSheet("padding: 4px; border: 1px solid #CBD5E1; border-radius: 4px; background: white;")

        btn_apply_override = QPushButton("Apply")
        btn_apply_override.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                color: white;
                font-weight: bold;
                padding: 5px 12px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        btn_apply_override.clicked.connect(self._apply_date_override)

        row_override.addWidget(lbl_override)
        row_override.addWidget(self.date_override)
        row_override.addWidget(btn_apply_override)
        row_override.addStretch()
        ih_layout.addLayout(row_override)

        scroll_layout.addWidget(card_inhouse)

        # -----------------------------------------------------------------
        # Card 2: PROPERTIES & ROOM COUNTS
        # -----------------------------------------------------------------
        card_prop = self._create_card("\U0001f3e8 PROPERTIES & ROOM CAPACITY")
        prop_layout = card_prop.layout()

        prop_desc = QLabel("Define total physical room capacity for each resort section to calibrate occupancy metrics across Dashboard and Blocks.")
        prop_desc.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
        prop_desc.setWordWrap(True)
        prop_layout.addWidget(prop_desc)

        row_beach = QHBoxLayout()
        lbl_beach = QLabel("Total Rooms \u2014 SANDY BEACH:")
        lbl_beach.setFixedWidth(230)
        lbl_beach.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.spin_beach_rooms = QSpinBox()
        self.spin_beach_rooms.setRange(1, 5000)
        self.spin_beach_rooms.setValue(660)
        self.spin_beach_rooms.setFixedWidth(120)
        self.spin_beach_rooms.setStyleSheet("padding: 4px; border: 1px solid #CBD5E1; border-radius: 4px; background: white;")
        row_beach.addWidget(lbl_beach)
        row_beach.addWidget(self.spin_beach_rooms)
        row_beach.addStretch()
        prop_layout.addLayout(row_beach)

        row_villas = QHBoxLayout()
        lbl_villas = QLabel("Total Rooms \u2014 SANDY VILLAS:")
        lbl_villas.setFixedWidth(230)
        lbl_villas.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.spin_villas_rooms = QSpinBox()
        self.spin_villas_rooms.setRange(1, 1000)
        self.spin_villas_rooms.setValue(40)
        self.spin_villas_rooms.setFixedWidth(120)
        self.spin_villas_rooms.setStyleSheet("padding: 4px; border: 1px solid #CBD5E1; border-radius: 4px; background: white;")
        row_villas.addWidget(lbl_villas)
        row_villas.addWidget(self.spin_villas_rooms)
        row_villas.addStretch()
        prop_layout.addLayout(row_villas)

        scroll_layout.addWidget(card_prop)

        # -----------------------------------------------------------------
        # Card 3: DATA LOCATIONS & DIRECTORY ROUTING
        # -----------------------------------------------------------------
        card_routing = self._create_card("\U0001f4c1 DATA LOCATIONS & DIRECTORY ROUTING")
        r_layout = card_routing.layout()

        # Database Directory
        row_db = QHBoxLayout()
        lbl_db = QLabel("Database Root Directory:")
        lbl_db.setFixedWidth(230)
        lbl_db.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_database_dir = QLineEdit(DATABASE_DIR)
        self.txt_database_dir.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
        btn_browse_db = QPushButton("Browse\u2026")
        btn_browse_db.setStyleSheet(btn_browse_style)
        btn_browse_db.clicked.connect(self._browse_database_dir)
        row_db.addWidget(lbl_db)
        row_db.addWidget(self.txt_database_dir)
        row_db.addWidget(btn_browse_db)
        r_layout.addLayout(row_db)

        # Templates Directory
        row_tpl = QHBoxLayout()
        lbl_tpl = QLabel("Document Templates Directory:")
        lbl_tpl.setFixedWidth(230)
        lbl_tpl.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_templates_dir = QLineEdit(TEMPLATES_DIR)
        self.txt_templates_dir.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
        btn_browse_tpl = QPushButton("Browse\u2026")
        btn_browse_tpl.setStyleSheet(btn_browse_style)
        btn_browse_tpl.clicked.connect(self._browse_templates_dir)
        row_tpl.addWidget(lbl_tpl)
        row_tpl.addWidget(self.txt_templates_dir)
        row_tpl.addWidget(btn_browse_tpl)
        r_layout.addLayout(row_tpl)

        # Booking Calls Workbook
        row_bk = QHBoxLayout()
        lbl_bk = QLabel("Booking Calls Workbook (.xlsx):")
        lbl_bk.setFixedWidth(230)
        lbl_bk.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_booking_calls_path = QLineEdit(os.path.join(BOOKING_CALLS_DIR, "BOOKING CALLS.xlsx"))
        self.txt_booking_calls_path.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
        btn_browse_bk = QPushButton("Browse\u2026")
        btn_browse_bk.setStyleSheet(btn_browse_style)
        btn_browse_bk.clicked.connect(self._browse_booking_calls_file)
        row_bk.addWidget(lbl_bk)
        row_bk.addWidget(self.txt_booking_calls_path)
        row_bk.addWidget(btn_browse_bk)
        r_layout.addLayout(row_bk)

        # Primary Hotel Data Set
        row_json = QHBoxLayout()
        lbl_json = QLabel("Primary Hotel Data Set (JSON):")
        lbl_json.setFixedWidth(230)
        lbl_json.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_json = QLineEdit(str(HOTEL_DATASET_PATH))
        self.txt_json.setReadOnly(True)
        self.txt_json.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
        row_json.addWidget(lbl_json)
        row_json.addWidget(self.txt_json)
        r_layout.addLayout(row_json)

        scroll_layout.addWidget(card_routing)

        # -----------------------------------------------------------------
        # Card 4: BOOKING CALLS WORKBOOK INTEGRATION
        # -----------------------------------------------------------------
        card_booking = self._create_card("\U0001f4de BOOKING CALLS WORKBOOK CONFIGURATION")
        b_layout = card_booking.layout()

        row_sheet = QHBoxLayout()
        lbl_sheet = QLabel("Target Follow-Up Sheet:")
        lbl_sheet.setFixedWidth(230)
        lbl_sheet.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_sheet_name = QLineEdit("FOLLOW UP")
        self.txt_sheet_name.setFixedWidth(160)
        self.txt_sheet_name.setStyleSheet("padding: 4px 8px; border: 1px solid #CBD5E1; border-radius: 4px; background: white;")
        row_sheet.addWidget(lbl_sheet)
        row_sheet.addWidget(self.txt_sheet_name)
        row_sheet.addStretch()
        b_layout.addLayout(row_sheet)

        self.chk_mirror_sheet = QCheckBox("Also mirror logs to 'FOLLOW UP 1' (Strict adherence to standard follow-up sheets)")
        self.chk_mirror_sheet.setChecked(True)
        self.chk_mirror_sheet.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
        b_layout.addWidget(self.chk_mirror_sheet)

        scroll_layout.addWidget(card_booking)

        # -----------------------------------------------------------------
        # Card 5: EXCLUSIVI API INTEGRATION
        # -----------------------------------------------------------------
        card_exclusivi = self._create_card("\U0001f50c EXCLUSIVI API INTEGRATION", accent_color="#7C3AED")
        ex_layout = card_exclusivi.layout()

        ex_desc = QLabel("Connect to Exclusivi applications for guest service management, amenity requests, and reservation synchronization.")
        ex_desc.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
        ex_desc.setWordWrap(True)
        ex_layout.addWidget(ex_desc)

        # Enable toggle
        self.chk_exclusivi_enabled = QCheckBox("Enable Exclusivi API Integration")
        self.chk_exclusivi_enabled.setStyleSheet("font-weight: bold; color: #1E293B; font-size: 12px; border: none;")
        self.chk_exclusivi_enabled.toggled.connect(self._toggle_exclusivi_fields)
        ex_layout.addWidget(self.chk_exclusivi_enabled)

        # API Base URL
        row_api_url = QHBoxLayout()
        lbl_api_url = QLabel("API Base URL:")
        lbl_api_url.setFixedWidth(230)
        lbl_api_url.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_exclusivi_url = QLineEdit()
        self.txt_exclusivi_url.setPlaceholderText("https://api.exclusivi.com/v1")
        self.txt_exclusivi_url.setStyleSheet("padding: 6px 10px; border: 1px solid #C4B5FD; border-radius: 4px; background: white;")
        row_api_url.addWidget(lbl_api_url)
        row_api_url.addWidget(self.txt_exclusivi_url)
        ex_layout.addLayout(row_api_url)

        # API Key
        row_api_key = QHBoxLayout()
        lbl_api_key = QLabel("API Key / Bearer Token:")
        lbl_api_key.setFixedWidth(230)
        lbl_api_key.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_exclusivi_key = QLineEdit()
        self.txt_exclusivi_key.setPlaceholderText("Enter your Exclusivi API key...")
        self.txt_exclusivi_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_exclusivi_key.setStyleSheet("padding: 6px 10px; border: 1px solid #C4B5FD; border-radius: 4px; background: white;")

        self.btn_toggle_key = QPushButton("\U0001f441")
        self.btn_toggle_key.setFixedWidth(36)
        self.btn_toggle_key.setStyleSheet("""
            QPushButton {
                background: #F5F3FF;
                border: 1px solid #C4B5FD;
                border-radius: 4px;
                padding: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background: #EDE9FE; }
        """)
        self.btn_toggle_key.clicked.connect(self._toggle_api_key_visibility)

        row_api_key.addWidget(lbl_api_key)
        row_api_key.addWidget(self.txt_exclusivi_key)
        row_api_key.addWidget(self.btn_toggle_key)
        ex_layout.addLayout(row_api_key)

        # Test Connection row
        row_test = QHBoxLayout()
        self.btn_test_connection = QPushButton("\U0001f517 Test Connection")
        self.btn_test_connection.setStyleSheet("""
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
        self.btn_test_connection.clicked.connect(self._test_exclusivi_connection)

        self.lbl_connection_status = QLabel("\u25cf Not configured")
        self.lbl_connection_status.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")

        row_test.addWidget(self.btn_test_connection)
        row_test.addWidget(self.lbl_connection_status)
        row_test.addStretch()
        ex_layout.addLayout(row_test)

        scroll_layout.addWidget(card_exclusivi)

        # -----------------------------------------------------------------
        # Card 6: DOCUMENT STORAGE LOCATIONS
        # -----------------------------------------------------------------
        card_storage = self._create_card("\U0001f4e6 DOCUMENT STORAGE LOCATIONS", accent_color="#065F46")
        st_layout = card_storage.layout()

        st_desc = QLabel("Configure where generated Offer Lists and Cake Memos are stored. Use the 'Open' buttons for quick Explorer access.")
        st_desc.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
        st_desc.setWordWrap(True)
        st_layout.addWidget(st_desc)

        # Offer Lists Directory
        row_offers_dir = QHBoxLayout()
        lbl_offers_dir = QLabel("Offer Lists Output Directory:")
        lbl_offers_dir.setFixedWidth(230)
        lbl_offers_dir.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_offer_lists_dir = QLineEdit(os.path.join(OUTPUT_DIR, "OFFERS"))
        self.txt_offer_lists_dir.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #A7F3D0; border-radius: 4px;")
        btn_browse_offers = QPushButton("Browse\u2026")
        btn_browse_offers.setStyleSheet(btn_browse_style)
        btn_browse_offers.clicked.connect(self._browse_offers_dir)
        btn_open_offers = QPushButton("\U0001f4c2 Open")
        btn_open_offers.setStyleSheet("""
            QPushButton {
                background-color: #065F46;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_open_offers.clicked.connect(lambda: self._open_folder(self.txt_offer_lists_dir.text()))
        row_offers_dir.addWidget(lbl_offers_dir)
        row_offers_dir.addWidget(self.txt_offer_lists_dir)
        row_offers_dir.addWidget(btn_browse_offers)
        row_offers_dir.addWidget(btn_open_offers)
        st_layout.addLayout(row_offers_dir)

        # Cake Memos Directory
        row_cakes_dir = QHBoxLayout()
        lbl_cakes_dir = QLabel("Cake Memos Output Directory:")
        lbl_cakes_dir.setFixedWidth(230)
        lbl_cakes_dir.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.txt_cake_memos_dir = QLineEdit(os.path.join(OUTPUT_DIR, "CAKE_MEMOS"))
        self.txt_cake_memos_dir.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #A7F3D0; border-radius: 4px;")
        btn_browse_cakes = QPushButton("Browse\u2026")
        btn_browse_cakes.setStyleSheet(btn_browse_style)
        btn_browse_cakes.clicked.connect(self._browse_cakes_dir)
        btn_open_cakes = QPushButton("\U0001f4c2 Open")
        btn_open_cakes.setStyleSheet("""
            QPushButton {
                background-color: #065F46;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_open_cakes.clicked.connect(lambda: self._open_folder(self.txt_cake_memos_dir.text()))
        row_cakes_dir.addWidget(lbl_cakes_dir)
        row_cakes_dir.addWidget(self.txt_cake_memos_dir)
        row_cakes_dir.addWidget(btn_browse_cakes)
        row_cakes_dir.addWidget(btn_open_cakes)
        st_layout.addLayout(row_cakes_dir)

        # File counts summary
        self.lbl_storage_summary = QLabel("")
        self.lbl_storage_summary.setStyleSheet("color: #065F46; font-size: 11px; font-weight: bold; padding-top: 4px; border: none;")
        st_layout.addWidget(self.lbl_storage_summary)

        scroll_layout.addWidget(card_storage)

        # -----------------------------------------------------------------
        # Card 7: WORKSPACE PREFERENCES
        # -----------------------------------------------------------------
        card_prefs = self._create_card("\U0001f3a8 WORKSPACE PREFERENCES")
        p_layout = card_prefs.layout()

        self.chk_fit_view = QCheckBox("Default 2D Map to 'Fit View' upon launch")
        self.chk_fit_view.setChecked(True)
        self.chk_fit_view.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
        p_layout.addWidget(self.chk_fit_view)

        row_prop = QHBoxLayout()
        lbl_prop = QLabel("Active Property Target:")
        lbl_prop.setFixedWidth(230)
        lbl_prop.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.combo_prop = QComboBox()
        self.combo_prop.addItems(["Sandy Beach (Exclusive Active Property)"])
        self.combo_prop.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_prop.addWidget(lbl_prop)
        row_prop.addWidget(self.combo_prop)
        row_prop.addStretch()
        p_layout.addLayout(row_prop)

        row_mode = QHBoxLayout()
        lbl_mode = QLabel("Operational Mode:")
        lbl_mode.setFixedWidth(230)
        lbl_mode.setStyleSheet("font-weight: bold; color: #333333; border: none;")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Production (Standard Gatekeeper & Centralized Database)", "Debug / Diagnostic"])
        self.combo_mode.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_mode.addWidget(lbl_mode)
        row_mode.addWidget(self.combo_mode)
        row_mode.addStretch()
        p_layout.addLayout(row_mode)

        scroll_layout.addWidget(card_prefs)

        # -----------------------------------------------------------------
        # Card 8: ACTIONS & SETTINGS PERSISTENCE
        # -----------------------------------------------------------------
        card_actions = self._create_card("\U0001f4be ACTIONS & SETTINGS PERSISTENCE")
        act_layout = card_actions.layout()

        row_save = QHBoxLayout()
        self.btn_save_config = QPushButton("\U0001f4be Save Configuration")
        self.btn_save_config.setStyleSheet("""
            QPushButton {
                background-color: #800020;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 9px 22px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover { background-color: #A00028; }
        """)
        self.btn_save_config.clicked.connect(self.save_configuration)

        self.btn_reload_config = QPushButton("\U0001f504 Reload Settings")
        self.btn_reload_config.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #1E293B;
                font-size: 12px;
                font-weight: bold;
                padding: 9px 18px;
                border-radius: 5px;
                border: 1px solid #CBD5E1;
            }
            QPushButton:hover { background-color: #E2E8F0; }
        """)
        self.btn_reload_config.clicked.connect(self.reload_configuration)

        self.lbl_saved_timestamp = QLabel("Settings not saved yet.")
        self.lbl_saved_timestamp.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic; border: none;")

        row_save.addWidget(self.btn_save_config)
        row_save.addWidget(self.btn_reload_config)
        row_save.addSpacing(15)
        row_save.addWidget(self.lbl_saved_timestamp)
        row_save.addStretch()
        act_layout.addLayout(row_save)

        scroll_layout.addWidget(card_actions)

        # -----------------------------------------------------------------
        # Card 9: DATABASE PURGE & RESET (Dangerous Actions)
        # -----------------------------------------------------------------
        card_danger = self._create_card("\U0001f5d1\ufe0f DATABASE PURGE & RESET (MAINTENANCE)", accent_color="#DC2626")
        d_layout = card_danger.layout()

        d_desc = QLabel("Clearing the database completely resets all transaction logs, guest records, memo caches, and active bookings.")
        d_desc.setWordWrap(True)
        d_desc.setStyleSheet("color: #64748b; font-size: 11px; border: none;")
        d_layout.addWidget(d_desc)

        btn_box = QHBoxLayout()
        self.btn_export_blocks = QPushButton("\U0001f504 Refresh Block Exports")
        self.btn_export_blocks.setStyleSheet("""
            QPushButton {
                background-color: #065F46;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_export_blocks.clicked.connect(self.refresh_block_exports)
        btn_box.addWidget(self.btn_export_blocks)

        self.btn_clear_db = QPushButton("\U0001f5d1\ufe0f Clear Hotel Database")
        self.btn_clear_db.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        self.btn_clear_db.clicked.connect(self.clear_hotel_database)
        btn_box.addWidget(self.btn_clear_db)
        btn_box.addStretch()
        d_layout.addLayout(btn_box)

        scroll_layout.addWidget(card_danger)
        scroll_layout.addStretch()

        cfg_scroll.setWidget(cfg_content)
        main_layout.addWidget(cfg_scroll)

    def _create_card(self, title: str, accent_color: str = "#800020") -> QFrame:
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

    # -----------------------------------------------------------------
    # Exclusivi API Helpers
    # -----------------------------------------------------------------
    def _toggle_exclusivi_fields(self, enabled: bool) -> None:
        """Enable/disable Exclusivi API fields based on the toggle."""
        self.txt_exclusivi_url.setEnabled(enabled)
        self.txt_exclusivi_key.setEnabled(enabled)
        self.btn_test_connection.setEnabled(enabled)
        self.btn_toggle_key.setEnabled(enabled)
        if not enabled:
            self.lbl_connection_status.setText("\u25cf Disabled")
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
            self.lbl_connection_status.setText("\u26a0\ufe0f URL is required")
            self.lbl_connection_status.setStyleSheet("color: #D97706; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")
            return

        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL")
        except Exception:
            self.lbl_connection_status.setText("\u274c Invalid URL format")
            self.lbl_connection_status.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")
            return

        self.btn_test_connection.setEnabled(False)
        self.lbl_connection_status.setText("\u23f3 Testing connection...")
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
            self.lbl_connection_status.setText(f"\u2705 Connected ({ts})")
            self.lbl_connection_status.setStyleSheet("color: #059669; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")
        else:
            display = status[:80] if len(status) > 80 else status
            self.lbl_connection_status.setText(f"\u274c {display} ({ts})")
            self.lbl_connection_status.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")

        # Store the test result
        self.current_settings.setdefault("exclusivi", {})["last_test_status"] = status.split(":")[0] if ":" in status else status
        self.current_settings["exclusivi"]["last_test_timestamp"] = ts

    # -----------------------------------------------------------------
    # Document Storage Helpers
    # -----------------------------------------------------------------
    def _browse_offers_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Offer Lists Output Directory", self.txt_offer_lists_dir.text())
        if folder:
            self.txt_offer_lists_dir.setText(folder)

    def _browse_cakes_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Cake Memos Output Directory", self.txt_cake_memos_dir.text())
        if folder:
            self.txt_cake_memos_dir.setText(folder)

    def _open_folder(self, path: str) -> None:
        """Open a directory in Windows Explorer."""
        path = path.strip()
        if os.path.exists(path):
            os.startfile(path)
        else:
            try:
                os.makedirs(path, exist_ok=True)
                os.startfile(path)
            except Exception as e:
                if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                    QMessageBox.warning(self, "Folder Error", f"Could not open folder:\n{path}\n\n{e}")

    def _refresh_storage_summary(self) -> None:
        """Count files in the offer lists and cake memos directories."""
        offers_dir = self.txt_offer_lists_dir.text().strip()
        cakes_dir = self.txt_cake_memos_dir.text().strip()

        offer_count = 0
        cake_count = 0

        if os.path.exists(offers_dir):
            for root, dirs, files in os.walk(offers_dir):
                offer_count += sum(1 for f in files if f.lower().endswith(('.docx', '.doc', '.pdf')))

        if os.path.exists(cakes_dir):
            for root, dirs, files in os.walk(cakes_dir):
                cake_count += sum(1 for f in files if f.lower().endswith(('.docx', '.doc', '.pdf')))

        self.lbl_storage_summary.setText(
            f"\U0001f4c4 {offer_count} Offer List(s) stored  |  \U0001f382 {cake_count} Cake Memo(s) stored"
        )

    # -----------------------------------------------------------------
    # Settings Population & Persistence
    # -----------------------------------------------------------------
    def populate_settings_ui(self) -> None:
        """Populates UI widgets from self.current_settings."""
        s = self.current_settings
        props = s.get("properties", {})
        self.spin_beach_rooms.setValue(int(props.get("sandy_beach_rooms", 660)))
        self.spin_villas_rooms.setValue(int(props.get("sandy_villas_rooms", 40)))

        paths = s.get("paths", {})
        self.txt_database_dir.setText(str(paths.get("database_dir", DATABASE_DIR)))
        self.txt_templates_dir.setText(str(paths.get("templates_dir", TEMPLATES_DIR)))
        self.txt_booking_calls_path.setText(str(paths.get("booking_calls_workbook", os.path.join(BOOKING_CALLS_DIR, "BOOKING CALLS.xlsx"))))

        bc = s.get("booking_calls", {})
        self.txt_sheet_name.setText(str(bc.get("sheet_name", "FOLLOW UP")))
        self.chk_mirror_sheet.setChecked(bool(bc.get("mirror_follow_up_1", True)))

        # Exclusivi API
        ex = s.get("exclusivi", {})
        self.chk_exclusivi_enabled.setChecked(bool(ex.get("enabled", False)))
        self.txt_exclusivi_url.setText(str(ex.get("api_base_url", "")))
        self.txt_exclusivi_key.setText(str(ex.get("api_key", "")))
        self._toggle_exclusivi_fields(self.chk_exclusivi_enabled.isChecked())

        last_test = ex.get("last_test_status")
        last_test_ts = ex.get("last_test_timestamp")
        if last_test and last_test_ts:
            if last_test == "connected":
                self.lbl_connection_status.setText(f"\u2705 Last: Connected ({last_test_ts})")
                self.lbl_connection_status.setStyleSheet("color: #059669; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")
            else:
                self.lbl_connection_status.setText(f"\u274c Last: {last_test} ({last_test_ts})")
                self.lbl_connection_status.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 11px; padding-left: 10px; border: none;")

        # Storage
        storage = s.get("storage", {})
        self.txt_offer_lists_dir.setText(str(storage.get("offer_lists_dir", os.path.join(OUTPUT_DIR, "OFFERS"))))
        self.txt_cake_memos_dir.setText(str(storage.get("cake_memos_dir", os.path.join(OUTPUT_DIR, "CAKE_MEMOS"))))

        # Preferences
        prefs = s.get("preferences", {})
        self.chk_fit_view.setChecked(bool(prefs.get("default_fit_view", True)))
        act_prop = prefs.get("active_property", "Sandy Beach (Exclusive Active Property)")
        idx = self.combo_prop.findText(act_prop)
        if idx >= 0:
            self.combo_prop.setCurrentIndex(idx)

        op_mode = prefs.get("operational_mode", "Production (Standard Gatekeeper & Centralized Database)")
        idx_m = self.combo_mode.findText(op_mode)
        if idx_m >= 0:
            self.combo_mode.setCurrentIndex(idx_m)

        last_saved = s.get("last_saved")
        if last_saved:
            self.lbl_saved_timestamp.setText(f"Last saved: {last_saved}")
        else:
            self.lbl_saved_timestamp.setText("Settings loaded from defaults.")

        # Refresh storage summary
        self._refresh_storage_summary()

    def collect_settings_from_ui(self) -> Dict[str, Any]:
        """Collects current values from UI inputs into a settings dict."""
        return {
            "properties": {
                "sandy_beach_rooms": self.spin_beach_rooms.value(),
                "sandy_villas_rooms": self.spin_villas_rooms.value(),
            },
            "paths": {
                "database_dir": self.txt_database_dir.text().strip(),
                "templates_dir": self.txt_templates_dir.text().strip(),
                "booking_calls_workbook": self.txt_booking_calls_path.text().strip(),
            },
            "booking_calls": {
                "sheet_name": self.txt_sheet_name.text().strip(),
                "mirror_follow_up_1": self.chk_mirror_sheet.isChecked(),
            },
            "exclusivi": {
                "enabled": self.chk_exclusivi_enabled.isChecked(),
                "api_base_url": self.txt_exclusivi_url.text().strip(),
                "api_key": self.txt_exclusivi_key.text().strip(),
                "last_test_status": self.current_settings.get("exclusivi", {}).get("last_test_status"),
                "last_test_timestamp": self.current_settings.get("exclusivi", {}).get("last_test_timestamp"),
            },
            "storage": {
                "offer_lists_dir": self.txt_offer_lists_dir.text().strip(),
                "cake_memos_dir": self.txt_cake_memos_dir.text().strip(),
            },
            "preferences": {
                "default_fit_view": self.chk_fit_view.isChecked(),
                "active_property": self.combo_prop.currentText(),
                "operational_mode": self.combo_mode.currentText(),
            },
        }

    def save_configuration(self, show_dialog: bool = True) -> bool:
        """Persists current UI configuration to app_settings.json and emits data_updated."""
        new_settings = self.collect_settings_from_ui()
        success = save_app_settings(new_settings)
        if success:
            self.current_settings = load_app_settings()
            self.lbl_saved_timestamp.setText(f"Last saved: {self.current_settings.get('last_saved', 'Just now')}")
            self._refresh_storage_summary()
            self.data_updated.emit()
            if show_dialog and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.information(
                    self,
                    "Configuration Saved",
                    "Application settings saved successfully to DATABASE/app_settings.json.\n\n"
                    "Live Stats and Booking Calls have been refreshed."
                )
            return True
        else:
            if show_dialog and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.critical(self, "Save Error", "Failed to save configuration settings.")
            return False

    def reload_configuration(self, show_dialog: bool = True) -> None:
        """Reloads settings from disk."""
        self.current_settings = load_app_settings()
        self.populate_settings_ui()
        if show_dialog and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QMessageBox.information(self, "Settings Reloaded", "Configuration settings reloaded from disk.")

    # -----------------------------------------------------------------
    # Browse Handlers
    # -----------------------------------------------------------------
    def _browse_database_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Database Directory", self.txt_database_dir.text())
        if folder:
            self.txt_database_dir.setText(folder)

    def _browse_templates_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Document Templates Directory", self.txt_templates_dir.text())
        if folder:
            self.txt_templates_dir.setText(folder)

    def _browse_booking_calls_file(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Booking Calls Excel Workbook",
            os.path.dirname(self.txt_booking_calls_path.text()),
            "Excel Files (*.xlsx *.xls);;All Files (*.*)"
        )
        if fpath:
            self.txt_booking_calls_path.setText(fpath)

    # -----------------------------------------------------------------
    # Gatekeeper Date Override
    # -----------------------------------------------------------------
    def _apply_date_override(self) -> None:
        qdt = self.date_override.date()
        target_d = date(qdt.year(), qdt.month(), qdt.day())
        try:
            self.data_manager.set_last_sync_date(target_d)
            self.refresh_timestamp_display()
            self.data_updated.emit()
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.information(
                    self,
                    "Override Applied",
                    f"Operational date override applied successfully: {target_d.strftime('%Y-%m-%d')}"
                )
        except Exception as e:
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.critical(self, "Override Error", f"Failed to apply operational date override:\n{e}")

    # -----------------------------------------------------------------
    # Ingestion & Database Maintenance Actions
    # -----------------------------------------------------------------
    def refresh_timestamp_display(self) -> None:
        master = self.data_manager.load_master_state()
        meta = self.data_manager.load_metadata()
        sync_date = meta.get("last_sync_date") or meta.get("last_processed_date")
        last_updated = meta.get("last_updated_at")

        if master and sync_date:
            ts_str = str(last_updated).split(".")[0].replace("T", " ") if last_updated else "N/A"
            self.txt_timestamp.setText(f"\u2705 Operational Date: {sync_date}  |  Last Synced: {ts_str}  ({len(master)} Active Bookings)")
            self.txt_timestamp.setStyleSheet("background-color: #ECFDF5; color: #065F46; font-weight: bold; padding: 8px 12px; border: 1px solid #A7F3D0; border-radius: 6px;")
        else:
            self.txt_timestamp.setText("\u26a0\ufe0f No In-House List Loaded \u2014 Load one to populate Stats and Guest Manifest")
            self.txt_timestamp.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 8px 12px; border: 1px solid #FECACA; border-radius: 6px;")

    def _prompt_for_operational_date(self, title: str, message: str, default_date: Optional[date] = None) -> Optional[date]:
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return default_date or date.today()

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedSize(400, 190)
        dlg.setStyleSheet("background-color: #FFFFFF; font-family: 'Segoe UI', Arial, sans-serif;")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 13px; color: #1F2937;")
        layout.addWidget(lbl)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        init_d = default_date or date.today()
        date_edit.setDate(QDate(init_d.year, init_d.month, init_d.day))
        date_edit.setStyleSheet("padding: 6px; font-size: 13px; border: 1px solid #D1D5DB; border-radius: 4px;")
        layout.addWidget(date_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            qd = date_edit.date()
            return date(qd.year(), qd.month(), qd.day())
        return None

    def load_inhouse_list(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select In-House List",
            BASE_DIR,
            "In-House Files (*.xlsx *.xls *.csv);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*.*)"
        )
        if not file_path:
            return

        extracted_dt, ts_str = extract_inhouse_report_date(file_path)
        target_today = date.today()

        rep_date = extracted_dt
        if rep_date is None:
            rep_date = self._prompt_for_operational_date(
                "Operational Date Required",
                f"No date was detected in '{os.path.basename(file_path)}'.\n"
                "Please confirm the operational date for this In-House list:",
                default_date=target_today
            )
            if not rep_date:
                return
        elif rep_date != target_today:
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                reply = QMessageBox.question(
                    self,
                    "Operational Date Confirmation",
                    f"Selected In-House List operational date:\n"
                    f"  📅 {rep_date.strftime('%Y-%m-%d')} ({rep_date.strftime('%A')})\n\n"
                    f"Today's system calendar date is {target_today.strftime('%Y-%m-%d')}.\n\n"
                    f"Do you want to ingest this In-House List for operational date {rep_date.strftime('%Y-%m-%d')}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        try:
            parsed = self.data_manager.parse_in_house_file(file_path)
            if not parsed:
                if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                    QMessageBox.warning(self, "Empty Dataset", "No valid bookings were found in the selected file.")
                return

            summary = self.data_manager.compare_and_update(parsed, processing_date=rep_date)
            self.refresh_timestamp_display()
            self.data_updated.emit()

            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.information(
                    self,
                    "Ingestion Successful",
                    f"In-House List ingested successfully!\n\n"
                    f"• Operational Date: {rep_date.strftime('%Y-%m-%d')}\n"
                    f"• Active In-House Bookings: {summary['total_in_house']}\n"
                    f"• Room Moves Detected: {len(summary['room_moves'])}\n"
                    f"• Check-Outs Archived: {len(summary['check_outs'])}\n\n"
                    f"All Room Block JSON metrics have been synchronized in PLOT/."
                )
        except Exception as e:
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.critical(self, "Ingestion Error", f"Failed to ingest In-House List:\n{str(e)}")

    def clear_hotel_database(self) -> None:
        confirm = QMessageBox.warning(
            self,
            "Confirm Database Reset",
            "This operation will purge guest manifests, reservation records, offer lists, and cake memos from all system JSON storage.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            res = self.data_manager.purge_hotel_database()
            purged_count = res.get("purged_count", 0) if isinstance(res, dict) else 0
            self.refresh_timestamp_display()
            self.data_updated.emit()
            QMessageBox.information(
                self,
                "Purge Complete",
                f"Database cleared successfully. {purged_count} JSON records and caches were reset."
            )
        except Exception as e:
            QMessageBox.critical(self, "Purge Error", f"Failed to clear hotel database:\n{str(e)}")

    def refresh_block_exports(self) -> None:
        try:
            res = self.data_manager.export_room_block_json_data()
            self.data_updated.emit()
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {res['total_exported']} room block JSON payloads to PLOT/."
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export room blocks:\n{str(e)}")

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        try:
            self.current_settings = load_app_settings()
            self.populate_settings_ui()
            self.refresh_timestamp_display()
        except Exception as e:
            print(f"[Configuration] Activation error: {e}")
