import sys
import os
import uuid
import win32gui
import win32con
import win32com.client
import pythoncom
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QStackedWidget, QListWidget, 
                             QLabel, QFileDialog, QListWidgetItem, QSizePolicy, QMenu,
                             QTabWidget, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor
from offers_module import (execute_offers_pipeline, get_todays_offer_list, 
                           duplicate_for_update, draft_email_payload, 
                           ARRIVALS_FOLDER, log_task)
from booking_calls import BookingCallsWidget


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
        
    def showEvent(self, event):
        super().showEvent(event)
        self.resize_office_window()

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
        self.btn_alldata = QPushButton("5. ALL DATA")
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
        
        self.menu_buttons = [self.btn_todo, self.btn_offers, self.btn_allergies, 
                             self.btn_cake, self.btn_booking, self.btn_alldata, self.btn_logs]
        
        for btn in self.menu_buttons:
            if btn == self.btn_offers:
                btn.clicked.connect(self.toggle_offers_submenu)
            elif btn == self.btn_logs:
                btn.clicked.connect(self.toggle_logs_submenu)
            else:
                btn.clicked.connect(self.handle_menu_click)
        
        sidebar_layout.addWidget(QLabel("Menu"))
        for btn in self.menu_buttons:
            sidebar_layout.addWidget(btn)
            if btn == self.btn_offers:
                sidebar_layout.addWidget(self.offers_submenu)
            elif btn == self.btn_logs:
                sidebar_layout.addWidget(self.logs_submenu)
        
        # Index 0: To Do List View
        self.todo_list = QListWidget()
        self.todo_list.setStyleSheet("background-color: #FFFFFF; color: black; font-weight: bold; font-size: 14px;")
        self.stacked_content.addWidget(self.todo_list)

        # Index 1: Offers View
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

        # Index 2-5: Placeholder Views
        self.allergies_view = QLabel("ALLERGIES PROCESSOR")
        self.stacked_content.addWidget(self.allergies_view)
        self.cake_view = QLabel("CAKE MEMOS PROCESSOR")
        self.stacked_content.addWidget(self.cake_view)
        self.booking_calls_widget = BookingCallsWidget()
        self.booking_calls_widget.feedback_submitted.connect(self.handle_booking_feedback_to_todo)
        self.stacked_content.addWidget(self.booking_calls_widget)
        self.alldata_view = QLabel("ALL DATA AGGREGATOR")
        self.stacked_content.addWidget(self.alldata_view)

        # Index 6: LOGS View
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

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stacked_content)
        self.handle_menu_click(button_override=self.btn_todo)
        self.add_log("All Activity", "Application initialized and ready.", "INFO")

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

    def toggle_logs_submenu(self):
        self.logs_submenu.setVisible(not self.logs_submenu.isVisible())
        self.stacked_content.setCurrentWidget(self.logs_view)
        for i, btn in enumerate(self.menu_buttons):
            btn.setProperty("active", btn == self.btn_logs)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def show_log_category(self, cat):
        self.stacked_content.setCurrentWidget(self.logs_view)
        for i, btn in enumerate(self.menu_buttons):
            btn.setProperty("active", btn == self.btn_logs)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if cat in self.log_lists:
            self.logs_tab_widget.setCurrentWidget(self.log_lists[cat])

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

    def toggle_offers_submenu(self):
        self.offers_submenu.setVisible(not self.offers_submenu.isVisible())
        self.stacked_content.setCurrentWidget(self.offers_view)
        for i, btn in enumerate(self.menu_buttons):
            btn.setProperty("active", btn == self.btn_offers)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def handle_menu_click(self, checked=False, button_override=None):
        sender = button_override if button_override else self.sender()
        if sender in self.menu_buttons:
            index = self.menu_buttons.index(sender)
            self.stacked_content.setCurrentIndex(index)
            for i, btn in enumerate(self.menu_buttons):
                btn.setProperty("active", i == index)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            if sender == self.btn_booking:
                self.booking_calls_widget.refresh_calls()


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