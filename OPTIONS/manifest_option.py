import os
import csv
from datetime import date
from typing import Any, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QHeaderView, QTableWidgetItem, QMessageBox, QFileDialog
)

from MODULES.data_manager import InHouseDataManager, OUTPUT_DIR

class ManifestWidget(QWidget):
    """
    Standalone widget for the Guest Manifest data table, fully decoupled from the Visual Analytics Suite.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_manifest()
    
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        lbl_header = QLabel("📋 Active In-House Guest Manifest")
        lbl_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        layout.addWidget(lbl_header)
        
        lbl_sub = QLabel("Search, filter, and inspect the current master in-house list directly with standardized English headers.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748b;")
        layout.addWidget(lbl_sub)
        
        man_bar = QHBoxLayout()
        lbl_man_tag = QLabel("Filter Manifest:")
        lbl_man_tag.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 12px;")
        man_bar.addWidget(lbl_man_tag)
        
        self.cmb_filter_block = QComboBox()
        self.cmb_filter_block.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-weight: bold;
                color: #1e293b;
            }
        """)
        self.cmb_filter_block.addItems(["All Blocks",
                                        "1100s", "1200s", "1300s", "1400s", "1500s", "1600s", "1700s", "1800s", "1900s",
                                        "2000s", "3000s", "4000s", "5000s", "6000s", "7000s", "8000s"])
        self.cmb_filter_block.currentIndexChanged.connect(self._filter_table)
        man_bar.addWidget(self.cmb_filter_block)
        
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Filter by Room, Guest Name, Booking ID, Agency...")
        self.txt_search.setStyleSheet("padding: 5px 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        self.txt_search.textChanged.connect(self._filter_table)
        man_bar.addWidget(self.txt_search, stretch=1)
        
        btn_export = QPushButton("📥 Export CSV")
        btn_export.setStyleSheet("""
            QPushButton { background-color: #059669; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #10b981; }
        """)
        btn_export.clicked.connect(self._export_manifest_csv)
        man_bar.addWidget(btn_export)
        
        layout.addLayout(man_bar)
        
        self.table_inhouse = QTableWidget(0, 8)
        self.table_inhouse.setHorizontalHeaderLabels([
            "Room", "Booking ID", "Guest Name(s)", "Arrival", "Departure", "Room Type", "Agency", "Meal Plan"
        ])
        self.table_inhouse.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table_inhouse.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table_inhouse.setAlternatingRowColors(True)
        self.table_inhouse.setSortingEnabled(True)
        layout.addWidget(self.table_inhouse)
        
    def activate(self) -> None:
        self.refresh_manifest()
        
    def refresh_manifest(self) -> None:
        master = self.data_manager.load_master_state()
        if not master:
            self.table_inhouse.setRowCount(0)
            return
            
        sorted_bookings = sorted(master.items(), key=lambda x: str(x[1].get("Room", "")))
        
        self.table_inhouse.setSortingEnabled(False)
        self.table_inhouse.setRowCount(len(sorted_bookings))
        
        for r_idx, (b_id, b_data) in enumerate(sorted_bookings):
            g_list = b_data.get("Guests") or b_data.get("Πελάτες", [])
            g_str = ", ".join(g_list) if isinstance(g_list, list) else str(g_list)
            
            self.table_inhouse.setItem(r_idx, 0, QTableWidgetItem(str(b_data.get("Room") or b_data.get("Δωμάτιο", ""))))
            self.table_inhouse.setItem(r_idx, 1, QTableWidgetItem(str(b_id)))
            self.table_inhouse.setItem(r_idx, 2, QTableWidgetItem(g_str))
            self.table_inhouse.setItem(r_idx, 3, QTableWidgetItem(str(b_data.get("Arrival") or b_data.get("Άφιξη", ""))))
            self.table_inhouse.setItem(r_idx, 4, QTableWidgetItem(str(b_data.get("Departure") or b_data.get("Αναχώρηση", ""))))
            self.table_inhouse.setItem(r_idx, 5, QTableWidgetItem(str(b_data.get("Room Type") or b_data.get("Τύπος Δωματίου", ""))))
            self.table_inhouse.setItem(r_idx, 6, QTableWidgetItem(str(b_data.get("Agency") or b_data.get("Χρεώστης", ""))))
            self.table_inhouse.setItem(r_idx, 7, QTableWidgetItem(str(b_data.get("Meal Plan") or b_data.get("Τύπος Γεύματος", ""))))
            
        self.table_inhouse.setSortingEnabled(True)
        self._filter_table()
        
    def _filter_table(self) -> None:
        query = self.txt_search.text().strip().lower()
        block_filter = self.cmb_filter_block.currentText()

        for r in range(self.table_inhouse.rowCount()):
            room = self.table_inhouse.item(r, 0).text().strip() if self.table_inhouse.item(r, 0) else ""

            # Block prefix filter
            block_match = True
            if block_filter != "All Blocks":
                prefix = block_filter.replace("s", "")
                block_match = room.startswith(prefix[:2])

            # Query match across row
            query_match = True
            if query:
                row_texts = [
                    (self.table_inhouse.item(r, c).text() if self.table_inhouse.item(r, c) else "")
                    for c in range(self.table_inhouse.columnCount())
                ]
                combined = " ".join(row_texts).lower()
                query_match = query in combined

            self.table_inhouse.setRowHidden(r, not (block_match and query_match))

    def _export_manifest_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Guest Manifest",
            os.path.join(OUTPUT_DIR, f"guest_manifest_{date.today().strftime('%Y%m%d')}.csv"),
            "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                headers = [self.table_inhouse.horizontalHeaderItem(c).text() for c in range(self.table_inhouse.columnCount())]
                writer.writerow(headers)
                for r in range(self.table_inhouse.rowCount()):
                    if not self.table_inhouse.isRowHidden(r):
                        row_vals = [
                            self.table_inhouse.item(r, c).text() if self.table_inhouse.item(r, c) else ""
                            for c in range(self.table_inhouse.columnCount())
                        ]
                        writer.writerow(row_vals)
            QMessageBox.information(self, "Export Successful", f"Guest manifest exported successfully to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export manifest:\n{e}")
