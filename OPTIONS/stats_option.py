"""
Stats Option: Live operational metrics, analytical dashboard, and guest manifest.
=================================================================================
Contains the StatsWidget (embedded in main window) and ResortStatsDialog (pop-out).
Features KPI cards, breakdown cards, 4-chart matplotlib suite, and filterable guest table.
"""

import os
import re
import json
import collections
import warnings
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QScrollArea, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QGridLayout, QLineEdit,
    QDialog
)
from PyQt6.QtCore import Qt

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from MODULES.data_manager import (
    InHouseDataManager, HOTEL_DATASET_PATH, BASE_DIR, PLOT_DIR
)


# =============================================================================
# ResortStatsDialog: Dedicated Pop-Out Window for Resort Analytics
# =============================================================================

class ResortStatsDialog(QDialog):
    """
    Dedicated Pop-Out Window for Resort Analytics & Guest Manifest.
    Scans HotelDataSet.json (physical capacity, blocks, venues) along with any active guest manifest
    (CSV, XLSX, or master_state.json) to calculate operational metrics.
    """
    def __init__(self, hotel_json_path: Optional[str] = None, manifest_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resort Analytics & Guest Manifest")
        self.resize(1150, 780)
        self.data_manager = InHouseDataManager()

        if not hotel_json_path:
            hotel_json_path = HOTEL_DATASET_PATH if os.path.exists(HOTEL_DATASET_PATH) else os.path.join(BASE_DIR, "HotelDataSet.json")
        self.hotel_json_path = str(hotel_json_path)

        if not manifest_path:
            cand = os.path.join(BASE_DIR, "inhouselist.csv")
            manifest_path = cand if os.path.exists(cand) else "inhouselist.csv"
        self.manifest_path = str(manifest_path)

        self.hotel_data = self._load_json_data()
        self.manifest_df = self._load_manifest_data()

        self._init_ui()

    def _load_json_data(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.hotel_json_path):
            try:
                with open(self.hotel_json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _load_manifest_data(self):
        try:
            import pandas as pd
        except ImportError:
            pd = None

        if os.path.exists(self.manifest_path) and pd is not None:
            try:
                if self.manifest_path.endswith(".csv"):
                    try:
                        return pd.read_csv(self.manifest_path, sep=None, engine="python")
                    except Exception:
                        return pd.read_csv(self.manifest_path, encoding="latin1")
                return pd.read_excel(self.manifest_path)
            except Exception:
                pass

        # Fallback to master_state.json from data_manager
        master = self.data_manager.load_master_state()
        if master and pd is not None:
            rows = []
            for b_id, b_data in master.items():
                g_list = b_data.get("Πελάτες", [])
                g_str = ", ".join(g_list) if isinstance(g_list, list) else str(g_list)
                rows.append({
                    "Room": str(b_data.get("Δωμάτιο", "")),
                    "Booking ID": str(b_id),
                    "Guest Name": g_str,
                    "Arrival": str(b_data.get("Άφιξη", "")),
                    "Departure": str(b_data.get("Αναχώρηση", "")),
                    "Board": str(b_data.get("Τύπος Γεύματος", "AI")),
                    "Debtor / Agency": str(b_data.get("Χρεώστης", b_data.get("agency", ""))),
                    "Nationality": str(b_data.get("Αγορά", "")),
                    "Pax": len(g_list) if isinstance(g_list, list) else 1
                })
            return pd.DataFrame(rows)

        return pd.DataFrame() if pd is not None else None

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Header bar
        hdr_box = QHBoxLayout()
        v_title = QVBoxLayout()
        t_lbl = QLabel("📊 RESORT ANALYTICS & GUEST MANIFEST")
        t_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #800020;")
        s_lbl = QLabel(f"Source JSON: {os.path.basename(self.hotel_json_path)} | Manifest: {os.path.basename(self.manifest_path)}")
        s_lbl.setStyleSheet("font-size: 11px; color: #555555;")
        v_title.addWidget(t_lbl)
        v_title.addWidget(s_lbl)
        hdr_box.addLayout(v_title)
        hdr_box.addStretch()

        btn_close = QPushButton("✕ Close")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #800020;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #A00028; }
        """)
        btn_close.clicked.connect(self.close)
        hdr_box.addWidget(btn_close)
        layout.addLayout(hdr_box)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #f1f5f9;
                color: #334155;
                padding: 8px 18px;
                font-weight: bold;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #e11d48;
                border-bottom: 2px solid #e11d48;
            }
        """)

        # Tab 1: Scrollable Visual Analytics Suite
        self.analytics_scroll = QScrollArea()
        self.analytics_scroll.setWidgetResizable(True)
        self.analytics_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.analytics_widget = QWidget()
        self.analytics_layout = QVBoxLayout(self.analytics_widget)
        self.analytics_layout.setContentsMargins(8, 8, 8, 8)
        self.analytics_layout.setSpacing(14)
        self._populate_analytics()
        self.analytics_scroll.setWidget(self.analytics_widget)

        # Tab 2: Guest Manifest Table
        self.manifest_widget = QWidget()
        self.manifest_layout = QVBoxLayout(self.manifest_widget)
        self.manifest_layout.setContentsMargins(10, 10, 10, 10)
        self.manifest_layout.setSpacing(10)
        self._populate_manifest()

        self.tabs.addTab(self.analytics_scroll, "📈 Visual Analytics Suite")
        self.tabs.addTab(self.manifest_widget, "📋 Guest Manifest Table")
        layout.addWidget(self.tabs, stretch=1)

    def _create_stat_card(self, title: str, value: str, subtitle: str = "") -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        c_layout = QVBoxLayout(card)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; text-transform: uppercase;")
        v_lbl = QLabel(str(value))
        v_lbl.setStyleSheet("color: #0f172a; font-size: 20px; font-weight: 800;")
        s_lbl = QLabel(subtitle)
        s_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        c_layout.addWidget(t_lbl)
        c_layout.addWidget(v_lbl)
        if subtitle:
            c_layout.addWidget(s_lbl)
        return card

    def _populate_analytics(self) -> None:
        # 1. Physical Capacity from JSON
        total_physical_rooms = sum(
            node.get("room_details", {}).get("total_rooms", 0)
            for node in self.hotel_data if node.get("category") == "Rooms"
        )
        total_blocks = len([n for n in self.hotel_data if "BLOCK" in n.get("name", "")])
        total_facilities = len([n for n in self.hotel_data if n.get("category") != "Rooms"])

        # 2. In-House Guest Manifest Data
        df = self.manifest_df
        total_inhouse_rooms = 0
        total_pax = 0
        board_counts = {}
        nat_counts = {}

        if df is not None and not getattr(df, 'empty', True):
            room_col = next((c for c in df.columns if "room" in str(c).lower() or "δωμ" in str(c).lower()), None)
            pax_col = next((c for c in df.columns if "pax" in str(c).lower() or "guest" in str(c).lower() or "ενηλ" in str(c).lower()), None)
            board_col = next((c for c in df.columns if "board" in str(c).lower() or "meal" in str(c).lower() or "γευμ" in str(c).lower()), None)
            nat_col = next((c for c in df.columns if "nat" in str(c).lower() or "country" in str(c).lower() or "αγορ" in str(c).lower() or "market" in str(c).lower() or "debtor" in str(c).lower() or "agency" in str(c).lower()), None)

            total_inhouse_rooms = df[room_col].nunique() if room_col else len(df)
            try:
                import pandas as pd
                if pax_col and pd.api.types.is_numeric_dtype(df[pax_col]):
                    total_pax = int(df[pax_col].sum())
                else:
                    total_pax = len(df)
            except Exception:
                total_pax = len(df)

            if board_col:
                board_counts = df[board_col].value_counts().to_dict()
            if nat_col:
                nat_counts = df[nat_col].value_counts().head(5).to_dict()
        else:
            master = self.data_manager.load_master_state()
            total_inhouse_rooms = len(master)
            total_pax = sum(len(b.get("Πελάτες", [])) if isinstance(b.get("Πελάτες"), list) else 1 for b in master.values())
            b_counter = collections.Counter()
            n_counter = collections.Counter()
            for b in master.values():
                b_counter[b.get("Τύπος Γεύματος") or "All Inclusive"] += 1
                n_counter[b.get("Αγορά") or b.get("Χρεώστης") or "General"] += 1
            board_counts = dict(b_counter.most_common(5))
            nat_counts = dict(n_counter.most_common(5))

        occ_pct = (total_inhouse_rooms / total_physical_rooms * 100.0) if total_physical_rooms > 0 else 0.0

        # Summary KPIs Grid
        kpi_grid = QGridLayout()
        kpi_grid.addWidget(self._create_stat_card("Total Capacity", f"{total_physical_rooms} Rooms", f"{total_blocks} Blocks"), 0, 0)
        kpi_grid.addWidget(self._create_stat_card("Occupied Rooms", f"{total_inhouse_rooms}", f"{occ_pct:.1f}% Occupancy"), 0, 1)
        kpi_grid.addWidget(self._create_stat_card("In-House Guests", f"{total_pax} Pax", "Active In-House"), 0, 2)
        kpi_grid.addWidget(self._create_stat_card("Facilities & Outlets", f"{total_facilities} Venues", "Restaurants, Bars & Sports"), 0, 3)
        self.analytics_layout.addLayout(kpi_grid)

        # Breakdowns Section
        details_layout = QHBoxLayout()
        details_layout.setSpacing(12)

        # Board Types Card
        board_box = QFrame()
        board_box.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;")
        bb_layout = QVBoxLayout(board_box)
        bb_lbl = QLabel("BOARD BASIS DISTRIBUTION")
        bb_lbl.setStyleSheet("font-weight: bold; color: #1e293b; margin-bottom: 5px;")
        bb_layout.addWidget(bb_lbl)
        if board_counts:
            for b_name, count in board_counts.items():
                lbl = QLabel(f"• {b_name}: {count} guests")
                lbl.setStyleSheet("color: #475569; font-size: 12px;")
                bb_layout.addWidget(lbl)
        else:
            bb_layout.addWidget(QLabel("No board data parsed from manifest."))
        bb_layout.addStretch()
        details_layout.addWidget(board_box)

        # Nationalities Card
        nat_box = QFrame()
        nat_box.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;")
        nb_layout = QVBoxLayout(nat_box)
        nb_lbl = QLabel("TOP NATIONALITIES & MARKETS")
        nb_lbl.setStyleSheet("font-weight: bold; color: #1e293b; margin-bottom: 5px;")
        nb_layout.addWidget(nb_lbl)
        if nat_counts:
            for nat, count in nat_counts.items():
                lbl = QLabel(f"• {nat}: {count} guests")
                lbl.setStyleSheet("color: #475569; font-size: 12px;")
                nb_layout.addWidget(lbl)
        else:
            nb_layout.addWidget(QLabel("No nationality data parsed."))
        nb_layout.addStretch()
        details_layout.addWidget(nat_box)

        self.analytics_layout.addLayout(details_layout)
        self.analytics_layout.addStretch()

    def _populate_manifest(self) -> None:
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("🔍 Filter manifest by room, guest name, voucher...")
        search_bar.setStyleSheet("padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        self.manifest_layout.addWidget(search_bar)

        table = QTableWidget()
        self.manifest_layout.addWidget(table, stretch=1)

        df = self.manifest_df
        if df is not None and not getattr(df, 'empty', True):
            table.setRowCount(len(df))
            table.setColumnCount(len(df.columns))
            table.setHorizontalHeaderLabels([str(c) for c in df.columns])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            for row_idx, (_, row) in enumerate(df.iterrows()):
                for col_idx, val in enumerate(row):
                    import pandas as pd
                    val_str = str(val) if pd.notna(val) else ""
                    table.setItem(row_idx, col_idx, QTableWidgetItem(val_str))
        else:
            master = self.data_manager.load_master_state()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(["Room", "Booking ID", "Guest Name(s)", "Arrival", "Departure", "Debtor / Agency"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.setRowCount(len(master))
            for r_idx, (b_id, b_data) in enumerate(master.items()):
                g_list = b_data.get("Πελάτες", [])
                g_str = ", ".join(g_list) if isinstance(g_list, list) else str(g_list)
                table.setItem(r_idx, 0, QTableWidgetItem(str(b_data.get("Δωμάτιο", ""))))
                table.setItem(r_idx, 1, QTableWidgetItem(str(b_id)))
                table.setItem(r_idx, 2, QTableWidgetItem(g_str))
                table.setItem(r_idx, 3, QTableWidgetItem(str(b_data.get("Άφιξη", ""))))
                table.setItem(r_idx, 4, QTableWidgetItem(str(b_data.get("Αναχώρηση", ""))))
                table.setItem(r_idx, 5, QTableWidgetItem(str(b_data.get("Χρεώστης", b_data.get("agency", "")))))

        search_bar.textChanged.connect(lambda text: self._filter_manifest_table(table, text))

    def _filter_manifest_table(self, table: QTableWidget, query: str) -> None:
        query = query.lower().strip()
        for row in range(table.rowCount()):
            match = False
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item and query in item.text().lower():
                    match = True
                    break
            table.setRowHidden(row, not match)


# =============================================================================
# StatsWidget: Embedded main-window analytics view
# =============================================================================

class StatsWidget(QWidget):
    """
    Dedicated view in the main window displaying live operational metrics and analytical visualizations.
    Two-tab layout: Visual Analytics Suite + Guest Manifest Table.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._init_ui()
        self.refresh_stats()

    def _init_ui(self) -> None:
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

        btn_popout = QPushButton("↗️ Pop Out Analytics")
        btn_popout.setStyleSheet("""
            QPushButton {
                background-color: #1E3A8A;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        btn_popout.clicked.connect(self.pop_out_dialog)
        top_bar.addWidget(btn_popout)

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

        # Tabs: Visual Analytics Suite vs Guest Manifest Table
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #FFB6C1; background: white; border-radius: 6px; }
            QTabBar::tab { background: #FFE4E1; border: 1px solid #FFB6C1; padding: 8px 18px; margin-right: 3px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #800020; color: white; border-color: #800020; }
        """)

        # Tab 1: Scrollable Visual Analytics Suite
        self.analytics_scroll = QScrollArea()
        self.analytics_scroll.setWidgetResizable(True)
        self.analytics_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.analytics_widget = QWidget()
        self.analytics_layout = QVBoxLayout(self.analytics_widget)
        self.analytics_layout.setContentsMargins(8, 8, 8, 8)
        self.analytics_layout.setSpacing(14)

        # KPI Cards Grid
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)

        self.card_capacity = self._create_kpi_card("🏨 Total Capacity", "0 Rooms", "0 Blocks", "#475569")
        self.card_inhouse = self._create_kpi_card("👥 Active In-House", "0 Bookings", "0 Guests", "#1E3A8A")
        self.card_occ = self._create_kpi_card("📊 Occupancy Rate", "0.0%", "0 Physical Rooms", "#0284C7")
        self.card_facilities = self._create_kpi_card("🍽️ Outlets & Venues", "0 Facilities", "Active Venues", "#7C3AED")
        self.card_checkouts = self._create_kpi_card("🚪 Check-Outs", "0 Today", "0 Total Archived", "#065F46")
        self.card_moves = self._create_kpi_card("🔄 Room Moves", "0 Moves", "Archived History", "#B45309")
        self.card_sync = self._create_kpi_card("⏱️ Last In-House Sync", "Never", "No records", "#4338CA")

        kpi_grid.addWidget(self.card_capacity, 0, 0)
        kpi_grid.addWidget(self.card_inhouse, 0, 1)
        kpi_grid.addWidget(self.card_occ, 0, 2)
        kpi_grid.addWidget(self.card_facilities, 0, 3)
        kpi_grid.addWidget(self.card_checkouts, 1, 0)
        kpi_grid.addWidget(self.card_moves, 1, 1)
        kpi_grid.addWidget(self.card_sync, 1, 2, 1, 2)
        self.analytics_layout.addLayout(kpi_grid)

        # Breakdown Cards Section (Board Basis, Nationalities, Room Types)
        breakdown_row = QHBoxLayout()
        breakdown_row.setSpacing(12)

        self.box_board = self._create_breakdown_card("BOARD BASIS DISTRIBUTION")
        self.box_nat = self._create_breakdown_card("TOP NATIONALITIES & MARKETS")
        self.box_rooms = self._create_breakdown_card("ROOM CATEGORY BREAKDOWN")

        breakdown_row.addWidget(self.box_board)
        breakdown_row.addWidget(self.box_nat)
        breakdown_row.addWidget(self.box_rooms)
        self.analytics_layout.addLayout(breakdown_row)

        # 4-Chart Matplotlib Figure Canvas
        self.figure = Figure(figsize=(11, 7.5), dpi=100, facecolor="#FAF9F6")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(650)
        self.analytics_layout.addWidget(self.canvas)

        self.analytics_scroll.setWidget(self.analytics_widget)
        self.tabs.addTab(self.analytics_scroll, "📈 Visual Analytics Suite")

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

    def pop_out_dialog(self) -> None:
        dlg = ResortStatsDialog(parent=self)
        dlg.exec()

    def _create_kpi_card(self, title: str, main_stat: str, sub_stat: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-top: 4px solid {accent_color};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(3)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {accent_color};")
        lbl_m = QLabel(main_stat)
        lbl_m.setStyleSheet("font-size: 18px; font-weight: bold; color: #1E293B;")
        lbl_s = QLabel(sub_stat)
        lbl_s.setStyleSheet("font-size: 11px; color: #64748B;")

        card.lbl_title = lbl_t
        card.lbl_main = lbl_m
        card.lbl_sub = lbl_s

        c_layout.addWidget(lbl_t)
        c_layout.addWidget(lbl_m)
        c_layout.addWidget(lbl_s)
        return card

    def _create_breakdown_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        l = QVBoxLayout(card)
        l.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet("font-size: 11px; font-weight: bold; color: #1E293B; text-transform: uppercase;")
        l.addWidget(t)
        content_lbl = QLabel("No active data")
        content_lbl.setStyleSheet("color: #475569; font-size: 11px;")
        content_lbl.setWordWrap(True)
        l.addWidget(content_lbl)
        l.addStretch()
        card.content_lbl = content_lbl
        return card

    def refresh_stats(self) -> None:
        try:
            self._do_refresh_stats()
        except Exception as e:
            print(f"[Stats] Refresh error: {e}")

    def _do_refresh_stats(self) -> None:
        master = self.data_manager.load_master_state()
        meta = self.data_manager.load_metadata()
        checkouts = self.data_manager.load_checkouts_history()
        moves = self.data_manager.load_room_moves_history()
        arrivals = self.data_manager.load_arrivals_state()

        # Physical capacity from HotelDataSet.json
        total_physical_rooms = 0
        total_blocks = 0
        total_facilities = 0
        if os.path.exists(HOTEL_DATASET_PATH):
            try:
                with open(HOTEL_DATASET_PATH, "r", encoding="utf-8") as f:
                    ds = json.load(f)
                    total_physical_rooms = sum(n.get("room_details", {}).get("total_rooms", 0) for n in ds if n.get("category") == "Rooms")
                    total_blocks = len([n for n in ds if "BLOCK" in n.get("name", "")])
                    total_facilities = len([n for n in ds if n.get("category") != "Rooms"])
            except Exception:
                pass

        # In-House Counts
        total_bookings = len(master)
        total_guests = sum(
            len(b.get("Πελάτες", [])) if isinstance(b.get("Πελάτες"), list) else 1
            for b in master.values()
        )
        occ_pct = (total_bookings / total_physical_rooms * 100.0) if total_physical_rooms > 0 else 0.0

        # Update KPI cards
        self.card_capacity.lbl_main.setText(f"{total_physical_rooms} Rooms")
        self.card_capacity.lbl_sub.setText(f"{total_blocks} Accommodation Blocks")

        self.card_inhouse.lbl_main.setText(f"{total_bookings} Bookings")
        self.card_inhouse.lbl_sub.setText(f"{total_guests} In-House Guests")

        self.card_occ.lbl_main.setText(f"{occ_pct:.1f}%")
        self.card_occ.lbl_sub.setText(f"{total_bookings} / {total_physical_rooms} Rooms Occupied")

        self.card_facilities.lbl_main.setText(f"{total_facilities} Venues")
        self.card_facilities.lbl_sub.setText("Restaurants, Bars & Recreation")

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

        # Breakdown stats
        board_counter = collections.Counter()
        nat_counter = collections.Counter()
        room_counter = collections.Counter()

        for b in master.values():
            b_board = b.get("Τύπος Γεύματος") or "All Inclusive"
            board_counter[b_board] += 1

            nat = b.get("Αγορά") or b.get("Χρεώστης") or "General"
            nat_counter[nat] += 1

            rtype = b.get("Τύπος Δωμ") or b.get("Κρατηθείς Τύπος") or "Standard"
            room_counter[rtype] += 1

        if board_counter:
            self.box_board.content_lbl.setText("\n".join(f"• {k}: {v} bookings" for k, v in board_counter.most_common(4)))
        else:
            self.box_board.content_lbl.setText("No active board data")

        if nat_counter:
            self.box_nat.content_lbl.setText("\n".join(f"• {k[:18]}: {v} bookings" for k, v in nat_counter.most_common(4)))
        else:
            self.box_nat.content_lbl.setText("No active nationality data")

        if room_counter:
            self.box_rooms.content_lbl.setText("\n".join(f"• {k[:18]}: {v} rooms" for k, v in room_counter.most_common(4)))
        else:
            self.box_rooms.content_lbl.setText("No active room category data")

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

    def _render_charts(self, master: Dict[str, Any], arrivals: Dict[str, Any], checkouts: Dict[str, Any]) -> None:
        self.figure.clear()

        # 2x2 Subplots Grid
        axs = self.figure.subplots(2, 2)
        ax1, ax2 = axs[0, 0], axs[0, 1]
        ax3, ax4 = axs[1, 0], axs[1, 1]

        # Chart 1: Occupancy Rate per Room Block (1100 to 8000)
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

        # Chart 2: Room Category Distribution (Donut Chart)
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

        # Chart 3: Operational Turnover (Arrivals vs. In-House vs. Departures)
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

        # Chart 4: Geographic / Agency / Market Breakdown
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

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self.figure.tight_layout(pad=1.8)
            except Exception:
                self.figure.subplots_adjust(top=0.92, bottom=0.08, left=0.08, right=0.95, hspace=0.35, wspace=0.25)
        self.canvas.draw()

    def _filter_table(self) -> None:
        query = self.txt_search.text().strip().lower()
        for r in range(self.table_inhouse.rowCount()):
            room = self.table_inhouse.item(r, 0).text().lower()
            b_id = self.table_inhouse.item(r, 1).text().lower()
            guest = self.table_inhouse.item(r, 2).text().lower()
            match = (not query) or (query in room) or (query in b_id) or (query in guest)
            self.table_inhouse.setRowHidden(r, not match)

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        try:
            self.refresh_stats()
        except Exception as e:
            print(f"[Stats] Activation error: {e}")
