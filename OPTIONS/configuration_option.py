"""
Configuration Option: System configuration, directory routing, and database maintenance.
========================================================================================
Provides the ConfigurationWidget with three card groups:
  1. DATA SOURCE ROUTING (File Routing)
  2. WORKSPACE PREFERENCES (Workspace Calibration)
  3. DATABASE PURGE & RESET (Dangerous Actions)
"""

import os
from datetime import date
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QScrollArea, QFrame,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSignal

from MODULES.data_manager import (
    InHouseDataManager, MASTER_STATE_PATH, STATE_META_PATH,
    CHECKOUTS_JSON, ROOM_MOVES_JSON, ARRIVALS_BEACH_PATH,
    DATABASE_DIR, OUTPUT_DIR, BASE_DIR, PLOT_DIR,
    HOTEL_DATASET_PATH, BOOKING_CALLS_TODAY_JSON,
    validate_inhouse_file_date
)


class ConfigurationWidget(QWidget):
    """
    Configuration Page: system configuration inputs, directory path settings,
    workspace calibration, and database maintenance controls.
    Categorized into 3 card groups:
      1. DATA SOURCE ROUTING (File Routing)
      2. WORKSPACE PREFERENCES (Workspace Calibration)
      3. DATABASE PURGE & RESET (Dangerous Actions)
    """
    data_updated = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_timestamp_display()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        lbl_title = QLabel("⚙️ SYSTEM CONFIGURATION & DATABASE MAINTENANCE")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Configure data source routing, workspace preferences, and execute system maintenance.")
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

        # -----------------------------------------------------------------
        # Card 1: DATA SOURCE ROUTING (File Routing)
        # -----------------------------------------------------------------
        card_routing = self._create_card("DATA SOURCE ROUTING")
        r_layout = QVBoxLayout(card_routing)
        r_layout.setSpacing(10)

        # Primary Hotel Data Set
        row_json = QHBoxLayout()
        lbl_json = QLabel("Primary Hotel Data Set (JSON):")
        lbl_json.setFixedWidth(210)
        lbl_json.setStyleSheet("font-weight: bold; color: #333333;")
        self.txt_json = QLineEdit(str(HOTEL_DATASET_PATH))
        self.txt_json.setReadOnly(True)
        self.txt_json.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
        row_json.addWidget(lbl_json)
        row_json.addWidget(self.txt_json)
        r_layout.addLayout(row_json)

        # In-House Manifest & Load Action
        row_manifest = QHBoxLayout()
        lbl_man = QLabel("In-House Manifest (CSV / XLSX):")
        lbl_man.setFixedWidth(210)
        lbl_man.setStyleSheet("font-weight: bold; color: #333333;")
        self.txt_timestamp = QLineEdit("No In-House List Loaded")
        self.txt_timestamp.setReadOnly(True)
        self.txt_timestamp.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 6px 10px; border: 1px solid #FECACA; border-radius: 4px;")
        self.btn_load_inhouse = QPushButton("📂 Load In-House List")
        self.btn_load_inhouse.setStyleSheet("""
            QPushButton {
                background-color: #1E3A8A;
                color: white;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        self.btn_load_inhouse.clicked.connect(self.load_inhouse_list)
        row_manifest.addWidget(lbl_man)
        row_manifest.addWidget(self.txt_timestamp, stretch=1)
        row_manifest.addWidget(self.btn_load_inhouse)
        r_layout.addLayout(row_manifest)

        # Standardized Database Topology
        paths_info = [
            ("Master State & Metadata:", MASTER_STATE_PATH),
            ("Booking Calls Today:", BOOKING_CALLS_TODAY_JSON),
            ("Check-Out Records:", CHECKOUTS_JSON),
            ("Room Moves History:", ROOM_MOVES_JSON),
            ("Sandy Beach Arrivals:", ARRIVALS_BEACH_PATH),
            ("Plot & Block Exports:", PLOT_DIR)
        ]
        for label_text, p_val in paths_info:
            r_box = QHBoxLayout()
            l = QLabel(label_text)
            l.setFixedWidth(210)
            l.setStyleSheet("font-weight: bold; color: #555555;")
            val = QLineEdit(p_val)
            val.setReadOnly(True)
            val.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
            r_box.addWidget(l)
            r_box.addWidget(val)
            r_layout.addLayout(r_box)

        scroll_layout.addWidget(card_routing)

        # -----------------------------------------------------------------
        # Card 2: WORKSPACE PREFERENCES (Workspace Calibration)
        # -----------------------------------------------------------------
        card_prefs = self._create_card("WORKSPACE PREFERENCES")
        p_layout = QVBoxLayout(card_prefs)
        p_layout.setSpacing(10)

        self.chk_fit_view = QCheckBox("Default 2D Map to 'Fit View' upon launch")
        self.chk_fit_view.setChecked(True)
        self.chk_fit_view.setStyleSheet("font-weight: bold; color: #1E293B;")
        p_layout.addWidget(self.chk_fit_view)

        row_prop = QHBoxLayout()
        lbl_prop = QLabel("Active Property Target:")
        lbl_prop.setFixedWidth(210)
        lbl_prop.setStyleSheet("font-weight: bold; color: #333333;")
        self.combo_prop = QComboBox()
        self.combo_prop.addItems(["Sandy Beach (Exclusive Active Property)"])
        self.combo_prop.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_prop.addWidget(lbl_prop)
        row_prop.addWidget(self.combo_prop)
        row_prop.addStretch()
        p_layout.addLayout(row_prop)

        row_mode = QHBoxLayout()
        lbl_mode = QLabel("Operational Mode:")
        lbl_mode.setFixedWidth(210)
        lbl_mode.setStyleSheet("font-weight: bold; color: #333333;")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Production (Standard Gatekeeper & Centralized Database)", "Debug / Diagnostic"])
        self.combo_mode.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_mode.addWidget(lbl_mode)
        row_mode.addWidget(self.combo_mode)
        row_mode.addStretch()
        p_layout.addLayout(row_mode)

        row_btn_block = QHBoxLayout()
        self.btn_export_blocks = QPushButton("🔄 Refresh Block Exports")
        self.btn_export_blocks.setStyleSheet("""
            QPushButton {
                background-color: #065F46;
                color: white;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_export_blocks.clicked.connect(self.refresh_block_exports)
        row_btn_block.addWidget(self.btn_export_blocks)
        row_btn_block.addStretch()
        p_layout.addLayout(row_btn_block)

        scroll_layout.addWidget(card_prefs)

        # -----------------------------------------------------------------
        # Card 3: DATABASE PURGE & RESET (Dangerous Actions)
        # -----------------------------------------------------------------
        card_danger = self._create_card("DATABASE PURGE & RESET")
        d_layout = QVBoxLayout(card_danger)
        d_layout.setSpacing(10)

        d_desc = QLabel("Clearing the database completely resets all transaction logs, guest records, memo caches, and active bookings.")
        d_desc.setWordWrap(True)
        d_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        d_layout.addWidget(d_desc)

        self.btn_clear_db = QPushButton("🗑️ Clear Hotel Database")
        self.btn_clear_db.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                font-weight: bold;
                padding: 10px 18px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.btn_clear_db.clicked.connect(self.clear_hotel_database)
        d_layout.addWidget(self.btn_clear_db)

        scroll_layout.addWidget(card_danger)
        scroll_layout.addStretch()

        cfg_scroll.setWidget(cfg_content)
        main_layout.addWidget(cfg_scroll)

    def _create_card(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        c_layout = QVBoxLayout(frame)
        c_layout.setSpacing(8)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #800020; font-size: 12px; font-weight: 800; border: none;")
        c_layout.addWidget(t_lbl)
        return frame

    def refresh_timestamp_display(self) -> None:
        master = self.data_manager.load_master_state()
        meta = self.data_manager.load_metadata()
        sync_date = meta.get("last_sync_date") or meta.get("last_processed_date")
        last_updated = meta.get("last_updated_at")

        if master and sync_date:
            ts_str = str(last_updated).split(".")[0].replace("T", " ") if last_updated else "N/A"
            self.txt_timestamp.setText(f"Operational Date: {sync_date}  |  Last Synced: {ts_str}  ({len(master)} Active Bookings)")
            self.txt_timestamp.setStyleSheet("background-color: #ECFDF5; color: #065F46; font-weight: bold; padding: 6px 10px; border: 1px solid #A7F3D0; border-radius: 4px;")
        else:
            self.txt_timestamp.setText("No In-House List Loaded")
            self.txt_timestamp.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 6px 10px; border: 1px solid #FECACA; border-radius: 4px;")

    def load_inhouse_list(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select In-House List",
            BASE_DIR,
            "In-House Files (*.xlsx *.xls *.csv);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*.*)"
        )
        if not file_path:
            return

        is_valid, rep_date, msg = validate_inhouse_file_date(file_path, target_date=date.today())
        if not is_valid:
            QMessageBox.critical(
                self,
                "Validation Error",
                f"{msg}\n\nIngestion has been aborted and the hotel database was not updated."
            )
            return

        try:
            parsed = self.data_manager.parse_in_house_file(file_path)
            if not parsed:
                QMessageBox.warning(self, "Empty Dataset", "No valid bookings were found in the selected file.")
                return

            summary = self.data_manager.compare_and_update(parsed, processing_date=rep_date)
            self.refresh_timestamp_display()
            self.data_updated.emit()

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
            self.refresh_timestamp_display()
        except Exception as e:
            print(f"[Configuration] Activation error: {e}")
