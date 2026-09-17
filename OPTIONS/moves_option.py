"""
Moves Option: Dedicated room moves history view.
=================================================
Reads directly from DATABASE/ROOM MOVES/room_moves.json and displays
historical room changes in a searchable, color-coded table.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit
)
from PyQt6.QtGui import QColor, QFont

from MODULES.data_manager import InHouseDataManager


class MovesWidget(QWidget):
    """
    Dedicated view in the main sidebar to inspect rooms that changed yesterday/recently,
    reading directly from DATABASE/ROOM MOVES/room_moves.json.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_moves()

    def _init_ui(self) -> None:
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

    def refresh_moves(self) -> None:
        try:
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
        except Exception as e:
            print(f"[Moves] Refresh error: {e}")

    def _filter_table(self) -> None:
        query = self.txt_search.text().strip().lower()
        for r in range(self.table_moves.rowCount()):
            old_r = self.table_moves.item(r, 3).text().lower()
            new_r = self.table_moves.item(r, 4).text().lower()
            b_id = self.table_moves.item(r, 1).text().lower()
            guest = self.table_moves.item(r, 2).text().lower()
            match = (not query) or (query in old_r) or (query in new_r) or (query in b_id) or (query in guest)
            self.table_moves.setRowHidden(r, not match)

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        try:
            self.refresh_moves()
        except Exception as e:
            print(f"[Moves] Activation error: {e}")
