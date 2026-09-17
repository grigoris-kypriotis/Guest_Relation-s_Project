"""
Plot Viewer Module: 2D Interactive Resort Node Graph Canvas & Entity Inspector
=============================================================================
Renders all 44 nodes from PLOT/HotelDataSet.json on a 2D interactive coordinate canvas
approximating the Sandy Beach resort map layout. Provides smooth pan/zoom, distinct
category styling, live occupancy badges, quick search, and an interactive Node Inspector
modal dialog displaying complete formatted JSON attributes.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialog, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPathItem, QLineEdit, QComboBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QTextEdit, QApplication, QMessageBox, QToolTip
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QPen, QFont, QPainter, QLinearGradient,
    QPainterPath, QCursor, QKeySequence, QShortcut
)

from data_manager import (
    BASE_DIR, PLOT_DIR, HOTEL_DATASET_PATH, InHouseDataManager
)


# =============================================================================
# Spatial Layout & Coordinates Configuration
# =============================================================================

# Coordinates (x, y, width, height) approximating Sandy Beach resort map layout
NODE_COORDINATES: Dict[int, Dict[str, Any]] = {
    # Upper/Left Room Blocks (Nodes 1 to 9: Blocks 1100 to 1900)
    1: {"x": 310, "y": 240, "w": 100, "h": 50},   # BLOCK 1100
    2: {"x": 200, "y": 240, "w": 100, "h": 50},   # BLOCK 1200
    3: {"x": 150, "y": 310, "w": 100, "h": 50},   # BLOCK 1300
    4: {"x": 100, "y": 380, "w": 100, "h": 50},   # BLOCK 1400
    5: {"x": 90, "y": 450, "w": 100, "h": 50},    # BLOCK 1500
    6: {"x": 90, "y": 520, "w": 100, "h": 50},    # BLOCK 1600
    7: {"x": 250, "y": 165, "w": 95, "h": 48},    # BLOCK 1700
    8: {"x": 355, "y": 165, "w": 95, "h": 48},    # BLOCK 1800
    9: {"x": 460, "y": 165, "w": 95, "h": 48},    # BLOCK 1900

    # Reception & Facilities Cluster (Nodes 17, 18, 19, 20, 21, 22, 30, 32, 42)
    17: {"x": 450, "y": 240, "w": 140, "h": 60},  # RECEPTION / MUSES / IL GUSTO
    18: {"x": 610, "y": 240, "w": 120, "h": 50},  # SHOPPING CENTER / HAIRDRESSER
    32: {"x": 390, "y": 320, "w": 100, "h": 48},  # APERITIVO Bar
    22: {"x": 510, "y": 320, "w": 125, "h": 50},  # CONFERENCE ROOM / DOCTOR
    19: {"x": 270, "y": 320, "w": 110, "h": 50},  # AQUA Pool Bar / TOWELS
    20: {"x": 215, "y": 390, "w": 105, "h": 48},  # SNACK CORNER
    21: {"x": 165, "y": 460, "w": 115, "h": 50},  # WATERSLIDES / PLAYGROUND
    42: {"x": 580, "y": 165, "w": 105, "h": 48},  # TENNIS COURT
    30: {"x": 700, "y": 165, "w": 115, "h": 48},  # BASKETBALL & FOOTBALL

    # Central & Beachside Blocks (Nodes 10 to 16: Blocks 2000 to 8000)
    16: {"x": 310, "y": 420, "w": 100, "h": 50},  # BLOCK 8000
    10: {"x": 435, "y": 420, "w": 105, "h": 50},  # BLOCK 2000
    11: {"x": 560, "y": 420, "w": 105, "h": 50},  # BLOCK 3000
    12: {"x": 330, "y": 510, "w": 105, "h": 50},  # BLOCK 4000
    13: {"x": 455, "y": 510, "w": 105, "h": 50},  # BLOCK 5000
    14: {"x": 580, "y": 510, "w": 105, "h": 50},  # BLOCK 6000
    15: {"x": 445, "y": 600, "w": 110, "h": 52},  # BLOCK 7000

    # Beachfront & Lower Amenities (Nodes 23, 24, 25, 26, 27, 28, 29, 31, 43, 44)
    23: {"x": 315, "y": 600, "w": 115, "h": 52},  # ELIA Main Restaurant
    24: {"x": 685, "y": 420, "w": 115, "h": 50},  # GAME CENTER / GYM
    25: {"x": 575, "y": 600, "w": 105, "h": 50},  # NAVIO Pool Bar
    26: {"x": 695, "y": 510, "w": 110, "h": 50},  # AMPHITHEATRE
    44: {"x": 200, "y": 660, "w": 115, "h": 50},  # ERMIS GYRO Greek Restaurant
    43: {"x": 315, "y": 690, "w": 115, "h": 50},  # MARE Adults Only Pool Bar
    28: {"x": 445, "y": 690, "w": 125, "h": 52},  # AMMOS Mediterranean Restaurant
    27: {"x": 585, "y": 690, "w": 105, "h": 50},  # KYMA Beach Bar
    31: {"x": 705, "y": 690, "w": 115, "h": 50},  # GELATERIA / SHOPPING
    29: {"x": 370, "y": 780, "w": 320, "h": 55},  # BEACH AREA (Main coast banner)

    # Detached/Unplotted Suites (Nodes 33–40: Blocks 100–800) in auxiliary cluster
    33: {"x": 880, "y": 200, "w": 105, "h": 50},  # BLOCK 100
    34: {"x": 1005, "y": 200, "w": 105, "h": 50}, # BLOCK 200
    35: {"x": 880, "y": 280, "w": 105, "h": 50},  # BLOCK 300
    36: {"x": 1005, "y": 280, "w": 105, "h": 50}, # BLOCK 400
    37: {"x": 880, "y": 360, "w": 105, "h": 50},  # BLOCK 500
    38: {"x": 1005, "y": 360, "w": 105, "h": 50}, # BLOCK 600
    39: {"x": 880, "y": 440, "w": 105, "h": 50},  # BLOCK 700
    40: {"x": 1005, "y": 440, "w": 105, "h": 50}, # BLOCK 800
    41: {"x": 940, "y": 520, "w": 110, "h": 46},  # Unlisted
}


def get_node_style(category: str, node_id: int) -> Dict[str, Any]:
    """Returns color styling, border, and badge metadata based on node category."""
    cat_lower = category.lower()

    if 33 <= node_id <= 40:
        # Detached Pool Suites (Sandy Villas)
        return {
            "bg_gradient": ("#7C3AED", "#5B21B6"),
            "border": "#A78BFA",
            "text": "#FFFFFF",
            "badge": "POOL SUITES",
            "badge_color": "#DDD6FE",
            "type_group": "Pool Suites"
        }
    elif "rooms" in cat_lower:
        # Standard Main Room Blocks
        return {
            "bg_gradient": ("#2563EB", "#1D4ED8"),
            "border": "#60A5FA",
            "text": "#FFFFFF",
            "badge": "ROOMS",
            "badge_color": "#BFDBFE",
            "type_group": "Rooms"
        }
    elif "restaurant" in cat_lower or "food" in cat_lower:
        return {
            "bg_gradient": ("#DC2626", "#991B1B"),
            "border": "#F87171",
            "text": "#FFFFFF",
            "badge": "DINING",
            "badge_color": "#FECACA",
            "type_group": "Facilities"
        }
    elif "bar" in cat_lower:
        return {
            "bg_gradient": ("#D97706", "#B45309"),
            "border": "#FBBF24",
            "text": "#FFFFFF",
            "badge": "BAR",
            "badge_color": "#FEF3C7",
            "type_group": "Facilities"
        }
    elif "recreation" in cat_lower or "entertainment" in cat_lower:
        return {
            "bg_gradient": ("#059669", "#047857"),
            "border": "#34D399",
            "text": "#FFFFFF",
            "badge": "RECREATION",
            "badge_color": "#A7F3D0",
            "type_group": "Facilities"
        }
    elif node_id == 41:
        return {
            "bg_gradient": ("#6B7280", "#4B5563"),
            "border": "#9CA3AF",
            "text": "#FFFFFF",
            "badge": "UNLISTED",
            "badge_color": "#E5E7EB",
            "type_group": "None"
        }
    else:
        # Generic Facilities / Front desk / Shopping
        return {
            "bg_gradient": ("#800020", "#5A0016"),
            "border": "#FFB6C1",
            "text": "#FFFFFF",
            "badge": "FACILITY",
            "badge_color": "#FFE4E1",
            "type_group": "Facilities"
        }


# =============================================================================
# Interactive QGraphicsItem for Canvas Nodes
# =============================================================================

class ResortNodeItem(QGraphicsItem):
    """Custom interactive 2D graphical node with hover glow and click triggers."""

    def __init__(self, node_data: Dict[str, Any], coords: Dict[str, Any], parent_viewer=None):
        super().__init__()
        self.node_data = node_data
        self.coords = coords
        self.parent_viewer = parent_viewer

        self.node_id = int(node_data.get("id", 0))
        self.node_name = str(node_data.get("name", f"Node {self.node_id}"))
        self.category = str(node_data.get("category", "Facilities"))

        self.style = get_node_style(self.category, self.node_id)
        self.is_hovered = False
        self.is_highlighted = False

        self.setPos(coords["x"], coords["y"])
        self.width = coords["w"]
        self.height = coords["h"]

        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Check for live occupancy metric
        self.occ_pct: Optional[float] = None
        self._load_occupancy_if_available()

    def _load_occupancy_if_available(self):
        slug = re.sub(r"[^\w\d]+", "_", self.node_name.strip()).strip("_")
        block_json = Path(PLOT_DIR) / slug / f"{slug}.json"
        if block_json.exists():
            try:
                with open(block_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    metrics = data.get("occupancy_metrics", {})
                    if "occupancy_percentage" in metrics:
                        self.occ_pct = float(metrics["occupancy_percentage"])
            except Exception:
                pass

    def boundingRect(self) -> QRectF:
        margin = 6
        return QRectF(-margin, -margin, self.width + margin * 2, self.height + margin * 2)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width, self.height)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        # Glow / Shadow effect when hovered or highlighted
        if self.is_highlighted:
            glow_pen = QPen(QColor("#F59E0B"), 6)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 10, 10)
        elif self.is_hovered:
            glow_pen = QPen(QColor(self.style["border"]), 4)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 9, 9)

        # Background Gradient
        grad = QLinearGradient(0, 0, 0, self.height)
        c1 = QColor(self.style["bg_gradient"][0])
        c2 = QColor(self.style["bg_gradient"][1])
        if self.is_hovered:
            c1 = c1.lighter(115)
            c2 = c2.lighter(115)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)

        pen = QPen(QColor(self.style["border"]), 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(path)

        # ID Badge (top left circle/pill)
        badge_rect = QRectF(5, 5, 20, 16)
        painter.setBrush(QColor(0, 0, 0, 90))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect, 4, 4)

        painter.setPen(QColor(self.style["badge_color"]))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(self.node_id))

        # Category / Occupancy Pill (top right)
        right_badge_text = f"{self.occ_pct:.0f}%" if self.occ_pct is not None else self.style["badge"]
        r_badge_rect = QRectF(self.width - 52, 5, 47, 16)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawRoundedRect(r_badge_rect, 4, 4)

        if self.occ_pct is not None:
            occ_color = "#34D399" if self.occ_pct < 80 else ("#FBBF24" if self.occ_pct < 95 else "#F87171")
            painter.setPen(QColor(occ_color))
        else:
            painter.setPen(QColor(self.style["badge_color"]))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(r_badge_rect, Qt.AlignmentFlag.AlignCenter, right_badge_text)

        # Entity Name (centered)
        painter.setPen(QColor(self.style["text"]))
        name_font_size = 9 if self.width < 120 else 10
        painter.setFont(QFont("Segoe UI", name_font_size, QFont.Weight.Bold))
        name_rect = QRectF(4, 22, self.width - 8, self.height - 24)

        disp_name = self.node_name
        if len(disp_name) > 28 and self.width < 180:
            disp_name = disp_name[:26] + "..."
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, disp_name)

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        if self.parent_viewer:
            occ_info = f" • Live Occupancy: {self.occ_pct}%" if self.occ_pct is not None else ""
            self.parent_viewer.set_status(f"Node #{self.node_id}: {self.node_name} [{self.category}]{occ_info}")
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        if self.parent_viewer:
            self.parent_viewer.set_status("Ready. Click on any node to inspect full attributes.")
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.parent_viewer:
                self.parent_viewer.open_node_inspector(self.node_data)
        super().mousePressEvent(event)


# =============================================================================
# Interactive Node Inspector Modal Dialog
# =============================================================================

class NodeInspectorDialog(QDialog):
    """Rich modal popup displaying the complete formatted JSON attributes of an entity."""

    def __init__(self, node_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.node_data = node_data
        self.node_id = node_data.get("id", "N/A")
        self.node_name = node_data.get("name", "Unknown Node")
        self.category = node_data.get("category", "None")

        self.setWindowTitle(f"Node Inspector : #{self.node_id} - {self.node_name}")
        self.resize(760, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FA;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header Card
        style = get_node_style(self.category, int(self.node_id) if str(self.node_id).isdigit() else 0)
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {style['bg_gradient'][0]}, stop:1 {style['bg_gradient'][1]});
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setSpacing(4)

        top_row = QHBoxLayout()
        lbl_id = QLabel(f"NODE #{self.node_id}")
        lbl_id.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 4px;")
        lbl_cat = QLabel(f"CATEGORY: {self.category.upper()}")
        lbl_cat.setStyleSheet("color: #FFE4E1; font-size: 12px; font-weight: bold;")
        top_row.addWidget(lbl_id)
        top_row.addWidget(lbl_cat)
        top_row.addStretch()

        lbl_title = QLabel(self.node_name)
        lbl_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-top: 4px;")

        h_layout.addLayout(top_row)
        h_layout.addWidget(lbl_title)
        layout.addWidget(header_frame)

        # 2. Tab Widget
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #E0E0E0; background: white; border-radius: 6px; }
            QTabBar::tab { background: #EFEFEF; padding: 8px 16px; margin-right: 2px; font-weight: bold; color: #444; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #800020; color: white; }
        """)

        # Tab 1: Formatted Attributes
        tab_formatted = QWidget()
        tf_layout = QVBoxLayout(tab_formatted)
        tf_layout.setContentsMargins(14, 14, 14, 14)
        tf_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        sc_layout = QVBoxLayout(scroll_content)
        sc_layout.setSpacing(12)

        # Description Card
        desc = self.node_data.get("description", "No description provided.")
        sc_layout.addWidget(self._create_section_card("📌 Description & Room Range", desc))

        # Distances & Adjacency Card
        dist = self.node_data.get("distances", "No distance metrics available.")
        sc_layout.addWidget(self._create_section_card("🧭 Distances & Adjacency", dist))

        # Room Details (If room block)
        rd = self.node_data.get("room_details", {})
        if rd or "Rooms" in self.category or self.node_name.startswith("BLOCK"):
            sc_layout.addWidget(self._create_room_details_card(rd))

        # Facilities Attributes (Operating hours, dress code, upgrade rates)
        op_hours = self.node_data.get("operating_hours")
        if op_hours:
            sc_layout.addWidget(self._create_operating_hours_card(op_hours))

        extra_info = self.node_data.get("extra_info")
        if extra_info:
            sc_layout.addWidget(self._create_section_card("ℹ️ Operational Notes & Rules", extra_info))

        upgrades = self.node_data.get("upgrade_rates_2026")
        if upgrades:
            sc_layout.addWidget(self._create_upgrade_rates_card(upgrades))

        sc_layout.addStretch()
        scroll.setWidget(scroll_content)
        tf_layout.addWidget(scroll)
        tabs.addTab(tab_formatted, "📋 Structured Details")

        # Tab 2: Raw JSON Inspector
        tab_json = QWidget()
        tj_layout = QVBoxLayout(tab_json)
        tj_layout.setContentsMargins(14, 14, 14, 14)

        json_str = json.dumps(self.node_data, indent=4, ensure_ascii=False)
        txt_json = QTextEdit()
        txt_json.setReadOnly(True)
        txt_json.setFont(QFont("Consolas", 10))
        txt_json.setText(json_str)
        txt_json.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4; border-radius: 6px; padding: 10px;")
        tj_layout.addWidget(txt_json)

        btn_copy = QPushButton("📋 Copy JSON to Clipboard")
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1B5E20; }
        """)
        btn_copy.clicked.connect(lambda: self._copy_to_clipboard(json_str))
        tj_layout.addWidget(btn_copy)

        tabs.addTab(tab_json, "{ } Raw JSON")
        layout.addWidget(tabs, stretch=1)

        # Close button
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background: #800020; color: white; font-weight: bold; padding: 8px 24px; border-radius: 4px;")
        btn_close.clicked.connect(self.accept)
        b_row = QHBoxLayout()
        b_row.addStretch()
        b_row.addWidget(btn_close)
        layout.addLayout(b_row)

    def _create_section_card(self, title: str, text: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #F8F9FA; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px; }")
        fl = QVBoxLayout(frame)
        fl.setSpacing(4)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-weight: bold; color: #800020; font-size: 12px;")
        lbl_val = QLabel(text)
        lbl_val.setWordWrap(True)
        lbl_val.setStyleSheet("color: #2D3748; font-size: 12px;")
        fl.addWidget(lbl_t)
        fl.addWidget(lbl_val)
        return frame

    def _create_room_details_card(self, rd: Dict[str, Any]) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px; padding: 10px; }")
        fl = QVBoxLayout(frame)
        fl.setSpacing(6)

        lbl_t = QLabel("🛏️ Room Block Breakdown & Specifications")
        lbl_t.setStyleSheet("font-weight: bold; color: #166534; font-size: 13px;")
        fl.addWidget(lbl_t)

        total_r = rd.get("total_rooms", "N/A")
        views = rd.get("views", self.node_data.get("views", "N/A"))
        features = rd.get("features", self.node_data.get("features", "Standard"))

        meta_lbl = QLabel(f"• Total Block Capacity: <b>{total_r} Rooms</b>\n• Views: <i>{views}</i>\n• Features: <i>{features}</i>")
        meta_lbl.setStyleSheet("color: #14532D; font-size: 12px;")
        fl.addWidget(meta_lbl)

        # Types breakdown
        types = rd.get("types", {})
        if types:
            types_str = " | ".join(f"<b>{k}</b>: {v}" for k, v in types.items())
            fl.addWidget(QLabel(f"• Room Types: {types_str}"))

        # Floors breakdown
        floors = rd.get("floors", {})
        if floors:
            fl.addWidget(QLabel("<b>Floor Assignments:</b>"))
            for fl_name, r_ranges in floors.items():
                fl.addWidget(QLabel(f"   ▫ {fl_name}: {', '.join(r_ranges)}"))

        return frame

    def _create_operating_hours_card(self, hours: Dict[str, str]) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #FEF3C7; border: 1px solid #FDE68A; border-radius: 6px; padding: 10px; }")
        fl = QVBoxLayout(frame)
        fl.setSpacing(4)
        lbl_t = QLabel("⏰ Operating Hours & Schedules")
        lbl_t.setStyleSheet("font-weight: bold; color: #92400E; font-size: 12px;")
        fl.addWidget(lbl_t)
        for venue, schedule in hours.items():
            fl.addWidget(QLabel(f"• <b>{venue}</b>: {schedule}"))
        return frame

    def _create_upgrade_rates_card(self, upgrades: Dict[str, Any]) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 6px; padding: 10px; }")
        fl = QVBoxLayout(frame)
        fl.setSpacing(6)
        lbl_t = QLabel("💎 Upgrade Rates 2026 Reference")
        lbl_t.setStyleSheet("font-weight: bold; color: #1E40AF; font-size: 13px;")
        fl.addWidget(lbl_t)

        seasons = upgrades.get("seasons", {})
        if seasons:
            fl.addWidget(QLabel(f"• Low/Mid Season: <i>{seasons.get('low_mid', '')}</i>"))
            fl.addWidget(QLabel(f"• High Season: <i>{seasons.get('high', '')}</i>"))

        fl.addWidget(QLabel("<i>Note: Detailed cross-tier rates table available in Raw JSON tab.</i>"))
        return frame

    def _copy_to_clipboard(self, text: str):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            QMessageBox.information(self, "Copied", "Raw JSON copied to system clipboard.")


# =============================================================================
# Custom 2D Graphics View with Smooth Pan & Zoom Controls
# =============================================================================

class ResortGraphicsView(QGraphicsView):
    """Custom QGraphicsView with wheel zoom, drag pan, and visual bounding boundaries."""

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.zoom_factor = 1.15

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.scale(self.zoom_factor, self.zoom_factor)
        else:
            self.scale(1.0 / self.zoom_factor, 1.0 / self.zoom_factor)


# =============================================================================
# Dedicated Plot Graph Window (Plot Option)
# =============================================================================

class PlotGraphWindow(QMainWindow):
    """
    Dedicated 2D interactive canvas/graph window for Sandy Beach resort map.
    Renders all 44 nodes from PLOT/HotelDataSet.json with spatial layout,
    category styling, smooth pan/zoom, search filter, and interactive inspection.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resort 2D Node Graph Visualization (Sandy Beach)")
        self.resize(1280, 850)
        self.setStyleSheet("QMainWindow { background-color: #F8F9FA; }")

        self.nodes_data: List[Dict[str, Any]] = []
        self.node_items: Dict[int, ResortNodeItem] = {}

        self._load_dataset()
        self._init_ui()
        self._build_scene()

    def _load_dataset(self):
        dataset_path = Path(HOTEL_DATASET_PATH)
        if dataset_path.exists():
            try:
                with open(dataset_path, "r", encoding="utf-8") as f:
                    self.nodes_data = json.load(f)
            except Exception as e:
                print(f"[PlotGraphWindow] Error loading dataset: {e}")
                self.nodes_data = []

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(12, 12, 12, 8)
        main_layout.setSpacing(8)

        # 1. Top Controls Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        # Title badge
        lbl_title = QLabel("🗺️ RESORT NODE GRAPH")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #800020;")
        top_bar.addWidget(lbl_title)

        top_bar.addSpacing(15)

        # Filter ComboBox
        lbl_filter = QLabel("Filter:")
        lbl_filter.setStyleSheet("font-weight: bold; color: #333333;")
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["All Nodes (44)", "Rooms Only", "Facilities Only", "Pool Suites (100-800)"])
        self.combo_filter.setStyleSheet("padding: 4px 8px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        self.combo_filter.currentTextChanged.connect(self._apply_filter)
        top_bar.addWidget(lbl_filter)
        top_bar.addWidget(self.combo_filter)

        top_bar.addSpacing(10)

        # Quick Search Box
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Find Node by ID or Name...")
        self.txt_search.setFixedWidth(220)
        self.txt_search.setStyleSheet("padding: 5px 8px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
        self.txt_search.textChanged.connect(self._search_nodes)
        top_bar.addWidget(self.txt_search)

        top_bar.addStretch()

        # Canvas Zoom Buttons
        btn_zoom_in = QPushButton("➕ Zoom In")
        btn_zoom_out = QPushButton("➖ Zoom Out")
        btn_fit = QPushButton("🎯 Fit View")
        btn_reset = QPushButton("🔄 Reset")

        btn_style = """
            QPushButton {
                background-color: #FFF0F5;
                border: 1px solid #FF69B4;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: bold;
                color: #800020;
            }
            QPushButton:hover { background-color: #FF69B4; color: white; }
        """
        for b in [btn_zoom_in, btn_zoom_out, btn_fit, btn_reset]:
            b.setStyleSheet(btn_style)

        btn_zoom_in.clicked.connect(lambda: self.view.scale(1.2, 1.2))
        btn_zoom_out.clicked.connect(lambda: self.view.scale(0.83, 0.83))
        btn_fit.clicked.connect(self._fit_to_view)
        btn_reset.clicked.connect(self._reset_view)

        top_bar.addWidget(btn_zoom_in)
        top_bar.addWidget(btn_zoom_out)
        top_bar.addWidget(btn_fit)
        top_bar.addWidget(btn_reset)

        main_layout.addLayout(top_bar)

        # 2. Graphics Scene and View
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 1160, 920)
        self.scene.setBackgroundBrush(QColor("#FAF9F6"))

        self.view = ResortGraphicsView(self.scene, self)
        self.view.setStyleSheet("border: 1px solid #FFB6C1; border-radius: 6px; background-color: #FDFBF7;")
        main_layout.addWidget(self.view, stretch=1)

        # 3. Status Bar
        self.lbl_status = QLabel("Ready. Pan with mouse drag, zoom with scroll wheel, click on any node to inspect.")
        self.lbl_status.setStyleSheet("color: #666666; font-size: 12px; padding: 2px 6px;")
        main_layout.addWidget(self.lbl_status)

    def _build_scene(self):
        """Constructs 2D canvas background zones and all 44 interactive nodes."""
        self.scene.clear()
        self.node_items.clear()

        # 1. Background Boundary Zones
        def add_rounded_zone(rect: QRectF, rx: float, ry: float, pen: QPen, brush: QBrush):
            p = QPainterPath()
            p.addRoundedRect(rect, rx, ry)
            it = self.scene.addPath(p, pen, brush)
            it.setZValue(-10)
            return it

        pen_zone = QPen(QColor("#E2E8F0"), 1.5, Qt.PenStyle.DashLine)
        add_rounded_zone(QRectF(60, 120, 770, 560), 16, 16, pen_zone, QBrush(QColor("#FFFFFF")))

        pen_beach = QPen(QColor("#BAE6FD"), 1.5)
        add_rounded_zone(QRectF(60, 700, 770, 170), 14, 14, pen_beach, QBrush(QColor("#F0F9FF")))

        pen_annex = QPen(QColor("#DDD6FE"), 1.5, Qt.PenStyle.DashLine)
        add_rounded_zone(QRectF(850, 120, 280, 480), 16, 16, pen_annex, QBrush(QColor("#FAF5FF")))

        # Zone Labels
        def add_zone_label(x, y, text, color):
            lbl = self.scene.addText(text, QFont("Segoe UI", 11, QFont.Weight.Bold))
            lbl.setDefaultTextColor(QColor(color))
            lbl.setPos(x, y)
            lbl.setZValue(-5)

        add_zone_label(80, 130, "🏨 Sandy Beach Main Resort & Room Blocks (1100 - 8000)", "#475569")
        add_zone_label(80, 710, "🌊 Beachfront Area, Promenades & Seaside Amenities", "#0284C7")
        add_zone_label(865, 130, "🏖️ Sandy Villas & Pool Suites (Blocks 100 - 800)", "#7C3AED")

        # 2. Render Nodes 1 to 44
        for item in self.nodes_data:
            n_id = int(item.get("id", 0))
            if n_id in NODE_COORDINATES:
                coords = NODE_COORDINATES[n_id]
                node_item = ResortNodeItem(item, coords, parent_viewer=self)
                node_item.setZValue(10)
                self.scene.addItem(node_item)
                self.node_items[n_id] = node_item

        # Initial view adjustment
        self._fit_to_view()

    def set_status(self, text: str):
        self.lbl_status.setText(text)

    def open_node_inspector(self, node_data: Dict[str, Any]):
        dlg = NodeInspectorDialog(node_data, parent=self)
        dlg.exec()

    def _apply_filter(self, filter_text: str):
        for n_id, item in self.node_items.items():
            if filter_text.startswith("All"):
                item.setVisible(True)
            elif filter_text.startswith("Rooms"):
                item.setVisible("rooms" in item.category.lower() or item.node_name.startswith("BLOCK"))
            elif filter_text.startswith("Facilities"):
                item.setVisible("rooms" not in item.category.lower() and not item.node_name.startswith("BLOCK"))
            elif filter_text.startswith("Pool Suites"):
                item.setVisible(33 <= n_id <= 40)

    def _search_nodes(self, query: str):
        query = query.strip().lower()
        if not query:
            for item in self.node_items.values():
                item.is_highlighted = False
                item.update()
            return

        for n_id, item in self.node_items.items():
            match = query in str(n_id) or query in item.node_name.lower() or query in item.category.lower()
            item.is_highlighted = match
            item.update()

    def _fit_to_view(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _reset_view(self):
        self.view.resetTransform()
        self._fit_to_view()


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    w = PlotGraphWindow()
    w.show()
    sys.exit(app.exec())
