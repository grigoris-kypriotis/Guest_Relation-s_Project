"""
Guest Relation Workspace — Application Shell
==============================================
Thin orchestration layer: sidebar navigation, stacked widget dispatch, and
cross-module signal wiring. All feature logic lives in the options/ package.
"""

import sys
import uuid

import pythoncom
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QPushButton, QStackedWidget, QLabel, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QPoint

from MODULES.data_manager import ensure_workspace_directories
from MODULES.plot_viewer import PlotGraphWindow

from OPTIONS._shared_widgets import Sidebar, WorkspaceViewerDialog
from OPTIONS.configuration_option import ConfigurationWidget
from OPTIONS.stats_option import StatsWidget, ResortStatsDialog
from OPTIONS.moves_option import MovesWidget
from OPTIONS.todo_option import TodoWidget
from OPTIONS.offers_option import OffersOptionWidget
from OPTIONS.allergies_option import AllergiesWidget
from OPTIONS.cake_memo_option import CakeMemoOptionWidget
from OPTIONS.booking_calls_option import BookingCallsOptionWidget
from OPTIONS.system_data_option import SystemDataOptionWidget
from OPTIONS.logs_option import LogsWidget

__all__ = [
    "GuestRelationApp",
    "ConfigurationWidget",
    "StatsWidget",
    "ResortStatsDialog",
    "WorkspaceViewerDialog",
]


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
        self.active_category = None

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

        # -----------------------------------------------------------------
        # Instantiate all option widgets (with log callback where needed)
        # -----------------------------------------------------------------
        self.logs_widget = LogsWidget()
        log_cb = self.logs_widget.add_log

        self.config_widget = ConfigurationWidget()
        self.stats_widget = StatsWidget()
        self.moves_widget = MovesWidget()
        self.todo_widget = TodoWidget(log_callback=log_cb)
        self.offers_widget = OffersOptionWidget(log_callback=log_cb)
        self.allergies_widget = AllergiesWidget()
        self.cake_widget = CakeMemoOptionWidget(log_callback=log_cb)
        self.booking_widget = BookingCallsOptionWidget(log_callback=log_cb)
        self.system_data_widget = SystemDataOptionWidget()

        # Map category keys to their widgets for dispatch
        self.option_widgets = {
            "CONFIG":      self.config_widget,
            "STATS":       self.stats_widget,
            "MOVES":       self.moves_widget,
            "TODO":        self.todo_widget,
            "OFFERS":      self.offers_widget,
            "ALLERGIES":   self.allergies_widget,
            "CAKE":        self.cake_widget,
            "BOOKING":     self.booking_widget,
            "SYSTEM_DATA": self.system_data_widget,
            "LOGS":        self.logs_widget,
        }

        # -----------------------------------------------------------------
        # Sidebar setup
        # -----------------------------------------------------------------
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

        self.offers_btn_create.clicked.connect(self.offers_widget.run_offers_creation)
        self.offers_btn_update.clicked.connect(self.offers_widget.run_offers_update)
        self.btn_save.clicked.connect(self.offers_widget.handle_doc_save)
        self.btn_close.clicked.connect(self.offers_widget.handle_doc_close)
        self.btn_save_close.clicked.connect(self.offers_widget.handle_doc_save_and_close)

        offers_submenu_layout.addWidget(self.offers_btn_create)
        offers_submenu_layout.addWidget(self.offers_btn_update)
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

        self.btn_cake_open_tpl.clicked.connect(self.cake_widget.open_cake_memo_template)
        self.btn_cake_save.clicked.connect(self.cake_widget.handle_cake_save)
        self.btn_cake_close.clicked.connect(self.cake_widget.handle_cake_close)
        self.btn_cake_save_close.clicked.connect(self.cake_widget.handle_cake_save_and_close)

        cake_submenu_layout.addWidget(self.btn_cake_open_tpl)
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

        # -----------------------------------------------------------------
        # Register all option widgets into the stacked widget
        # -----------------------------------------------------------------
        # Order matters for index compatibility, but we use references not indices
        for key in ["CONFIG", "STATS", "MOVES", "TODO", "OFFERS",
                     "ALLERGIES", "CAKE", "BOOKING", "SYSTEM_DATA", "LOGS"]:
            self.stacked_content.addWidget(self.option_widgets[key])

        # Clean Canvas View (empty landing page)
        self.empty_view = QWidget()
        empty_layout = QVBoxLayout(self.empty_view)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_clean = QLabel("Select an option from the menu to get started.")
        lbl_clean.setStyleSheet("font-size: 14px; color: #999999; font-style: italic;")
        empty_layout.addWidget(lbl_clean)
        self.stacked_content.addWidget(self.empty_view)

        # -----------------------------------------------------------------
        # Cross-widget signal connections
        # -----------------------------------------------------------------
        self.config_widget.data_updated.connect(self.stats_widget.refresh_stats)
        self.config_widget.data_updated.connect(self.booking_widget.refresh_calls)
        self.booking_widget.feedback_submitted.connect(self.handle_booking_feedback_to_todo)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stacked_content)

        self.handle_category_click("STATS")
        self.add_log("All Activity", "Application initialized and ready. Live Stats mounted.", "INFO")

    # -----------------------------------------------------------------
    # COM pump (required for embedded Office)
    # -----------------------------------------------------------------
    def pump_com_messages(self) -> None:
        pythoncom.PumpWaitingMessages()

    # -----------------------------------------------------------------
    # Menu dispatch
    # -----------------------------------------------------------------
    def show_popout_menu(self) -> None:
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

    def open_plot_window(self) -> None:
        if self.plot_window is None or not self.plot_window.isVisible():
            self.plot_window = PlotGraphWindow()
            self.plot_window.show()
        else:
            self.plot_window.raise_()
            self.plot_window.activateWindow()
        self.add_log("All Activity", "Resort Node Graph Visualization (Plot) window opened.", "INFO")

    def collapse_all_submenus(self) -> None:
        self.offers_submenu.hide()
        self.cake_submenu.hide()

    def select_category(self, cat_key: str) -> None:
        """Dictionary-dispatched category selection — replaces if/elif chain."""
        self.active_category = cat_key
        self.collapse_all_submenus()

        widget = self.option_widgets.get(cat_key)
        if widget:
            self.stacked_content.setCurrentWidget(widget)
            widget.activate()

        # Show relevant submenus
        if cat_key == "OFFERS":
            self.offers_submenu.show()
        elif cat_key == "CAKE":
            self.cake_submenu.show()

        self.update_sidebar_button_states()

    def handle_category_click(self, cat_key: str) -> None:
        """Toggle: clicking the same category deselects it."""
        if getattr(self, "active_category", None) == cat_key:
            self.active_category = None
            self.collapse_all_submenus()
            self.stacked_content.setCurrentWidget(self.empty_view)
            self.update_sidebar_button_states()
            return
        self.select_category(cat_key)

    def update_sidebar_button_states(self) -> None:
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

    # -----------------------------------------------------------------
    # Logging (delegates to LogsWidget)
    # -----------------------------------------------------------------
    def add_log(self, category: str, message: str, level: str = "INFO") -> None:
        self.logs_widget.add_log(category, message, level)

    # -----------------------------------------------------------------
    # Cross-widget handlers
    # -----------------------------------------------------------------
    def handle_booking_feedback_to_todo(self, room: str, comment: str) -> None:
        desc = f"Feedback on exclusivi: {comment} - Room {room}"
        self.todo_widget.add_task_auto(desc)
        self.add_log("To Do List", f"Booking call feedback captured: {desc}", "INFO")


# =============================================================================
# Main Entrypoint
# =============================================================================

if __name__ == "__main__":
    ensure_workspace_directories()
    app = QApplication(sys.argv)
    window = GuestRelationApp()
    window.show()
    sys.exit(app.exec())