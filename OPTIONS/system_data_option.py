"""
System Data Option: Landing page for DATABASE/ inspection.
============================================================
Provides SystemDataOptionWidget with tabbed views for master state,
Sandy Beach arrivals, room moves, and checkout records.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)

from MODULES.data_manager import InHouseDataManager


class SystemDataOptionWidget(QWidget):
    """
    Landing Page Data Records Dashboard:
    Direct inspection of active state and historical datasets stored in DATABASE/.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
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

    def load_all_records(self) -> None:
        """Alias for refresh_data() — used by app.py for backward compatibility."""
        self.refresh_data()

    def refresh_data(self) -> None:
        """Reload all data from DATABASE/ JSON files."""
        try:
            self._do_refresh_data()
        except Exception as e:
            print(f"[SystemData] Refresh error: {e}")

    def _do_refresh_data(self) -> None:
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

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        try:
            self.refresh_data()
        except Exception as e:
            print(f"[SystemData] Activation error: {e}")
