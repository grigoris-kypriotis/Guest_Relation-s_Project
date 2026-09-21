"""
System Data Option: Landing page for DATABASE/ inspection.
============================================================
Provides SystemDataOptionWidget with tabbed views for master state,
Sandy Beach arrivals, room moves, and checkout records.
Includes dynamic room and keyword filtering across all system tables.
"""

from datetime import date
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt

from MODULES.data_manager import InHouseDataManager


class SystemDataOptionWidget(QWidget):
    """
    Landing Page Data Records Dashboard:
    Direct inspection of active state and historical datasets stored in DATABASE/.
    Features interactive Room and Keyword filtering across all records.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Header Bar
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

        # Interactive Filter Toolbar
        filter_box = QHBoxLayout()
        filter_box.setSpacing(8)

        lbl_filter_tag = QLabel("🔍 Room & Keyword Filter:")
        lbl_filter_tag.setStyleSheet("font-weight: bold; color: #800020; font-size: 12px;")
        filter_box.addWidget(lbl_filter_tag)

        self.cmb_room_filter = QComboBox()
        self.cmb_room_filter.setStyleSheet("""
            QComboBox {
                padding: 5px 10px;
                border: 1px solid #FFB6C1;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-weight: bold;
                color: #800020;
                min-width: 140px;
            }
        """)
        self.cmb_room_filter.addItems([
            "All Rooms / Blocks",
            "Block 1100s",
            "Block 1200s",
            "Block 1300s",
            "Block 1400s",
            "Block 1500s",
            "Block 1600s",
            "Block 1700s",
            "Block 1800s",
            "Block 1900s",
            "Block 2000s",
            "Block 3000s",
            "Block 4000s",
            "Block 5000s",
            "Block 6000s",
            "Block 7000s",
            "Block 8000s",
        ])
        self.cmb_room_filter.currentIndexChanged.connect(self._apply_filter)
        filter_box.addWidget(self.cmb_room_filter)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter by Room, Guest Name, Booking ID, Agency...")
        self.txt_filter.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #FFB6C1;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-size: 12px;
            }
        """)
        self.txt_filter.returnPressed.connect(self._apply_filter)
        self.txt_filter.textChanged.connect(self._apply_filter)
        filter_box.addWidget(self.txt_filter, stretch=1)

        self.btn_filter = QPushButton("🔍 Filter")
        self.btn_filter.setStyleSheet("""
            QPushButton {
                background-color: #800020;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 14px;
                border: none;
            }
            QPushButton:hover { background-color: #A0002A; }
        """)
        self.btn_filter.clicked.connect(self._apply_filter)
        filter_box.addWidget(self.btn_filter)

        self.btn_clear_filter = QPushButton("✖ Clear")
        self.btn_clear_filter.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #374151;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
                border: 1px solid #D1D5DB;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        self.btn_clear_filter.clicked.connect(self._clear_filter)
        filter_box.addWidget(self.btn_clear_filter)

        self.lbl_filter_count = QLabel("")
        self.lbl_filter_count.setStyleSheet("font-size: 11px; color: #4B5563; font-weight: bold;")
        filter_box.addWidget(self.lbl_filter_count)

        main_layout.addLayout(filter_box)

        # Tabbed Records Container
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #FFB6C1; background-color: #FFFFFF; border-radius: 6px; }
            QTabBar::tab { background-color: #FFE4E1; border: 1px solid #FFB6C1; padding: 8px 14px; margin-right: 3px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #FF69B4; color: #FFFFFF; }
        """)
        self.tab_widget.currentChanged.connect(lambda _: self._apply_filter())

        # Tab 1: Master State & In-House List
        tab_master = QWidget()
        layout_master = QVBoxLayout(tab_master)
        self.lbl_master_stats = QLabel("Loading Master State...")
        self.lbl_master_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_master.addWidget(self.lbl_master_stats)

        self.table_master = QTableWidget(0, 7)
        self.table_master.setHorizontalHeaderLabels([
            "Booking ID", "Room", "Guest Name(s)", "Arrival", "Departure", "Room Type", "Agency"
        ])
        self.table_master.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_master.setAlternatingRowColors(True)
        self.table_master.setSortingEnabled(True)
        layout_master.addWidget(self.table_master)
        self.tab_widget.addTab(tab_master, "👥 Master State & In-House List")

        # Tab 2: Sandy Beach Arrivals
        tab_beach = QWidget()
        layout_beach = QVBoxLayout(tab_beach)
        self.lbl_beach_stats = QLabel("Loading Sandy Beach Arrivals...")
        self.lbl_beach_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_beach.addWidget(self.lbl_beach_stats)

        self.table_beach_arrivals = QTableWidget(0, 8)
        self.table_beach_arrivals.setHorizontalHeaderLabels([
            "Room", "Booking ID", "Guest Name(s)", "Adults", "Kids", "Arrival", "Departure", "Agency"
        ])
        self.table_beach_arrivals.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_beach_arrivals.setAlternatingRowColors(True)
        self.table_beach_arrivals.setSortingEnabled(True)
        layout_beach.addWidget(self.table_beach_arrivals)
        self.tab_widget.addTab(tab_beach, "🏖️ Sandy Beach Arrivals")

        # Tab 3: Room Moves History
        tab_moves = QWidget()
        layout_moves = QVBoxLayout(tab_moves)
        self.lbl_moves_stats = QLabel("Loading Room Moves...")
        self.lbl_moves_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_moves.addWidget(self.lbl_moves_stats)

        self.table_moves = QTableWidget(0, 6)
        self.table_moves.setHorizontalHeaderLabels([
            "Date", "Booking ID", "Guest Name(s)", "Previous Room", "New Room", "Departure"
        ])
        self.table_moves.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_moves.setAlternatingRowColors(True)
        self.table_moves.setSortingEnabled(True)
        layout_moves.addWidget(self.table_moves)
        self.tab_widget.addTab(tab_moves, "🔄 Room Moves History")

        # Tab 4: Checkout Records
        tab_checkouts = QWidget()
        layout_checkouts = QVBoxLayout(tab_checkouts)
        self.lbl_checkouts_stats = QLabel("Loading Checkouts...")
        self.lbl_checkouts_stats.setStyleSheet("background-color: #FFF0F5; padding: 8px 12px; border: 1px solid #FFB6C1; border-radius: 4px; font-weight: bold; color: #800020;")
        layout_checkouts.addWidget(self.lbl_checkouts_stats)

        self.table_checkouts = QTableWidget(0, 5)
        self.table_checkouts.setHorizontalHeaderLabels([
            "Checkout Date", "Booking ID", "Guest Name(s)", "Room", "Departure"
        ])
        self.table_checkouts.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_checkouts.setAlternatingRowColors(True)
        self.table_checkouts.setSortingEnabled(True)
        layout_checkouts.addWidget(self.table_checkouts)
        self.tab_widget.addTab(tab_checkouts, "🚪 Checkout Records")

        main_layout.addWidget(self.tab_widget)
        self.tabs = self.tab_widget

    def load_all_records(self) -> None:
        """Alias for refresh_data() — used for backward compatibility."""
        self.refresh_data()

    def refresh_data(self) -> None:
        """Reload all data from DATABASE/ JSON files."""
        try:
            self._do_refresh_data()
            self._apply_filter()
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
            f"Active In-House Bookings: {len(bookings_dict)} | Last Sync Date: {last_dt} | Timestamp: {last_ts} | File: DATABASE/HOTEL STATE/master_state.json"
        )
        self.table_master.setSortingEnabled(False)
        self.table_master.setRowCount(0)
        for b_id, b_data in bookings_dict.items():
            r = self.table_master.rowCount()
            self.table_master.insertRow(r)
            self.table_master.setItem(r, 0, QTableWidgetItem(str(b_id)))
            rm = str(b_data.get("Room") or b_data.get("Δωμάτιο", ""))
            self.table_master.setItem(r, 1, QTableWidgetItem(rm))
            guests = b_data.get("Guests") or b_data.get("Πελάτες", [])
            g_str = ", ".join(guests) if isinstance(guests, list) else str(guests)
            self.table_master.setItem(r, 2, QTableWidgetItem(g_str))
            self.table_master.setItem(r, 3, QTableWidgetItem(str(b_data.get("Arrival") or b_data.get("Άφιξη", ""))))
            self.table_master.setItem(r, 4, QTableWidgetItem(str(b_data.get("Departure") or b_data.get("Αναχώρηση", ""))))
            self.table_master.setItem(r, 5, QTableWidgetItem(str(b_data.get("Room Type") or b_data.get("Τύπος Δωματίου", "Standard"))))
            self.table_master.setItem(r, 6, QTableWidgetItem(str(b_data.get("Agency") or b_data.get("Χρεώστης", b_data.get("agency", "")))))
        self.table_master.setSortingEnabled(True)

        # 2. Sandy Beach Arrivals
        arr_state = self.data_manager.load_arrivals_state()
        beach_arr = arr_state.get("SANDY BEACH", {})
        if not beach_arr and bookings_dict:
            # Fallback: scan master_state for bookings whose arrival date matches last_dt or today
            today_str1 = date.today().strftime("%d/%m/%Y")
            today_str2 = f"{date.today().day}/{date.today().month}/{date.today().year}"
            target_dates = {str(last_dt), today_str1, today_str2}
            fallback_arrivals = {}
            for b_id, b_data in bookings_dict.items():
                arr = str(b_data.get("Arrival") or b_data.get("Άφιξη", "")).strip()
                if arr in target_dates:
                    fallback_arrivals[b_id] = {
                        "room": str(b_data.get("Room") or b_data.get("Δωμάτιο", "")),
                        "Room": str(b_data.get("Room") or b_data.get("Δωμάτιο", "")),
                        "guests": b_data.get("Guests") or b_data.get("Πελάτες", []),
                        "adults": str(b_data.get("Adults") or b_data.get("Σύν. Ατόμων", "1")),
                        "children": str(b_data.get("Children") or b_data.get("Αρ. Παιδ", "0")),
                        "arrival": arr,
                        "departure": str(b_data.get("Departure") or b_data.get("Αναχώρηση", "")),
                        "agency": str(b_data.get("Agency") or b_data.get("Χρεώστης", "")),
                        "room_type": str(b_data.get("Room Type") or b_data.get("Τύπος Δωματίου", ""))
                    }
            if fallback_arrivals:
                beach_arr = fallback_arrivals
                self.data_manager.save_arrivals_state(beach_arr)

        self.lbl_beach_stats.setText(
            f"Active Sandy Beach Arrivals: {len(beach_arr)} | File: DATABASE/SANDY BEACH/ARRIVALS/today_arrivals.json"
        )
        self.table_beach_arrivals.setSortingEnabled(False)
        self.table_beach_arrivals.setRowCount(0)
        for b_id, r_info in beach_arr.items():
            r = self.table_beach_arrivals.rowCount()
            self.table_beach_arrivals.insertRow(r)
            rm = str(r_info.get("Room") or r_info.get("room", ""))
            self.table_beach_arrivals.setItem(r, 0, QTableWidgetItem(rm))
            self.table_beach_arrivals.setItem(r, 1, QTableWidgetItem(str(b_id)))
            g_raw = r_info.get("Guests") or r_info.get("guests", [])
            g_names = ", ".join(g_raw) if isinstance(g_raw, list) else str(g_raw)
            self.table_beach_arrivals.setItem(r, 2, QTableWidgetItem(g_names))
            self.table_beach_arrivals.setItem(r, 3, QTableWidgetItem(str(r_info.get("Adults") or r_info.get("adults", "1"))))
            self.table_beach_arrivals.setItem(r, 4, QTableWidgetItem(str(r_info.get("Children") or r_info.get("children", "0"))))
            self.table_beach_arrivals.setItem(r, 5, QTableWidgetItem(str(r_info.get("Arrival") or r_info.get("arrival", ""))))
            self.table_beach_arrivals.setItem(r, 6, QTableWidgetItem(str(r_info.get("Departure") or r_info.get("departure", ""))))
            self.table_beach_arrivals.setItem(r, 7, QTableWidgetItem(str(r_info.get("Agency") or r_info.get("agency", ""))))
        self.table_beach_arrivals.setSortingEnabled(True)

        # 3. Room Moves History
        moves_data = self.data_manager.load_room_moves_history()
        moves_msg = f"Archived Room Moves: {len(moves_data)} | File: DATABASE/ROOM MOVES/room_moves.json"
        if not moves_data:
            moves_msg += " (Moves are detected automatically when consecutive PMS In-House files are imported)"
        self.lbl_moves_stats.setText(moves_msg)
        self.table_moves.setSortingEnabled(False)
        self.table_moves.setRowCount(0)
        for rm in moves_data:
            r = self.table_moves.rowCount()
            self.table_moves.insertRow(r)
            self.table_moves.setItem(r, 0, QTableWidgetItem(str(rm.get("date", ""))))
            self.table_moves.setItem(r, 1, QTableWidgetItem(str(rm.get("booking_id", ""))))
            g_names = rm.get("guests") or rm.get("Πελάτες", [])
            g_str = ", ".join(g_names) if isinstance(g_names, list) else str(g_names)
            self.table_moves.setItem(r, 2, QTableWidgetItem(g_str))
            self.table_moves.setItem(r, 3, QTableWidgetItem(str(rm.get("old_room", ""))))
            self.table_moves.setItem(r, 4, QTableWidgetItem(str(rm.get("new_room", ""))))
            self.table_moves.setItem(r, 5, QTableWidgetItem(str(rm.get("departure", ""))))
        self.table_moves.setSortingEnabled(True)

        # 4. Checkout Records
        co_payload = self.data_manager.load_checkouts_history()
        records = co_payload.get("records", [])
        co_msg = f"Archived Check-Outs: {len(records)} | File: DATABASE/CHECK OUT HISTORY/checkouts.json"
        if not records:
            co_msg += " (Check-outs are archived automatically when departing guests leave in new PMS In-House imports)"
        self.lbl_checkouts_stats.setText(co_msg)
        self.table_checkouts.setSortingEnabled(False)
        self.table_checkouts.setRowCount(0)
        for co in records:
            r = self.table_checkouts.rowCount()
            self.table_checkouts.insertRow(r)
            self.table_checkouts.setItem(r, 0, QTableWidgetItem(str(co.get("checkout_date", ""))))
            self.table_checkouts.setItem(r, 1, QTableWidgetItem(str(co.get("booking_id", ""))))
            g_names = co.get("guests") or co.get("Πελάτες", [])
            g_str = ", ".join(g_names) if isinstance(g_names, list) else str(g_names)
            self.table_checkouts.setItem(r, 2, QTableWidgetItem(g_str))
            self.table_checkouts.setItem(r, 3, QTableWidgetItem(str(co.get("room") or co.get("Room", ""))))
            self.table_checkouts.setItem(r, 4, QTableWidgetItem(str(co.get("departure", ""))))
        self.table_checkouts.setSortingEnabled(True)

    def _get_active_table(self) -> Optional[QTableWidget]:
        idx = self.tab_widget.currentIndex()
        if idx == 0:
            return self.table_master
        elif idx == 1:
            return self.table_beach_arrivals
        elif idx == 2:
            return self.table_moves
        elif idx == 3:
            return self.table_checkouts
        return None

    def _apply_filter(self) -> None:
        """Applies room prefix filter and text search across the active tab's table."""
        query = self.txt_filter.text().strip().lower()
        block_selection = self.cmb_room_filter.currentText()

        table = self._get_active_table()
        if not table:
            return

        total_rows = table.rowCount()
        visible_count = 0

        # Room column index: 1 in master, 0 in beach arrivals, 4 in moves (new_room), 3 in checkouts
        idx = self.tab_widget.currentIndex()
        room_col = 1 if idx == 0 else (0 if idx == 1 else (4 if idx == 2 else 3))

        for r in range(total_rows):
            room_item = table.item(r, room_col)
            room_val = room_item.text().strip() if room_item else ""

            # Check room block filter
            block_match = True
            if block_selection != "All Rooms / Blocks":
                if "Block 1100s" in block_selection:
                    block_match = room_val.startswith("11")
                elif "Block 1200s" in block_selection:
                    block_match = room_val.startswith("12")
                elif "Block 1300s" in block_selection:
                    block_match = room_val.startswith("13")
                elif "Block 1400s" in block_selection:
                    block_match = room_val.startswith("14")
                elif "Block 1500s" in block_selection:
                    block_match = room_val.startswith("15")
                elif "Block 1600s" in block_selection:
                    block_match = room_val.startswith("16")
                elif "Block 1700s" in block_selection:
                    block_match = room_val.startswith("17")
                elif "Block 1800s" in block_selection:
                    block_match = room_val.startswith("18")
                elif "Block 1900s" in block_selection:
                    block_match = room_val.startswith("19")
                elif "Block 2000s" in block_selection:
                    block_match = room_val.startswith("20")
                elif "Block 3000s" in block_selection:
                    block_match = room_val.startswith("30")
                elif "Block 4000s" in block_selection:
                    block_match = room_val.startswith("40")
                elif "Block 5000s" in block_selection:
                    block_match = room_val.startswith("50")
                elif "Block 6000s" in block_selection:
                    block_match = room_val.startswith("60")
                elif "Block 7000s" in block_selection:
                    block_match = room_val.startswith("70")
                elif "Block 8000s" in block_selection:
                    block_match = room_val.startswith("80")

            # Check text query match across all cells in the row
            query_match = True
            if query:
                row_texts = [
                    (table.item(r, c).text() if table.item(r, c) else "")
                    for c in range(table.columnCount())
                ]
                combined = " ".join(row_texts).lower()
                query_match = query in combined

            show = block_match and query_match
            table.setRowHidden(r, not show)
            if show:
                visible_count += 1

        if query or block_selection != "All Rooms / Blocks":
            self.lbl_filter_count.setText(f"Showing: {visible_count} / {total_rows} records")
        else:
            self.lbl_filter_count.setText(f"Total: {total_rows} records")

    def _clear_filter(self) -> None:
        """Resets the search box and block combo box."""
        self.txt_filter.blockSignals(True)
        self.cmb_room_filter.blockSignals(True)
        self.txt_filter.clear()
        self.cmb_room_filter.setCurrentIndex(0)
        self.txt_filter.blockSignals(False)
        self.cmb_room_filter.blockSignals(False)
        self._apply_filter()

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        try:
            self.refresh_data()
        except Exception as e:
            print(f"[SystemData] Activation error: {e}")
