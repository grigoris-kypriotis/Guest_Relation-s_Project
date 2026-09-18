"""
Stats Option: Live operational metrics, analytical dashboard, and guest manifest.
=================================================================================
Contains the StatsWidget (embedded in main window) and ResortStatsDialog (pop-out).
Features a unified scrollable dashboard with executive KPI cards, block occupancy meters,
Matplotlib visual analytics suite, distribution cards, filterable guest manifest,
and document production tracking.
"""

import os
import csv
import re
import json
import collections
import warnings
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QScrollArea, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QGridLayout, QLineEdit,
    QDialog, QProgressBar, QSizePolicy, QFileDialog, QMessageBox,
    QDateEdit, QDialogButtonBox, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QDate

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from MODULES.data_manager import (
    InHouseDataManager, HOTEL_DATASET_PATH, BASE_DIR, PLOT_DIR,
    OUTPUT_DIR, validate_inhouse_file_date, extract_inhouse_report_date
)


# =============================================================================
# ResortStatsDialog: Dedicated Pop-Out Window for Resort Analytics
# =============================================================================

class ResortStatsDialog(QDialog):
    """
    Dedicated Pop-Out Window for Resort Analytics & Guest Manifest.
    Scans HotelDataSet.json (physical capacity, blocks, venues) along with active guest manifest
    (master_state.json or CSV/XLSX) to calculate operational metrics with English canonical keys.
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
                g_list = b_data.get("Guests") or b_data.get("Πελάτες", [])
                g_str = ", ".join(g_list) if isinstance(g_list, list) else str(g_list)
                rows.append({
                    "Room": str(b_data.get("Room") or b_data.get("Δωμάτιο", "")),
                    "Booking ID": str(b_id),
                    "Guest Name": g_str,
                    "Arrival": str(b_data.get("Arrival") or b_data.get("Άφιξη", "")),
                    "Departure": str(b_data.get("Departure") or b_data.get("Αναχώρηση", "")),
                    "Room Type": str(b_data.get("Room Type") or b_data.get("Τύπος Δωματίου", "Standard")),
                    "Board": str(b_data.get("Meal Plan") or b_data.get("Τύπος Γεύματος", "All Inclusive")),
                    "Debtor / Agency": str(b_data.get("Agency") or b_data.get("Χρεώστης", "")),
                    "Nationality": str(b_data.get("Market") or b_data.get("Αγορά", "")),
                    "Pax": len(g_list) if isinstance(g_list, list) else 1
                })
            return pd.DataFrame(rows)

        return pd.DataFrame() if pd is not None else None

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Header Title
        title_box = QHBoxLayout()
        icon_lbl = QLabel("📊")
        icon_lbl.setStyleSheet("font-size: 24px;")
        title_box.addWidget(icon_lbl)

        v_titles = QVBoxLayout()
        main_title = QLabel("Resort Operational Analytics")
        main_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        sub_title = QLabel(f"Integrated dataset: {os.path.basename(self.hotel_json_path)} | Manifest: {os.path.basename(self.manifest_path)}")
        sub_title.setStyleSheet("font-size: 12px; color: #64748b;")
        v_titles.addWidget(main_title)
        v_titles.addWidget(sub_title)
        title_box.addLayout(v_titles)
        title_box.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background: #f1f5f9; color: #475569; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_close.clicked.connect(self.accept)
        title_box.addWidget(btn_close)
        layout.addLayout(title_box)

        # Tabs: Analytics vs Manifest
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #cbd5e1; background: #ffffff; border-radius: 4px; }
            QTabBar::tab { background: #f8fafc; border: 1px solid #cbd5e1; padding: 8px 16px; margin-right: 2px; font-weight: bold; }
            QTabBar::tab:selected { background: #3b82f6; color: #ffffff; }
        """)

        # Tab 1: Operational Analytics Suite
        self.analytics_scroll = QScrollArea()
        self.analytics_scroll.setWidgetResizable(True)
        self.analytics_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.analytics_widget = QWidget()
        self.analytics_layout = QVBoxLayout(self.analytics_widget)
        self.analytics_layout.setContentsMargins(16, 16, 16, 16)
        self.analytics_layout.setSpacing(16)
        self.analytics_scroll.setWidget(self.analytics_widget)
        self.tabs.addTab(self.analytics_scroll, "📈 Analytics Suite")

        # Tab 2: Guest Manifest Table
        self.manifest_widget = QWidget()
        self.manifest_layout = QVBoxLayout(self.manifest_widget)
        self.manifest_layout.setContentsMargins(16, 16, 16, 16)
        self.manifest_layout.setSpacing(12)
        self.tabs.addTab(self.manifest_widget, "📋 Guest Manifest")

        layout.addWidget(self.tabs)

        self._populate_analytics()
        self._populate_manifest()

    def _create_stat_card(self, title: str, value: str, subtitle: str = "") -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-left: 4px solid #3b82f6;
                border-radius: 6px;
                padding: 10px 14px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(3)
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
        total_physical_rooms = sum(
            node.get("room_details", {}).get("total_rooms", 0)
            for node in self.hotel_data if node.get("category") == "Rooms"
        )
        if total_physical_rooms == 0:
            try:
                from OPTIONS.configuration_option import load_app_settings
                total_physical_rooms = int(load_app_settings().get("properties", {}).get("sandy_beach_rooms", 660))
            except Exception:
                total_physical_rooms = 660

        total_blocks = len([n for n in self.hotel_data if "BLOCK" in n.get("name", "")])
        total_facilities = len([n for n in self.hotel_data if n.get("category") != "Rooms"])

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
            total_pax = sum(len(b.get("Guests") or b.get("Πελάτες", [])) if isinstance(b.get("Guests") or b.get("Πελάτες"), list) else 1 for b in master.values())
            b_counter = collections.Counter()
            n_counter = collections.Counter()
            for b in master.values():
                b_counter[b.get("Meal Plan") or b.get("Τύπος Γεύματος") or "All Inclusive"] += 1
                n_counter[b.get("Market") or b.get("Αγορά") or b.get("Agency") or b.get("Χρεώστης") or "General"] += 1
            board_counts = dict(b_counter.most_common(5))
            nat_counts = dict(n_counter.most_common(5))

        occ_pct = (total_inhouse_rooms / total_physical_rooms * 100.0) if total_physical_rooms > 0 else 0.0

        kpi_grid = QGridLayout()
        kpi_grid.addWidget(self._create_stat_card("Total Capacity", f"{total_physical_rooms} Rooms", f"{total_blocks} Blocks"), 0, 0)
        kpi_grid.addWidget(self._create_stat_card("Occupied Rooms", f"{total_inhouse_rooms}", f"{occ_pct:.1f}% Occupancy"), 0, 1)
        kpi_grid.addWidget(self._create_stat_card("In-House Guests", f"{total_pax} Pax", "Active In-House"), 0, 2)
        kpi_grid.addWidget(self._create_stat_card("Facilities & Outlets", f"{total_facilities} Venues", "Restaurants, Bars & Recreation"), 0, 3)
        self.analytics_layout.addLayout(kpi_grid)

        details_layout = QHBoxLayout()
        details_layout.setSpacing(12)

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
            bb_layout.addWidget(QLabel("No board data available."))
        bb_layout.addStretch()
        details_layout.addWidget(board_box)

        nat_box = QFrame()
        nat_box.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;")
        nb_layout = QVBoxLayout(nat_box)
        nb_lbl = QLabel("TOP MARKETS & AGENCIES")
        nb_lbl.setStyleSheet("font-weight: bold; color: #1e293b; margin-bottom: 5px;")
        nb_layout.addWidget(nb_lbl)
        if nat_counts:
            for nat, count in nat_counts.items():
                lbl = QLabel(f"• {nat}: {count} guests")
                lbl.setStyleSheet("color: #475569; font-size: 12px;")
                nb_layout.addWidget(lbl)
        else:
            nb_layout.addWidget(QLabel("No agency data available."))
        nb_layout.addStretch()
        details_layout.addWidget(nat_box)

        self.analytics_layout.addLayout(details_layout)
        self.analytics_layout.addStretch()

    def _populate_manifest(self) -> None:
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("🔍 Filter manifest by room, guest name, booking id...")
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
            table.setColumnCount(7)
            table.setHorizontalHeaderLabels(["Room", "Booking ID", "Guest Name(s)", "Arrival", "Departure", "Room Type", "Agency"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.setRowCount(len(master))
            for r_idx, (b_id, b_data) in enumerate(master.items()):
                g_list = b_data.get("Guests") or b_data.get("Πελάτες", [])
                g_str = ", ".join(g_list) if isinstance(g_list, list) else str(g_list)
                table.setItem(r_idx, 0, QTableWidgetItem(str(b_data.get("Room") or b_data.get("Δωμάτιο", ""))))
                table.setItem(r_idx, 1, QTableWidgetItem(str(b_id)))
                table.setItem(r_idx, 2, QTableWidgetItem(g_str))
                table.setItem(r_idx, 3, QTableWidgetItem(str(b_data.get("Arrival") or b_data.get("Άφιξη", ""))))
                table.setItem(r_idx, 4, QTableWidgetItem(str(b_data.get("Departure") or b_data.get("Αναχώρηση", ""))))
                table.setItem(r_idx, 5, QTableWidgetItem(str(b_data.get("Room Type") or b_data.get("Τύπος Δωματίου", "Standard"))))
                table.setItem(r_idx, 6, QTableWidgetItem(str(b_data.get("Agency") or b_data.get("Χρεώστης", ""))))

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
# StatsWidget: Redesigned Scrollable Operational Dashboard & Visual Stats
# =============================================================================

class StatsWidget(QWidget):
    """
    Main In-App Operational Dashboard & Visual Analytics Segment.
    Completely scrollable view packed with visual statistics:
      1. Executive KPI Status Cards & Occupancy Progress Gauge
      2. Room Block Visual Occupancy Meters (Grid of individual block cards)
      3. Matplotlib 4-Chart Analytics Suite (Block %, Categories, Turnover, Debtors)
      4. Categorical Breakdown Cards (Meal Plans, Markets, Room Types, Document Output)
      5. Embedded Active In-House Guest Manifest with search & filter
      6. Quick In-House Ingestion & Maintenance Tools
    """

    TARGET_BLOCKS = [
        "BLOCK 100", "BLOCK 200", "BLOCK 300", "BLOCK 400",
        "BLOCK 500", "BLOCK 600", "BLOCK 700", "BLOCK 800",
        "BLOCK 1100", "BLOCK 1200", "BLOCK 1300", "BLOCK 1400",
        "BLOCK 1500", "BLOCK 1600", "BLOCK 1700", "BLOCK 1800",
        "BLOCK 1900", "BLOCK 2000", "BLOCK 3000", "BLOCK 4000",
        "BLOCK 5000", "BLOCK 6000", "BLOCK 7000", "BLOCK 8000"
    ]

    MAJOR_16_BLOCKS = [
        "BLOCK 1100", "BLOCK 1200", "BLOCK 1300", "BLOCK 1400",
        "BLOCK 1500", "BLOCK 1600", "BLOCK 1700", "BLOCK 1800",
        "BLOCK 1900", "BLOCK 2000", "BLOCK 3000", "BLOCK 4000",
        "BLOCK 5000", "BLOCK 6000", "BLOCK 7000", "BLOCK 8000"
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self._is_loading = False
        self.block_card_widgets: Dict[str, QFrame] = {}
        self._init_ui()
        self.refresh_stats(sync=True)

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # Header Bar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        lbl_title = QLabel("📊 RESORT OPERATIONAL STATS & ANALYTICS")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel("Comprehensive scrollable resort dashboard with block visual meters, analytical charts, and live manifest.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #666666;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)
        header.addStretch()

        self.lbl_status = QLabel("🟢 Live State")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #065F46; font-weight: bold; padding-right: 6px;")
        header.addWidget(self.lbl_status)

        self.btn_refresh = QPushButton("🔄 Refresh Stats")
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
        self.btn_refresh.clicked.connect(lambda: self.refresh_stats(sync=False))
        header.addWidget(self.btn_refresh)

        btn_popout = QPushButton("🗗 Pop-Out Window")
        btn_popout.setStyleSheet("""
            QPushButton {
                background-color: #4A5568;
                border: 1px solid #718096;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover { background-color: #2D3748; }
        """)
        btn_popout.clicked.connect(self.pop_out_dialog)
        header.addWidget(btn_popout)
        root_layout.addLayout(header)

        # Tabs container (Main Tab 0 is the full unified scrollable dashboard)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #FFB6C1; background-color: #FFFFFF; border-radius: 6px; }
            QTabBar::tab { background-color: #FFE4E1; border: 1px solid #FFB6C1; padding: 8px 14px; margin-right: 3px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #FF69B4; color: #FFFFFF; }
        """)

        # Tab 1: Unified Scrollable Analytics Suite
        self.analytics_scroll = QScrollArea()
        self.analytics_scroll.setWidgetResizable(True)
        self.analytics_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.analytics_widget = QWidget()
        self.analytics_layout = QVBoxLayout(self.analytics_widget)
        self.analytics_layout.setContentsMargins(14, 14, 14, 14)
        self.analytics_layout.setSpacing(18)

        # 1. Executive KPIs Section
        sec_kpi = self._create_section_container(
            "🏨 EXECUTIVE OPERATIONAL STATUS",
            "Key resort metrics: capacity, live in-house bookings, occupancy gauge, turnover, and sync dates."
        )
        kpi_inner = sec_kpi.layout()

        # Occupancy Progress Bar
        occ_bar_box = QVBoxLayout()
        occ_bar_header = QHBoxLayout()
        lbl_occ_meter = QLabel("Overall Resort Occupancy Meter:")
        lbl_occ_meter.setStyleSheet("font-size: 12px; font-weight: bold; color: #1E293B;")
        self.lbl_occ_pct_badge = QLabel("0.0%")
        self.lbl_occ_pct_badge.setStyleSheet("font-size: 13px; font-weight: 800; color: #800020;")
        occ_bar_header.addWidget(lbl_occ_meter)
        occ_bar_header.addStretch()
        occ_bar_header.addWidget(self.lbl_occ_pct_badge)
        occ_bar_box.addLayout(occ_bar_header)

        self.progress_occ = QProgressBar()
        self.progress_occ.setFixedHeight(18)
        self.progress_occ.setRange(0, 100)
        self.progress_occ.setValue(0)
        self.progress_occ.setTextVisible(True)
        self.progress_occ.setStyleSheet("""
            QProgressBar {
                background-color: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 9px;
                text-align: center;
                font-weight: bold;
                font-size: 10px;
                color: #0F172A;
            }
            QProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 8px;
            }
        """)
        occ_bar_box.addWidget(self.progress_occ)
        kpi_inner.addLayout(occ_bar_box)

        # KPI Cards Grid
        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(10)

        self.card_capacity = self._create_kpi_card("Physical Capacity", "0 Rooms", "16 Accommodation Blocks", "#4F46E5")
        self.card_inhouse = self._create_kpi_card("Active In-House", "0 Bookings", "0 Guests In-House", "#059669")
        self.card_occ = self._create_kpi_card("Occupancy Rate", "0.0%", "0 / 0 Rooms Occupied", "#DC2626")
        self.card_arrivals = self._create_kpi_card("Today's Arrivals", "0 Expected", "Sandy Beach Arrivals", "#2563EB")
        self.card_checkouts = self._create_kpi_card("Today's Departures", "0 Departures", "0 Archived Checkouts", "#D97706")
        self.card_moves = self._create_kpi_card("Room Moves", "0 Moves", "Archived in room_moves.json", "#7C3AED")
        self.card_facilities = self._create_kpi_card("Resort Facilities", "28 Venues", "Restaurants, Bars & Pools", "#0D9488")
        self.card_sync = self._create_kpi_card("PMS Sync State", "Not Synced", "DATABASE/HOTEL STATE", "#800020")

        self.kpi_grid.addWidget(self.card_capacity, 0, 0)
        self.kpi_grid.addWidget(self.card_inhouse, 0, 1)
        self.kpi_grid.addWidget(self.card_occ, 0, 2)
        self.kpi_grid.addWidget(self.card_arrivals, 0, 3)
        self.kpi_grid.addWidget(self.card_checkouts, 1, 0)
        self.kpi_grid.addWidget(self.card_moves, 1, 1)
        self.kpi_grid.addWidget(self.card_facilities, 1, 2)
        self.kpi_grid.addWidget(self.card_sync, 1, 3)
        kpi_inner.addLayout(self.kpi_grid)
        self.analytics_layout.addWidget(sec_kpi)

        # 2. Block-by-Block Visual Occupancy Grid
        sec_blocks = self._create_section_container(
            "🏨 ROOM BLOCK OCCUPANCY METERS",
            "Visual occupancy meters for each accommodation block (Blocks 100-800 & 1100-8000). Blue: <75%, Amber: 75-89%, Red: ≥90%."
        )
        blocks_inner = sec_blocks.layout()

        self.block_grid = QGridLayout()
        self.block_grid.setSpacing(8)

        col_count = 4
        for idx, b_name in enumerate(self.TARGET_BLOCKS):
            row = idx // col_count
            col = idx % col_count
            card = self._create_block_meter_card(b_name, 0.0, 0, 0, "")
            self.block_card_widgets[b_name] = card
            self.block_grid.addWidget(card, row, col)

        blocks_inner.addLayout(self.block_grid)
        self.analytics_layout.addWidget(sec_blocks)

        # 3. Matplotlib 4-Chart Visual Suite
        sec_charts = self._create_section_container(
            "📈 VISUAL ANALYTICS SUITE",
            "High-DPI analytical charts: room block occupancy, room category distribution, tour operator / agency shares, and turnover flow."
        )
        chart_inner = sec_charts.layout()

        self.figure = Figure(figsize=(11, 7.5), dpi=95, facecolor="#FFFFFF")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.canvas.setMinimumHeight(620)
        chart_inner.addWidget(self.canvas)
        self.analytics_layout.addWidget(sec_charts)

        # 4. Categorical Breakdown Cards
        sec_breakdowns = self._create_section_container(
            "📊 DISTRIBUTION BREAKDOWNS & DOCUMENT PRODUCTION",
            "Detailed categorical distributions for board plans, markets, room types, and document generation metrics."
        )
        bk_inner = sec_breakdowns.layout()
        bk_grid = QGridLayout()
        bk_grid.setSpacing(10)

        self.box_board = self._create_breakdown_card("🍽️ BOARD BASIS DISTRIBUTION")
        self.box_nat = self._create_breakdown_card("🌍 MARKET & TOUR OPERATORS")
        self.box_rooms = self._create_breakdown_card("🛏️ ROOM CATEGORIES OCCUPIED")

        # Document Production Mini-Card
        self.box_docs = QFrame()
        self.box_docs.setStyleSheet("background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px;")
        bd_layout = QVBoxLayout(self.box_docs)
        lbl_bd_title = QLabel("📄 DOCUMENT OUTPUT METRICS")
        lbl_bd_title.setStyleSheet("font-weight: bold; color: #1E293B; font-size: 11px;")
        bd_layout.addWidget(lbl_bd_title)

        doc_sub_grid = QHBoxLayout()
        self.card_offers_count = self._create_kpi_card("Offer Lists", "0 Documents", "Saved in Output", "#4338CA")
        self.card_cakes_count = self._create_kpi_card("Cake Memos", "0 Documents", "Saved in Output", "#BE185D")
        doc_sub_grid.addWidget(self.card_offers_count)
        doc_sub_grid.addWidget(self.card_cakes_count)
        bd_layout.addLayout(doc_sub_grid)

        bk_grid.addWidget(self.box_board, 0, 0)
        bk_grid.addWidget(self.box_nat, 0, 1)
        bk_grid.addWidget(self.box_rooms, 1, 0)
        bk_grid.addWidget(self.box_docs, 1, 1)
        bk_inner.addLayout(bk_grid)
        self.analytics_layout.addWidget(sec_breakdowns)

        # 5. Embedded In-House Guest Manifest Section
        sec_manifest = self._create_section_container(
            "📋 ACTIVE IN-HOUSE GUEST MANIFEST",
            "Search, filter, and inspect the current master in-house list directly with standardized English headers."
        )
        man_inner = sec_manifest.layout()

        man_bar = QHBoxLayout()
        lbl_man_tag = QLabel("Filter Manifest:")
        lbl_man_tag.setStyleSheet("font-weight: bold; color: #800020; font-size: 12px;")
        man_bar.addWidget(lbl_man_tag)

        self.cmb_filter_block = QComboBox()
        self.cmb_filter_block.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #FFB6C1;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-weight: bold;
                color: #800020;
            }
        """)
        self.cmb_filter_block.addItems(["All Blocks", "100s", "200s", "300s", "400s", "500s", "600s", "700s", "800s",
                                        "1100s", "1200s", "1300s", "1400s", "1500s", "1600s", "1700s", "1800s", "1900s",
                                        "2000s", "3000s", "4000s", "5000s", "6000s", "7000s", "8000s"])
        self.cmb_filter_block.currentIndexChanged.connect(self._filter_table)
        man_bar.addWidget(self.cmb_filter_block)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Filter by Room, Guest Name, Booking ID, Agency...")
        self.txt_search.setStyleSheet("padding: 5px 8px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        self.txt_search.textChanged.connect(self._filter_table)
        man_bar.addWidget(self.txt_search, stretch=1)

        btn_export_csv = QPushButton("📥 Export CSV")
        btn_export_csv.setStyleSheet("""
            QPushButton { background-color: #065F46; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_export_csv.clicked.connect(self._export_manifest_csv)
        man_bar.addWidget(btn_export_csv)
        man_inner.addLayout(man_bar)

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
        self.table_inhouse.setMinimumHeight(350)
        man_inner.addWidget(self.table_inhouse)
        self.analytics_layout.addWidget(sec_manifest)

        # 6. Quick Actions Section in Scroll
        sec_qa = self._create_section_container(
            "⚡ QUICK INGESTION & DATA REFRESH",
            "Load today's PMS export directly, refresh block JSON files, and access database directories."
        )
        qa_inner = sec_qa.layout()

        self.lbl_inhouse_status = QLabel("⚠️ Checking in-house status...")
        self.lbl_inhouse_status.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 8px 12px; border: 1px solid #FECACA; border-radius: 6px;")
        qa_inner.addWidget(self.lbl_inhouse_status)

        qa_btn_row = QHBoxLayout()
        self.btn_quick_load = QPushButton("📂 Load In-House List (.xlsx / .csv)")
        self.btn_quick_load.setStyleSheet("""
            QPushButton {
                background-color: #1E3A8A;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        self.btn_quick_load.clicked.connect(self._quick_load_inhouse)
        qa_btn_row.addWidget(self.btn_quick_load)

        btn_refresh_blocks = QPushButton("🔄 Refresh Block Exports")
        btn_refresh_blocks.setStyleSheet("""
            QPushButton { background-color: #065F46; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_refresh_blocks.clicked.connect(self._quick_refresh_blocks)
        qa_btn_row.addWidget(btn_refresh_blocks)

        btn_open_database = QPushButton("📁 Open DATABASE")
        btn_open_database.setStyleSheet("""
            QPushButton { background-color: #475569; color: white; font-weight: bold; padding: 8px 14px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #334155; }
        """)
        btn_open_database.clicked.connect(lambda: self._open_output_folder(None, os.path.join(BASE_DIR, "DATABASE")))
        qa_btn_row.addWidget(btn_open_database)

        btn_open_output = QPushButton("📁 Open OUTPUT")
        btn_open_output.setStyleSheet("""
            QPushButton { background-color: #475569; color: white; font-weight: bold; padding: 8px 14px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #334155; }
        """)
        btn_open_output.clicked.connect(lambda: self._open_output_folder(None, OUTPUT_DIR))
        qa_btn_row.addWidget(btn_open_output)

        qa_btn_row.addStretch()
        qa_inner.addLayout(qa_btn_row)

        self.lbl_activity_log = QLabel("No recent activity recorded.")
        self.lbl_activity_log.setStyleSheet("color: #475569; font-size: 11px; padding: 6px; border: none;")
        self.lbl_activity_log.setWordWrap(True)
        qa_inner.addWidget(self.lbl_activity_log)
        self.analytics_layout.addWidget(sec_qa)

        self.analytics_scroll.setWidget(self.analytics_widget)
        self.tabs.addTab(self.analytics_scroll, "📈 Visual Analytics Suite")

        # Tab 2: Standalone Manifest Table View
        self.tab_table = QWidget()
        tt_layout = QVBoxLayout(self.tab_table)
        tt_layout.setContentsMargins(12, 12, 12, 12)
        tt_layout.setSpacing(10)
        lbl_tt_header = QLabel("Active In-House Guest Manifest (Standalone View)")
        lbl_tt_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #2C3E50;")
        tt_layout.addWidget(lbl_tt_header)

        # Embedded reference to the table or clone
        self.table_inhouse_standalone = QTableWidget(0, 8)
        self.table_inhouse_standalone.setHorizontalHeaderLabels([
            "Room", "Booking ID", "Guest Name(s)", "Arrival", "Departure", "Room Type", "Agency", "Meal Plan"
        ])
        self.table_inhouse_standalone.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_inhouse_standalone.setAlternatingRowColors(True)
        self.table_inhouse_standalone.setSortingEnabled(True)
        tt_layout.addWidget(self.table_inhouse_standalone)
        self.tabs.addTab(self.tab_table, "📋 Guest Manifest Table")

        # Tab 3: Dedicated Quick Actions
        self.tab_actions = QWidget()
        qa_tab_layout = QVBoxLayout(self.tab_actions)
        qa_tab_layout.setContentsMargins(16, 16, 16, 16)
        qa_tab_layout.setSpacing(14)
        lbl_qa_head = QLabel("Operational Tools & System Management")
        lbl_qa_head.setStyleSheet("font-size: 14px; font-weight: bold; color: #800020;")
        qa_tab_layout.addWidget(lbl_qa_head)
        qa_tab_layout.addWidget(self._create_kpi_card("Quick Actions", "PMS Sync Ready", "Select an action below", "#800020"))
        qa_tab_layout.addStretch()
        self.tabs.addTab(self.tab_actions, "⚡ Quick Actions")

        root_layout.addWidget(self.tabs, stretch=1)

    # -----------------------------------------------------------------
    # UI Component Builders
    # -----------------------------------------------------------------
    def _create_section_container(self, title: str, subtitle: str) -> QFrame:
        container = QFrame()
        container.setFrameShape(QFrame.Shape.StyledPanel)
        container.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #FFB6C1;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(10)

        t_box = QVBoxLayout()
        t_box.setSpacing(2)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 13px; font-weight: bold; color: #800020;")
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet("font-size: 10.5px; color: #666666;")
        t_box.addWidget(lbl_t)
        t_box.addWidget(lbl_sub)
        c_layout.addLayout(t_box)
        return container

    def _create_kpi_card(self, title: str, main_stat: str, sub_stat: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFF0F5;
                border: 1px solid #FFB6C1;
                border-left: 4px solid {accent_color};
                border-radius: 6px;
                padding: 8px 12px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(3)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 10.5px; font-weight: bold; color: {accent_color}; text-transform: uppercase;")
        card.lbl_main = QLabel(main_stat)
        card.lbl_main.setStyleSheet("font-size: 17px; font-weight: 800; color: #1E293B;")
        card.lbl_sub = QLabel(sub_stat)
        card.lbl_sub.setStyleSheet("font-size: 10px; color: #64748B;")

        c_layout.addWidget(lbl_t)
        c_layout.addWidget(card.lbl_main)
        c_layout.addWidget(card.lbl_sub)
        return card

    def _create_block_meter_card(self, b_name: str, pct: float, occupied: int, total: int, desc: str = "") -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        if pct < 75:
            accent = "#2563EB"
            bg = "#EFF6FF"
        elif pct < 90:
            accent = "#D97706"
            bg = "#FFFBEB"
        else:
            accent = "#DC2626"
            bg = "#FEF2F2"

        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {accent}33;
                border-left: 4px solid {accent};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(2)

        top_row = QHBoxLayout()
        card.lbl_name = QLabel(b_name)
        card.lbl_name.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {accent};")
        top_row.addWidget(card.lbl_name)
        top_row.addStretch()

        card.lbl_pct = QLabel(f"{pct:.0f}%")
        card.lbl_pct.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {accent};")
        top_row.addWidget(card.lbl_pct)
        c_layout.addLayout(top_row)

        card.pbar = QProgressBar()
        card.pbar.setFixedHeight(6)
        card.pbar.setTextVisible(False)
        card.pbar.setRange(0, 100)
        card.pbar.setValue(min(100, int(round(pct))))
        card.pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #E2E8F0;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 3px;
            }}
        """)
        c_layout.addWidget(card.pbar)

        bot_row = QHBoxLayout()
        card.lbl_rooms = QLabel(f"{occupied}/{total} Occ" if total > 0 else "0 Rooms")
        card.lbl_rooms.setStyleSheet("font-size: 9.5px; color: #475569;")
        bot_row.addWidget(card.lbl_rooms)
        bot_row.addStretch()
        vacant = max(0, total - occupied)
        card.lbl_vacant = QLabel(f"{vacant} Vac" if total > 0 else "")
        card.lbl_vacant.setStyleSheet("font-size: 9.5px; font-weight: bold; color: #64748B;")
        bot_row.addWidget(card.lbl_vacant)
        c_layout.addLayout(bot_row)

        card.setToolTip(f"{b_name}: {occupied}/{total} rooms ({pct:.1f}%)\n{desc}")
        return card

    def _create_breakdown_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(6, 6, 6, 6)
        c_layout.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-weight: bold; color: #1E293B; font-size: 11px;")
        c_layout.addWidget(lbl_t)

        card.content_lbl = QLabel("No active data loaded")
        card.content_lbl.setStyleSheet("color: #475569; font-size: 11px;")
        card.content_lbl.setWordWrap(True)
        c_layout.addWidget(card.content_lbl)
        c_layout.addStretch()
        return card

    def pop_out_dialog(self) -> None:
        dlg = ResortStatsDialog(parent=self)
        dlg.exec()

    # -----------------------------------------------------------------
    # Stats Refresh Engine
    # -----------------------------------------------------------------
    def refresh_stats(self, sync: bool = False) -> None:
        """Refreshes live operational metrics synchronously or via background worker."""
        is_headless = os.environ.get("QT_QPA_PLATFORM") == "offscreen"
        if sync or is_headless:
            try:
                data = self._fetch_all_stats_data()
                self._apply_stats_data(data)
            except Exception as e:
                print(f"[Stats] Sync refresh error: {e}")
            return

        if self._is_loading:
            return
        self._set_loading_ui(True)

        def worker():
            try:
                data = self._fetch_all_stats_data()
                QTimer.singleShot(0, lambda: self._on_stats_loaded(data))
            except Exception as e:
                print(f"[Stats] Worker async refresh error: {e}")
                QTimer.singleShot(0, lambda: self._set_loading_ui(False))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_stats_loaded(self, data: Dict[str, Any]) -> None:
        try:
            self._apply_stats_data(data)
        except Exception as e:
            print(f"[Stats] Error applying stats data: {e}")
        finally:
            self._set_loading_ui(False)

    def _set_loading_ui(self, loading: bool) -> None:
        self._is_loading = loading
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.setEnabled(not loading)
        if hasattr(self, "lbl_status"):
            if loading:
                self.lbl_status.setText("⏳ Updating analytics in background...")
                self.lbl_status.setStyleSheet("font-size: 11px; color: #D97706; font-weight: bold; padding-right: 8px;")
            else:
                self.lbl_status.setText("🟢 Live State")
                self.lbl_status.setStyleSheet("font-size: 11px; color: #065F46; font-weight: bold; padding-right: 8px;")

    def _fetch_all_stats_data(self) -> Dict[str, Any]:
        """Fetches data from disk and computes live occupancy and turnover metrics."""
        master = self.data_manager.load_master_state() or {}
        meta = self.data_manager.load_metadata() or {}
        checkouts = self.data_manager.load_checkouts_history() or {}
        moves = self.data_manager.load_room_moves_history() or []
        arrivals_state = self.data_manager.load_arrivals_state() or {}

        # Physical capacity
        total_physical_rooms = 0
        total_blocks = 0
        total_facilities = 0
        dataset_nodes = []
        if os.path.exists(HOTEL_DATASET_PATH):
            try:
                with open(HOTEL_DATASET_PATH, "r", encoding="utf-8") as f:
                    dataset_nodes = json.load(f)
                    total_physical_rooms = sum(n.get("room_details", {}).get("total_rooms", 0) for n in dataset_nodes if n.get("category") == "Rooms")
                    total_blocks = len([n for n in dataset_nodes if "BLOCK" in n.get("name", "")])
                    total_facilities = len([n for n in dataset_nodes if n.get("category") != "Rooms"])
            except Exception:
                pass

        if total_physical_rooms == 0:
            try:
                from OPTIONS.configuration_option import load_app_settings
                app_cfg = load_app_settings()
                total_physical_rooms = int(app_cfg.get("properties", {}).get("sandy_beach_rooms", 660))
            except Exception:
                total_physical_rooms = 660

        total_bookings = len(master)
        total_guests = sum(
            len(b.get("Guests") or b.get("Πελάτες", [])) if isinstance(b.get("Guests") or b.get("Πελάτες"), list) else 1
            for b in master.values()
        )
        occ_pct = (total_bookings / total_physical_rooms * 100.0) if total_physical_rooms > 0 else 0.0

        # Checkouts & Departures
        co_records = checkouts.get("records", []) if isinstance(checkouts, dict) else []
        today_str = date.today().strftime("%d/%m/%Y")
        today_cos = sum(1 for c in co_records if str(c.get("checkout_date", "")).startswith(today_str))

        # Categorical Counters (Checking English canonical keys first, Greek aliases fallback)
        board_counter = collections.Counter()
        nat_counter = collections.Counter()
        room_counter = collections.Counter()
        agency_counter = collections.Counter()
        room_types_for_chart = collections.Counter()

        for b in master.values():
            b_board = b.get("Meal Plan") or b.get("Τύπος Γεύματος") or "All Inclusive"
            board_counter[b_board] += 1

            nat = b.get("Market") or b.get("Αγορά") or b.get("Agency") or b.get("Χρεώστης") or "General"
            nat_counter[nat] += 1

            rtype = b.get("Room Type") or b.get("Τύπος Δωματίου") or b.get("Τύπος Δωμ") or b.get("Booked Room Type") or "Standard"
            room_counter[rtype] += 1

            guests_list = b.get("Guests") or b.get("Πελάτες") or []
            guests_cnt = len(guests_list) if isinstance(guests_list, list) else 1
            room_types_for_chart[rtype] += guests_cnt

            agency = b.get("Agency") or b.get("Χρεώστης") or b.get("agency") or "Direct"
            agency_counter[agency] += guests_cnt

        # Major 16 blocks for Chart 1
        target_blocks = self.MAJOR_16_BLOCKS
        block_percentages = []
        all_blocks_info = []

        # Scrape occupancy per block across all TARGET_BLOCKS
        for b_name in self.TARGET_BLOCKS:
            slug = re.sub(r"[^\w\d]+", "_", b_name.strip()).strip("_")
            b_file = Path(PLOT_DIR) / slug / f"{slug}.json"
            pct = 0.0
            occupied = 0
            tot = 0
            desc = ""

            if b_file.exists():
                try:
                    with open(b_file, "r", encoding="utf-8") as f:
                        b_json = json.load(f)
                        metrics = b_json.get("occupancy_metrics", {})
                        pct = float(metrics.get("occupancy_percentage", 0.0))
                        occupied = int(metrics.get("occupied_rooms", 0))
                        tot = int(metrics.get("total_rooms", 0))
                        desc = str(b_json.get("description", ""))
                except Exception:
                    pass

            # If PLOT json is missing or 0 rooms, attempt dataset calculation
            if tot == 0 and dataset_nodes:
                for n in dataset_nodes:
                    if n.get("name", "").upper() == b_name.upper():
                        tot = int(n.get("room_details", {}).get("total_rooms", 0))
                        desc = str(n.get("description", ""))
                        break

            all_blocks_info.append({
                "name": b_name,
                "pct": pct,
                "occupied": occupied,
                "total": tot,
                "desc": desc
            })

            if b_name in target_blocks:
                block_percentages.append(pct)

        # Arrivals fallback
        beach_arr = arrivals_state.get("SANDY BEACH", {})
        if not beach_arr and master:
            sync_dt = meta.get("last_sync_date") or meta.get("last_processed_date")
            target_dates = {str(sync_dt), today_str, f"{date.today().day}/{date.today().month}/{date.today().year}"}
            for b_id, b_data in master.items():
                arr = str(b_data.get("Arrival") or b_data.get("Άφιξη", "")).strip()
                if arr in target_dates:
                    beach_arr[b_id] = b_data

        # Sorted manifest rows
        sorted_bookings = sorted(
            master.items(),
            key=lambda x: (
                not str(x[1].get("Room") or x[1].get("Δωμάτιο", "")).isdigit(),
                int(x[1].get("Room") or x[1].get("Δωμάτιο", 0)) if str(x[1].get("Room") or x[1].get("Δωμάτιο", "")).isdigit() else str(x[1].get("Room") or x[1].get("Δωμάτιο", ""))
            )
        )

        doc_counts = self._count_documents()

        return {
            "master": master,
            "meta": meta,
            "checkouts": checkouts,
            "moves": moves,
            "arrivals": beach_arr,
            "total_physical_rooms": total_physical_rooms,
            "total_blocks": total_blocks,
            "total_facilities": total_facilities,
            "total_bookings": total_bookings,
            "total_guests": total_guests,
            "occ_pct": occ_pct,
            "co_records_len": len(co_records),
            "today_cos": today_cos,
            "board_counter": board_counter,
            "nat_counter": nat_counter,
            "room_counter": room_counter,
            "agency_counter": agency_counter,
            "room_types_for_chart": room_types_for_chart,
            "target_blocks": target_blocks,
            "block_percentages": block_percentages,
            "all_blocks_info": all_blocks_info,
            "sorted_bookings": sorted_bookings,
            "doc_counts": doc_counts,
        }

    def _apply_stats_data(self, data: Dict[str, Any]) -> None:
        """Applies loaded dataset to all UI components on the main Qt thread."""
        total_physical_rooms = data.get("total_physical_rooms", 660)
        total_blocks = data.get("total_blocks", 16)
        total_facilities = data.get("total_facilities", 28)
        total_bookings = data.get("total_bookings", 0)
        total_guests = data.get("total_guests", 0)
        occ_pct = data.get("occ_pct", 0.0)

        # Progress bar
        self.progress_occ.setValue(min(100, int(round(occ_pct))))
        self.lbl_occ_pct_badge.setText(f"{occ_pct:.1f}%")
        bar_color = "#2563EB" if occ_pct < 75 else ("#D97706" if occ_pct < 90 else "#DC2626")
        self.progress_occ.setStyleSheet(f"""
            QProgressBar {{
                background-color: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 9px;
                text-align: center;
                font-weight: bold;
                font-size: 10px;
                color: #0F172A;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 8px;
            }}
        """)

        # KPI Cards
        self.card_capacity.lbl_main.setText(f"{total_physical_rooms} Rooms")
        self.card_capacity.lbl_sub.setText(f"{total_blocks} Accommodation Blocks")

        self.card_inhouse.lbl_main.setText(f"{total_bookings} Bookings")
        self.card_inhouse.lbl_sub.setText(f"{total_guests} In-House Guests")

        self.card_occ.lbl_main.setText(f"{occ_pct:.1f}%")
        self.card_occ.lbl_sub.setText(f"{total_bookings} / {total_physical_rooms} Rooms Occupied")

        arrivals_dict = data.get("arrivals", {})
        arr_len = len(arrivals_dict)
        self.card_arrivals.lbl_main.setText(f"{arr_len} Expected")
        self.card_arrivals.lbl_sub.setText(f"{arr_len} Today's Arrivals")

        self.card_facilities.lbl_main.setText(f"{total_facilities} Venues")
        self.card_facilities.lbl_sub.setText("Restaurants, Bars & Recreation")

        self.card_checkouts.lbl_main.setText(f"{data.get('today_cos', 0)} Today")
        self.card_checkouts.lbl_sub.setText(f"{data.get('co_records_len', 0)} Total Archived")

        moves = data.get("moves", [])
        self.card_moves.lbl_main.setText(f"{len(moves)} Moves")
        self.card_moves.lbl_sub.setText("Archived in room_moves.json")

        meta = data.get("meta", {})
        last_dt = meta.get("last_sync_date") or meta.get("last_processed_date") or "Not Synced"
        last_ts = meta.get("last_updated_at", "")
        if "T" in str(last_ts):
            last_ts = str(last_ts).split(".")[0].replace("T", " ")
        self.card_sync.lbl_main.setText(str(last_dt))
        self.card_sync.lbl_sub.setText(f"Updated: {last_ts}" if last_ts else "No timestamp")

        # Update Block Occupancy Meter Cards
        all_blocks_info = data.get("all_blocks_info", [])
        for b_info in all_blocks_info:
            b_name = b_info["name"]
            pct = b_info["pct"]
            occ = b_info["occupied"]
            tot = b_info["total"]
            desc = b_info["desc"]
            if b_name in self.block_card_widgets:
                card = self.block_card_widgets[b_name]
                accent = "#2563EB" if pct < 75 else ("#D97706" if pct < 90 else "#DC2626")
                bg = "#EFF6FF" if pct < 75 else ("#FFFBEB" if pct < 90 else "#FEF2F2")
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {bg};
                        border: 1px solid {accent}33;
                        border-left: 4px solid {accent};
                        border-radius: 6px;
                        padding: 6px 10px;
                    }}
                """)
                card.lbl_name.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {accent};")
                card.lbl_pct.setText(f"{pct:.0f}%")
                card.lbl_pct.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {accent};")
                card.pbar.setValue(min(100, int(round(pct))))
                card.pbar.setStyleSheet(f"""
                    QProgressBar {{
                        background-color: #E2E8F0;
                        border: none;
                        border-radius: 3px;
                    }}
                    QProgressBar::chunk {{
                        background-color: {accent};
                        border-radius: 3px;
                    }}
                """)
                card.lbl_rooms.setText(f"{occ}/{tot} Occ" if tot > 0 else "0 Rooms")
                vacant = max(0, tot - occ)
                card.lbl_vacant.setText(f"{vacant} Vac" if tot > 0 else "")
                card.setToolTip(f"{b_name}: {occ}/{tot} rooms occupied ({pct:.1f}%)\n{desc}")

        # Breakdown Cards
        board_counter = data.get("board_counter", collections.Counter())
        nat_counter = data.get("nat_counter", collections.Counter())
        room_counter = data.get("room_counter", collections.Counter())

        if board_counter:
            self.box_board.content_lbl.setText("\n".join(f"• {k}: {v} bookings" for k, v in board_counter.most_common(4)))
        else:
            self.box_board.content_lbl.setText("No active board data")

        if nat_counter:
            self.box_nat.content_lbl.setText("\n".join(f"• {k[:22]}: {v} bookings" for k, v in nat_counter.most_common(4)))
        else:
            self.box_nat.content_lbl.setText("No active nationality data")

        if room_counter:
            self.box_rooms.content_lbl.setText("\n".join(f"• {k[:22]}: {v} rooms" for k, v in room_counter.most_common(4)))
        else:
            self.box_rooms.content_lbl.setText("No active room category data")

        # Document Production Summary
        doc_counts = data.get("doc_counts", {"offers": 0, "cakes": 0})
        self.card_offers_count.lbl_main.setText(f"{doc_counts['offers']} Documents")
        self.card_offers_count.lbl_sub.setText("Total in Output Storage")
        self.card_cakes_count.lbl_main.setText(f"{doc_counts['cakes']} Documents")
        self.card_cakes_count.lbl_sub.setText("Total in Output Storage")

        # In-House status banner
        if hasattr(self, "lbl_inhouse_status"):
            sync_date = meta.get("last_sync_date") or meta.get("last_processed_date")
            if sync_date:
                ts_display = str(meta.get("last_updated_at", "")).split(".")[0].replace("T", " ") if meta.get("last_updated_at") else "N/A"
                self.lbl_inhouse_status.setText(
                    f"✅ Loaded: {sync_date}  |  {total_bookings} Bookings  |  Last PMS sync: {ts_display}"
                )
                self.lbl_inhouse_status.setStyleSheet("background-color: #ECFDF5; color: #065F46; font-weight: bold; padding: 8px 12px; border: 1px solid #A7F3D0; border-radius: 6px;")
            else:
                self.lbl_inhouse_status.setText("⚠️ No In-House List loaded yet")
                self.lbl_inhouse_status.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 8px 12px; border: 1px solid #FECACA; border-radius: 6px;")

        if hasattr(self, "lbl_activity_log"):
            self.lbl_activity_log.setText(self._build_activity_log(meta))

        # Populate Manifest Tables
        self._populate_manifest_table(self.table_inhouse, data.get("sorted_bookings", []))
        if hasattr(self, "table_inhouse_standalone"):
            self._populate_manifest_table(self.table_inhouse_standalone, data.get("sorted_bookings", []))

        # Re-render Matplotlib Charts
        self._render_charts(data)

    def _populate_manifest_table(self, table: QTableWidget, sorted_bookings: List[Any]) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for b_id, b_data in sorted_bookings:
            r = table.rowCount()
            table.insertRow(r)
            rm = str(b_data.get("Room") or b_data.get("Δωμάτιο", ""))
            table.setItem(r, 0, QTableWidgetItem(rm))
            table.setItem(r, 1, QTableWidgetItem(str(b_id)))
            g_list = b_data.get("Guests") or b_data.get("Πελάτες", [])
            g_str = ", ".join(g_list) if isinstance(g_list, list) else str(g_list)
            table.setItem(r, 2, QTableWidgetItem(g_str))
            table.setItem(r, 3, QTableWidgetItem(str(b_data.get("Arrival") or b_data.get("Άφιξη", ""))))
            table.setItem(r, 4, QTableWidgetItem(str(b_data.get("Departure") or b_data.get("Αναχώρηση", ""))))
            table.setItem(r, 5, QTableWidgetItem(str(b_data.get("Room Type") or b_data.get("Τύπος Δωματίου", "Standard"))))
            table.setItem(r, 6, QTableWidgetItem(str(b_data.get("Agency") or b_data.get("Χρεώστης", ""))))
            table.setItem(r, 7, QTableWidgetItem(str(b_data.get("Meal Plan") or b_data.get("Τύπος Γεύματος", "All Inclusive"))))
        table.setSortingEnabled(True)

    def _render_charts(self, *args, **kwargs) -> None:
        if args and isinstance(args[0], dict) and "master" in args[0] and "block_percentages" in args[0]:
            data = args[0]
        else:
            data = self._fetch_all_stats_data()

        self.figure.clear()
        axs = self.figure.subplots(2, 2)
        ax1, ax2 = axs[0, 0], axs[0, 1]
        ax3, ax4 = axs[1, 0], axs[1, 1]

        # Chart 1: Occupancy Rate per Room Block (%)
        target_blocks = data.get("target_blocks", [])
        percentages = data.get("block_percentages", [])
        labels = [b.replace("BLOCK ", "") for b in target_blocks]
        bar_colors = [
            "#2563EB" if p < 75 else ("#D97706" if p < 90 else "#DC2626")
            for p in percentages
        ]

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
        room_types = data.get("room_types_for_chart", collections.Counter())
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
        arrivals = data.get("arrivals", {})
        arr_cnt = len(arrivals)
        inhouse_cnt = data.get("total_bookings", 0)
        today_cos = data.get("today_cos", 0)

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

        # Chart 4: Debtor / Agency Distribution
        agencies = data.get("agency_counter", collections.Counter())
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

    # -----------------------------------------------------------------
    # Manifest Filtering & Quick Actions
    # -----------------------------------------------------------------
    def _filter_table(self) -> None:
        query = self.txt_search.text().strip().lower()
        block_filter = self.cmb_filter_block.currentText() if hasattr(self, "cmb_filter_block") else "All Blocks"

        for r in range(self.table_inhouse.rowCount()):
            room = self.table_inhouse.item(r, 0).text().strip() if self.table_inhouse.item(r, 0) else ""

            # Block prefix filter
            block_match = True
            if block_filter != "All Blocks":
                prefix = block_filter.replace("s", "")
                if len(prefix) == 3:
                    block_match = room.startswith(prefix[0]) and len(room) == 3
                else:
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

    def _prompt_for_operational_date(self, title: str, message: str, default_date: Optional[date] = None) -> Optional[date]:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(380)
        d_layout = QVBoxLayout(dialog)
        d_layout.setSpacing(12)

        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 12px; color: #1E293B;")
        d_layout.addWidget(lbl)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd/MM/yyyy")
        d_val = default_date or date.today()
        date_edit.setDate(QDate(d_val.year, d_val.month, d_val.day))
        date_edit.setStyleSheet("font-size: 13px; font-weight: bold; padding: 6px; border: 1px solid #FFB6C1; border-radius: 4px;")
        d_layout.addWidget(date_edit)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        d_layout.addWidget(btns)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            qd = date_edit.date()
            return date(qd.year(), qd.month(), qd.day())
        return None

    def _quick_load_inhouse(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Select In-House List Export",
            "", "Spreadsheet Files (*.xlsx *.xls *.csv);;CSV Files (*.csv);;All Files (*.*)"
        )
        if not fpath:
            return

        file_dt, date_source = extract_inhouse_report_date(fpath)
        processing_dt: Optional[date] = None

        if file_dt:
            if file_dt == date.today():
                processing_dt = file_dt
            else:
                resp = QMessageBox.question(
                    self,
                    "In-House Report Date Detected",
                    f"The file contains a report date of {file_dt.strftime('%d/%m/%Y')} (Source: {date_source}).\n\n"
                    f"Today is {date.today().strftime('%d/%m/%Y')}.\n\n"
                    f"Do you want to process this file for {file_dt.strftime('%d/%m/%Y')}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes
                )
                if resp == QMessageBox.StandardButton.Yes:
                    processing_dt = file_dt
                elif resp == QMessageBox.StandardButton.No:
                    processing_dt = self._prompt_for_operational_date(
                        "Set Operational Date",
                        "Please select the operational date to assign to this in-house list:",
                        default_date=date.today()
                    )
                    if processing_dt is None:
                        return
                else:
                    return
        else:
            processing_dt = self._prompt_for_operational_date(
                "Operational Date Required",
                f"Could not automatically detect the report date inside:\n{os.path.basename(fpath)}\n\n"
                f"Please specify the operational date for this In-House list:",
                default_date=date.today()
            )
            if processing_dt is None:
                return

        try:
            new_bookings = self.data_manager.parse_in_house_file(fpath)
            if not new_bookings:
                QMessageBox.warning(self, "Empty File", f"No valid bookings could be extracted from:\n{os.path.basename(fpath)}")
                return

            summary = self.data_manager.compare_and_update(new_bookings, processing_date=processing_dt)
            self.refresh_stats(sync=True)
            QMessageBox.information(
                self, "In-House List Synchronized",
                f"Successfully ingested {summary['total_in_house']} bookings for {summary['date']}!\n\n"
                f"• In-House Active: {summary['total_in_house']}\n"
                f"• Room Moves Detected: {len(summary.get('room_moves', []))}\n"
                f"• Check-Ins Recorded: {len(summary.get('check_ins', []))}\n"
                f"• Check-Outs Recorded: {len(summary.get('check_outs', []))}\n"
                f"• Master State and Block metrics refreshed."
            )
        except Exception as e:
            QMessageBox.critical(self, "Ingestion Error", f"Failed to ingest in-house file:\n{e}")

    def _quick_refresh_blocks(self) -> None:
        try:
            res = self.data_manager.export_room_block_json_data()
            self.refresh_stats(sync=True)
            QMessageBox.information(
                self, "Block Exports Refreshed",
                f"Successfully refreshed {res.get('total_blocks_exported', 0)} room block JSON exports in PLOT directory."
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Error exporting room blocks:\n{e}")

    def _open_output_folder(self, subfolder: Optional[str] = None, full_path: Optional[str] = None) -> None:
        target = full_path or (os.path.join(OUTPUT_DIR, subfolder) if subfolder else OUTPUT_DIR)
        os.makedirs(target, exist_ok=True)
        try:
            os.startfile(target)
        except Exception as e:
            QMessageBox.warning(self, "Cannot Open Folder", f"Could not open directory:\n{e}")

    def _count_documents(self) -> Dict[str, int]:
        offers_count = 0
        cakes_count = 0
        cand_offers = [os.path.join(OUTPUT_DIR, "OFFERS"), os.path.join(OUTPUT_DIR, "OFFER LISTS")]
        for p in cand_offers:
            if os.path.exists(p):
                offers_count += len([f for f in os.listdir(p) if f.lower().endswith(('.xlsx', '.docx', '.pdf'))])

        cand_cakes = [os.path.join(OUTPUT_DIR, "CAKES"), os.path.join(OUTPUT_DIR, "CAKE MEMOS")]
        for p in cand_cakes:
            if os.path.exists(p):
                cakes_count += len([f for f in os.listdir(p) if f.lower().endswith(('.xlsx', '.docx', '.pdf'))])
        return {"offers": offers_count, "cakes": cakes_count}

    def _build_activity_log(self, meta: Dict[str, Any]) -> str:
        lines = []
        sync_date = meta.get("last_sync_date") or meta.get("last_processed_date")
        if sync_date:
            ts = str(meta.get("last_updated_at", "")).split(".")[0].replace("T", " ")
            lines.append(f"• Last In-House Sync: {sync_date} at {ts} ({meta.get('total_bookings', 0)} bookings)")
        else:
            lines.append("• No In-House sync events recorded in state_metadata.json.")
        return "\n".join(lines)

    def activate(self) -> None:
        """Called by app navigation when Stats option is selected."""
        try:
            self.refresh_stats(sync=True)
        except Exception as e:
            print(f"[Stats] Activation error: {e}")
