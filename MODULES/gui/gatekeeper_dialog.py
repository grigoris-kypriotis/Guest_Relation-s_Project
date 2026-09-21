"""
Gatekeeper Modal Dialog Module
==============================
Provides the PyQt6 GatekeeperDialog and run_gatekeeper_if_needed startup validator.
Enforces sequential ingestion of all missing daily In-House CSV files for Sandy Beach.
"""

import os
import sys
from datetime import date
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QProgressBar, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal

from MODULES.common.paths_config import BASE_DIR


class GatekeeperDialog(QDialog):
    """
    Blocking startup dialog that enforces sequential ingestion of all
    missing daily In-House CSV files for Sandy Beach up to today.
    """

    ingestion_completed = pyqtSignal()

    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        if data_manager is None:
            from MODULES.data_manager import InHouseDataManager
            data_manager = InHouseDataManager()
        self.data_manager = data_manager
        self.missing_dates: List[date] = self.data_manager.get_missing_dates()
        self.current_step_idx: int = 0
        self.selected_inhouse_path: Optional[str] = None

        self.setWindowTitle("Gatekeeper : In-House Synchronization")
        self.setMinimumSize(780, 560)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        self._setup_styles()
        self._init_ui()
        self._update_step_ui()

    def _setup_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FA;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#header_card {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #800020, stop:1 #B03060);
                border-radius: 8px;
                padding: 18px;
            }
            QLabel#header_title {
                color: #FFFFFF;
                font-size: 19px;
                font-weight: bold;
            }
            QLabel#header_subtitle {
                color: #FFE4E1;
                font-size: 13px;
            }
            QFrame#step_card {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 18px;
            }
            QLabel#target_date_badge {
                background-color: #FFF0F5;
                color: #800020;
                border: 1px solid #B03060;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton.action-btn {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton.action-btn:hover {
                background-color: #357ABD;
            }
            QPushButton#btn_process_inhouse {
                background-color: #2ECC71;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 22px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btn_process_inhouse:hover {
                background-color: #27AE60;
            }
            QPushButton#btn_process_inhouse:disabled {
                background-color: #BDC3C7;
            }
            QPushButton#btn_quit {
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 18px;
                font-weight: bold;
            }
            QPushButton#btn_quit:hover {
                background-color: #C0392B;
            }
            QPushButton#btn_continue {
                background-color: #27AE60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 11px 26px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#btn_continue:hover {
                background-color: #219653;
            }
            QPushButton#btn_continue:disabled {
                background-color: #E0E0E0;
                color: #A0A0A0;
            }
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                gridline-color: #F0F0F0;
            }
            QHeaderView::section {
                background-color: #F4F6F7;
                font-weight: bold;
                color: #2C3E50;
                border: none;
                padding: 6px;
            }
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # 1. Header Banner
        header_card = QFrame()
        header_card.setObjectName("header_card")
        h_layout = QVBoxLayout(header_card)
        lbl_title = QLabel("GATEKEEPER : Sequential In-House Synchronization")
        lbl_title.setObjectName("header_title")
        lbl_sub = QLabel(
            "State integrity validation is mandatory before accessing the workspace.\n"
            "All daily In-House lists through today must be ingested sequentially for Sandy Beach."
        )
        lbl_sub.setObjectName("header_subtitle")
        h_layout.addWidget(lbl_title)
        h_layout.addWidget(lbl_sub)
        main_layout.addWidget(header_card)

        # 2. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        # 3. In-House Synchronization Card
        self.step_card = QFrame()
        self.step_card.setObjectName("step_card")
        s_layout = QVBoxLayout(self.step_card)
        s_layout.setSpacing(12)

        self.lbl_step_info = QLabel()
        self.lbl_step_info.setStyleSheet("font-size: 14px; font-weight: bold; color: #2C3E50;")
        s_layout.addWidget(self.lbl_step_info)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Target Date to Ingest (Sandy Beach):"))
        self.lbl_target_date = QLabel()
        self.lbl_target_date.setObjectName("target_date_badge")
        date_row.addWidget(self.lbl_target_date)
        date_row.addStretch()
        s_layout.addLayout(date_row)

        file_row = QHBoxLayout()
        self.lbl_inhouse_file = QLabel("No file selected")
        self.lbl_inhouse_file.setStyleSheet("color: #7F8C8D; font-style: italic;")
        self.btn_browse_inhouse = QPushButton("📁 Browse In-House CSV...")
        self.btn_browse_inhouse.setProperty("class", "action-btn")
        self.btn_browse_inhouse.clicked.connect(self._browse_inhouse_csv)

        file_row.addWidget(self.lbl_inhouse_file, stretch=1)
        file_row.addWidget(self.btn_browse_inhouse)
        s_layout.addLayout(file_row)

        btn_action_row = QHBoxLayout()
        self.btn_process_inhouse = QPushButton("⚡ Ingest In-House List")
        self.btn_process_inhouse.setObjectName("btn_process_inhouse")
        self.btn_process_inhouse.setEnabled(False)
        self.btn_process_inhouse.clicked.connect(self._process_inhouse_file)
        btn_action_row.addStretch()
        btn_action_row.addWidget(self.btn_process_inhouse)
        s_layout.addLayout(btn_action_row)

        main_layout.addWidget(self.step_card)

        # 4. Ingestion Results Table
        self.table_results = QTableWidget(0, 6)
        self.table_results.setHorizontalHeaderLabels([
            "Ingested Date", "Total In-House", "Room Moves", "Room Merges", "Check-Ins", "Check-Outs"
        ])
        self.table_results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        main_layout.addWidget(self.table_results, stretch=1)

        # 5. Bottom Controls
        bottom_row = QHBoxLayout()
        self.btn_quit = QPushButton("❌ Quit Application")
        self.btn_quit.setObjectName("btn_quit")
        self.btn_quit.clicked.connect(self._abort_and_quit)

        self.btn_continue = QPushButton("🚀 Access Guest Relations Workspace")
        self.btn_continue.setObjectName("btn_continue")
        self.btn_continue.setEnabled(False)
        self.btn_continue.clicked.connect(self.accept)

        bottom_row.addWidget(self.btn_quit)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_continue)
        main_layout.addLayout(bottom_row)

    def _update_step_ui(self):
        total_missing = len(self.missing_dates)
        if total_missing == 0 or self.current_step_idx >= total_missing:
            self.progress_bar.setValue(100)
            self.lbl_step_info.setText("✅ In-House state is fully up to date through today!")
            self.lbl_target_date.setText("All In-House Dates Synchronized")
            self.lbl_target_date.setStyleSheet("background-color: #D4EDDA; color: #155724; border: 1px solid #28A745; padding: 6px 14px;")
            self.btn_browse_inhouse.setEnabled(False)
            self.btn_process_inhouse.setEnabled(False)
            self.btn_continue.setEnabled(True)
            self.btn_continue.setStyleSheet("""
                background-color: #27AE60;
                color: white;
                font-weight: bold;
                padding: 11px 26px;
                border-radius: 4px;
                font-size: 14px;
            """)
            return

        progress_pct = int((self.current_step_idx / total_missing) * 100)
        self.progress_bar.setValue(progress_pct)

        target_date = self.missing_dates[self.current_step_idx]
        self.lbl_step_info.setText(f"Step {self.current_step_idx + 1} of {total_missing}: Mandatory In-House Ingestion")
        self.lbl_target_date.setText(target_date.strftime("%d/%m/%Y (%A)"))

        self.selected_inhouse_path = None
        self.lbl_inhouse_file.setText("No file selected — Click Browse to choose CSV")
        self.lbl_inhouse_file.setStyleSheet("color: #7F8C8D; font-style: italic;")
        self.btn_process_inhouse.setEnabled(False)
        has_state = bool(self.data_manager.load_master_state())
        if self.current_step_idx > 0 or has_state:
            self.btn_continue.setEnabled(True)
            self.btn_continue.setText("🚀 Access Guest Relations Workspace")
            self.btn_continue.setStyleSheet("""
                background-color: #27AE60;
                color: white;
                font-weight: bold;
                padding: 11px 26px;
                border-radius: 4px;
                font-size: 14px;
            """)
        else:
            self.btn_continue.setEnabled(False)
            self.btn_continue.setText("🚀 Access Guest Relations Workspace")
            self.btn_continue.setStyleSheet("")

    def _browse_inhouse_csv(self):
        target_date = self.missing_dates[self.current_step_idx]
        initial_dir = BASE_DIR
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select In-House List CSV for {target_date.strftime('%d/%m/%Y')}",
            initial_dir,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if file_path:
            self.selected_inhouse_path = file_path
            self.lbl_inhouse_file.setText(f"Selected: {os.path.basename(file_path)}")
            self.lbl_inhouse_file.setStyleSheet("color: #2C3E50; font-weight: bold;")
            self.btn_process_inhouse.setEnabled(True)

    def _process_inhouse_file(self):
        if not self.selected_inhouse_path or not os.path.exists(self.selected_inhouse_path):
            QMessageBox.warning(self, "Error", "Selected file does not exist.")
            return

        target_date = self.missing_dates[self.current_step_idx]
        try:
            parsed = self.data_manager.parse_in_house_csv(self.selected_inhouse_path)
            if not parsed:
                QMessageBox.warning(self, "Validation Error", "No valid bookings detected in the selected CSV file.")
                return

            summary = self.data_manager.compare_and_update(parsed, processing_date=target_date)
            self.data_manager.cleanup_file(self.selected_inhouse_path, mode="trash")

            # Update results table
            row = self.table_results.rowCount()
            self.table_results.insertRow(row)
            self.table_results.setItem(row, 0, QTableWidgetItem(target_date.strftime("%d/%m/%Y")))
            self.table_results.setItem(row, 1, QTableWidgetItem(str(summary["total_in_house"])))
            self.table_results.setItem(row, 2, QTableWidgetItem(str(len(summary["room_moves"]))))
            self.table_results.setItem(row, 3, QTableWidgetItem(str(len(summary.get("room_merges", [])))))
            self.table_results.setItem(row, 4, QTableWidgetItem(str(len(summary["check_ins"]))))
            self.table_results.setItem(row, 5, QTableWidgetItem(str(len(summary["check_outs"]))))

            self.current_step_idx += 1
            self._update_step_ui()

        except Exception as e:
            QMessageBox.critical(self, "Processing Error", f"Failed to ingest CSV:\n{str(e)}")

    def _abort_and_quit(self):
        reply = QMessageBox.question(
            self,
            "Quit Application?",
            "Closing the Gatekeeper without synchronizing missing In-House dates will terminate the application. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reject()


def run_gatekeeper_if_needed(parent=None) -> bool:
    """Checks if there are any missing dates and triggers Gatekeeper if needed."""
    from MODULES.data_manager import InHouseDataManager
    dm = InHouseDataManager()
    missing = dm.get_missing_dates()

    if not missing:
        return True

    dialog = GatekeeperDialog(data_manager=dm, parent=parent)
    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted
