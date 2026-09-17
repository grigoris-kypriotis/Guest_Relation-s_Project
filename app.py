import sys
import os
import re
import json
import uuid
import shutil
from datetime import datetime, date
import win32gui
import win32con
import win32com.client
import pythoncom
import docx

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, 
    QVBoxLayout, QPushButton, QStackedWidget, QListWidget, 
    QLabel, QFileDialog, QListWidgetItem, QSizePolicy, QMenu,
    QTabWidget, QScrollArea, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QLineEdit,
    QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QColor, QFont

import collections
from pathlib import Path
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from plot_viewer import PlotGraphWindow
from offers_module import (
    execute_offers_pipeline, get_todays_offer_list, 
    duplicate_for_update, ARRIVALS_FOLDER, log_task
)
from booking_calls import BookingCallsWidget
from data_manager import (
    InHouseDataManager, MASTER_STATE_PATH, STATE_META_PATH,
    CHECKOUTS_JSON, ROOM_MOVES_JSON, ARRIVALS_BEACH_PATH,
    DEPARTURES_BEACH_PATH, BOOKING_CALLS_TODAY_JSON,
    DATABASE_DIR, TEMPLATES_DIR, OUTPUT_DIR, TRASH_DIR, BASE_DIR,
    PLOT_DIR, HOTEL_DATASET_PATH,
    ensure_workspace_directories, resolve_template_path,
    DEFAULT_PROPERTY, run_gatekeeper_if_needed,
    validate_inhouse_file_date, extract_inhouse_report_date
)


class HamburgerButton(QPushButton):
    hovered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("☰", parent)
        self.setObjectName("btn_hamburger")
        self.setToolTip("Options Menu")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(36, 32)
        self.setStyleSheet("""
            QPushButton#btn_hamburger {
                background-color: #FFC0CB;
                border: 1px solid #FF69B4;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                color: #800020;
                padding: 0px;
                text-align: center;
            }
            QPushButton#btn_hamburger:hover {
                background-color: #FF69B4;
                color: white;
            }
            QPushButton#btn_hamburger[active="true"] {
                background-color: #FF69B4;
                color: white;
            }
        """)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.hovered.emit()


class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(180)
        self.setObjectName("sidebar_root")
        self.setStyleSheet("""
            QWidget#sidebar_root { background-color: #FFB6C1; }
            QScrollArea { background-color: #FFB6C1; border: none; }
            QWidget#sidebar_container { background-color: #FFB6C1; }
            QPushButton {
                background-color: #FFC0CB;
                border: 1px solid #FF69B4;
                padding: 10px;
                text-align: left;
                font-weight: bold;
                color: black;
            }
            QPushButton:hover { background-color: #FF69B4; color: white; }
            QPushButton[active="true"] { background-color: #FF69B4; color: white; }
            QLabel { font-weight: bold; padding: 10px; color: #B03060; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.container.setObjectName("sidebar_container")
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Bottom-left container for hamburger button
        self.bottom_bar = QWidget()
        self.bottom_bar.setObjectName("sidebar_bottom_bar")
        self.bottom_bar.setStyleSheet("background-color: #FFB6C1;")
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(12, 6, 12, 12)
        bottom_layout.setSpacing(0)
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.btn_hamburger = HamburgerButton()
        bottom_layout.addWidget(self.btn_hamburger)
        layout.addWidget(self.bottom_bar, stretch=0)


class TaskWidget(QWidget):
    def __init__(self, description, task_id, state_change_callback=None):
        super().__init__()
        self.task_id = task_id
        self.state_change_callback = state_change_callback
        self.states = ["⏳", "❌", "✅", "➖"]
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_desc = QLabel(description)
        self.btn_state = QPushButton(self.states[0])
        self.btn_state.setFixedWidth(40)
        self.btn_state.clicked.connect(self.show_status_menu)
        
        layout.addWidget(self.lbl_desc)
        layout.addStretch()
        layout.addWidget(self.btn_state)

    def show_status_menu(self):
        menu = QMenu(self)
        for state in self.states:
            action = menu.addAction(state)
            action.triggered.connect(lambda checked=False, s=state: self.set_state(s))
        menu.exec(self.btn_state.mapToGlobal(self.btn_state.rect().bottomLeft()))

    def set_state(self, state):
        self.btn_state.setText(state)
        log_task(f"{state} {self.lbl_desc.text()}", "STATE_CHANGED")
        if self.state_change_callback:
            self.state_change_callback(state, self.task_id, self.lbl_desc.text())


class OfficeViewer(QWidget):
    file_saved_and_closed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.office_app = None
        self.doc = None
        self.office_hwnd = None
        self.current_filepath = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hide()

    def open_file(self, filepath):
        self.close_file()
        self.current_filepath = os.path.abspath(filepath)
        ext = os.path.splitext(filepath)[1].lower()
        
        try:
            if ext in ['.doc', '.docx']:
                self.office_app = win32com.client.DispatchEx("Word.Application")
                self.office_app.WindowState = 0 
                self.office_app.Visible = True
                self.doc = self.office_app.Documents.Open(self.current_filepath)
                try:
                    self.office_app.ActiveWindow.ActivePane.View.Zoom.Percentage = 70
                except Exception:
                    pass
                self.office_hwnd = self.office_app.ActiveWindow.Hwnd
            elif ext in ['.csv', '.xls', '.xlsx']:
                self.office_app = win32com.client.DispatchEx("Excel.Application")
                self.office_app.WindowState = -4143 
                self.office_app.Visible = True
                self.doc = self.office_app.Workbooks.Open(self.current_filepath)
                self.office_hwnd = self.office_app.Hwnd
                
            if self.office_hwnd:
                win32gui.SetParent(self.office_hwnd, int(self.winId()))
                style = win32gui.GetWindowLong(self.office_hwnd, win32con.GWL_STYLE)
                style = style & ~win32con.WS_CAPTION & ~win32con.WS_THICKFRAME & ~win32con.WS_SYSMENU
                win32gui.SetWindowLong(self.office_hwnd, win32con.GWL_STYLE, style)
                QTimer.singleShot(500, self.resize_office_window)
            self.show()
        except Exception as e:
            print(f"System Error (open_file): {e}")

    def save_file(self):
        if self.doc:
            try:
                self.doc.Save()
            except:
                pass

    def close_file(self):
        if self.doc:
            try:
                self.doc.Close(False)
            except:
                pass
            self.doc = None
            
        if self.office_app:
            try:
                self.office_app.Quit()
            except:
                pass
            self.office_app = None
            
        self.office_hwnd = None
        self.hide()

    def save_and_close(self):
        fp = self.current_filepath
        self.save_file()
        self.close_file()
        if fp:
            self.file_saved_and_closed.emit(fp)

    def resize_office_window(self):
        if self.office_hwnd:
            ratio = self.devicePixelRatioF()
            w = int(self.width() * ratio)
            h = int(self.height() * ratio)
            win32gui.SetWindowPos(
                self.office_hwnd, 
                win32con.HWND_TOP, 
                0, 0, w, h, 
                win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_office_window()


class ConfigurationWidget(QWidget):
    """
    Configuration View:
    - Real-time timestamp and operational date display for the active In-House List.
    - Safe hotel database purge ("Clear Hotel Database").
    - Validated in-house file ingestion ("Load In-House List") with report timestamp security check.
    - System configuration inputs and database topology paths.
    """
    data_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_timestamp_display()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(16)

        lbl_title = QLabel("⚙️ SYSTEM CONFIGURATION & HOTEL DATABASE CONTROLS")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Configure workspace directory topology, active property targeting, and in-house database state.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #555555;")
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # 1. In-House State & Ingestion Actions Group
        grp_db = QGroupBox("Active In-House Database State & Synchronization")
        grp_db.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #800020;
                border: 1px solid #FFB6C1;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        layout_db = QVBoxLayout(grp_db)
        layout_db.setSpacing(12)

        # Timestamp Display Row
        row_ts = QHBoxLayout()
        lbl_ts_title = QLabel("Loaded In-House List:")
        lbl_ts_title.setFixedWidth(160)
        lbl_ts_title.setStyleSheet("font-weight: bold; color: #333333;")
        self.txt_timestamp = QLineEdit("No In-House List Loaded")
        self.txt_timestamp.setReadOnly(True)
        self.txt_timestamp.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 6px 10px; border: 1px solid #FECACA; border-radius: 4px;")
        row_ts.addWidget(lbl_ts_title)
        row_ts.addWidget(self.txt_timestamp)
        layout_db.addLayout(row_ts)

        # Action Buttons Row
        row_actions = QHBoxLayout()
        row_actions.setSpacing(10)

        self.btn_load_inhouse = QPushButton("📂 Load In-House List")
        self.btn_load_inhouse.setStyleSheet("""
            QPushButton {
                background-color: #1E3A8A;
                color: white;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        self.btn_load_inhouse.clicked.connect(self.load_inhouse_list)

        self.btn_clear_db = QPushButton("🗑️ Clear Hotel Database")
        self.btn_clear_db.setStyleSheet("""
            QPushButton {
                background-color: #B91C1C;
                color: white;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #DC2626; }
        """)
        self.btn_clear_db.clicked.connect(self.clear_hotel_database)

        self.btn_export_blocks = QPushButton("🔄 Refresh Block Exports")
        self.btn_export_blocks.setStyleSheet("""
            QPushButton {
                background-color: #065F46;
                color: white;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_export_blocks.clicked.connect(self.refresh_block_exports)

        row_actions.addWidget(self.btn_load_inhouse)
        row_actions.addWidget(self.btn_clear_db)
        row_actions.addWidget(self.btn_export_blocks)
        row_actions.addStretch()
        layout_db.addLayout(row_actions)

        main_layout.addWidget(grp_db)

        # 2. System Configuration Inputs
        grp_sys = QGroupBox("System Configuration Inputs")
        grp_sys.setStyleSheet("QGroupBox { font-weight: bold; color: #800020; border: 1px solid #FFB6C1; border-radius: 6px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_sys = QVBoxLayout(grp_sys)
        layout_sys.setSpacing(10)

        row_prop = QHBoxLayout()
        lbl_prop = QLabel("Active Property Target:")
        lbl_prop.setFixedWidth(200)
        lbl_prop.setStyleSheet("font-weight: bold; color: #333333;")
        self.combo_prop = QComboBox()
        self.combo_prop.addItems(["Sandy Beach (Exclusive Active Property)"])
        self.combo_prop.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_prop.addWidget(lbl_prop)
        row_prop.addWidget(self.combo_prop)
        row_prop.addStretch()
        layout_sys.addLayout(row_prop)

        row_mode = QHBoxLayout()
        lbl_mode = QLabel("Operational Mode:")
        lbl_mode.setFixedWidth(200)
        lbl_mode.setStyleSheet("font-weight: bold; color: #333333;")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Production (Standard Gatekeeper & Centralized Database)", "Debug / Diagnostic"])
        self.combo_mode.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_mode.addWidget(lbl_mode)
        row_mode.addWidget(self.combo_mode)
        row_mode.addStretch()
        layout_sys.addLayout(row_mode)

        main_layout.addWidget(grp_sys)

        # 3. Directory Paths Topology
        grp_paths = QGroupBox("Standardized Database Topology")
        grp_paths.setStyleSheet("QGroupBox { font-weight: bold; color: #800020; border: 1px solid #FFB6C1; border-radius: 6px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_paths = QVBoxLayout(grp_paths)
        layout_paths.setSpacing(8)

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
            l.setFixedWidth(200)
            l.setStyleSheet("font-weight: bold; color: #555555;")
            val = QLineEdit(p_val)
            val.setReadOnly(True)
            val.setStyleSheet("background-color: #F8F9FA; padding: 4px 8px; border: 1px solid #DDD; border-radius: 4px;")
            r_box.addWidget(l)
            r_box.addWidget(val)
            layout_paths.addLayout(r_box)

        main_layout.addWidget(grp_paths)
        main_layout.addStretch()

    def refresh_timestamp_display(self):
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

    def load_inhouse_list(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select In-House List",
            BASE_DIR,
            "In-House Files (*.xlsx *.xls *.csv);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*.*)"
        )
        if not file_path:
            return

        # 4. Timestamp Security & Ingestion Validator
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

    def clear_hotel_database(self):
        reply = QMessageBox.question(
            self,
            "Clear Hotel Database?",
            "Are you sure you want to clear the Hotel Database?\n\n"
            "This will purge all transient room and guest records from DATABASE/HOTEL STATE/ "
            "and reset current occupancy states. Templates and system configuration will remain intact.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.data_manager.purge_hotel_database()
                self.refresh_timestamp_display()
                self.data_updated.emit()
                QMessageBox.information(
                    self,
                    "Database Cleared",
                    "Hotel transient database and occupancy states have been reset successfully."
                )
            except Exception as e:
                QMessageBox.critical(self, "Purge Error", f"Failed to clear hotel database:\n{str(e)}")

    def refresh_block_exports(self):
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


# =============================================================================
# Option: 📊 STATS (Live Operational Metrics & Analytical Dashboard)
# =============================================================================

class StatsWidget(QWidget):
    """
    Dedicated view displaying live operational metrics and analytical visualizations:
      - 4-Chart Matplotlib Analytics Suite:
          1. Occupancy Rate per Room Block (bar chart)
          2. Room Category Distribution (donut chart)
          3. Arrivals vs. In-House vs. Departures (turnover chart)
          4. Geographic / Agency Breakdown (horizontal bar chart)
      - KPI summary cards
      - Active In-House Guest Manifest table with search filter
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_stats()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        top_bar = QHBoxLayout()
        v_title = QVBoxLayout()
        lbl_title = QLabel("📊 OPERATIONAL METRICS & HOTEL ANALYTICS")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Real-time occupancy analytics, room block performance, turnover, and market breakdown.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #555555;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        top_bar.addLayout(v_title)
        top_bar.addStretch()

        btn_refresh = QPushButton("🔄 Refresh Analytics")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #800020;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #B03060; }
        """)
        btn_refresh.clicked.connect(self.refresh_stats)
        top_bar.addWidget(btn_refresh)
        layout.addLayout(top_bar)

        # KPI Cards Row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self.card_inhouse = self._create_kpi_card("👥 Active In-House", "0 Bookings", "0 Guests", "#1E3A8A")
        self.card_checkouts = self._create_kpi_card("🚪 Check-Outs", "0 Today", "0 Total Archived", "#065F46")
        self.card_moves = self._create_kpi_card("🔄 Room Moves", "0 Moves", "Archived History", "#B45309")
        self.card_sync = self._create_kpi_card("⏱️ Last In-House Sync", "Never", "No records", "#4338CA")

        kpi_row.addWidget(self.card_inhouse)
        kpi_row.addWidget(self.card_checkouts)
        kpi_row.addWidget(self.card_moves)
        kpi_row.addWidget(self.card_sync)
        layout.addLayout(kpi_row)

        # Tabs: Analytics Dashboard vs Guest Manifest Table
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #FFB6C1; background: white; border-radius: 6px; }
            QTabBar::tab { background: #FFE4E1; border: 1px solid #FFB6C1; padding: 8px 18px; margin-right: 3px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #800020; color: white; border-color: #800020; }
        """)

        # Tab 1: Matplotlib Charts Canvas
        self.tab_charts = QWidget()
        tc_layout = QVBoxLayout(self.tab_charts)
        tc_layout.setContentsMargins(4, 4, 4, 4)

        self.figure = Figure(figsize=(11, 7), dpi=100, facecolor="#FAF9F6")
        self.canvas = FigureCanvas(self.figure)
        tc_layout.addWidget(self.canvas)
        self.tabs.addTab(self.tab_charts, "📈 Visual Analytics Suite")

        # Tab 2: Guest Manifest Table
        self.tab_table = QWidget()
        tt_layout = QVBoxLayout(self.tab_table)
        tt_layout.setContentsMargins(12, 12, 12, 12)
        tt_layout.setSpacing(10)

        tbl_bar = QHBoxLayout()
        lbl_table_header = QLabel("Active In-House Guest Manifest")
        lbl_table_header.setStyleSheet("font-size: 15px; font-weight: bold; color: #2C3E50;")
        tbl_bar.addWidget(lbl_table_header)
        tbl_bar.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Filter Room, Guest, or Booking ID...")
        self.txt_search.setFixedWidth(260)
        self.txt_search.setStyleSheet("padding: 5px 8px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        self.txt_search.textChanged.connect(self._filter_table)
        tbl_bar.addWidget(self.txt_search)
        tt_layout.addLayout(tbl_bar)

        self.table_inhouse = QTableWidget(0, 6)
        self.table_inhouse.setHorizontalHeaderLabels([
            "Room", "Booking ID", "Guest Name(s)", "Arrival", "Departure", "Debtor / Agency"
        ])
        self.table_inhouse.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.setAlternatingRowColors(True)
        tt_layout.addWidget(self.table_inhouse)

        self.tabs.addTab(self.tab_table, "📋 Guest Manifest Table")
        layout.addWidget(self.tabs, stretch=1)

    def _create_kpi_card(self, title: str, main_stat: str, sub_stat: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-top: 4px solid {accent_color};
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(4)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {accent_color};")
        lbl_m = QLabel(main_stat)
        lbl_m.setStyleSheet("font-size: 20px; font-weight: bold; color: #1E293B;")
        lbl_s = QLabel(sub_stat)
        lbl_s.setStyleSheet("font-size: 11px; color: #64748B;")

        card.lbl_title = lbl_t
        card.lbl_main = lbl_m
        card.lbl_sub = lbl_s

        c_layout.addWidget(lbl_t)
        c_layout.addWidget(lbl_m)
        c_layout.addWidget(lbl_s)
        return card

    def refresh_stats(self):
        master = self.data_manager.load_master_state()
        meta = self.data_manager.load_metadata()
        checkouts = self.data_manager.load_checkouts_history()
        moves = self.data_manager.load_room_moves_history()
        arrivals = self.data_manager.load_arrivals_state()

        # In-House Counts
        total_bookings = len(master)
        total_guests = sum(
            len(b.get("Πελάτες", [])) if isinstance(b.get("Πελάτες"), list) else 1
            for b in master.values()
        )
        self.card_inhouse.lbl_main.setText(f"{total_bookings} Bookings")
        self.card_inhouse.lbl_sub.setText(f"{total_guests} Total In-House Guests")

        # Checkouts
        co_records = checkouts.get("records", []) if isinstance(checkouts, dict) else []
        today_str = date.today().strftime("%d/%m/%Y")
        today_cos = sum(1 for c in co_records if str(c.get("checkout_date", "")).startswith(today_str))
        self.card_checkouts.lbl_main.setText(f"{today_cos} Today")
        self.card_checkouts.lbl_sub.setText(f"{len(co_records)} Total Archived")

        # Moves
        self.card_moves.lbl_main.setText(f"{len(moves)} Moves")
        self.card_moves.lbl_sub.setText("Archived in room_moves.json")

        # Last Sync
        last_dt = meta.get("last_sync_date") or meta.get("last_processed_date") or "Not Synced"
        last_ts = meta.get("last_updated_at", "")
        if "T" in str(last_ts):
            last_ts = str(last_ts).split(".")[0].replace("T", " ")
        self.card_sync.lbl_main.setText(str(last_dt))
        self.card_sync.lbl_sub.setText(f"Updated: {last_ts}" if last_ts else "No update timestamp")

        # Populate Manifest Table
        self.table_inhouse.setRowCount(0)
        sorted_bookings = sorted(
            master.items(),
            key=lambda x: (not str(x[1].get("Δωμάτιο", "")).isdigit(), int(x[1].get("Δωμάτιο", 0)) if str(x[1].get("Δωμάτιο", "")).isdigit() else str(x[1].get("Δωμάτιο", "")))
        )
        for b_id, b_data in sorted_bookings:
            r = self.table_inhouse.rowCount()
            self.table_inhouse.insertRow(r)
            self.table_inhouse.setItem(r, 0, QTableWidgetItem(str(b_data.get("Δωμάτιο", ""))))
            self.table_inhouse.setItem(r, 1, QTableWidgetItem(str(b_id)))
            g_list = b_data.get("Πελάτες", [])
            g_str = ", ".join(g_list) if isinstance(g_list, list) else str(g_list)
            self.table_inhouse.setItem(r, 2, QTableWidgetItem(g_str))
            self.table_inhouse.setItem(r, 3, QTableWidgetItem(str(b_data.get("Άφιξη", ""))))
            self.table_inhouse.setItem(r, 4, QTableWidgetItem(str(b_data.get("Αναχώρηση", ""))))
            self.table_inhouse.setItem(r, 5, QTableWidgetItem(str(b_data.get("Χρεώστης", b_data.get("agency", "")))))

        # Re-render Matplotlib 4-Chart Suite
        self._render_charts(master, arrivals, checkouts)

    def _render_charts(self, master: Dict[str, Any], arrivals: Dict[str, Any], checkouts: Dict[str, Any]):
        self.figure.clear()

        # 2x2 Subplots Grid
        axs = self.figure.subplots(2, 2)
        ax1, ax2 = axs[0, 0], axs[0, 1]
        ax3, ax4 = axs[1, 0], axs[1, 1]

        # ---------------------------------------------------------------------
        # Chart 1: Occupancy Rate per Room Block (1100 to 8000)
        # ---------------------------------------------------------------------
        target_blocks = [
            "BLOCK 1100", "BLOCK 1200", "BLOCK 1300", "BLOCK 1400",
            "BLOCK 1500", "BLOCK 1600", "BLOCK 1700", "BLOCK 1800",
            "BLOCK 1900", "BLOCK 2000", "BLOCK 3000", "BLOCK 4000",
            "BLOCK 5000", "BLOCK 6000", "BLOCK 7000", "BLOCK 8000"
        ]
        labels = [b.replace("BLOCK ", "") for b in target_blocks]
        percentages = []
        bar_colors = []

        for b_name in target_blocks:
            slug = re.sub(r"[^\w\d]+", "_", b_name.strip()).strip("_")
            b_file = Path(PLOT_DIR) / slug / f"{slug}.json"
            pct = 0.0
            if b_file.exists():
                try:
                    with open(b_file, "r", encoding="utf-8") as f:
                        b_data = json.load(f)
                        pct = float(b_data.get("occupancy_metrics", {}).get("occupancy_percentage", 0.0))
                except Exception:
                    pass
            percentages.append(pct)
            if pct < 75:
                bar_colors.append("#2563EB")
            elif pct < 90:
                bar_colors.append("#D97706")
            else:
                bar_colors.append("#DC2626")

        bars = ax1.bar(labels, percentages, color=bar_colors, width=0.65, edgecolor="#1E293B", linewidth=0.5)
        ax1.set_title("Occupancy Rate per Room Block (%)", fontsize=10, fontweight="bold", color="#800020", pad=6)
        ax1.set_ylim(0, 115)
        ax1.set_ylabel("Occupancy %", fontsize=8, color="#475569")
        ax1.tick_params(axis="x", rotation=45, labelsize=7.5)
        ax1.tick_params(axis="y", labelsize=7.5)
        ax1.grid(axis="y", linestyle="--", alpha=0.4)
        for bar, pct in zip(bars, percentages):
            ax1.text(bar.get_x() + bar.get_width() / 2.0, bar.get_height() + 2, f"{pct:.0f}%",
                     ha="center", va="bottom", fontsize=6.5, fontweight="bold", color="#1E293B")

        # ---------------------------------------------------------------------
        # Chart 2: Room Category Distribution (Donut Chart)
        # ---------------------------------------------------------------------
        room_types = collections.Counter()
        for b in master.values():
            rtype = b.get("Τύπος Δωμ") or b.get("Κρατηθείς Τύπος") or "Other"
            guests_cnt = len(b.get("Πελάτες", [])) if isinstance(b.get("Πελάτες"), list) else 1
            room_types[rtype] += guests_cnt

        if room_types:
            top_types = room_types.most_common(6)
            other_cnt = sum(c for _, c in room_types.most_common()[6:])
            if other_cnt > 0:
                top_types.append(("Other", other_cnt))
            pie_labels = [k for k, _ in top_types]
            pie_vals = [v for _, v in top_types]
            colors = ["#2563EB", "#7C3AED", "#059669", "#D97706", "#DC2626", "#EC4899", "#64748B"]
            wedges, texts, autotexts = ax2.pie(
                pie_vals, labels=pie_labels, autopct="%1.0f%%", pctdistance=0.75,
                colors=colors[:len(pie_vals)], wedgeprops=dict(width=0.45, edgecolor="white", linewidth=1.5),
                textprops=dict(fontsize=7.5, fontweight="bold")
            )
            for at in autotexts:
                at.set_fontsize(7)
                at.set_color("white")
            ax2.set_title("Guest Room Category Distribution", fontsize=10, fontweight="bold", color="#800020", pad=6)
        else:
            ax2.text(0.5, 0.5, "No In-House Data", ha="center", va="center", color="#94A3B8")
            ax2.set_title("Guest Room Category Distribution", fontsize=10, fontweight="bold", color="#800020")

        # ---------------------------------------------------------------------
        # Chart 3: Operational Turnover (Arrivals vs. In-House vs. Departures)
        # ---------------------------------------------------------------------
        arr_cnt = 0
        if isinstance(arrivals, dict):
            arr_bookings = arrivals.get("bookings", arrivals.get("arrivals", {}))
            arr_cnt = len(arr_bookings) if isinstance(arr_bookings, dict) else len(arrivals)

        inhouse_cnt = len(master)

        co_records = checkouts.get("records", []) if isinstance(checkouts, dict) else []
        today_str = date.today().strftime("%d/%m/%Y")
        today_cos = sum(1 for c in co_records if str(c.get("checkout_date", "")).startswith(today_str))

        flow_labels = ["Arrivals", "In-House", "Departures"]
        flow_vals = [arr_cnt, inhouse_cnt, today_cos]
        flow_colors = ["#3B82F6", "#10B981", "#EF4444"]

        f_bars = ax3.bar(flow_labels, flow_vals, color=flow_colors, width=0.55, edgecolor="#1E293B", linewidth=0.5)
        ax3.set_title("Operational Turnover Overview", fontsize=10, fontweight="bold", color="#800020", pad=6)
        ax3.set_ylabel("Count", fontsize=8, color="#475569")
        ax3.tick_params(axis="x", labelsize=8)
        ax3.tick_params(axis="y", labelsize=7.5)
        ax3.grid(axis="y", linestyle="--", alpha=0.4)
        for bar, val in zip(f_bars, flow_vals):
            ax3.text(bar.get_x() + bar.get_width() / 2.0, bar.get_height() + (max(flow_vals) * 0.02 + 1), str(val),
                     ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#1E293B")
        if max(flow_vals) > 0:
            ax3.set_ylim(0, max(flow_vals) * 1.18)

        # ---------------------------------------------------------------------
        # Chart 4: Geographic / Agency / Market Breakdown
        # ---------------------------------------------------------------------
        agencies = collections.Counter()
        for b in master.values():
            agency = b.get("Χρεώστης") or b.get("agency") or "Unknown"
            guests_cnt = len(b.get("Πελάτες", [])) if isinstance(b.get("Πελάτες"), list) else 1
            agencies[agency] += guests_cnt

        if agencies:
            top_agencies = agencies.most_common(7)
            top_agencies.reverse()
            ag_names = [a[0][:20] + "..." if len(a[0]) > 20 else a[0] for a in top_agencies]
            ag_counts = [a[1] for a in top_agencies]
            h_bars = ax4.barh(ag_names, ag_counts, color="#4F46E5", height=0.6, edgecolor="#1E293B", linewidth=0.5)
            ax4.set_title("Top Debtor / Agency Distribution", fontsize=10, fontweight="bold", color="#800020", pad=6)
            ax4.set_xlabel("Guests", fontsize=8, color="#475569")
            ax4.tick_params(axis="y", labelsize=7.5)
            ax4.tick_params(axis="x", labelsize=7.5)
            ax4.grid(axis="x", linestyle="--", alpha=0.4)
            for bar, val in zip(h_bars, ag_counts):
                ax4.text(bar.get_width() + 2, bar.get_y() + bar.get_height() / 2.0, str(val),
                         ha="left", va="center", fontsize=7, fontweight="bold", color="#1E293B")
            if max(ag_counts) > 0:
                ax4.set_xlim(0, max(ag_counts) * 1.15)
        else:
            ax4.text(0.5, 0.5, "No In-House Data", ha="center", va="center", color="#94A3B8")
            ax4.set_title("Top Debtor / Agency Distribution", fontsize=10, fontweight="bold", color="#800020")

        try:
            self.figure.tight_layout(pad=1.8)
        except Exception:
            self.figure.subplots_adjust(top=0.92, bottom=0.08, left=0.08, right=0.95, hspace=0.35, wspace=0.25)
        self.canvas.draw()

    def _filter_table(self):
        query = self.txt_search.text().strip().lower()
        for r in range(self.table_inhouse.rowCount()):
            room = self.table_inhouse.item(r, 0).text().lower()
            b_id = self.table_inhouse.item(r, 1).text().lower()
            guest = self.table_inhouse.item(r, 2).text().lower()
            match = (not query) or (query in room) or (query in b_id) or (query in guest)
            self.table_inhouse.setRowHidden(r, not match)


# =============================================================================
# New Option: 🔄 MOVES (Dedicated Room Moves View)
# =============================================================================

class MovesWidget(QWidget):
    """
    Dedicated view in the main sidebar to inspect rooms that changed yesterday/recently,
    reading directly from DATABASE/ROOM MOVES/room_moves.json.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_moves()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        top_bar = QHBoxLayout()
        v_title = QVBoxLayout()
        lbl_title = QLabel("🔄 ROOM MOVES HISTORY & AUDIT")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Inspect historical room changes for Sandy Beach (merges excluded). Source: DATABASE/ROOM MOVES/room_moves.json")
        lbl_sub.setStyleSheet("font-size: 12px; color: #555555;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        top_bar.addLayout(v_title)
        top_bar.addStretch()

        self.lbl_badge = QLabel("Total Moves: 0")
        self.lbl_badge.setStyleSheet("background-color: #FFF0F5; color: #800020; border: 1px solid #FFB6C1; padding: 6px 14px; border-radius: 4px; font-weight: bold;")
        top_bar.addWidget(self.lbl_badge)

        btn_reload = QPushButton("🔄 Reload Moves")
        btn_reload.setStyleSheet("""
            QPushButton {
                background-color: #800020;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #B03060; }
        """)
        btn_reload.clicked.connect(self.refresh_moves)
        top_bar.addWidget(btn_reload)
        layout.addLayout(top_bar)

        # Search filter
        search_bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Filter Room, Booking ID, or Guest...")
        self.txt_search.setFixedWidth(280)
        self.txt_search.textChanged.connect(self._filter_table)
        search_bar.addWidget(self.txt_search)
        search_bar.addStretch()
        layout.addLayout(search_bar)

        # Moves Table
        self.table_moves = QTableWidget(0, 6)
        self.table_moves.setHorizontalHeaderLabels([
            "Move Date", "Booking ID", "Guest Name(s)", "Previous Room", "New Room", "Departure"
        ])
        self.table_moves.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_moves.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.setAlternatingRowColors(True)
        layout.addWidget(self.table_moves, stretch=1)

    def refresh_moves(self):
        moves_data = self.data_manager.load_room_moves_history()
        self.lbl_badge.setText(f"Total Moves: {len(moves_data)}")

        self.table_moves.setRowCount(0)
        for rm in reversed(moves_data):
            r = self.table_moves.rowCount()
            self.table_moves.insertRow(r)
            self.table_moves.setItem(r, 0, QTableWidgetItem(str(rm.get("date", ""))))
            self.table_moves.setItem(r, 1, QTableWidgetItem(str(rm.get("booking_id", ""))))

            g_names = rm.get("guests", [])
            g_str = ", ".join(g_names) if isinstance(g_names, list) else str(g_names)
            self.table_moves.setItem(r, 2, QTableWidgetItem(g_str))

            # Old Room highlighted red
            item_old = QTableWidgetItem(str(rm.get("old_room", "")))
            item_old.setForeground(QColor("#C0392B"))
            self.table_moves.setItem(r, 3, item_old)

            # New Room highlighted bold green
            item_new = QTableWidgetItem(str(rm.get("new_room", "")))
            item_new.setForeground(QColor("#27AE60"))
            item_new.setFont(QFont("Segoe UI", weight=QFont.Weight.Bold))
            self.table_moves.setItem(r, 4, item_new)

            self.table_moves.setItem(r, 5, QTableWidgetItem(str(rm.get("departure", ""))))

    def _filter_table(self):
        query = self.txt_search.text().strip().lower()
        for r in range(self.table_moves.rowCount()):
            old_r = self.table_moves.item(r, 3).text().lower()
            new_r = self.table_moves.item(r, 4).text().lower()
            b_id = self.table_moves.item(r, 1).text().lower()
            guest = self.table_moves.item(r, 2).text().lower()
            match = (not query) or (query in old_r) or (query in new_r) or (query in b_id) or (query in guest)
            self.table_moves.setRowHidden(r, not match)


# =============================================================================
# Helper: Parse Cake Memo Word Document Table
# =============================================================================

def parse_cake_memo_docx(docx_path: str) -> Dict[str, str]:
    """
    Parses a Cake Memo .docx table and extracts:
      - room_number (from column 'ROOM NUMBER' or data row)
      - cake_location (ERMIS, IL GUSTO, ELIA, AMMOS, or ROOM)
      - cake_time (e.g. 14:00, 20:30, 7:00 PM, 19.30PM)
      - cake_date_display (dd/MM)
      - cake_date_file (dd.MM.yyyy)
      - memo_month_year (MM.yyyy)
    """
    doc = docx.Document(docx_path)
    room_number = ""
    provided_at_text = ""
    date_text = ""

    for table in doc.tables:
        if not table.rows:
            continue
        header_cells = [c.text.strip().upper().replace("\n", " ") for c in table.rows[0].cells]

        col_room = -1
        col_provided = -1
        col_date = -1

        for idx, h in enumerate(header_cells):
            if "ROOM" in h:
                col_room = idx
            elif "PROVIDED" in h or "AT" in h:
                col_provided = idx
            elif "DATE" in h:
                col_date = idx

        if col_room == -1 and len(header_cells) >= 7:
            col_room = 6
        if col_provided == -1 and len(header_cells) >= 4:
            col_provided = 3
        if col_date == -1 and len(header_cells) >= 5:
            col_date = 4

        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if not any(cells):
                continue

            r_val = cells[col_room] if 0 <= col_room < len(cells) else ""
            p_val = cells[col_provided] if 0 <= col_provided < len(cells) else ""
            d_val = cells[col_date] if 0 <= col_date < len(cells) else ""

            if not r_val:
                for c_text in cells:
                    m_room = re.search(r"\b(\d{3,4})\b", c_text)
                    if m_room:
                        r_val = m_room.group(1)
                        break

            if r_val or p_val or d_val:
                room_number = r_val
                provided_at_text = p_val
                date_text = d_val
                break

    # Parse Location: Look for ERMIS, IL GUSTO, ELIA, AMMOS, or ROOM
    location = "ROOM"
    loc_match = re.search(r"(?i)\b(ERMIS|IL GUSTO|ELIA|AMMOS|ROOM)\b", provided_at_text)
    if loc_match:
        location = loc_match.group(1).upper()

    # Parse Time: e.g., 14:00, 20:30, 7:00 PM, 19.30PM
    time_match = re.search(r"(\b\d{1,2}[:.]\d{2}\s*(?:AM|PM|am|pm)?|\b\d{1,2}\s*(?:AM|PM|am|pm)\b)", provided_at_text)
    time_val = time_match.group(1) if time_match else "N/A"

    # Normalize Date
    now = datetime.now()
    date_match = re.search(r"(\d{1,2})[\/\.\-](\d{1,2})", date_text)
    if date_match:
        d_day = int(date_match.group(1))
        d_month = int(date_match.group(2))
        cake_date_display = f"{d_day:02d}/{d_month:02d}"
        cake_date_file = f"{d_day:02d}.{d_month:02d}.{now.year}"
        memo_month_year = f"{d_month:02d}.{now.year}"
    else:
        cake_date_display = now.strftime("%d/%m")
        cake_date_file = now.strftime("%d.%m.%Y")
        memo_month_year = now.strftime("%m.%Y")

    if not room_number:
        room_number = "UNKNOWN"

    return {
        "room_number": room_number,
        "cake_location": location,
        "cake_time": time_val,
        "cake_date_display": cake_date_display,
        "cake_date_file": cake_date_file,
        "memo_month_year": memo_month_year
    }


def create_cake_memo_outlook_draft(docx_path: str, memo_data: Dict[str, str]):
    """Generates an Outlook draft with the specified recipients, subject, and formatted HTML body."""
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)

    to_recipients = (
        "Executive Chef Sandy Beach <chef.sandybeach@rizosresorts.gr>; "
        "headchef.sandybeach@rizosresorts.gr; "
        "F&B Manager Sandy Beach <gabriela.stere@rizosresorts.gr>; "
        "assistfb.sandybeach@rizosresorts.gr; "
        "assistfb2.sandybeach@rizosresorts <assistfb2.sandybeach@rizosresorts.gr>;"
    )

    cc_recipients = (
        "Operation Manager <Mariela.Tsvetkova@rizosresorts.gr>; "
        "Rooms Division Manager - Sandy Beach <harrys.palikiras@rizosresorts.gr>; "
        "Front Office Manager Sandy Beach <fom.sandy@rizosresorts.gr>; "
        "Guest Relations Sandy Beach <guest.sandybeach@rizosresorts.gr>;"
    )

    room_number = memo_data["room_number"]
    cake_date = memo_data["cake_date_display"]
    cake_location = memo_data["cake_location"]
    cake_time = memo_data["cake_time"]

    subject = f"CAKE MEMO {cake_date} R{room_number}"

    html_body = f"""<div style='font-family: Calibri, sans-serif; font-size: 11pt;'>
  Dear all,<br>Kindly find attached the Cake Memo for Room {room_number}.<br><br>
  <b>Service Details:</b><br>
  &bull; <b>Date:</b> {cake_date}<br>
  &bull; <b>Location:</b> {cake_location}<br>
  &bull; <b>Time:</b> {cake_time}<br><br>
  For any further information don’t hesitate to contact the Guest Relations Team.
</div>"""

    mail.To = to_recipients
    mail.CC = cc_recipients
    mail.Subject = subject
    mail.HTMLBody = html_body + mail.HTMLBody
    mail.Attachments.Add(os.path.abspath(docx_path))
    mail.Display()
    return mail


# =============================================================================
# System Data Records Widget (Updated Standardized Paths)
# =============================================================================

class SystemDataRecordsWidget(QWidget):
    """
    Landing Page Data Records Dashboard:
    Direct inspection of active state and historical datasets stored in DATABASE/.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        lbl_title = QLabel("📁 SYSTEM DATA & STATE RECORDS")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Centralized inspection of datasets persisted strictly within the DATABASE/ directory hierarchy.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #666666;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.btn_refresh = QPushButton("🔄 Reload from DATABASE/")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
                color: #800020;
            }
            QPushButton:hover { background-color: #FF69B4; color: white; }
        """)
        self.btn_refresh.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.btn_refresh)
        main_layout.addLayout(header_layout)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #FFB6C1; background-color: #FFFFFF; border-radius: 6px; }
            QTabBar::tab { background-color: #FFE4E1; border: 1px solid #FFB6C1; padding: 8px 14px; margin-right: 3px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #FF69B4; color: #FFFFFF; }
        """)

        # Tab 1: Master State & Metadata
        tab_master = QWidget()
        layout_master = QVBoxLayout(tab_master)
        self.lbl_master_stats = QLabel("Loading Master State...")
        self.lbl_master_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_master.addWidget(self.lbl_master_stats)

        self.table_master = QTableWidget(0, 6)
        self.table_master.setHorizontalHeaderLabels(["Booking ID", "Room", "Guest(s)", "Arrival", "Departure", "Agency"])
        self.table_master.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout_master.addWidget(self.table_master)
        self.tab_widget.addTab(tab_master, "👥 Master State & Metadata")

        # Tab 2: Sandy Beach Arrivals
        tab_beach = QWidget()
        layout_beach = QVBoxLayout(tab_beach)
        self.lbl_beach_stats = QLabel("Loading Sandy Beach Arrivals...")
        self.lbl_beach_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_beach.addWidget(self.lbl_beach_stats)

        self.table_beach_arrivals = QTableWidget(0, 6)
        self.table_beach_arrivals.setHorizontalHeaderLabels(["Room", "Guest(s)", "Adults", "Kids", "Arrival", "Agency"])
        self.table_beach_arrivals.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout_beach.addWidget(self.table_beach_arrivals)
        self.tab_widget.addTab(tab_beach, "🏖️ Sandy Beach Arrivals")

        # Tab 3: Room Moves
        tab_moves = QWidget()
        layout_moves = QVBoxLayout(tab_moves)
        self.lbl_moves_stats = QLabel("Loading Room Moves...")
        self.lbl_moves_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_moves.addWidget(self.lbl_moves_stats)

        self.table_moves = QTableWidget(0, 6)
        self.table_moves.setHorizontalHeaderLabels(["Date", "Booking ID", "Guest(s)", "Previous Room", "New Room", "Departure"])
        self.table_moves.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout_moves.addWidget(self.table_moves)
        self.tab_widget.addTab(tab_moves, "🔄 Room Moves History")

        # Tab 4: Checkout Records
        tab_checkouts = QWidget()
        layout_checkouts = QVBoxLayout(tab_checkouts)
        self.lbl_checkouts_stats = QLabel("Loading Checkouts...")
        self.lbl_checkouts_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_checkouts.addWidget(self.lbl_checkouts_stats)

        self.table_checkouts = QTableWidget(0, 5)
        self.table_checkouts.setHorizontalHeaderLabels(["Checkout Date", "Booking ID", "Guest(s)", "Room", "Departure"])
        self.table_checkouts.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout_checkouts.addWidget(self.table_checkouts)
        self.tab_widget.addTab(tab_checkouts, "🚪 Checkout Records")

        main_layout.addWidget(self.tab_widget)
        self.tabs = self.tab_widget

    def load_all_records(self):
        self.refresh_data()

    def refresh_data(self):
        master = self.data_manager.load_master_state()
        meta = self.data_manager.load_metadata()
        bookings_dict = {k: v for k, v in master.items() if isinstance(v, dict)}
        last_dt = meta.get("last_sync_date") or meta.get("last_processed_date") or "N/A"
        last_ts = meta.get("last_updated_at", "N/A")
        if "T" in str(last_ts):
            last_ts = str(last_ts).split(".")[0].replace("T", " ")

        self.lbl_master_stats.setText(
            f"Active Bookings: {len(bookings_dict)} | Last In-House Sync: {last_dt} | Last Timestamp: {last_ts} | File: DATABASE/HOTEL STATE/master_state.json"
        )
        self.table_master.setRowCount(0)
        for b_id, b_data in bookings_dict.items():
            r = self.table_master.rowCount()
            self.table_master.insertRow(r)
            self.table_master.setItem(r, 0, QTableWidgetItem(str(b_id)))
            self.table_master.setItem(r, 1, QTableWidgetItem(str(b_data.get("Δωμάτιο", ""))))
            guests = b_data.get("Πελάτες", [])
            g_str = ", ".join(guests) if isinstance(guests, list) else str(guests)
            self.table_master.setItem(r, 2, QTableWidgetItem(g_str))
            self.table_master.setItem(r, 3, QTableWidgetItem(str(b_data.get("Άφιξη", ""))))
            self.table_master.setItem(r, 4, QTableWidgetItem(str(b_data.get("Αναχώρηση", ""))))
            self.table_master.setItem(r, 5, QTableWidgetItem(str(b_data.get("Χρεώστης", b_data.get("agency", "")))))

        arr_state = self.data_manager.load_arrivals_state()
        beach_arr = arr_state.get("SANDY BEACH", {})
        self.lbl_beach_stats.setText(f"Sandy Beach Arrivals: {len(beach_arr)} | File: DATABASE/SANDY BEACH/ARRIVALS/today_arrivals.json")
        self.table_beach_arrivals.setRowCount(0)
        for b_id, r_info in beach_arr.items():
            r = self.table_beach_arrivals.rowCount()
            self.table_beach_arrivals.insertRow(r)
            self.table_beach_arrivals.setItem(r, 0, QTableWidgetItem(str(r_info.get("room", ""))))
            g_names = ", ".join(r_info.get("guests", [])) if isinstance(r_info.get("guests"), list) else str(r_info.get("guests", ""))
            self.table_beach_arrivals.setItem(r, 1, QTableWidgetItem(g_names))
            self.table_beach_arrivals.setItem(r, 2, QTableWidgetItem(str(r_info.get("adults", ""))))
            self.table_beach_arrivals.setItem(r, 3, QTableWidgetItem(str(r_info.get("children", ""))))
            self.table_beach_arrivals.setItem(r, 4, QTableWidgetItem(str(r_info.get("arrival", ""))))
            self.table_beach_arrivals.setItem(r, 5, QTableWidgetItem(str(r_info.get("agency", ""))))

        moves_data = self.data_manager.load_room_moves_history()
        self.lbl_moves_stats.setText(f"Archived Room Moves: {len(moves_data)} | File: DATABASE/ROOM MOVES/room_moves.json")
        self.table_moves.setRowCount(0)
        for rm in moves_data:
            r = self.table_moves.rowCount()
            self.table_moves.insertRow(r)
            self.table_moves.setItem(r, 0, QTableWidgetItem(str(rm.get("date", ""))))
            self.table_moves.setItem(r, 1, QTableWidgetItem(str(rm.get("booking_id", ""))))
            g_names = rm.get("guests", [])
            g_str = ", ".join(g_names) if isinstance(g_names, list) else str(g_names)
            self.table_moves.setItem(r, 2, QTableWidgetItem(g_str))
            self.table_moves.setItem(r, 3, QTableWidgetItem(str(rm.get("old_room", ""))))
            self.table_moves.setItem(r, 4, QTableWidgetItem(str(rm.get("new_room", ""))))
            self.table_moves.setItem(r, 5, QTableWidgetItem(str(rm.get("departure", ""))))

        co_payload = self.data_manager.load_checkouts_history()
        records = co_payload.get("records", [])
        self.lbl_checkouts_stats.setText(f"Archived Check-Outs: {len(records)} | File: DATABASE/CHECK OUT HISTORY/checkouts.json")
        self.table_checkouts.setRowCount(0)
        for co in records:
            r = self.table_checkouts.rowCount()
            self.table_checkouts.insertRow(r)
            self.table_checkouts.setItem(r, 0, QTableWidgetItem(str(co.get("checkout_date", ""))))
            self.table_checkouts.setItem(r, 1, QTableWidgetItem(str(co.get("booking_id", ""))))
            g_names = co.get("guests", [])
            g_str = ", ".join(g_names) if isinstance(g_names, list) else str(g_names)
            self.table_checkouts.setItem(r, 2, QTableWidgetItem(g_str))
            self.table_checkouts.setItem(r, 3, QTableWidgetItem(str(co.get("room", ""))))
            self.table_checkouts.setItem(r, 4, QTableWidgetItem(str(co.get("departure", ""))))


# =============================================================================
# Main Application Window
# =============================================================================

class GuestRelationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guest Relation Workspace")
        self.resize(1240, 820)
        self.setStyleSheet("QMainWindow { background-color: #FFF0F5; }")
        
        self.plot_window = None
        self.mail_references = []
        self.active_tasks = {}
        self.is_update_mode = False
        self.active_category = None
        
        self.log_categories = [
            "All Activity",
            "To Do List",
            "OFFERS",
            "ALLERGIES",
            "CAKE MEMOS",
            "Booking Calls",
            "ALL DATA"
        ]
        
        self.com_timer = QTimer()
        self.com_timer.timeout.connect(self.pump_com_messages)
        self.com_timer.start(500)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stacked_content = QStackedWidget()
        self.stacked_content.setStyleSheet("QStackedWidget { background-color: #FFF0F5; border-left: 2px solid #FFB6C1; }")

        self.office_viewer = OfficeViewer()
        self.office_viewer.file_saved_and_closed.connect(self.handle_save_and_close)

        self.cake_office_viewer = OfficeViewer()
        self.cake_office_viewer.file_saved_and_closed.connect(self.handle_cake_save_and_close)

        self.sidebar = Sidebar()
        sidebar_layout = QVBoxLayout(self.sidebar.container)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.btn_todo = QPushButton("To Do List")
        self.btn_offers = QPushButton("OFFERS")
        
        # Sub-Menu for OFFERS
        self.offers_submenu = QWidget()
        offers_submenu_layout = QVBoxLayout(self.offers_submenu)
        offers_submenu_layout.setContentsMargins(0, 4, 0, 6)
        offers_submenu_layout.setSpacing(5)
        self.offers_submenu.setStyleSheet("""
            QWidget { background-color: transparent; }
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                border-radius: 4px;
                padding: 7px 10px 7px 20px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                color: black;
                margin-bottom: 2px;
            }
            QPushButton:hover { background-color: #FF69B4; color: white; }
        """)
        
        self.offers_btn_create = QPushButton("Create Offerlist")
        self.offers_btn_update = QPushButton("UPDATE Offerlist")
        self.btn_save = QPushButton("SAVE")
        self.btn_close = QPushButton("CLOSE")
        self.btn_save_close = QPushButton("SAVE & CLOSE")
        
        blue_sub_style = """
            QPushButton {
                background-color: #B0E0E6; 
                border: 1px solid #4682B4; 
                border-radius: 4px;
                padding: 7px 10px 7px 20px; 
                text-align: left; 
                font-size: 11px; 
                font-weight: bold; 
                color: #0F3460;
                margin-bottom: 2px;
            }
            QPushButton:hover { background-color: #4682B4; color: white; }
        """
        self.btn_save.setStyleSheet(blue_sub_style)
        self.btn_close.setStyleSheet(blue_sub_style)
        self.btn_save_close.setStyleSheet(blue_sub_style)

        self.offers_btn_create.clicked.connect(self.run_offers_creation)
        self.offers_btn_update.clicked.connect(self.run_offers_update)
        self.btn_save.clicked.connect(self.handle_doc_save)
        self.btn_close.clicked.connect(self.handle_doc_close)
        self.btn_save_close.clicked.connect(self.office_viewer.save_and_close)

        offers_submenu_layout.addWidget(self.offers_btn_create)
        offers_submenu_layout.addWidget(self.offers_btn_update)
        # Visual separation gap between white and blue buttons
        offers_submenu_layout.addSpacing(14)
        offers_submenu_layout.addWidget(self.btn_save)
        offers_submenu_layout.addWidget(self.btn_close)
        offers_submenu_layout.addWidget(self.btn_save_close)
        self.offers_submenu.hide()

        self.btn_allergies = QPushButton("ALLERGIES")
        self.btn_cake = QPushButton("CAKE MEMOS")

        # Sub-Menu for CAKE MEMOS
        self.cake_submenu = QWidget()
        cake_submenu_layout = QVBoxLayout(self.cake_submenu)
        cake_submenu_layout.setContentsMargins(0, 4, 0, 6)
        cake_submenu_layout.setSpacing(5)
        self.cake_submenu.setStyleSheet(self.offers_submenu.styleSheet())

        self.btn_cake_open_tpl = QPushButton("Open Cake Memo Template")
        self.btn_cake_save = QPushButton("SAVE")
        self.btn_cake_close = QPushButton("CLOSE")
        self.btn_cake_save_close = QPushButton("SAVE & CLOSE (Outlook Draft)")
        
        self.btn_cake_save.setStyleSheet(blue_sub_style)
        self.btn_cake_close.setStyleSheet(blue_sub_style)
        self.btn_cake_save_close.setStyleSheet(blue_sub_style)

        self.btn_cake_open_tpl.clicked.connect(self.open_cake_memo_template)
        self.btn_cake_save.clicked.connect(self.handle_cake_save)
        self.btn_cake_close.clicked.connect(self.handle_cake_close)
        self.btn_cake_save_close.clicked.connect(self.cake_office_viewer.save_and_close)

        cake_submenu_layout.addWidget(self.btn_cake_open_tpl)
        # Visual separation gap between white and blue buttons
        cake_submenu_layout.addSpacing(14)
        cake_submenu_layout.addWidget(self.btn_cake_save)
        cake_submenu_layout.addWidget(self.btn_cake_close)
        cake_submenu_layout.addWidget(self.btn_cake_save_close)
        self.cake_submenu.hide()

        self.btn_booking = QPushButton("BOOKING CALLS")

        # Pop-out Menu triggered by bottom-left hamburger button
        self.popout_menu = QMenu(self)
        self.popout_menu.setObjectName("popout_menu")
        self.popout_menu.setStyleSheet("""
            QMenu {
                background-color: #FFF0F5;
                border: 1px solid #FF69B4;
                border-radius: 6px;
                padding: 4px;
                font-weight: bold;
                font-size: 12px;
                color: #333333;
            }
            QMenu::item {
                padding: 8px 24px 8px 14px;
                border-radius: 4px;
                margin: 2px 0px;
            }
            QMenu::item:selected {
                background-color: #FF69B4;
                color: #FFFFFF;
            }
        """)

        self.action_stats = self.popout_menu.addAction("Stats")
        self.action_plot = self.popout_menu.addAction("Plot")
        self.action_config = self.popout_menu.addAction("Configuration")
        self.action_system_data = self.popout_menu.addAction("System Data Records")
        self.action_logs = self.popout_menu.addAction("Logs")

        self.action_stats.triggered.connect(lambda: self.select_category("STATS"))
        self.action_plot.triggered.connect(self.open_plot_window)
        self.action_config.triggered.connect(lambda: self.select_category("CONFIG"))
        self.action_system_data.triggered.connect(lambda: self.select_category("SYSTEM_DATA"))
        self.action_logs.triggered.connect(lambda: self.select_category("LOGS"))

        self.sidebar.btn_hamburger.clicked.connect(self.show_popout_menu)
        self.sidebar.btn_hamburger.hovered.connect(self.show_popout_menu)

        # Connect Main Sidebar Buttons
        self.btn_todo.clicked.connect(lambda: self.handle_category_click("TODO"))
        self.btn_offers.clicked.connect(lambda: self.handle_category_click("OFFERS"))
        self.btn_allergies.clicked.connect(lambda: self.handle_category_click("ALLERGIES"))
        self.btn_cake.clicked.connect(lambda: self.handle_category_click("CAKE"))
        self.btn_booking.clicked.connect(lambda: self.handle_category_click("BOOKING"))

        self.menu_buttons = [
            self.btn_todo,
            self.btn_offers,
            self.btn_allergies,
            self.btn_cake,
            self.btn_booking,
        ]

        sidebar_layout.addWidget(QLabel("Menu"))
        sidebar_layout.addWidget(self.btn_todo)
        sidebar_layout.addWidget(self.btn_offers)
        sidebar_layout.addWidget(self.offers_submenu)
        sidebar_layout.addWidget(self.btn_allergies)
        sidebar_layout.addWidget(self.btn_cake)
        sidebar_layout.addWidget(self.cake_submenu)
        sidebar_layout.addWidget(self.btn_booking)
        sidebar_layout.addStretch()

        # 0: Configuration View
        self.config_widget = ConfigurationWidget()
        self.stacked_content.addWidget(self.config_widget)

        # 1: STATS View
        self.stats_widget = StatsWidget()
        self.stacked_content.addWidget(self.stats_widget)

        # 2: MOVES View
        self.moves_widget = MovesWidget()
        self.stacked_content.addWidget(self.moves_widget)

        # 3: To Do List View
        self.todo_list = QListWidget()
        self.todo_list.setStyleSheet("background-color: #FFFFFF; color: black; font-weight: bold; font-size: 14px;")
        self.stacked_content.addWidget(self.todo_list)

        # 4: Offers View
        self.offers_view = QWidget()
        offers_layout = QVBoxLayout(self.offers_view)
        offers_layout.setContentsMargins(0, 0, 0, 0)
        offers_layout.setSpacing(0)
        self.offers_status = QLabel("OFFERS PROCESSOR\nTarget: TEMPLATES/OFFER LIST TEMPLATE/")
        self.offers_status.setWordWrap(True)
        self.offers_status.setStyleSheet("font-weight: bold; color: #B03060; padding: 5px;")
        offers_layout.addWidget(self.offers_status)
        offers_layout.addWidget(self.office_viewer, stretch=1)
        self.stacked_content.addWidget(self.offers_view)

        # 5: Allergies Placeholder View
        self.allergies_view = QLabel("ALLERGIES PROCESSOR")
        self.allergies_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stacked_content.addWidget(self.allergies_view)

        # 6: Cake Memos View
        self.cake_view = QWidget()
        cake_layout = QVBoxLayout(self.cake_view)
        cake_layout.setContentsMargins(0, 0, 0, 0)
        cake_layout.setSpacing(0)
        self.cake_status = QLabel("🎂 CAKE MEMOS PROCESSOR\nLoads from: TEMPLATES/CAKE MEMO TEMPLATE/CAKE MEMO.docx")
        self.cake_status.setStyleSheet("font-weight: bold; color: #800020; padding: 8px;")
        cake_layout.addWidget(self.cake_status)
        cake_layout.addWidget(self.cake_office_viewer, stretch=1)
        self.stacked_content.addWidget(self.cake_view)

        # 7: Booking Calls CRM View
        self.booking_calls_widget = BookingCallsWidget()
        self.booking_calls_widget.feedback_submitted.connect(self.handle_booking_feedback_to_todo)
        self.stacked_content.addWidget(self.booking_calls_widget)

        # Cross-widget synchronization
        self.config_widget.data_updated.connect(self.stats_widget.refresh_stats)
        self.config_widget.data_updated.connect(self.booking_calls_widget.refresh_calls)

        # 8: System Data Records View
        self.system_data_widget = SystemDataRecordsWidget()
        self.stacked_content.addWidget(self.system_data_widget)

        # 9: LOGS View
        self.logs_view = QWidget()
        logs_layout = QVBoxLayout(self.logs_view)
        logs_layout.setContentsMargins(15, 15, 15, 15)
        logs_layout.setSpacing(10)
        self.logs_tab_widget = QTabWidget()
        self.logs_tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #FFB6C1; background-color: #FFFFFF; border-radius: 6px; }
            QTabBar::tab { background-color: #FFE4E1; border: 1px solid #FFB6C1; padding: 8px 14px; margin-right: 3px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #FF69B4; color: #FFFFFF; }
        """)
        self.log_lists = {}
        for cat in self.log_categories:
            lw = QListWidget()
            lw.setWordWrap(True)
            self.log_lists[cat] = lw
            self.logs_tab_widget.addTab(lw, cat)
        logs_layout.addWidget(self.logs_tab_widget)
        self.stacked_content.addWidget(self.logs_view)

        # 10: Clean Canvas View
        self.empty_view = QWidget()
        empty_layout = QVBoxLayout(self.empty_view)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_clean = QLabel("Select an option from the menu to get started.")
        lbl_clean.setStyleSheet("font-size: 14px; color: #999999; font-style: italic;")
        empty_layout.addWidget(lbl_clean)
        self.stacked_content.addWidget(self.empty_view)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stacked_content)

        self.handle_category_click("STATS")
        self.add_log("All Activity", "Application initialized and ready. Live Stats mounted.", "INFO")

    def pump_com_messages(self):
        pythoncom.PumpWaitingMessages()

    def show_popout_menu(self):
        if hasattr(self, "popout_menu") and self.popout_menu.isVisible():
            return
        btn = self.sidebar.btn_hamburger
        menu_size = self.popout_menu.sizeHint()
        btn_global = btn.mapToGlobal(QPoint(0, 0))
        target_x = btn_global.x()
        target_y = btn_global.y() - menu_size.height() - 2
        if target_y < 0:
            target_y = btn_global.y() + btn.height() + 2
        self.popout_menu.popup(QPoint(target_x, target_y))

    def open_plot_window(self):
        if self.plot_window is None or not self.plot_window.isVisible():
            self.plot_window = PlotGraphWindow()
            self.plot_window.show()
        else:
            self.plot_window.raise_()
            self.plot_window.activateWindow()
        self.add_log("All Activity", "Resort Node Graph Visualization (Plot) window opened.", "INFO")

    def add_log(self, category, message, level="INFO"):
        clean_cat = re.sub(r"^\d+\.\s*", "", category)
        target_cat = clean_cat if clean_cat in self.log_lists else (category if category in self.log_lists else None)

        now_str = datetime.now().strftime("%H:%M:%S")
        formatted_entry = f"[{now_str}] [{level}] {message}"
        color_map = {
            "SUCCESS": "#2E7D32", "OK": "#2E7D32", "ERROR": "#C62828",
            "WARNING": "#E65100", "INFO": "#1976D2"
        }
        text_color = color_map.get(level.upper(), "#333333")
        if target_cat and target_cat in self.log_lists:
            item = QListWidgetItem(formatted_entry)
            item.setForeground(QColor(text_color))
            self.log_lists[target_cat].addItem(item)
            self.log_lists[target_cat].scrollToBottom()
        if target_cat != "All Activity" and "All Activity" in self.log_lists:
            all_entry = f"[{now_str}] [{target_cat or category}] [{level}] {message}"
            all_item = QListWidgetItem(all_entry)
            all_item.setForeground(QColor(text_color))
            self.log_lists["All Activity"].addItem(all_item)
            self.log_lists["All Activity"].scrollToBottom()
        try:
            log_task(f"[{target_cat or category}] {message}", level)
        except Exception:
            pass

    def handle_booking_feedback_to_todo(self, room: str, comment: str):
        task_id = str(uuid.uuid4())
        desc = f"Feedback on exclusivi: {comment} - Room {room}"
        self.add_task_to_list(task_id, desc)
        self.add_log("To Do List", f"Booking call feedback captured: {desc}", "INFO")

    def add_task_to_list(self, task_id, description):
        item = QListWidgetItem(self.todo_list)
        item.setSizeHint(QSize(0, 40))
        task_widget = TaskWidget(description, task_id, state_change_callback=self.handle_task_state_change)
        self.todo_list.setItemWidget(item, task_widget)
        self.active_tasks[task_id] = task_widget
        log_task(f"⏳ {description}", "ADDED")
        self.add_log("To Do List", f"Task created: ⏳ {description}", "INFO")

    def handle_task_state_change(self, state, task_id, desc):
        if state == "✅":
            log_task(f"✅ {desc}", "COMPLETED")
            self.add_log("To Do List", f"Task COMPLETED: {desc}", "SUCCESS")
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            for row in range(self.todo_list.count()):
                item = self.todo_list.item(row)
                w = self.todo_list.itemWidget(item)
                if w and getattr(w, 'task_id', None) == task_id:
                    self.todo_list.takeItem(row)
                    break
        else:
            self.add_log("To Do List", f"Task status updated to {state}: {desc}", "INFO")

    def collapse_all_submenus(self):
        self.offers_submenu.hide()
        self.cake_submenu.hide()

    def update_sidebar_button_states(self):
        category_button_map = {
            "TODO": self.btn_todo,
            "OFFERS": self.btn_offers,
            "ALLERGIES": self.btn_allergies,
            "CAKE": self.btn_cake,
            "BOOKING": self.btn_booking,
        }
        active_btn = category_button_map.get(self.active_category, None)
        for btn in self.menu_buttons:
            is_active = (btn == active_btn) if active_btn else False
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        is_popout_active = self.active_category in ["STATS", "CONFIG", "SYSTEM_DATA", "LOGS"]
        self.sidebar.btn_hamburger.setProperty("active", is_popout_active)
        self.sidebar.btn_hamburger.style().unpolish(self.sidebar.btn_hamburger)
        self.sidebar.btn_hamburger.style().polish(self.sidebar.btn_hamburger)

    def select_category(self, cat_key: str):
        self.active_category = cat_key
        self.collapse_all_submenus()

        if cat_key == "CONFIG":
            self.stacked_content.setCurrentWidget(self.config_widget)
        elif cat_key == "STATS":
            self.stacked_content.setCurrentWidget(self.stats_widget)
            self.stats_widget.refresh_stats()
        elif cat_key == "TODO":
            self.stacked_content.setCurrentWidget(self.todo_list)
        elif cat_key == "OFFERS":
            self.offers_submenu.show()
            self.stacked_content.setCurrentWidget(self.offers_view)
        elif cat_key == "ALLERGIES":
            self.stacked_content.setCurrentWidget(self.allergies_view)
        elif cat_key == "CAKE":
            self.cake_submenu.show()
            self.stacked_content.setCurrentWidget(self.cake_view)
            self.open_cake_memo_template()
        elif cat_key == "BOOKING":
            self.stacked_content.setCurrentWidget(self.booking_calls_widget)
            self.booking_calls_widget.refresh_calls()
        elif cat_key == "SYSTEM_DATA":
            self.stacked_content.setCurrentWidget(self.system_data_widget)
            self.system_data_widget.load_all_records()
        elif cat_key == "LOGS":
            self.stacked_content.setCurrentWidget(self.logs_view)

        self.update_sidebar_button_states()

    def handle_category_click(self, cat_key: str):
        if getattr(self, "active_category", None) == cat_key:
            self.active_category = None
            self.collapse_all_submenus()
            self.stacked_content.setCurrentWidget(self.empty_view)
            self.update_sidebar_button_states()
            return

        self.select_category(cat_key)

    # -------------------------------------------------------------------------
    # 1. OFFERS (Strictly Save to OUTPUT/OFFERS/ — No Outlook Generation)
    # -------------------------------------------------------------------------
    def handle_doc_save(self):
        self.offers_status.hide()
        self.office_viewer.save_file()
        if self.office_viewer.current_filepath:
            self.add_log("OFFERS", f"Document saved: {os.path.basename(self.office_viewer.current_filepath)}", "INFO")

    def handle_doc_close(self):
        self.offers_status.hide()
        if self.office_viewer.current_filepath:
            self.add_log("OFFERS", f"Document closed: {os.path.basename(self.office_viewer.current_filepath)}", "INFO")
        self.office_viewer.close_file()

    def run_offers_creation(self):
        self.offers_status.hide()
        self.is_update_mode = False
        self.add_log("OFFERS", "Action: Create Offerlist triggered", "INFO")
        
        if get_todays_offer_list() is not None:
            self.add_log("OFFERS", "Today's offer list already exists. Operation denied. Use UPDATE Offerlist.", "WARNING")
            return

        self.add_log("OFFERS", "Processing Data... Please wait.", "INFO")
        self.office_viewer.close_file()
        self.repaint() 
        
        pipeline_status, msg, final_path = execute_offers_pipeline()
        
        if not pipeline_status and msg == "MISSING_CSVS":
            self.add_log("OFFERS", "Missing CSVs in ARRIVALS. Prompting file selector...", "WARNING")
            files, _ = QFileDialog.getOpenFileNames(self, "Select 2 CSV Files (Hold Ctrl for multiple)", ARRIVALS_FOLDER, "CSV (*.csv)")
            if len(files) == 1:
                second_file, _ = QFileDialog.getOpenFileName(self, "Select the SECOND CSV File", ARRIVALS_FOLDER, "CSV (*.csv)")
                if second_file:
                    files.append(second_file)
            if len(files) == 2:
                self.add_log("OFFERS", f"User selected CSV files: {os.path.basename(files[0])}, {os.path.basename(files[1])}", "INFO")
                pipeline_status, msg, final_path = execute_offers_pipeline(selected_csvs=files)
            else:
                self.add_log("OFFERS", "Requirement: Exactly 2 CSV files. Operation aborted.", "ERROR")
                return
                
        level = "SUCCESS" if pipeline_status else "ERROR"
        self.add_log("OFFERS", msg, level)
        if pipeline_status and final_path:
            self.add_log("OFFERS", f"Opening generated document in OfficeViewer: {os.path.basename(final_path)}", "INFO")
            self.office_viewer.open_file(final_path)

    def run_offers_update(self):
        self.offers_status.hide()
        self.is_update_mode = True
        self.add_log("OFFERS", "Action: UPDATE Offerlist triggered", "INFO")
        self.add_log("OFFERS", "Searching for today's file...", "INFO")
        self.repaint()
        
        file_path = get_todays_offer_list()
        if file_path:
            self.add_log("OFFERS", f"File located. Mode: UPDATE. Target: {os.path.basename(file_path)}", "SUCCESS")
            self.office_viewer.open_file(file_path)
        else:
            self.add_log("OFFERS", "No offer list found for today. Please create one first.", "WARNING")

    def handle_save_and_close(self, filepath):
        """
        Offerlist Save & Close Handler:
        Strictly saves/updates the Word document in OUTPUT/OFFERS/.
        Completely removed Outlook email draft generation per user specification.
        """
        self.offers_status.hide()
        if self.is_update_mode:
            self.add_log("OFFERS", f"Saving updated offerlist: {os.path.basename(filepath)}", "INFO")
            try:
                new_path = duplicate_for_update(filepath)
                self.add_log("OFFERS", f"Offerlist updated & saved successfully: {os.path.basename(new_path)}", "SUCCESS")
                QMessageBox.information(self, "Saved", f"Offerlist updated & saved successfully:\n{os.path.basename(new_path)}")
            except Exception as e:
                self.add_log("OFFERS", f"Update save error: {e}", "ERROR")
        else:
            self.add_log("OFFERS", f"Offerlist saved successfully: {os.path.basename(filepath)}", "SUCCESS")
            QMessageBox.information(self, "Saved", f"Offerlist saved successfully:\n{os.path.basename(filepath)}")

    # -------------------------------------------------------------------------
    # 3. CAKE MEMOS (Word Table Parsing, Save As & Automated Outlook Draft)
    # -------------------------------------------------------------------------
    def open_cake_memo_template(self):
        """Opens base Cake Memo template from TEMPLATES/ inside OfficeViewer."""
        template_path = resolve_template_path("cake_memo")
        if not template_path or not os.path.exists(template_path):
            self.add_log("CAKE MEMOS", "Cake Memo template not found in TEMPLATES/", "ERROR")
            QMessageBox.warning(self, "Template Error", "Cake Memo template not found in TEMPLATES/CAKE MEMO TEMPLATE/.")
            return

        cake_temp_dir = os.path.join(OUTPUT_DIR, "CAKE_MEMOS")
        os.makedirs(cake_temp_dir, exist_ok=True)
        working_file = os.path.join(cake_temp_dir, "WORKING_CAKE_MEMO.docx")
        try:
            shutil.copy2(template_path, working_file)
        except Exception as e:
            print(f"[CakeMemo] Error copying template: {e}")
            working_file = template_path

        self.add_log("CAKE MEMOS", f"Opening Cake Memo template in OfficeViewer: {os.path.basename(working_file)}", "INFO")
        self.cake_office_viewer.open_file(working_file)

    def handle_cake_save(self):
        self.cake_office_viewer.save_file()
        if self.cake_office_viewer.current_filepath:
            self.add_log("CAKE MEMOS", f"Cake memo working document saved: {os.path.basename(self.cake_office_viewer.current_filepath)}", "INFO")

    def handle_cake_close(self):
        if self.cake_office_viewer.current_filepath:
            self.add_log("CAKE MEMOS", f"Cake memo document closed: {os.path.basename(self.cake_office_viewer.current_filepath)}", "INFO")
        self.cake_office_viewer.close_file()

    def handle_cake_save_and_close(self, filepath):
        """
        Executes Save As pipeline:
        1. Read and parse Word table content using python-docx.
        2. Extract ROOM NUMBER, Location, Time, Date.
        3. Determine destination: OUTPUT/CAKE_MEMOS/GR CAKE MEMO MM.yyyy/
        4. Filename: ROOM {roomNumber} CAKE MEMO ({dd.MM.yyyy}).docx (with collision handling).
        5. Move / Save final document.
        6. Generate Automated Outlook Draft.
        """
        try:
            self.add_log("CAKE MEMOS", "Parsing Cake Memo table content...", "INFO")
            memo_data = parse_cake_memo_docx(filepath)

            room_num = memo_data["room_number"]
            dest_folder = os.path.join(OUTPUT_DIR, "CAKE_MEMOS", f"GR CAKE MEMO {memo_data['memo_month_year']}")
            os.makedirs(dest_folder, exist_ok=True)

            base_dest_name = f"ROOM {room_num} CAKE MEMO ({memo_data['cake_date_file']})"
            dest_path = os.path.join(dest_folder, f"{base_dest_name}.docx")

            # Collision Handling
            counter = 2
            if os.path.exists(dest_path):
                dest_path = os.path.join(dest_folder, f"{base_dest_name} UPDATED.docx")
                while os.path.exists(dest_path):
                    dest_path = os.path.join(dest_folder, f"{base_dest_name} UPDATED ({counter}).docx")
                    counter += 1

            shutil.copy2(filepath, dest_path)
            self.add_log("CAKE MEMOS", f"Cake memo saved to: {os.path.basename(dest_path)}", "SUCCESS")

            # Outlook Draft Generation
            self.add_log("CAKE MEMOS", "Generating automated Outlook draft...", "INFO")
            try:
                create_cake_memo_outlook_draft(dest_path, memo_data)
                self.add_log("CAKE MEMOS", f"Outlook draft created and displayed for Room {room_num}.", "SUCCESS")
                QMessageBox.information(
                    self,
                    "Cake Memo Processed",
                    f"Cake Memo saved successfully!\n\n"
                    f"• Room: {room_num}\n"
                    f"• Date: {memo_data['cake_date_display']}\n"
                    f"• Location: {memo_data['cake_location']}\n"
                    f"• Time: {memo_data['cake_time']}\n"
                    f"• Saved To: {os.path.basename(dest_path)}\n\n"
                    f"Outlook email draft has been generated and displayed."
                )
            except Exception as mail_err:
                self.add_log("CAKE MEMOS", f"Outlook draft generation failed: {mail_err}", "WARNING")
                QMessageBox.warning(
                    self,
                    "Cake Memo Saved (Email Warning)",
                    f"Cake Memo was saved to:\n{dest_path}\n\n"
                    f"However, Outlook email draft could not be generated:\n{mail_err}"
                )

        except Exception as e:
            self.add_log("CAKE MEMOS", f"Error in Cake Memo pipeline: {e}", "ERROR")
            QMessageBox.critical(self, "Pipeline Error", f"Failed to process Cake Memo:\n{str(e)}")


# =============================================================================
# Main Entrypoint
# =============================================================================

if __name__ == "__main__":
    ensure_workspace_directories()
    app = QApplication(sys.argv)
    window = GuestRelationApp()
    window.show()
    sys.exit(app.exec())