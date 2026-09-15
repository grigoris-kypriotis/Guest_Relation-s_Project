import sys
import os
import json
import uuid
import win32gui
import win32con
import win32com.client
import pythoncom
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QStackedWidget, QListWidget, 
                             QLabel, QFileDialog, QListWidgetItem, QSizePolicy, QMenu,
                             QTabWidget, QScrollArea, QFrame, QTableWidget,
                             QTableWidgetItem, QHeaderView, QGroupBox, QLineEdit,
                             QComboBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont
from offers_module import (execute_offers_pipeline, get_todays_offer_list, 
                           duplicate_for_update, draft_email_payload, 
                           ARRIVALS_FOLDER, log_task)
from booking_calls import BookingCallsWidget
from data_manager import (
    InHouseDataManager, MASTER_STATE_PATH, STATE_META_PATH,
    CHECKOUTS_TODAY_JSON, CHECKOUT_HISTORY_PATH,
    ROOM_MOVES_YESTERDAY_JSON, ROOM_MOVES_HISTORY_PATH,
    ARRIVALS_BEACH_PATH, DEPARTURES_BEACH_PATH,
    ARRIVALS_VILLAS_PATH, DEPARTURES_VILLAS_PATH,
    BOOKING_CALLS_TODAY_JSON, DATABASE_DIR, DATABASE_SUBDIR,
    TEMPLATES_DIR, OUTPUT_DIR, TRASH_DIR, BASE_DIR,
    ensure_workspace_directories, cleanup_obsolete_python_files,
    DEFAULT_PROPERTY
)


class Sidebar(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(180)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
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
        self.container = QWidget()
        self.container.setObjectName("sidebar_container")
        self.setWidget(self.container)

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
        self.current_filepath = filepath
        ext = os.path.splitext(filepath)[1].lower()
        
        try:
            if ext in ['.doc', '.docx']:
                self.office_app = win32com.client.DispatchEx("Word.Application")
                self.office_app.WindowState = 0 
                self.office_app.Visible = True
                self.doc = self.office_app.Documents.Open(filepath)
                try:
                    self.office_app.ActiveWindow.ActivePane.View.Zoom.Percentage = 70
                except Exception:
                    pass
                self.office_hwnd = self.office_app.ActiveWindow.Hwnd
            elif ext in ['.csv', '.xls', '.xlsx']:
                self.office_app = win32com.client.DispatchEx("Excel.Application")
                self.office_app.WindowState = -4143 
                self.office_app.Visible = True
                self.doc = self.office_app.Workbooks.Open(filepath)
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
    Configuration Page (Decoupled from operational metrics):
    Strictly limited to system configuration inputs, directory path settings,
    and environment-level controls. Contains NO operational tables or JSON data.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(18)

        # Header
        lbl_title = QLabel("⚙️ SYSTEM CONFIGURATION & ENVIRONMENT CONTROLS")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Configure workspace directory topology, active property targeting, and system environment controls.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #555555;")
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # 1. System Configuration Inputs Group
        grp_sys = QGroupBox("System Configuration Inputs")
        grp_sys.setStyleSheet("QGroupBox { font-weight: bold; color: #800020; border: 1px solid #FFB6C1; border-radius: 6px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_sys = QVBoxLayout(grp_sys)
        layout_sys.setSpacing(10)

        # Active Property Target
        row_prop = QHBoxLayout()
        lbl_prop = QLabel("Active Property Target:")
        lbl_prop.setFixedWidth(200)
        lbl_prop.setStyleSheet("font-weight: bold; color: #333333;")
        self.combo_prop = QComboBox()
        self.combo_prop.addItems(["Sandy Beach (Default)", "Sandy Villas"])
        self.combo_prop.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_prop.addWidget(lbl_prop)
        row_prop.addWidget(self.combo_prop)
        row_prop.addStretch()
        layout_sys.addLayout(row_prop)

        # Operational Mode
        row_mode = QHBoxLayout()
        lbl_mode = QLabel("Operational Mode:")
        lbl_mode.setFixedWidth(200)
        lbl_mode.setStyleSheet("font-weight: bold; color: #333333;")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Production (Standard Gatekeeper & Autonomous Archiving)", "Debug / Diagnostic"])
        self.combo_mode.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_mode.addWidget(lbl_mode)
        row_mode.addWidget(self.combo_mode)
        row_mode.addStretch()
        layout_sys.addLayout(row_mode)

        # Log Verbosity
        row_log = QHBoxLayout()
        lbl_log = QLabel("Log Verbosity:")
        lbl_log.setFixedWidth(200)
        lbl_log.setStyleSheet("font-weight: bold; color: #333333;")
        self.combo_log = QComboBox()
        self.combo_log.addItems(["INFO (Recommended)", "DEBUG", "WARNING", "ERROR"])
        self.combo_log.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        row_log.addWidget(lbl_log)
        row_log.addWidget(self.combo_log)
        row_log.addStretch()
        layout_sys.addLayout(row_log)

        main_layout.addWidget(grp_sys)

        # 2. Directory Path Settings Group
        grp_paths = QGroupBox("Directory Path Settings")
        grp_paths.setStyleSheet("QGroupBox { font-weight: bold; color: #800020; border: 1px solid #FFB6C1; border-radius: 6px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_paths = QVBoxLayout(grp_paths)
        layout_paths.setSpacing(10)

        path_definitions = [
            ("Workspace Root:", BASE_DIR),
            ("Database Root (database/):", DATABASE_DIR),
            ("Master State Subdirectory (database/database/):", DATABASE_SUBDIR),
            ("Output Directory (output/):", OUTPUT_DIR),
            ("Templates Directory (templates/):", TEMPLATES_DIR),
            ("Trash Archive (trash/):", TRASH_DIR)
        ]

        self.path_inputs = {}
        for label_text, default_val in path_definitions:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(240)
            lbl.setStyleSheet("font-weight: bold; color: #333333;")
            txt = QLineEdit(str(default_val))
            txt.setReadOnly(True)
            txt.setStyleSheet("background-color: #F8F9FA; border: 1px solid #CED4DA; border-radius: 4px; padding: 6px; color: #495057;")
            btn_browse = QPushButton("📁 Browse...")
            btn_browse.setStyleSheet("""
                QPushButton {
                    background-color: #FFE4E1;
                    border: 1px solid #FFB6C1;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    color: #800020;
                }
                QPushButton:hover {
                    background-color: #FF69B4;
                    color: white;
                }
            """)
            btn_browse.clicked.connect(lambda checked=False, target_txt=txt: self._browse_directory(target_txt))
            row.addWidget(lbl)
            row.addWidget(txt, stretch=1)
            row.addWidget(btn_browse)
            layout_paths.addLayout(row)
            self.path_inputs[label_text] = txt

        main_layout.addWidget(grp_paths)

        # 3. Environment-Level Controls Group
        grp_env = QGroupBox("Environment-Level Controls")
        grp_env.setStyleSheet("QGroupBox { font-weight: bold; color: #800020; border: 1px solid #FFB6C1; border-radius: 6px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_env = QVBoxLayout(grp_env)
        layout_env.setSpacing(10)

        btn_row = QHBoxLayout()
        btn_repair = QPushButton("🛠️ Verify & Repair Directory Topology")
        btn_repair.setStyleSheet("""
            QPushButton {
                background-color: #D4EDDA;
                border: 1px solid #28A745;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                color: #155724;
            }
            QPushButton:hover {
                background-color: #28A745;
                color: white;
            }
        """)
        btn_repair.clicked.connect(self._run_repair)

        btn_cleanup = QPushButton("🧹 Clean Obsolete Workspace Files")
        btn_cleanup.setStyleSheet("""
            QPushButton {
                background-color: #FFF3CD;
                border: 1px solid #FFC107;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                color: #856404;
            }
            QPushButton:hover {
                background-color: #FFC107;
                color: white;
            }
        """)
        btn_cleanup.clicked.connect(self._run_cleanup)

        btn_row.addWidget(btn_repair)
        btn_row.addWidget(btn_cleanup)
        btn_row.addStretch()
        layout_env.addLayout(btn_row)

        self.lbl_status = QLabel("System Status: All workspace paths initialized and active.")
        self.lbl_status.setStyleSheet("padding: 8px 12px; background-color: #E8F4F8; border: 1px solid #BEE5EB; border-radius: 4px; color: #0C5460; font-weight: bold;")
        layout_env.addWidget(self.lbl_status)

        main_layout.addWidget(grp_env)
        main_layout.addStretch()

    def _browse_directory(self, target_line_edit: QLineEdit):
        curr = target_line_edit.text()
        chosen = QFileDialog.getExistingDirectory(self, "Select Directory", curr or BASE_DIR)
        if chosen:
            target_line_edit.setText(os.path.abspath(chosen))
            self.lbl_status.setText(f"Path verified: {chosen}")

    def _run_repair(self):
        try:
            ensure_workspace_directories()
            self.lbl_status.setText(f"[{datetime.now().strftime('%H:%M:%S')}] Directory topology verified and all missing folders generated successfully.")
            self.lbl_status.setStyleSheet("padding: 8px 12px; background-color: #D4EDDA; border: 1px solid #28A745; border-radius: 4px; color: #155724; font-weight: bold;")
        except Exception as e:
            self.lbl_status.setText(f"[{datetime.now().strftime('%H:%M:%S')}] Error repairing topology: {e}")
            self.lbl_status.setStyleSheet("padding: 8px 12px; background-color: #F8D7DA; border: 1px solid #DC3545; border-radius: 4px; color: #721C24; font-weight: bold;")

    def _run_cleanup(self):
        try:
            removed = cleanup_obsolete_python_files()
            self.lbl_status.setText(f"[{datetime.now().strftime('%H:%M:%S')}] Cleanup completed. Removed {len(removed)} obsolete file(s).")
            self.lbl_status.setStyleSheet("padding: 8px 12px; background-color: #D4EDDA; border: 1px solid #28A745; border-radius: 4px; color: #155724; font-weight: bold;")
        except Exception as e:
            self.lbl_status.setText(f"[{datetime.now().strftime('%H:%M:%S')}] Error during cleanup: {e}")
            self.lbl_status.setStyleSheet("padding: 8px 12px; background-color: #F8D7DA; border: 1px solid #DC3545; border-radius: 4px; color: #721C24; font-weight: bold;")


class SystemDataRecordsWidget(QWidget):
    """
    Landing Page Data Records Dashboard:
    Direct inspection of active state and historical datasets stored strictly in database/:
      - Master State & Metadata (database/database/master_state.json & state_metadata.json)
      - Sandy Beach Arrivals & Departures (arrivals_today.json & departures_today.json)
      - Room Moves Yesterday (database/room moves/room_moves_yesterday.json)
      - Checkout Records (database/check out history/checkouts_today.json)
      - Active Booking Calls (database/booking calls for today/booking_calls_today.json)
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

        # Header with title and reload button
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        lbl_title = QLabel("📁 SYSTEM DATA & STATE RECORDS")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Centralized inspection of datasets persisted strictly within the database/ directory hierarchy.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #666666;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.btn_refresh = QPushButton("🔄 Reload from database/")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FF69B4;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
                color: #800020;
            }
            QPushButton:hover {
                background-color: #FF69B4;
                color: white;
            }
        """)
        self.btn_refresh.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.btn_refresh)
        main_layout.addLayout(header_layout)

        # Tabs for domain datasets
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #FFB6C1;
                background-color: #FFFFFF;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                border-bottom: none;
                padding: 8px 14px;
                margin-right: 3px;
                font-weight: bold;
                color: #333333;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #FF69B4;
                color: #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background-color: #FFD1DC;
            }
        """)

        # Tab 1: Master State & Metadata
        tab_master = QWidget()
        layout_master = QVBoxLayout(tab_master)
        self.lbl_master_stats = QLabel("Loading Master State...")
        self.lbl_master_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_master.addWidget(self.lbl_master_stats)

        self.table_master = QTableWidget(0, 6)
        self.table_master.setHorizontalHeaderLabels(["Booking ID", "Room", "Guest(s)", "Arrival", "Departure", "Agency"])
        self.table_master.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_master.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_master.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_master.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_master.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_master.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_master.setAlternatingRowColors(True)
        layout_master.addWidget(self.table_master)
        self.tab_widget.addTab(tab_master, "👥 Master State & Metadata")

        # Tab 2: Sandy Beach Arrivals & Departures
        tab_beach = QWidget()
        layout_beach = QVBoxLayout(tab_beach)
        self.lbl_beach_stats = QLabel("Loading Sandy Beach Arrivals & Departures...")
        self.lbl_beach_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_beach.addWidget(self.lbl_beach_stats)

        grp_arrivals = QGroupBox("Today's Arrivals (arrivals_today.json)")
        grp_arrivals.setStyleSheet("QGroupBox { font-weight: bold; color: #800020; border: 1px solid #FFB6C1; border-radius: 4px; margin-top: 8px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        layout_arr_box = QVBoxLayout(grp_arrivals)
        self.table_beach_arrivals = QTableWidget(0, 6)
        self.table_beach_arrivals.setHorizontalHeaderLabels(["Room", "Guest(s)", "Adults", "Kids", "Arrival", "Departure"])
        self.table_beach_arrivals.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_beach_arrivals.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_beach_arrivals.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_beach_arrivals.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_beach_arrivals.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_beach_arrivals.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_beach_arrivals.setAlternatingRowColors(True)
        layout_arr_box.addWidget(self.table_beach_arrivals)
        layout_beach.addWidget(grp_arrivals, stretch=1)

        grp_departures = QGroupBox("Today's Departures (departures_today.json)")
        grp_departures.setStyleSheet("QGroupBox { font-weight: bold; color: #800020; border: 1px solid #FFB6C1; border-radius: 4px; margin-top: 8px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        layout_dep_box = QVBoxLayout(grp_departures)
        self.table_beach_departures = QTableWidget(0, 4)
        self.table_beach_departures.setHorizontalHeaderLabels(["Room", "Guest(s)", "Booking ID", "Departure Date"])
        self.table_beach_departures.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_beach_departures.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_beach_departures.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_beach_departures.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_beach_departures.setAlternatingRowColors(True)
        layout_dep_box.addWidget(self.table_beach_departures)
        layout_beach.addWidget(grp_departures, stretch=1)

        self.tab_widget.addTab(tab_beach, "🏖️ Sandy Beach Arrivals & Departures")

        # Tab 3: Room Moves Yesterday
        tab_moves = QWidget()
        layout_moves = QVBoxLayout(tab_moves)
        self.lbl_moves_stats = QLabel("Loading Room Moves...")
        self.lbl_moves_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_moves.addWidget(self.lbl_moves_stats)

        self.table_moves = QTableWidget(0, 6)
        self.table_moves.setHorizontalHeaderLabels(["Date", "Booking ID", "Guest(s)", "Previous Room", "New Room", "Departure"])
        self.table_moves.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_moves.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.setAlternatingRowColors(True)
        layout_moves.addWidget(self.table_moves)
        self.tab_widget.addTab(tab_moves, "🔄 Room Moves Yesterday")

        # Tab 4: Checkout Records
        tab_checkouts = QWidget()
        layout_checkouts = QVBoxLayout(tab_checkouts)
        self.lbl_checkouts_stats = QLabel("Loading Checkouts...")
        self.lbl_checkouts_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_checkouts.addWidget(self.lbl_checkouts_stats)

        self.table_checkouts = QTableWidget(0, 6)
        self.table_checkouts.setHorizontalHeaderLabels(["Property", "Date", "Booking ID", "Guest(s)", "Room", "Departure"])
        self.table_checkouts.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_checkouts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_checkouts.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_checkouts.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_checkouts.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_checkouts.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_checkouts.setAlternatingRowColors(True)
        layout_checkouts.addWidget(self.table_checkouts)
        self.tab_widget.addTab(tab_checkouts, "🚪 Checkout Records")

        # Tab 5: Active Booking Calls
        tab_calls = QWidget()
        layout_calls = QVBoxLayout(tab_calls)
        self.lbl_calls_stats = QLabel("Loading Booking Calls...")
        self.lbl_calls_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_calls.addWidget(self.lbl_calls_stats)

        self.table_calls = QTableWidget(0, 7)
        self.table_calls.setHorizontalHeaderLabels(["Room", "Guest Name", "Agency", "Arrival", "Departure", "Status", "Notes"])
        self.table_calls.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_calls.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_calls.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_calls.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_calls.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_calls.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_calls.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table_calls.setAlternatingRowColors(True)
        layout_calls.addWidget(self.table_calls)
        self.tab_widget.addTab(tab_calls, "📞 Active Booking Calls")

        main_layout.addWidget(self.tab_widget)
        self.tabs = self.tab_widget

    def load_all_records(self):
        """Convenience method to refresh all tables."""
        self.refresh_data()

    def set_active_tab(self, idx: int):
        if 0 <= idx < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(idx)
        self.refresh_data()

    def refresh_data(self):
        # 1. Master state & Metadata
        master = self.data_manager.load_master_state()
        meta = self.data_manager.load_metadata()
        bookings_dict = {k: v for k, v in master.items() if isinstance(v, dict)}
        total_bookings = len(bookings_dict)
        total_guests = sum(
            len(b.get("Πελάτες", [])) if isinstance(b.get("Πελάτες"), list) else 0
            for b in bookings_dict.values()
        )
        last_dt = meta.get("last_processed_date", "N/A")
        last_ts = meta.get("last_updated_at", "N/A")
        if "T" in str(last_ts):
            last_ts = str(last_ts).split(".")[0].replace("T", " ")
        self.lbl_master_stats.setText(
            f"Active In-House Bookings: {total_bookings} | Total Guests: {total_guests} | "
            f"Last Ingested Date: {last_dt} | Last Sync: {last_ts} | Directory: database/database/"
        )
        self.table_master.setRowCount(0)
        for b_id, b_data in bookings_dict.items():
            r = self.table_master.rowCount()
            self.table_master.insertRow(r)
            self.table_master.setItem(r, 0, QTableWidgetItem(str(b_id)))
            self.table_master.setItem(r, 1, QTableWidgetItem(str(b_data.get("Δωμάτιο", ""))))
            guests = b_data.get("Πελάτες", [])
            guests_str = ", ".join(guests) if isinstance(guests, list) else str(guests or "")
            self.table_master.setItem(r, 2, QTableWidgetItem(guests_str))
            self.table_master.setItem(r, 3, QTableWidgetItem(str(b_data.get("Άφιξη", ""))))
            self.table_master.setItem(r, 4, QTableWidgetItem(str(b_data.get("Αναχώρηση", ""))))
            self.table_master.setItem(r, 5, QTableWidgetItem(str(b_data.get("agency", ""))))

        # 2. Sandy Beach Arrivals & Departures
        arr_state = self.data_manager.load_arrivals_state()
        beach_arr = arr_state.get("SANDY BEACH", {})
        dep_state = self.data_manager.load_departures_state("sandy_beach")
        beach_deps = dep_state.get("departures", [])
        self.lbl_beach_stats.setText(
            f"🏖️ Sandy Beach Today | Arrivals: {len(beach_arr)} | Departures: {len(beach_deps)} | "
            f"Paths: database/sandy beach/arrivals/ & departures/"
        )

        self.table_beach_arrivals.setRowCount(0)
        for room_no, r_info in beach_arr.items():
            r = self.table_beach_arrivals.rowCount()
            self.table_beach_arrivals.insertRow(r)
            self.table_beach_arrivals.setItem(r, 0, QTableWidgetItem(str(room_no)))
            g_names = ", ".join(r_info.get("guests", [])) if isinstance(r_info.get("guests"), list) else str(r_info.get("guests", ""))
            self.table_beach_arrivals.setItem(r, 1, QTableWidgetItem(g_names))
            self.table_beach_arrivals.setItem(r, 2, QTableWidgetItem(str(r_info.get("adults", ""))))
            self.table_beach_arrivals.setItem(r, 3, QTableWidgetItem(str(r_info.get("children", ""))))
            self.table_beach_arrivals.setItem(r, 4, QTableWidgetItem(str(r_info.get("arrival", ""))))
            self.table_beach_arrivals.setItem(r, 5, QTableWidgetItem(str(r_info.get("departure", ""))))

        self.table_beach_departures.setRowCount(0)
        for d in beach_deps:
            r = self.table_beach_departures.rowCount()
            self.table_beach_departures.insertRow(r)
            self.table_beach_departures.setItem(r, 0, QTableWidgetItem(str(d.get("room", ""))))
            g_names = ", ".join(d.get("guests", [])) if isinstance(d.get("guests"), list) else str(d.get("guests", ""))
            self.table_beach_departures.setItem(r, 1, QTableWidgetItem(g_names))
            self.table_beach_departures.setItem(r, 2, QTableWidgetItem(str(d.get("booking_id", ""))))
            self.table_beach_departures.setItem(r, 3, QTableWidgetItem(str(d.get("departure", d.get("checkout_date", "")))))

        # 3. Room moves yesterday
        moves_data = self.data_manager.load_room_moves_history()
        self.lbl_moves_stats.setText(
            f"Total Room Moves Archived: {len(moves_data)} | File: database/room moves/room_moves_yesterday.json"
        )
        self.table_moves.setRowCount(0)
        for rm in moves_data:
            r = self.table_moves.rowCount()
            self.table_moves.insertRow(r)
            self.table_moves.setItem(r, 0, QTableWidgetItem(str(rm.get("date", ""))))
            self.table_moves.setItem(r, 1, QTableWidgetItem(str(rm.get("booking_id", ""))))
            guests_str = ", ".join(rm.get("guests", [])) if isinstance(rm.get("guests"), list) else str(rm.get("guests", ""))
            self.table_moves.setItem(r, 2, QTableWidgetItem(guests_str))
            
            old_item = QTableWidgetItem(str(rm.get("old_room", "")))
            old_item.setForeground(QColor("#C0392B"))
            self.table_moves.setItem(r, 3, old_item)

            new_item = QTableWidgetItem(str(rm.get("new_room", "")))
            new_item.setForeground(QColor("#27AE60"))
            new_item.setFont(QFont("Segoe UI", weight=QFont.Weight.Bold))
            self.table_moves.setItem(r, 4, new_item)

            self.table_moves.setItem(r, 5, QTableWidgetItem(str(rm.get("departure", ""))))

        # 4. Checkout records (Property-tagged)
        co_payload = self.data_manager.load_checkouts_history()
        records = co_payload.get("records", []) if isinstance(co_payload, dict) else co_payload
        self.lbl_checkouts_stats.setText(
            f"Total Check-Outs Archived: {len(records)} | File: database/check out history/checkouts_today.json"
        )
        self.table_checkouts.setRowCount(0)
        for co in records:
            r = self.table_checkouts.rowCount()
            self.table_checkouts.insertRow(r)
            self.table_checkouts.setItem(r, 0, QTableWidgetItem(str(co.get("property", DEFAULT_PROPERTY))))
            self.table_checkouts.setItem(r, 1, QTableWidgetItem(str(co.get("date", co.get("checkout_date", "")))))
            self.table_checkouts.setItem(r, 2, QTableWidgetItem(str(co.get("booking_id", ""))))
            guests_str = ", ".join(co.get("guests", [])) if isinstance(co.get("guests"), list) else str(co.get("guests", ""))
            self.table_checkouts.setItem(r, 3, QTableWidgetItem(guests_str))
            self.table_checkouts.setItem(r, 4, QTableWidgetItem(str(co.get("room", ""))))
            self.table_checkouts.setItem(r, 5, QTableWidgetItem(str(co.get("departure", ""))))

        # 5. Booking Calls Today
        calls_data = []
        if os.path.exists(BOOKING_CALLS_TODAY_JSON):
            try:
                with open(BOOKING_CALLS_TODAY_JSON, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        calls_data = content
                    elif isinstance(content, dict) and "calls" in content:
                        calls_data = content["calls"]
            except Exception:
                calls_data = []
        self.lbl_calls_stats.setText(
            f"Total Scheduled Calls Today: {len(calls_data)} | File: database/booking calls for today/booking_calls_today.json"
        )
        self.table_calls.setRowCount(0)
        for c in calls_data:
            r = self.table_calls.rowCount()
            self.table_calls.insertRow(r)
            self.table_calls.setItem(r, 0, QTableWidgetItem(str(c.get("room", ""))))
            self.table_calls.setItem(r, 1, QTableWidgetItem(str(c.get("guest_name", ""))))
            self.table_calls.setItem(r, 2, QTableWidgetItem(str(c.get("agency", ""))))
            self.table_calls.setItem(r, 3, QTableWidgetItem(str(c.get("arrival", ""))))
            self.table_calls.setItem(r, 4, QTableWidgetItem(str(c.get("departure", ""))))
            self.table_calls.setItem(r, 5, QTableWidgetItem(str(c.get("status", ""))))
            self.table_calls.setItem(r, 6, QTableWidgetItem(str(c.get("notes", ""))))


class GuestRelationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guest Relation Workspace")
        self.resize(1200, 800)
        self.setStyleSheet("QMainWindow { background-color: #FFF0F5; }")
        
        self.mail_references = []
        self.active_tasks = {}
        self.is_update_mode = False
        
        self.log_categories = [
            "All Activity",
            "To Do List",
            "1. OFFERS",
            "2. ALLERGIES",
            "3. CAKE MEMOS",
            "4. Booking Calls",
            "5. ALL DATA"
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

        self.sidebar = Sidebar()
        sidebar_layout = QVBoxLayout(self.sidebar.container)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.btn_config = QPushButton("⚙️ Configuration")
        self.btn_todo = QPushButton("☰ To Do List")
        self.btn_offers = QPushButton("1. OFFERS")
        
        # Sub-Menu container for OFFERS (Accordion pattern)
        self.offers_submenu = QWidget()
        offers_submenu_layout = QVBoxLayout(self.offers_submenu)
        offers_submenu_layout.setContentsMargins(0, 2, 0, 4)
        offers_submenu_layout.setSpacing(4)
        self.offers_submenu.setStyleSheet("""
            QWidget { background-color: transparent; }
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                padding: 6px 8px 6px 20px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                color: black;
            }
            QPushButton:hover {
                background-color: #FF69B4;
                color: white;
            }
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
                padding: 6px 8px 6px 20px; 
                text-align: left; 
                font-size: 11px; 
                font-weight: bold; 
                color: black;
            }
            QPushButton:hover {
                background-color: #4682B4;
                color: white;
            }
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
        offers_submenu_layout.addWidget(self.btn_save)
        offers_submenu_layout.addWidget(self.btn_close)
        offers_submenu_layout.addWidget(self.btn_save_close)
        
        self.offers_submenu.hide()

        self.btn_allergies = QPushButton("2. ALLERGIES")
        self.btn_cake = QPushButton("3. CAKE MEMOS")
        self.btn_booking = QPushButton("BOOKING CALLS")
        self.btn_system_data = QPushButton("📁 System Data & State Records")

        # Sub-Menu container for SYSTEM DATA & STATE RECORDS (Accordion pattern)
        self.system_data_submenu = QWidget()
        system_data_submenu_layout = QVBoxLayout(self.system_data_submenu)
        system_data_submenu_layout.setContentsMargins(0, 2, 0, 4)
        system_data_submenu_layout.setSpacing(4)
        self.system_data_submenu.setStyleSheet("""
            QWidget { background-color: transparent; }
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                padding: 6px 8px 6px 20px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                color: black;
            }
            QPushButton:hover {
                background-color: #FF69B4;
                color: white;
            }
        """)

        sysdata_sub_items = [
            ("👥 Master State & Metadata", 0),
            ("🏖️ Sandy Beach Arrivals & Departures", 1),
            ("🔄 Room Moves Yesterday", 2),
            ("🚪 Checkout Records", 3),
            ("📞 Active Booking Calls", 4)
        ]
        for label, idx in sysdata_sub_items:
            sub_btn = QPushButton(label)
            sub_btn.clicked.connect(lambda checked=False, i=idx: self.show_system_data_category(i))
            system_data_submenu_layout.addWidget(sub_btn)
        self.system_data_submenu.hide()

        self.btn_logs = QPushButton("📋 LOGS")
        
        # Sub-Menu container for LOGS (Accordion pattern)
        self.logs_submenu = QWidget()
        logs_submenu_layout = QVBoxLayout(self.logs_submenu)
        logs_submenu_layout.setContentsMargins(0, 2, 0, 4)
        logs_submenu_layout.setSpacing(4)
        self.logs_submenu.setStyleSheet("""
            QWidget { background-color: transparent; }
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                padding: 6px 8px 6px 20px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                color: black;
            }
            QPushButton:hover {
                background-color: #FF69B4;
                color: white;
            }
        """)
        
        self.logs_submenu_buttons = {}
        for cat in self.log_categories:
            cat_btn = QPushButton(cat)
            cat_btn.clicked.connect(lambda checked=False, c=cat: self.show_log_category(c))
            logs_submenu_layout.addWidget(cat_btn)
            self.logs_submenu_buttons[cat] = cat_btn
        self.logs_submenu.hide()
        
        self.btn_config.clicked.connect(lambda: self.handle_category_click("CONFIG"))
        self.btn_todo.clicked.connect(lambda: self.handle_category_click("TODO"))
        self.btn_offers.clicked.connect(lambda: self.handle_category_click("OFFERS"))
        self.btn_allergies.clicked.connect(lambda: self.handle_category_click("ALLERGIES"))
        self.btn_cake.clicked.connect(lambda: self.handle_category_click("CAKE"))
        self.btn_booking.clicked.connect(lambda: self.handle_category_click("BOOKING"))
        self.btn_system_data.clicked.connect(lambda: self.handle_category_click("SYSTEM_DATA"))
        self.btn_logs.clicked.connect(lambda: self.handle_category_click("LOGS"))
        
        self.menu_buttons = [
            self.btn_config,
            self.btn_todo,
            self.btn_offers,
            self.btn_allergies,
            self.btn_cake,
            self.btn_booking,
            self.btn_system_data,
            self.btn_logs
        ]
        self.active_category = "CONFIG"
        
        sidebar_layout.addWidget(QLabel("Menu"))
        sidebar_layout.addWidget(self.btn_config)
        sidebar_layout.addWidget(self.btn_todo)
        sidebar_layout.addWidget(self.btn_offers)
        sidebar_layout.addWidget(self.offers_submenu)
        sidebar_layout.addWidget(self.btn_allergies)
        sidebar_layout.addWidget(self.btn_cake)
        sidebar_layout.addWidget(self.btn_booking)
        sidebar_layout.addWidget(self.btn_system_data)
        sidebar_layout.addWidget(self.system_data_submenu)
        sidebar_layout.addWidget(self.btn_logs)
        sidebar_layout.addWidget(self.logs_submenu)
        
        # Index 0: Configuration View (Decoupled: strictly system config inputs, paths, env controls)
        self.config_widget = ConfigurationWidget()
        self.stacked_content.addWidget(self.config_widget)

        # Index 1: To Do List View
        self.todo_list = QListWidget()
        self.todo_list.setStyleSheet("background-color: #FFFFFF; color: black; font-weight: bold; font-size: 14px;")
        self.stacked_content.addWidget(self.todo_list)

        # Index 2: Offers View
        self.offers_view = QWidget()
        offers_layout = QVBoxLayout(self.offers_view)
        offers_layout.setContentsMargins(0, 0, 0, 0)
        offers_layout.setSpacing(0)
        
        self.offers_status = QLabel("OFFERS PROCESSOR\nTarget: ARRIVALS Directory")
        self.offers_status.setWordWrap(True)
        self.offers_status.setStyleSheet("font-weight: bold; color: #B03060; padding: 5px;")
        
        offers_layout.addWidget(self.offers_status)
        offers_layout.addWidget(self.office_viewer, stretch=1)
        self.stacked_content.addWidget(self.offers_view)

        # Index 3-5: Placeholder & Booking Views
        self.allergies_view = QLabel("ALLERGIES PROCESSOR")
        self.stacked_content.addWidget(self.allergies_view)
        self.cake_view = QLabel("CAKE MEMOS PROCESSOR")
        self.stacked_content.addWidget(self.cake_view)
        self.booking_calls_widget = BookingCallsWidget()
        self.booking_calls_widget.feedback_submitted.connect(self.handle_booking_feedback_to_todo)
        self.stacked_content.addWidget(self.booking_calls_widget)
        
        # Index 6: System Data & State Records View
        self.system_data_widget = SystemDataRecordsWidget()
        self.stacked_content.addWidget(self.system_data_widget)

        # Index 7: LOGS View
        self.logs_view = QWidget()
        logs_layout = QVBoxLayout(self.logs_view)
        logs_layout.setContentsMargins(15, 15, 15, 15)
        logs_layout.setSpacing(10)
        
        header_layout = QHBoxLayout()
        lbl_logs_title = QLabel("SYSTEM & OPERATIONAL LOGS")
        lbl_logs_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #B03060;")
        header_layout.addWidget(lbl_logs_title)
        header_layout.addStretch()
        
        btn_clear_tab = QPushButton("🗑 Clear Current Tab")
        btn_clear_tab.setStyleSheet("""
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
                color: #333333;
            }
            QPushButton:hover {
                background-color: #FF69B4;
                color: white;
            }
        """)
        btn_clear_tab.clicked.connect(self.clear_current_tab_logs)
        header_layout.addWidget(btn_clear_tab)
        logs_layout.addLayout(header_layout)
        
        self.logs_tab_widget = QTabWidget()
        self.logs_tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #FFB6C1;
                background-color: #FFFFFF;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                border-bottom: none;
                padding: 8px 14px;
                margin-right: 3px;
                font-weight: bold;
                color: #333333;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #FF69B4;
                color: #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background-color: #FFD1DC;
            }
        """)
        
        self.log_lists = {}
        for cat in self.log_categories:
            list_widget = QListWidget()
            list_widget.setWordWrap(True)
            list_widget.setStyleSheet("""
                QListWidget {
                    background-color: #FFFFFF;
                    border: none;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 12px;
                    padding: 8px;
                }
                QListWidget::item {
                    padding: 6px 10px;
                    border-bottom: 1px solid #F5F5F5;
                }
            """)
            self.log_lists[cat] = list_widget
            self.logs_tab_widget.addTab(list_widget, cat)
            
        logs_layout.addWidget(self.logs_tab_widget)
        self.stacked_content.addWidget(self.logs_view)

        # Index 8: Clean Canvas View (Mounted when user toggles/dismisses active category)
        self.empty_view = QWidget()
        empty_layout = QVBoxLayout(self.empty_view)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_clean = QLabel("Select an option from the menu to get started.")
        lbl_clean.setStyleSheet("font-size: 14px; color: #999999; font-style: italic;")
        empty_layout.addWidget(lbl_clean)
        self.stacked_content.addWidget(self.empty_view)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stacked_content)
        self.handle_category_click("CONFIG")
        self.add_log("All Activity", "Application initialized and ready. Configuration loaded.", "INFO")

    def pump_com_messages(self):
        pythoncom.PumpWaitingMessages()

    def add_log(self, category, message, level="INFO"):
        now_str = datetime.now().strftime("%H:%M:%S")
        formatted_entry = f"[{now_str}] [{level}] {message}"
        
        color_map = {
            "SUCCESS": "#2E7D32",
            "OK": "#2E7D32",
            "ERROR": "#C62828",
            "WARNING": "#E65100",
            "INFO": "#1976D2"
        }
        text_color = color_map.get(level.upper(), "#333333")
        
        # Add to specific category tab
        if category in self.log_lists:
            item = QListWidgetItem(formatted_entry)
            item.setForeground(QColor(text_color))
            self.log_lists[category].addItem(item)
            self.log_lists[category].scrollToBottom()
            
        # Add to aggregate All Activity tab if not already logged as All Activity
        if category != "All Activity" and "All Activity" in self.log_lists:
            all_entry = f"[{now_str}] [{category}] [{level}] {message}"
            all_item = QListWidgetItem(all_entry)
            all_item.setForeground(QColor(text_color))
            self.log_lists["All Activity"].addItem(all_item)
            self.log_lists["All Activity"].scrollToBottom()
            
        # If WARNING or ERROR, show it on the original page as requested
        if level.upper() in ["WARNING", "ERROR"]:
            self.show_page_alert(category, message, level)
            
        # Also persist to disk task log
        try:
            log_task(f"[{category}] {message}", level)
        except Exception:
            pass

    def show_page_alert(self, category, message, level="WARNING"):
        if category == "1. OFFERS":
            self.show_offers_alert(message, level)

    def show_offers_alert(self, message, level="WARNING"):
        is_error = level.upper() == "ERROR"
        if is_error:
            self.offers_status.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    font-size: 12px;
                    color: #B71C1C;
                    background-color: #FFEBEE;
                    border: 1px solid #EF9A9A;
                    border-radius: 4px;
                    padding: 8px 12px;
                }
            """)
            self.offers_status.setText(f"❌ ERROR: {message}")
        else:
            self.offers_status.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    font-size: 12px;
                    color: #BF360C;
                    background-color: #FFF3E0;
                    border: 1px solid #FFCC80;
                    border-radius: 4px;
                    padding: 8px 12px;
                }
            """)
            self.offers_status.setText(f"⚠️ WARNING: {message}")
        self.offers_status.show()

    def clear_current_tab_logs(self):
        current_widget = self.logs_tab_widget.currentWidget()
        if isinstance(current_widget, QListWidget):
            current_widget.clear()

    def handle_booking_feedback_to_todo(self, room: str, comment: str):
        task_id = str(uuid.uuid4())
        desc = f"Feedback on exclusivi: {comment} - Room {room}"
        self.add_task_to_list(task_id, desc)
        self.add_log("To Do List", f"Booking call feedback captured: {desc}", "INFO")

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

    def draft_event_callback(self, task_id, event_type):
        if task_id in self.active_tasks:
            task_widget = self.active_tasks[task_id]
            desc = task_widget.lbl_desc.text()
            if event_type == "SENT":
                task_widget.btn_state.setText("✅")
                log_task(f"✅ {desc}", "COMPLETED")
                self.add_log("To Do List", f"Task COMPLETED (Email sent): {desc}", "SUCCESS")
                del self.active_tasks[task_id]
                for row in range(self.todo_list.count()):
                    item = self.todo_list.item(row)
                    w = self.todo_list.itemWidget(item)
                    if w and getattr(w, 'task_id', None) == task_id:
                        self.todo_list.takeItem(row)
                        break
            elif event_type == "CLOSED":
                task_widget.btn_state.setText("➖")
                log_task(f"➖ {desc}", "TERMINATED")
                self.add_log("To Do List", f"Task TERMINATED (Email closed without sending): {desc}", "WARNING")
                del self.active_tasks[task_id]

    def add_task_to_list(self, task_id, description):
        item = QListWidgetItem(self.todo_list)
        item.setSizeHint(QSize(0, 40))
        task_widget = TaskWidget(description, task_id, state_change_callback=self.handle_task_state_change)
        self.todo_list.setItemWidget(item, task_widget)
        self.active_tasks[task_id] = task_widget
        log_task(f"⏳ {description}", "ADDED")
        self.add_log("To Do List", f"Task created: ⏳ {description}", "INFO")

    def collapse_all_submenus(self):
        """Collapses and hides all subcategory menus immediately."""
        self.offers_submenu.hide()
        self.system_data_submenu.hide()
        self.logs_submenu.hide()

    def update_sidebar_button_states(self):
        """Updates active styling on sidebar category buttons."""
        category_button_map = {
            "CONFIG": self.btn_config,
            "TODO": self.btn_todo,
            "OFFERS": self.btn_offers,
            "ALLERGIES": self.btn_allergies,
            "CAKE": self.btn_cake,
            "BOOKING": self.btn_booking,
            "SYSTEM_DATA": self.btn_system_data,
            "LOGS": self.btn_logs
        }
        active_btn = category_button_map.get(self.active_category, None)
        for btn in self.menu_buttons:
            is_active = (btn == active_btn) if active_btn else False
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def handle_category_click(self, cat_key: str):
        """
        Handles category clicks with:
        1. Strict Mutual Exclusion: only the active category's subcategories render. All others immediately collapse.
        2. Automatic Teardown: switching categories collapses all other submenus immediately.
        3. Toggle/Dismiss: clicking an already active category toggles its state to inactive/closed,
           unmounting its subcategories and leaving the canvas clean.
        """
        # Toggle / Dismiss check: clicking an already active main category toggles it to closed/clean canvas
        if self.active_category == cat_key:
            self.active_category = None
            self.collapse_all_submenus()
            self.stacked_content.setCurrentWidget(self.empty_view)
            self.update_sidebar_button_states()
            return

        # Switching or opening new category
        self.active_category = cat_key
        self.collapse_all_submenus()

        if cat_key == "CONFIG":
            self.stacked_content.setCurrentWidget(self.config_widget)
        elif cat_key == "TODO":
            self.stacked_content.setCurrentWidget(self.todo_list)
        elif cat_key == "OFFERS":
            self.offers_submenu.show()
            self.stacked_content.setCurrentWidget(self.offers_view)
        elif cat_key == "ALLERGIES":
            self.stacked_content.setCurrentWidget(self.allergies_view)
        elif cat_key == "CAKE":
            self.stacked_content.setCurrentWidget(self.cake_view)
        elif cat_key == "BOOKING":
            self.stacked_content.setCurrentWidget(self.booking_calls_widget)
            self.booking_calls_widget.refresh_calls()
        elif cat_key == "SYSTEM_DATA":
            self.system_data_submenu.show()
            self.stacked_content.setCurrentWidget(self.system_data_widget)
            self.system_data_widget.load_all_records()
        elif cat_key == "LOGS":
            self.logs_submenu.show()
            self.stacked_content.setCurrentWidget(self.logs_view)

        self.update_sidebar_button_states()

    def show_system_data_category(self, tab_index: int):
        """Selects a subcategory tab within System Data & State Records."""
        self.active_category = "SYSTEM_DATA"
        self.collapse_all_submenus()
        self.system_data_submenu.show()
        self.stacked_content.setCurrentWidget(self.system_data_widget)
        if hasattr(self.system_data_widget, "tabs") and 0 <= tab_index < self.system_data_widget.tabs.count():
            self.system_data_widget.tabs.setCurrentIndex(tab_index)
        self.system_data_widget.refresh_data()
        self.update_sidebar_button_states()

    def show_log_category(self, cat: str):
        """Selects a subcategory tab within Logs."""
        self.active_category = "LOGS"
        self.collapse_all_submenus()
        self.logs_submenu.show()
        self.stacked_content.setCurrentWidget(self.logs_view)
        if cat in self.log_lists:
            self.logs_tab_widget.setCurrentWidget(self.log_lists[cat])
        self.update_sidebar_button_states()


    def handle_doc_save(self):
        self.offers_status.hide()
        self.office_viewer.save_file()
        if self.office_viewer.current_filepath:
            self.add_log("1. OFFERS", f"Document saved: {os.path.basename(self.office_viewer.current_filepath)}", "INFO")

    def handle_doc_close(self):
        self.offers_status.hide()
        if self.office_viewer.current_filepath:
            self.add_log("1. OFFERS", f"Document closed: {os.path.basename(self.office_viewer.current_filepath)}", "INFO")
        self.office_viewer.close_file()

    def run_offers_creation(self):
        self.offers_status.hide()
        self.is_update_mode = False
        self.add_log("1. OFFERS", "Action: Create Offerlist triggered", "INFO")
        
        if get_todays_offer_list() is not None:
            self.add_log("1. OFFERS", "Today's offer list already exists. Operation denied. Use UPDATE Offerlist.", "WARNING")
            return

        self.add_log("1. OFFERS", "Processing Data... Please wait.", "INFO")
        self.office_viewer.close_file()
        self.repaint() 
        
        pipeline_status, msg, final_path = execute_offers_pipeline()
        
        if not pipeline_status and msg == "MISSING_CSVS":
            self.add_log("1. OFFERS", "Missing CSVs in ARRIVALS. Prompting file selector...", "WARNING")
            files, _ = QFileDialog.getOpenFileNames(self, "Select 2 CSV Files (Hold Ctrl for multiple)", ARRIVALS_FOLDER, "CSV (*.csv)")
            if len(files) == 1:
                second_file, _ = QFileDialog.getOpenFileName(self, "Select the SECOND CSV File", ARRIVALS_FOLDER, "CSV (*.csv)")
                if second_file:
                    files.append(second_file)
            if len(files) == 2:
                self.add_log("1. OFFERS", f"User selected CSV files: {os.path.basename(files[0])}, {os.path.basename(files[1])}", "INFO")
                pipeline_status, msg, final_path = execute_offers_pipeline(selected_csvs=files)
            else:
                self.add_log("1. OFFERS", "Requirement: Exactly 2 CSV files. Operation aborted.", "ERROR")
                return
                
        level = "SUCCESS" if pipeline_status else "ERROR"
        self.add_log("1. OFFERS", msg, level)
        if pipeline_status and final_path:
            self.add_log("1. OFFERS", f"Opening generated document in OfficeViewer: {os.path.basename(final_path)}", "INFO")
            self.office_viewer.open_file(final_path)

    def run_offers_update(self):
        self.offers_status.hide()
        self.is_update_mode = True
        self.add_log("1. OFFERS", "Action: UPDATE Offerlist triggered", "INFO")
        self.add_log("1. OFFERS", "Searching for today's file...", "INFO")
        self.repaint()
        
        file_path = get_todays_offer_list()
        if file_path:
            self.add_log("1. OFFERS", f"File located. Mode: UPDATE. Target: {os.path.basename(file_path)}", "SUCCESS")
            self.office_viewer.open_file(file_path)
        else:
            self.add_log("1. OFFERS", "No offer list found for today. Please create one first.", "WARNING")

    def handle_save_and_close(self, filepath):
        self.offers_status.hide()
        task_id = str(uuid.uuid4())
        if self.is_update_mode:
            self.add_log("1. OFFERS", f"Compiling updated document and Outlook payload: {os.path.basename(filepath)}", "INFO")
            self.repaint()
            try:
                new_path = duplicate_for_update(filepath)
                mail_ref = draft_email_payload(new_path, True, task_id, self.draft_event_callback)
                self.mail_references.append(mail_ref)
                self.add_task_to_list(task_id, f"Email UPDATED Offerlist: {os.path.basename(new_path)}")
                self.add_log("1. OFFERS", f"Compilation successful. Outlook draft created: {os.path.basename(new_path)}", "SUCCESS")
            except Exception as e:
                self.add_log("1. OFFERS", f"Update compilation error: {e}", "ERROR")
        else:
            self.add_log("1. OFFERS", f"Compiling new document and Outlook payload: {os.path.basename(filepath)}", "INFO")
            self.repaint()
            try:
                mail_ref = draft_email_payload(filepath, False, task_id, self.draft_event_callback)
                self.mail_references.append(mail_ref)
                self.add_task_to_list(task_id, f"Email Offerlist: {os.path.basename(filepath)}")
                self.add_log("1. OFFERS", f"Compilation successful. Outlook draft created: {os.path.basename(filepath)}", "SUCCESS")
            except Exception as e:
                self.add_log("1. OFFERS", f"Creation compilation error: {e}", "ERROR")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    from data_manager import run_gatekeeper_if_needed
    if not run_gatekeeper_if_needed():
        sys.exit(0)
    window = GuestRelationApp()
    window.show()
    sys.exit(app.exec())