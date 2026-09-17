"""
Plot Viewer Module: Interactive Resort Node Graph & Node Popup Inspector
=======================================================================
Renders the Sandy Beach resort map purely as a graph of connected nodes.

Each entity from PLOT/HotelDataSet.json is a circular node placed at its real
position on the printed Sandy Beach map (see REAL_MAP_COORDINATES). Nodes are linked by a walkway network
that is recomputed whenever the filter changes, so the visible set is always
one connected graph (minimum spanning tree + short proximity links).

Clicking a node opens a small popup window next to the cursor containing that
node's information. No search bar; a single filter with three modes:
    "Rooms Only" (default) | "Facilities Only" | "All Facilities"
"""

import sys
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialog, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsPathItem, QComboBox, QFrame,
    QScrollArea, QTextEdit, QApplication, QSizePolicy, QLineEdit
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QPen, QFont, QPainter, QRadialGradient,
    QPainterPath, QCursor, QFontMetrics
)

# --- Project imports (kept optional so the module can also run standalone) ---
try:
    from MODULES.data_manager import BASE_DIR, PLOT_DIR, HOTEL_DATASET_PATH
except Exception:  # pragma: no cover - fallback for isolated execution
    try:
        from data_manager import BASE_DIR, PLOT_DIR, HOTEL_DATASET_PATH
    except Exception:
        BASE_DIR = Path(__file__).resolve().parent.parent
        PLOT_DIR = BASE_DIR / "PLOT"
        HOTEL_DATASET_PATH = PLOT_DIR / "HotelDataSet.json"


# =============================================================================
# Spatial Layout & Coordinates Configuration
# =============================================================================

# Node centres in scene units, derived directly from the printed resort map:
# red markers were detected in the brochure scan, identified against the four
# section close-ups (sub-pixel agreement where the sections overlap), and scaled
# by 2.0 with a light de-crowding pass so no two nodes sit closer than 64 units
# (largest correction: 9 units, i.e. under 5px on the original scan).
REAL_MAP_COORDINATES: Dict[int, Tuple[int, int]] = {
    # --- West: beachfront, pools and blocks 4000-8000 ---
    29: (  60, 343),   # Beach Area
    43: ( 288,  60),   # Mare Adults Only Pool Bar
    28: ( 205, 147),   # Ammos Mediterranean Restaurant
    26: ( 292, 197),   # Amphitheatre
    27: ( 220, 212),   # Kyma Beach Bar
    31: ( 261, 260),   # Gelateria / Shopping Center
    25: ( 329, 255),   # Navio Pool Bar
    12: ( 309, 419),   # Block 4000
    13: ( 305, 537),   # Block 5000
    14: ( 207, 635),   # Block 6000
    15: ( 472, 155),   # Block 7000
    23: ( 533, 368),   # Elia Main Restaurant
    24: ( 503, 567),   # Game Center / Gym
    11: ( 521, 432),   # Block 3000
    10: ( 643, 459),   # Block 2000
    22: ( 691, 270),   # Conference Room / Doctor's Office
    16: ( 700, 205),   # Block 8000

    # --- Centre: main pool, blocks 1100-1900 ---
    4: ( 842, 296),   # Block 1400
    5: ( 879, 171),   # Block 1500
    20: ( 880, 391),   # Snack Corner
    21: ( 912, 336),   # Waterslides / Playground
    3: ( 920, 483),   # Block 1300
    19: ( 993, 451),   # Aqua Pool Bar / Towels Kiosk
    6: (1031, 225),   # Block 1600
    18: (1093, 428),   # Shopping Center / Hairdresser
    7: (1106, 181),   # Block 1700
    2: (1106, 600),   # Block 1200
    32: (1163, 375),   # Aperitivo Bar
    8: (1192, 211),   # Block 1800
    17: (1197, 322),   # Reception / Muses Lobby Bar / Il Gusto
    1: (1204, 486),   # Block 1100

    # --- East: sports and the road to the villas ---
    9: (1311, 192),   # Block 1900
    30: (1382, 284),   # Basketball & Five-a-side Football
    42: (1439, 422),   # Tennis Court

    # --- Far east: Sandy Villas compound (unnumbered on the brochure;
    #     placed on the eight structures detected inside the compound) ---
    41: (1513, 327),   # Unlisted
    39: (1541, 195),   # Block 700
    40: (1571, 303),   # Block 800
    38: (1586, 241),   # Block 600
    36: (1642, 210),   # Block 400
    37: (1659, 271),   # Block 500
    35: (1727, 227),   # Block 300
    34: (1737, 158),   # Block 200
    33: (1801, 190),   # Block 100
    44: (1874,  90),   # Ermis Gyro Greek Restaurant
}

# Derived node spatial mapping with width/height attributes (backwards compatibility)
NODE_COORDINATES: Dict[int, Dict[str, Any]] = {
    _nid: {"x": _x, "y": _y, "w": 70, "h": 36}
    for _nid, (_x, _y) in REAL_MAP_COORDINATES.items()
}

# The printed map is a wide panorama (roughly 3:1), so a true-to-map graph leaves
# empty canvas above and below. Raise this to trade geometric accuracy for a fuller
# canvas: 1.0 keeps the real proportions, ~1.4 fills a typical 16:9 window.
VERTICAL_STRETCH = 1.0

NODE_RADIUS = 20
LABEL_WIDTH = 100
LABEL_HEIGHT = 30
PROXIMITY_LINK = 115.0    # extra walkway links shorter than this are drawn
MAX_DEGREE = 4            # cap on extra links per node

FILTER_ROOMS = "Rooms Only"
FILTER_FACILITIES = "Facilities Only"
FILTER_ALL = "All Facilities"


def get_node_style(category: str, node_id: int) -> Dict[str, Any]:
    """Colour styling and grouping metadata for a node."""
    cat_lower = (category or "").lower()
    name_hint = cat_lower

    if 33 <= node_id <= 40:
        return {
            "bg_gradient": ("#8B5CF6", "#5B21B6"),
            "border": "#C4B5FD",
            "text": "#FFFFFF",
            "badge": "POOL SUITES",
            "badge_color": "#DDD6FE",
            "type_group": "Rooms",
        }
    if "rooms" in name_hint:
        return {
            "bg_gradient": ("#3B82F6", "#1D4ED8"),
            "border": "#93C5FD",
            "text": "#FFFFFF",
            "badge": "ROOMS",
            "badge_color": "#BFDBFE",
            "type_group": "Rooms",
        }
    if "restaurant" in name_hint or "food" in name_hint or "dining" in name_hint:
        return {
            "bg_gradient": ("#EF4444", "#991B1B"),
            "border": "#FCA5A5",
            "text": "#FFFFFF",
            "badge": "DINING",
            "badge_color": "#FECACA",
            "type_group": "Facilities",
        }
    if "bar" in name_hint:
        return {
            "bg_gradient": ("#F59E0B", "#B45309"),
            "border": "#FCD34D",
            "text": "#FFFFFF",
            "badge": "BAR",
            "badge_color": "#FEF3C7",
            "type_group": "Facilities",
        }
    if "recreation" in name_hint or "entertainment" in name_hint or "sport" in name_hint:
        return {
            "bg_gradient": ("#10B981", "#047857"),
            "border": "#6EE7B7",
            "text": "#FFFFFF",
            "badge": "RECREATION",
            "badge_color": "#A7F3D0",
            "type_group": "Facilities",
        }
    if node_id == 41:
        return {
            "bg_gradient": ("#9CA3AF", "#4B5563"),
            "border": "#D1D5DB",
            "text": "#FFFFFF",
            "badge": "UNLISTED",
            "badge_color": "#E5E7EB",
            "type_group": "Other",
        }
    return {
        "bg_gradient": ("#9F1239", "#5A0016"),
        "border": "#FDA4AF",
        "text": "#FFFFFF",
        "badge": "FACILITY",
        "badge_color": "#FFE4E6",
        "type_group": "Facilities",
    }


# =============================================================================
# Interactive circular node
# =============================================================================

class ResortNodeItem(QGraphicsItem):
    """Circular graph node with hover glow, caption, and click-to-inspect."""

    def __init__(self, node_data: Dict[str, Any], pos: Any = (0, 0), parent_viewer=None, **kwargs):
        super().__init__()
        self.node_data = node_data or {}

        # Flexible coordinate unpack to support (x, y) tuple, separate x, y args, QPointF, or dict
        if isinstance(pos, (int, float)) and isinstance(parent_viewer, (int, float)):
            x_coord, y_coord = float(pos), float(parent_viewer)
            self.parent_viewer = kwargs.get("parent_viewer", None)
        elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
            x_coord, y_coord = float(pos[0]), float(pos[1])
            self.parent_viewer = parent_viewer
        elif isinstance(pos, dict):
            x_coord, y_coord = float(pos.get("x", 0)), float(pos.get("y", 0))
            self.parent_viewer = parent_viewer
        elif isinstance(pos, QPointF):
            x_coord, y_coord = pos.x(), pos.y()
            self.parent_viewer = parent_viewer
        else:
            x_coord, y_coord = 0.0, 0.0
            self.parent_viewer = parent_viewer

        self.coords = {"x": x_coord, "y": y_coord}

        raw_id = self.node_data.get("id", 0)
        self.node_id = int(raw_id) if str(raw_id).strip().isdigit() else 0
        self.node_name = str(self.node_data.get("name") or f"Node {self.node_id}")
        self.category = str(self.node_data.get("category") or "Facilities")

        self.style = get_node_style(self.category, self.node_id)
        self.group = self.style["type_group"]
        if self.group == "Facilities" and self.node_name.upper().startswith("BLOCK"):
            self.group = "Rooms"

        self.is_hovered = False
        self.is_selected_node = False
        self.is_highlighted = False
        self.label_above = False   # flipped by the viewer when captions collide
        self.show_caption = True   # cleared when zoomed out (see PlotGraphWindow._update_lod)

        self.setPos(QPointF(x_coord, y_coord))
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setZValue(10)

        self.occ_pct: Optional[float] = None
        self._load_occupancy_if_available()
        self._caption = self._build_caption()

    # ---------------------------------------------------------------- helpers
    def _load_occupancy_if_available(self):
        slug = re.sub(r"[^\w\d]+", "_", self.node_name.strip()).strip("_")
        try:
            block_json = Path(PLOT_DIR) / slug / f"{slug}.json"
            if block_json.exists():
                with open(block_json, "r", encoding="utf-8") as f:
                    metrics = json.load(f).get("occupancy_metrics", {})
                if "occupancy_percentage" in metrics:
                    self.occ_pct = float(metrics["occupancy_percentage"])
        except Exception:
            self.occ_pct = None

    MAX_CAPTION = 17

    def _build_caption(self) -> str:
        """Short caption for the canvas; the popup and status bar keep the full name."""
        name = self.node_name.strip()
        primary = re.split(r"\s*[/|]\s*", name)[0].strip() or name
        if len(primary) <= self.MAX_CAPTION:
            return primary
        cut = primary[:self.MAX_CAPTION]
        if " " in cut:
            cut = cut[:cut.rfind(" ")]
        return cut.rstrip(" ,&-") + "…"

    # ------------------------------------------------------------- qt drawing
    def boundingRect(self) -> QRectF:
        half_w = max(LABEL_WIDTH / 2, NODE_RADIUS + 10)
        half_h = NODE_RADIUS + 6 + LABEL_HEIGHT + 4
        return QRectF(-half_w, -half_h, half_w * 2, half_h * 2)

    def label_rect(self) -> QRectF:
        """Caption rectangle in item coordinates (above or below the disc)."""
        if self.label_above:
            return QRectF(-LABEL_WIDTH / 2, -NODE_RADIUS - 4 - LABEL_HEIGHT,
                          LABEL_WIDTH, LABEL_HEIGHT)
        return QRectF(-LABEL_WIDTH / 2, NODE_RADIUS + 4, LABEL_WIDTH, LABEL_HEIGHT)

    def label_rect_scene(self, above: Optional[bool] = None) -> QRectF:
        """Approximate caption footprint in scene coordinates, for collision tests."""
        flip = self.label_above if above is None else above
        top = (-NODE_RADIUS - 4 - 20) if flip else (NODE_RADIUS + 4)
        rect = QRectF(-LABEL_WIDTH / 2, top, LABEL_WIDTH, 20)
        return rect.translated(self.pos())

    def shape(self) -> QPainterPath:
        # Only the circle is clickable, so captions never steal clicks
        p = QPainterPath()
        p.addEllipse(QPointF(0, 0), NODE_RADIUS + 3, NODE_RADIUS + 3)
        return p

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = NODE_RADIUS

        # Selection / hover halo
        if self.is_selected_node or getattr(self, "is_highlighted", False):
            painter.setPen(QPen(QColor("#F59E0B"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), r + 6, r + 6)
        elif self.is_hovered:
            painter.setPen(QPen(QColor(self.style["border"]), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), r + 5, r + 5)

        # Node disc
        c1 = QColor(self.style["bg_gradient"][0])
        c2 = QColor(self.style["bg_gradient"][1])
        if self.is_hovered:
            c1, c2 = c1.lighter(115), c2.lighter(115)
        grad = QRadialGradient(QPointF(-r * 0.3, -r * 0.4), r * 1.8)
        grad.setColorAt(0.0, c1.lighter(118))
        grad.setColorAt(1.0, c2)

        painter.setPen(QPen(QColor(self.style["border"]), 1.6))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(0, 0), r, r)

        # Node id
        painter.setPen(QColor(self.style["text"]))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(-r, -r, r * 2, r * 2),
                         Qt.AlignmentFlag.AlignCenter, str(self.node_id))

        # Occupancy pill, always on the side opposite the caption
        if self.occ_pct is not None:
            pill = QRectF(-21, (r + 3) if self.label_above else (-r - 17), 42, 14)
            occ_color = "#059669" if self.occ_pct < 80 else ("#D97706" if self.occ_pct < 95 else "#DC2626")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 230))
            painter.drawRoundedRect(pill, 6, 6)
            painter.setPen(QColor(occ_color))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, f"{self.occ_pct:.0f}%")

        # Caption (hidden when zoomed out, always drawn for the focused node)
        if not (self.show_caption or self.is_hovered or self.is_selected_node):
            return
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        label_rect = self.label_rect()
        align = int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap |
                    (Qt.AlignmentFlag.AlignBottom if self.label_above else Qt.AlignmentFlag.AlignTop))
        fm = QFontMetrics(painter.font())
        text_rect = fm.boundingRect(label_rect.toRect(), align, self._caption)
        plate = QRectF(text_rect).adjusted(-5, -2, 5, 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 215))
        painter.drawRoundedRect(plate, 5, 5)

        painter.setPen(QColor("#111827") if self.is_hovered else QColor("#1F2937"))
        painter.drawText(label_rect, align, self._caption)

    # -------------------------------------------------------------- behaviour
    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.setZValue(20)
        self.update()
        if self.parent_viewer:
            occ = f"  •  Occupancy {self.occ_pct:.0f}%" if self.occ_pct is not None else ""
            self.parent_viewer.set_status(f"#{self.node_id}  {self.node_name}  [{self.category}]{occ}")
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.setZValue(10)
        self.update()
        if self.parent_viewer:
            self.parent_viewer.reset_status()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            if self.parent_viewer:
                try:
                    self.parent_viewer.open_node_inspector(
                        self.node_data, event.screenPos(), self.node_id
                    )
                except Exception as err:  # never let a popup failure kill the canvas
                    print(f"[ResortNodeItem] popup error: {err}")
                    self.parent_viewer.set_status(f"#{self.node_id}  {self.node_name}")
            return
        super().mousePressEvent(event)


# =============================================================================
# Small pop-out node information window
# =============================================================================

class NodePopup(QDialog):
    """Compact popup showing a single node's information next to the cursor."""

    WIDTH = 370
    MAX_HEIGHT = 460

    closed = pyqtSignal()

    def __init__(self, node_data: Dict[str, Any], parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.node_data = node_data or {}

        raw_id = self.node_data.get("id", "N/A")
        self.node_id = str(raw_id)
        self.node_name = str(self.node_data.get("name") or "Unknown Node")
        self.category = str(self.node_data.get("category") or "General")
        self.style = get_node_style(self.category, int(raw_id) if str(raw_id).isdigit() else 0)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedWidth(self.WIDTH)
        self.setStyleSheet("""
            QDialog { background: #FFFFFF; border: 1px solid #D8DEE9; border-radius: 10px; }
            QLabel  { color: #1F2937; font-family: 'Segoe UI', Arial, sans-serif; }
            QScrollArea { border: none; background: transparent; }
        """)
        self._build_ui()

    # ------------------------------------------------------------------ build
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(12, 10, 12, 10)
        self.body_layout.setSpacing(8)

        self._fill_body()
        self.body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        # Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(12, 6, 12, 10)
        btn_json = QPushButton("{ } Raw JSON")
        btn_json.setStyleSheet(
            "QPushButton { background:#EEF2F7; color:#334155; border:1px solid #CBD5E1;"
            "border-radius:5px; padding:5px 10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#E2E8F0; }")
        btn_json.clicked.connect(self._show_raw_json)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(
            "QPushButton { background:#800020; color:white; border:none; border-radius:5px;"
            "padding:5px 16px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#9F1239; }")
        btn_close.clicked.connect(self.close)

        footer.addWidget(btn_json)
        footer.addStretch()
        footer.addWidget(btn_close)
        root.addLayout(footer)

        self.adjustSize()
        self.setFixedHeight(min(self.sizeHint().height(), self.MAX_HEIGHT))

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 {self.style['bg_gradient'][0]},
                            stop:1 {self.style['bg_gradient'][1]});
                border-top-left-radius: 9px; border-top-right-radius: 9px;
            }}
        """)
        lay = QVBoxLayout(header)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(6)
        lbl_id = QLabel(f"#{self.node_id}")
        lbl_id.setStyleSheet("color:#FFFFFF; background:rgba(0,0,0,0.28); font-size:11px;"
                             "font-weight:bold; padding:2px 7px; border-radius:4px;")
        lbl_badge = QLabel(self.style["badge"])
        lbl_badge.setStyleSheet(f"color:{self.style['badge_color']}; font-size:10px; font-weight:bold;")
        top.addWidget(lbl_id)
        top.addWidget(lbl_badge)
        top.addStretch()

        lbl_name = QLabel(self.node_name)
        lbl_name.setWordWrap(True)
        lbl_name.setStyleSheet("color:#FFFFFF; font-size:14px; font-weight:bold;")

        lbl_cat = QLabel(self.category)
        lbl_cat.setStyleSheet("color:rgba(255,255,255,0.85); font-size:10px;")

        lay.addLayout(top)
        lay.addWidget(lbl_name)
        lay.addWidget(lbl_cat)
        return header

    def _fill_body(self):
        d = self.node_data

        desc = d.get("description")
        if desc:
            self.body_layout.addWidget(self._card("Description", self._as_text(desc), "#800020", "#FFF5F7"))

        rd = d.get("room_details")
        if isinstance(rd, dict) and rd:
            self.body_layout.addWidget(self._room_card(rd))

        hours = d.get("operating_hours")
        if hours:
            self.body_layout.addWidget(self._card("Operating Hours", self._as_lines(hours), "#92400E", "#FFFBEB"))

        dist = d.get("distances")
        if dist:
            self.body_layout.addWidget(self._card("Distances & Adjacency", self._as_lines(dist), "#1E40AF", "#EFF6FF"))

        extra = d.get("extra_info")
        if extra:
            self.body_layout.addWidget(self._card("Notes & Rules", self._as_lines(extra), "#166534", "#F0FDF4"))

        upgrades = d.get("upgrade_rates_2026")
        if isinstance(upgrades, dict) and upgrades:
            seasons = upgrades.get("seasons", {})
            txt = ""
            if isinstance(seasons, dict):
                if seasons.get("low_mid"):
                    txt += f"Low / Mid season: {seasons['low_mid']}\n"
                if seasons.get("high"):
                    txt += f"High season: {seasons['high']}\n"
            txt += "Full rate matrix available in Raw JSON."
            self.body_layout.addWidget(self._card("Upgrade Rates 2026", txt.strip(), "#5B21B6", "#FAF5FF"))

        # Anything else in the record that has not been rendered above
        known = {"id", "name", "category", "description", "room_details",
                 "operating_hours", "distances", "extra_info", "upgrade_rates_2026"}
        leftovers = {k: v for k, v in d.items() if k not in known and v not in (None, "", [], {})}
        if leftovers:
            self.body_layout.addWidget(
                self._card("Additional Attributes", self._as_lines(leftovers), "#334155", "#F8FAFC"))

        if self.body_layout.count() == 0:
            self.body_layout.addWidget(self._card("Information", "No further details recorded for this node.",
                                                  "#334155", "#F8FAFC"))

    # ----------------------------------------------------------------- pieces
    def _card(self, title: str, text: str, accent: str, bg: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background:{bg}; border:1px solid #E5E7EB; border-radius:7px; }}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)

        lbl_t = QLabel(title.upper())
        lbl_t.setStyleSheet(f"color:{accent}; font-size:10px; font-weight:bold; letter-spacing:0.5px;")
        lbl_v = QLabel(text)
        lbl_v.setWordWrap(True)
        lbl_v.setTextFormat(Qt.TextFormat.PlainText)
        lbl_v.setStyleSheet("color:#374151; font-size:11px;")
        lbl_v.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        lay.addWidget(lbl_t)
        lay.addWidget(lbl_v)
        return frame

    def _room_card(self, rd: Dict[str, Any]) -> QFrame:
        lines: List[str] = []
        total = rd.get("total_rooms", self.node_data.get("total_rooms"))
        if total:
            lines.append(f"Total rooms: {total}")

        views = rd.get("views", self.node_data.get("views"))
        if views:
            lines.append(f"Views: {self._as_text(views)}")

        features = rd.get("features", self.node_data.get("features"))
        if features:
            lines.append(f"Features: {self._as_text(features)}")

        types = rd.get("types")
        if isinstance(types, dict) and types:
            lines.append("Room types:")
            lines += [f"   • {k}: {v}" for k, v in types.items()]
        elif types:
            lines.append(f"Room types: {self._as_text(types)}")

        floors = rd.get("floors")
        if isinstance(floors, dict) and floors:
            lines.append("Floors:")
            for fname, ranges in floors.items():
                rstr = ", ".join(str(r) for r in ranges) if isinstance(ranges, list) else str(ranges)
                lines.append(f"   • {fname}: {rstr}")
        elif floors:
            lines.append(f"Floors: {self._as_text(floors)}")

        return self._card("Room Block Breakdown", "\n".join(lines) or "No breakdown recorded.",
                          "#1D4ED8", "#EFF6FF")

    @staticmethod
    def _as_text(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            return ", ".join(str(v) for v in value)
        if isinstance(value, dict):
            return "; ".join(f"{k}: {v}" for k, v in value.items())
        return str(value)

    @classmethod
    def _as_lines(cls, value: Any) -> str:
        if isinstance(value, dict):
            return "\n".join(f"• {k}: {cls._as_text(v)}" for k, v in value.items())
        if isinstance(value, (list, tuple)):
            return "\n".join(f"• {cls._as_text(v)}" for v in value)
        return str(value)

    # ------------------------------------------------------------- raw viewer
    def _show_raw_json(self):
        dlg = QDialog(self.parent())
        dlg.setWindowTitle(f"Raw JSON — #{self.node_id} {self.node_name}")
        dlg.resize(620, 520)
        lay = QVBoxLayout(dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFont(QFont("Consolas", 10))
        txt.setText(json.dumps(self.node_data, indent=4, ensure_ascii=False))
        txt.setStyleSheet("background:#1E1E1E; color:#D4D4D4; border-radius:6px; padding:10px;")
        lay.addWidget(txt)
        self.close()
        dlg.exec()

    # ------------------------------------------------------------- placement
    def popup_at(self, global_pos: QPointF):
        """Show the popup near the cursor, clamped to the visible screen."""
        screen = QApplication.screenAt(global_pos.toPoint()) or QApplication.primaryScreen()
        avail = screen.availableGeometry()

        x = int(global_pos.x()) + 16
        y = int(global_pos.y()) + 12
        if x + self.width() > avail.right():
            x = int(global_pos.x()) - self.width() - 16
        if y + self.height() > avail.bottom():
            y = avail.bottom() - self.height() - 8
        x = max(avail.left() + 4, x)
        y = max(avail.top() + 4, y)

        self.move(x, y)
        self.show()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


# Backwards-compatible alias for callers elsewhere in the project
NodeInspectorDialog = NodePopup


# =============================================================================
# Graphics view with pan & zoom
# =============================================================================

class ResortGraphicsView(QGraphicsView):
    """QGraphicsView with wheel zoom, drag pan, and bounded scale."""

    MIN_SCALE = 0.25
    MAX_SCALE = 6.0

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.owner = parent
        self.setRenderHints(QPainter.RenderHint.Antialiasing |
                            QPainter.RenderHint.SmoothPixmapTransform |
                            QPainter.RenderHint.TextAntialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.zoom_factor = 1.15

    def current_scale(self) -> float:
        return self.transform().m11()

    def zoom_by(self, factor: float):
        target = self.current_scale() * factor
        if target < self.MIN_SCALE or target > self.MAX_SCALE:
            return
        self.scale(factor, factor)
        if self.owner is not None:
            self.owner.user_zoomed = True
            self.owner.update_detail_level()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self.zoom_by(self.zoom_factor if delta > 0 else 1.0 / self.zoom_factor)
        event.accept()


# =============================================================================
# Main window
# =============================================================================

class PlotGraphWindow(QMainWindow):
    """Interactive connected-node graph of the Sandy Beach resort map."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resort Node Graph — Sandy Beach")
        self.resize(1280, 850)
        self.setStyleSheet("QMainWindow { background-color: #F8F9FA; }")

        self.nodes_data: List[Dict[str, Any]] = []
        self.node_items: Dict[int, ResortNodeItem] = {}
        self.edge_items: List[QGraphicsPathItem] = []
        self.active_popup: Optional[NodePopup] = None
        self.selected_id: Optional[int] = None
        self.user_zoomed = False

        self._load_dataset()
        self._init_ui()
        self._build_scene()
        self._apply_filter(FILTER_ROOMS)

    # ------------------------------------------------------------------ data
    def _load_dataset(self):
        path = Path(HOTEL_DATASET_PATH)
        if not path.exists():
            print(f"[PlotGraphWindow] Dataset not found: {path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Tolerate {"nodes": [...]} style wrappers
                for key in ("nodes", "entities", "data", "hotel", "records"):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
            self.nodes_data = data if isinstance(data, list) else []
        except Exception as e:
            print(f"[PlotGraphWindow] Error loading dataset: {e}")
            self.nodes_data = []

    # -------------------------------------------------------------------- ui
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        # --- top bar -------------------------------------------------------
        top = QHBoxLayout()
        top.setSpacing(10)

        title = QLabel("RESORT NODE GRAPH")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#800020; letter-spacing:0.5px;")
        top.addWidget(title)
        top.addSpacing(18)

        lbl_filter = QLabel("View:")
        lbl_filter.setStyleSheet("font-weight:bold; color:#334155;")
        self.combo_filter = QComboBox()
        self.combo_filter.addItems([FILTER_ROOMS, FILTER_FACILITIES, FILTER_ALL])
        self.combo_filter.setCurrentText(FILTER_ROOMS)   # default view
        self.combo_filter.setFixedWidth(160)
        self.combo_filter.setStyleSheet(
            "QComboBox { padding:5px 8px; border:1px solid #FFB6C1; border-radius:5px;"
            "background:white; font-weight:bold; color:#800020; }")
        self.combo_filter.currentTextChanged.connect(self._apply_filter)
        top.addWidget(lbl_filter)
        top.addWidget(self.combo_filter)

        top.addStretch()

        btn_style = """
            QPushButton {
                background-color: #FFF0F5; border: 1px solid #FF69B4; border-radius: 5px;
                padding: 5px 12px; font-weight: bold; color: #800020;
            }
            QPushButton:hover { background-color: #FF69B4; color: white; }
        """
        for text, slot in (
            ("Zoom In", lambda: self.view.zoom_by(1.2)),
            ("Zoom Out", lambda: self.view.zoom_by(1 / 1.2)),
            ("Fit View", self._fit_to_view),
            ("Reset", self._reset_view),
        ):
            b = QPushButton(text)
            b.setStyleSheet(btn_style)
            b.clicked.connect(slot)
            top.addWidget(b)

        layout.addLayout(top)

        # --- legend --------------------------------------------------------
        legend = QHBoxLayout()
        legend.setSpacing(14)
        for label, color in (("Rooms", "#3B82F6"), ("Pool Suites", "#8B5CF6"),
                             ("Dining", "#EF4444"), ("Bars", "#F59E0B"),
                             ("Recreation", "#10B981"), ("Services", "#9F1239")):
            chip = QLabel(f"●  {label}")
            chip.setStyleSheet(f"color:{color}; font-size:11px; font-weight:bold;")
            legend.addWidget(chip)
        legend.addStretch()
        layout.addLayout(legend)

        # --- canvas --------------------------------------------------------
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QColor("#FAFAF8"))
        self.view = ResortGraphicsView(self.scene, self)
        self.view.setStyleSheet("border:1px solid #FFB6C1; border-radius:6px; background:#FAFAF8;")
        layout.addWidget(self.view, stretch=1)

        # --- status --------------------------------------------------------
        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet("color:#64748B; font-size:12px; padding:2px 6px;")
        layout.addWidget(self.lbl_status)
        self.reset_status()

        # Backwards-compatible headless search bar (not rendered in UI per design, enables programmatic test/script searches)
        self.txt_search = QLineEdit()
        self.txt_search.textChanged.connect(self._search_nodes)

        QTimer.singleShot(60, self._fit_to_view)

    # ----------------------------------------------------------------- scene
    def _build_scene(self):
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()

        placed = set(REAL_MAP_COORDINATES)
        fallback_slot = 0

        for record in self.nodes_data:
            raw_id = record.get("id", "")
            n_id = int(raw_id) if str(raw_id).strip().isdigit() else None
            if n_id is None:
                continue
            if n_id in REAL_MAP_COORDINATES:
                mx, my = REAL_MAP_COORDINATES[n_id]
                pos = (mx, my * VERTICAL_STRETCH)
            else:
                # Unmapped entity: park it on a tidy row below the map
                pos = (90 + (fallback_slot % 8) * 105, 540 + (fallback_slot // 8) * 80)
                fallback_slot += 1
                placed.add(n_id)
            item = ResortNodeItem(record, pos, parent_viewer=self)
            self.scene.addItem(item)
            self.node_items[n_id] = item

        if not self.node_items:
            msg = self.scene.addText("No nodes loaded — check PLOT/HotelDataSet.json",
                                     QFont("Segoe UI", 12, QFont.Weight.Bold))
            msg.setDefaultTextColor(QColor("#9CA3AF"))
            msg.setPos(40, 40)

        self._update_scene_rect()

    def _update_scene_rect(self):
        rect = self.scene.itemsBoundingRect()
        if rect.isNull():
            rect = QRectF(0, 0, 880, 560)
        self.scene.setSceneRect(rect.adjusted(-60, -60, 60, 60))

    # ----------------------------------------------------------------- edges
    def _visible_nodes(self) -> List[Tuple[int, QPointF]]:
        return [(nid, it.pos()) for nid, it in self.node_items.items() if it.isVisible()]

    @staticmethod
    def _dist(a: QPointF, b: QPointF) -> float:
        return math.hypot(a.x() - b.x(), a.y() - b.y())

    def _compute_edges(self, nodes: List[Tuple[int, QPointF]]) -> List[Tuple[int, int]]:
        """Minimum spanning tree (guarantees one connected graph) + short links."""
        n = len(nodes)
        if n < 2:
            return []

        pts = [p for _, p in nodes]
        in_tree = [False] * n
        best = [float("inf")] * n
        parent = [-1] * n
        best[0] = 0.0
        edges: List[Tuple[int, int]] = []

        for _ in range(n):
            u, u_cost = -1, float("inf")
            for i in range(n):
                if not in_tree[i] and best[i] < u_cost:
                    u, u_cost = i, best[i]
            if u == -1:
                break
            in_tree[u] = True
            if parent[u] >= 0:
                edges.append((parent[u], u))
            for v in range(n):
                if not in_tree[v]:
                    d = self._dist(pts[u], pts[v])
                    if d < best[v]:
                        best[v] = d
                        parent[v] = u

        degree = [0] * n
        seen = set()
        for a, b in edges:
            degree[a] += 1
            degree[b] += 1
            seen.add((min(a, b), max(a, b)))

        candidates = []
        for i in range(n):
            for j in range(i + 1, n):
                d = self._dist(pts[i], pts[j])
                if d <= PROXIMITY_LINK:
                    candidates.append((d, i, j))
        candidates.sort()

        for _, i, j in candidates:
            if (i, j) in seen:
                continue
            if degree[i] >= MAX_DEGREE or degree[j] >= MAX_DEGREE:
                continue
            edges.append((i, j))
            seen.add((i, j))
            degree[i] += 1
            degree[j] += 1

        return [(nodes[a][0], nodes[b][0]) for a, b in edges]

    # ---------------------------------------------------------------- labels
    def _measure_spacing(self):
        """Median nearest-neighbour distance across the visible nodes, in scene units."""
        pts = [p for _, p in self._visible_nodes()]
        if len(pts) < 2:
            self._node_spacing = 200.0
            return
        nearest = []
        for i, a in enumerate(pts):
            nearest.append(min(self._dist(a, b) for j, b in enumerate(pts) if j != i))
        nearest.sort()
        self._node_spacing = nearest[len(nearest) // 2]

    def _resolve_labels(self):
        """Flip a caption above its node when the default position covers a neighbour."""
        visible = [it for it in self.node_items.values() if it.isVisible()]
        discs = [(it, QRectF(it.pos().x() - NODE_RADIUS - 2, it.pos().y() - NODE_RADIUS - 2,
                             (NODE_RADIUS + 2) * 2, (NODE_RADIUS + 2) * 2)) for it in visible]

        def hits(owner: ResortNodeItem, rect: QRectF) -> bool:
            return any(other is not owner and rect.intersects(disc) for other, disc in discs)

        for item in visible:
            below_clear = not hits(item, item.label_rect_scene(False))
            if below_clear:
                new_state = False
            else:
                new_state = not hits(item, item.label_rect_scene(True))
            if new_state != item.label_above:
                item.label_above = new_state
                item.update()

    def _rebuild_edges(self):
        for e in self.edge_items:
            if e.scene() is self.scene:
                self.scene.removeItem(e)
        self.edge_items.clear()

        nodes = self._visible_nodes()
        if len(nodes) < 2:
            return

        pos_by_id = dict(nodes)
        casing = QPen(QColor(226, 232, 240), 6.0)
        casing.setCapStyle(Qt.PenCapStyle.RoundCap)
        line = QPen(QColor(148, 163, 184, 200), 1.8)
        line.setCapStyle(Qt.PenCapStyle.RoundCap)

        for a, b in self._compute_edges(nodes):
            pa, pb = pos_by_id[a], pos_by_id[b]
            path = QPainterPath(pa)
            path.lineTo(pb)

            under = QGraphicsPathItem(path)
            under.setPen(casing)
            under.setZValue(-3)
            self.scene.addItem(under)
            self.edge_items.append(under)

            over = QGraphicsPathItem(path)
            over.setPen(line)
            over.setZValue(-2)
            self.scene.addItem(over)
            self.edge_items.append(over)

    # ---------------------------------------------------------------- filter
    def _apply_filter(self, filter_text: str):
        mode = filter_text or FILTER_ROOMS
        shown = 0
        for item in self.node_items.values():
            if mode == FILTER_ALL:
                visible = True
            elif mode == FILTER_ROOMS:
                visible = item.group == "Rooms"
            elif mode == FILTER_FACILITIES:
                visible = item.group == "Facilities"
            else:
                visible = True
            item.setVisible(visible)
            shown += int(visible)

        self._close_popup()
        self._measure_spacing()
        self._resolve_labels()
        self._rebuild_edges()
        self._update_scene_rect()
        if not self.user_zoomed:
            self._fit_to_view()

        hint = ("click a node for details, drag to pan, scroll to zoom"
                if getattr(self, "_captions_shown", False) else
                "hover for a name, zoom in for labels, click a node for details")
        self._base_status = f"{mode}  •  {shown} nodes shown  •  {hint}"
        self.reset_status()

    # ----------------------------------------------------------------- popup
    def _clear_selection(self):
        if self.selected_id is not None:
            item = self.node_items.get(self.selected_id)
            if item is not None:
                item.is_selected_node = False
                item.update()
            self.selected_id = None

    def _close_popup(self):
        popup, self.active_popup = self.active_popup, None
        if popup is not None:
            try:
                popup.close()
            except RuntimeError:
                pass  # C++ object already deleted
        self._clear_selection()

    def _on_popup_closed(self, popup: "NodePopup"):
        # Only react if this is still the popup on screen; a stale close
        # signal from a previous popup must not clear the current one.
        if self.active_popup is popup:
            self.active_popup = None
            self._clear_selection()

    def open_node_inspector(self, node_data: Dict[str, Any],
                            global_pos: Optional[QPointF] = None,
                            node_id: Optional[int] = None):
        self._close_popup()

        popup = NodePopup(node_data, parent=self)
        if global_pos is None:
            global_pos = QPointF(QCursor.pos())
        popup.popup_at(global_pos)

        self.active_popup = popup
        if node_id is not None and node_id in self.node_items:
            self.selected_id = node_id
            self.node_items[node_id].is_selected_node = True
            self.node_items[node_id].update()
        popup.closed.connect(lambda p=popup: self._on_popup_closed(p))

    def _on_node_clicked(self, node_data: Dict[str, Any]):
        """Backwards-compatible handler for programmatic node click invocation."""
        raw_id = node_data.get("id", "")
        n_id = int(raw_id) if str(raw_id).strip().isdigit() else None
        name = str(node_data.get("name") or f"Node {raw_id}")
        self.set_status(f"#{raw_id}  {name}")
        self.open_node_inspector(node_data, node_id=n_id)

    def _search_nodes(self, query: str):
        """Backwards-compatible search filter method for testing / programmatic highlighting."""
        q = (query or "").strip().lower()
        for nid, item in self.node_items.items():
            if not q:
                item.is_highlighted = False
            else:
                matched = (q in str(nid)) or (q in item.node_name.lower()) or (q in item.category.lower())
                item.is_highlighted = matched
            item.update()

    # ---------------------------------------------------------------- status
    def set_status(self, text: str):
        self.lbl_status.setText(text)

    def reset_status(self):
        self.lbl_status.setText(getattr(self, "_base_status", "Ready."))

    # ------------------------------------------------------------------ view
    CAPTION_PIXELS = 54      # on-screen spacing needed before captions are readable

    def update_detail_level(self):
        """Show captions once the visible nodes are far enough apart on screen."""
        spacing = getattr(self, "_node_spacing", 90.0)
        show = self.view.current_scale() * spacing >= self.CAPTION_PIXELS
        if show == getattr(self, "_captions_shown", None):
            return
        self._captions_shown = show
        for item in self.node_items.values():
            item.show_caption = show
            item.update()
        self.reset_status()

    def _fit_to_view(self):
        rect = self.scene.itemsBoundingRect()
        if rect.isNull():
            rect = self.scene.sceneRect()
        self.view.fitInView(rect.adjusted(-30, -30, 30, 30),
                            Qt.AspectRatioMode.KeepAspectRatio)
        self.user_zoomed = False
        self.update_detail_level()

    def _reset_view(self):
        self.view.resetTransform()
        self._fit_to_view()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(60, self._fit_to_view)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.user_zoomed:
            QTimer.singleShot(0, self._fit_to_view)

    def closeEvent(self, event):
        self._close_popup()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    w = PlotGraphWindow()
    w.show()
    sys.exit(app.exec())
