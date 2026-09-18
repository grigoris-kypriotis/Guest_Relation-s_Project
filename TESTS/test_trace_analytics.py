"""
Unit Tests for Trace List Ingestion, Room-Matching Engine & Visual Analytics Suite
==================================================================================
Tests:
  1. Trace file scanning and detection in DATABASE/
  2. Parsing and schema normalization of trace files (CSV / Excel)
  3. Deterministic keyword tagging (Room Change Requests & Dietary Alerts)
  4. ROOMS/<room_number>.json generation and idempotency verification
  5. Computation of all 10 Visual Analytics metrics
  6. Matplotlib TraceAnalyticsPlotEngine rendering without errors
  7. StatsWidget vertical scroll architecture & UI controls integration
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import date

# Ensure project root is on sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from MODULES.data_manager import InHouseDataManager, DATABASE_DIR
from MODULES.trace_analytics import (
    scan_for_trace_files, parse_trace_file, extract_rcr_tags,
    extract_allergy_tokens, parse_room_block_floor, generate_trace_id,
    generate_room_json_mappings, compute_visual_analytics_data,
    classify_trace, fuse_inhouse_and_traces, compute_repeat_issue_rooms,
    compute_rcr_analytics, compute_clear_trace_analytics,
    compute_normalized_block_defect_rate, compute_departmental_attribution,
    compute_dietary_risk_index, PHYSICAL_DEFECT_TAGS, CLEAR_SERVICE_CATEGORIES,
    ROOM_ISSUE_CATEGORIES, EXCLUDED_ROOM_ISSUE_CATEGORIES, is_room_issue_trace,
    classify_trace_subcategory, compute_rcr_resolution_status, classify_feedback_sentiment,
    LENS_ALL, LENS_ROOM_STAY, LENS_GR_TRACES, LENS_DIETARY, LENS_CATEGORIES,
    PRIMARY_TRACE_CATEGORIES
)
from MODULES.plot_viewer import TraceAnalyticsPlotEngine, ResortGraphicsView
from OPTIONS._shared_widgets import NonScrollableFigureCanvas
from PyQt6.QtCore import Qt
from matplotlib.figure import Figure


class TestTraceAnalyticsEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_trace_")
        self.rooms_dir = os.path.join(self.temp_dir, "ROOMS")
        self.dm = InHouseDataManager()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. File Scanning & Detection
    # -------------------------------------------------------------------------
    def test_scan_for_trace_files(self):
        detected = scan_for_trace_files(DATABASE_DIR)
        self.assertIsInstance(detected, list)
        if detected:
            self.assertTrue(any("traces.csv" in f.lower() for f in detected))

    # -------------------------------------------------------------------------
    # 2. Parsing & Schema Normalization
    # -------------------------------------------------------------------------
    def test_parse_traces_csv_schema(self):
        detected = scan_for_trace_files(DATABASE_DIR)
        if not detected:
            self.skipTest("traces.csv not present in test environment")

        traces = parse_trace_file(detected[0])
        self.assertGreater(len(traces), 0)

        required_keys = [
            "trace_id", "room_number", "guest_name", "arrival",
            "departure", "tour_operator", "room_booked", "room_assigned",
            "category", "notes", "status", "booking_id", "tags"
        ]

        for tr in traces:
            for k in required_keys:
                self.assertIn(k, tr, f"Missing key '{k}' in trace record")

            # Validate date ISO format if present
            if tr["arrival"]:
                self.assertRegex(tr["arrival"], r"^\d{4}-\d{2}-\d{2}$")
            if tr["departure"]:
                self.assertRegex(tr["departure"], r"^\d{4}-\d{2}-\d{2}$")

            # Validate trace_id uniqueness format
            self.assertTrue(tr["trace_id"].startswith("trc_"))

        # Verify Room 7030 specifically
        r7030_traces = [t for t in traces if t["room_number"] == "7030"]
        self.assertGreaterEqual(len(r7030_traces), 1)
        t7030 = r7030_traces[0]
        self.assertEqual(t7030["category"], "Room Change Request")
        self.assertIn("smell", t7030["tags"])

    # -------------------------------------------------------------------------
    # 3. Deterministic Keyword Tagging
    # -------------------------------------------------------------------------
    def test_rcr_keyword_tagging(self):
        cases = [
            ("too loud music from the bar", ["noise"]),
            ("bad smell and drain stink", ["smell"]),
            ("they want a sea view instead of trees", ["view_mismatch"]),
            ("no hot water and clogged shower", ["no_hot_water", "water_plumbing"]),
            ("guests are disabled and need elevator", ["accessibility"]),
            ("connecting room with next door", ["room_merge"]),
            ("everything is normal here", ["unclassified"]),
            ("", ["unclassified"])
        ]
        for note, expected_tags in cases:
            tags = extract_rcr_tags(note)
            for et in expected_tags:
                self.assertIn(et, tags, f"Expected tag '{et}' in tags {tags} for note '{note}'")

    def test_allergy_token_extraction(self):
        cases = [
            ("GLUTEN FREE", ["Gluten"]),
            ("lactose intolerance and dairy free", ["Lactose/Dairy"]),
            ("peanut and nut allergy", ["Nuts/Peanuts"]),
            ("shrimp and all fish", ["Shellfish/Seafood"]),
            ("strictly vegan", ["Vegan"]),
            ("no mushrooms please", ["Mushrooms"]),
            ("egg white allergy", ["Egg"]),
            ("general sensitive diet", ["Other / Unspecified"])
        ]
        for note, expected_tokens in cases:
            tokens = extract_allergy_tokens(note)
            for tok in expected_tokens:
                self.assertIn(tok, tokens, f"Expected token '{tok}' in {tokens} for note '{note}'")

    def test_room_block_floor_parsing(self):
        self.assertEqual(parse_room_block_floor("7030"), ("7", "0"))
        self.assertEqual(parse_room_block_floor("7110"), ("7", "1"))
        self.assertEqual(parse_room_block_floor("6212"), ("6", "2"))
        self.assertEqual(parse_room_block_floor("102"), ("1", "0"))
        self.assertEqual(parse_room_block_floor("invalid"), ("Unknown", "Unknown"))

    # -------------------------------------------------------------------------
    # 4. ROOMS/ Directory Generation & Idempotency
    # -------------------------------------------------------------------------
    def test_room_json_generation_and_idempotency(self):
        mock_traces = [
            {
                "trace_id": "trc_test_001",
                "room_number": "7030",
                "guest_name": "Test Guest",
                "arrival": "2026-09-17",
                "departure": "2026-09-24",
                "tour_operator": "TUI Germany",
                "room_booked": "Standard Sea View",
                "room_assigned": "Standard Sea View",
                "category": "Room Change Request",
                "notes": "no hot water in shower",
                "status": "Checked In",
                "booking_id": "87940",
                "tags": ["no_hot_water"]
            },
            {
                "trace_id": "trc_test_002",
                "room_number": "7030",
                "guest_name": "Test Guest",
                "arrival": "2026-09-17",
                "departure": "2026-09-24",
                "tour_operator": "TUI Germany",
                "room_booked": "Standard Sea View",
                "room_assigned": "Standard Sea View",
                "category": "Room Change Request",
                "notes": "bad smell",
                "status": "Checked In",
                "booking_id": "87940",
                "tags": ["smell"]
            },
            {
                "trace_id": "trc_test_003",
                "room_number": "5014",
                "guest_name": "Second Guest",
                "arrival": "2026-09-10",
                "departure": "2026-09-24",
                "tour_operator": "TUI France",
                "room_booked": "DUG",
                "room_assigned": "DUG",
                "category": "Allergies",
                "notes": "GLUTEN FREE",
                "status": "Checked In",
                "booking_id": "56132",
                "tags": ["gluten"]
            }
        ]

        # First run: should create files
        res1 = generate_room_json_mappings(mock_traces, rooms_dir=self.rooms_dir)
        self.assertEqual(res1["created"], 2)
        self.assertEqual(res1["updated"], 0)

        # Inspect 7030.json
        file_7030 = os.path.join(self.rooms_dir, "7030.json")
        self.assertTrue(os.path.exists(file_7030))
        with open(file_7030, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["room_number"], "7030")
        self.assertEqual(data["block"], "7")
        self.assertEqual(data["floor"], "0")
        self.assertEqual(data["total_traces"], 2)
        self.assertEqual(len(data["traces"]), 2)
        self.assertEqual(data["traces"][0]["tour_operator"], "TUI Germany")
        self.assertEqual(data["traces"][0]["room_booked"], "Standard Sea View")
        self.assertEqual(data["traces"][0]["room_assigned"], "Standard Sea View")

        # Manually add a custom key to verify persistence during re-sync
        data["manual_housekeeping_note"] = "Inspected by Duty Manager"
        with open(file_7030, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Second run: should be idempotent and update without duplicating traces
        res2 = generate_room_json_mappings(mock_traces, rooms_dir=self.rooms_dir)
        self.assertEqual(res2["created"], 0)
        self.assertEqual(res2["updated"], 2)

        with open(file_7030, "r", encoding="utf-8") as f:
            data2 = json.load(f)

        self.assertEqual(data2["total_traces"], 2)
        self.assertEqual(len(data2["traces"]), 2)
        self.assertEqual(data2.get("manual_housekeeping_note"), "Inspected by Duty Manager")

    # -------------------------------------------------------------------------
    # 5. Visual Analytics 10-Metric Calculation Engine
    # -------------------------------------------------------------------------
    def test_visual_analytics_calculation(self):
        sample_traces = [
            {
                "trace_id": "t1", "room_number": "7030", "guest_name": "A", "arrival": "2026-09-10",
                "departure": "2026-09-17", "tour_operator": "TUI Germany", "room_booked": "Standard",
                "room_assigned": "Suite", "category": "Room Change Request", "notes": "too loud noise",
                "status": "Checked In", "tags": ["noise"]
            },
            {
                "trace_id": "t2", "room_number": "7030", "guest_name": "A", "arrival": "2026-09-10",
                "departure": "2026-09-17", "tour_operator": "TUI Germany", "room_booked": "Standard",
                "room_assigned": "Suite", "category": "Room Change Request", "notes": "bad smell",
                "status": "Checked In", "tags": ["smell"]
            },
            {
                "trace_id": "t3", "room_number": "5014", "guest_name": "B", "arrival": "2026-09-12",
                "departure": "2026-09-16", "tour_operator": "Rainbow Tours", "room_booked": "Family",
                "room_assigned": "Family", "category": "Allergies", "notes": "gluten and lactose",
                "status": "Checked Out", "tags": ["gluten", "lactose"]
            },
        ]

        metrics = compute_visual_analytics_data(sample_traces)

        # 1. Tour Operator Mix
        self.assertIn("tour_operator_mix", metrics)
        self.assertGreater(len(metrics["tour_operator_mix"]), 0)

        # 2. Length of Stay
        self.assertIn("length_of_stay_dist", metrics)
        self.assertEqual(metrics["length_of_stay_dist"]["7-9 nights"], 1)
        self.assertEqual(metrics["length_of_stay_dist"]["4-6 nights"], 1)

        # 3. Room Type Upgrade / Downgrade
        up_down = metrics["room_type_upgrade_downgrade"]
        self.assertEqual(up_down["upgrade"], 2)
        self.assertEqual(up_down["exact_match"], 1)

        # 4. Daily Arrivals & Departures
        self.assertIn("daily_arrivals_departures", metrics)
        self.assertGreater(len(metrics["daily_arrivals_departures"]), 0)

        # 5. Trace Category Breakdown
        cats = [c["category"] for c in metrics["trace_category_breakdown"]]
        self.assertIn("Room Change Request", cats)
        self.assertIn("Allergies", cats)

        # 6. RCR Reason Tagging
        rcr_reasons = [r["reason"] for r in metrics["rcr_reason_tagging"]]
        self.assertIn("Noise", rcr_reasons)
        self.assertIn("Smell", rcr_reasons)

        # 7. Allergy Frequency
        allergy_names = [a["allergen"] for a in metrics["allergy_dietary_frequency"]]
        self.assertIn("Gluten", allergy_names)
        self.assertIn("Lactose/Dairy", allergy_names)

        # 8. Repeat-Issue Rooms
        repeat_rooms = metrics["repeat_issue_rooms"]
        self.assertEqual(len(repeat_rooms), 1)
        self.assertEqual(repeat_rooms[0]["room_number"], "7030")
        self.assertEqual(repeat_rooms[0]["total_traces"], 2)

        # 9. Trace Status Funnel
        funnel = metrics["trace_status_funnel"]
        self.assertIn("Room Change Request", funnel["categories"])
        self.assertIn("Checked In", funnel["statuses"])

        # 10. Spatial Complaint Density
        density = metrics["block_floor_complaint_density"]
        self.assertIn("blocks", density)
        self.assertIn("matrix", density)

    def test_visual_analytics_empty_resilience(self):
        metrics = compute_visual_analytics_data([])
        self.assertEqual(metrics["total_traces"], 0)
        self.assertEqual(len(metrics["repeat_issue_rooms"]), 0)
        self.assertIsInstance(metrics["tour_operator_mix"], list)

    # -------------------------------------------------------------------------
    # 6. Plot Engine Rendering
    # -------------------------------------------------------------------------
    def test_plot_engine_all_renderers(self):
        analytics = compute_visual_analytics_data([])
        fig = Figure(figsize=(8, 4), dpi=100)

        TraceAnalyticsPlotEngine.render_tour_operator_mix(fig, analytics)
        TraceAnalyticsPlotEngine.render_length_of_stay(fig, analytics)
        TraceAnalyticsPlotEngine.render_room_type_upgrade_downgrade(fig, analytics)
        TraceAnalyticsPlotEngine.render_daily_arrivals_departures(fig, analytics)
        TraceAnalyticsPlotEngine.render_trace_category_breakdown(fig, analytics)
        TraceAnalyticsPlotEngine.render_rcr_reason_tagging(fig, analytics)
        TraceAnalyticsPlotEngine.render_allergy_dietary_frequency(fig, analytics)
        TraceAnalyticsPlotEngine.render_repeat_issue_rooms(fig, analytics)
        TraceAnalyticsPlotEngine.render_trace_status_funnel(fig, analytics)
        TraceAnalyticsPlotEngine.render_block_floor_density(fig, analytics)

    # -------------------------------------------------------------------------
    # 7. Dual-Source Fusion, Classification & Strict Repeat-Issue Filtration
    # -------------------------------------------------------------------------
    def test_classify_trace(self):
        # Physical defects
        t_leak = {"category": "Trace", "notes": "severe pipe leak in bathroom"}
        is_def, is_srv = classify_trace(t_leak)
        self.assertTrue(is_def)
        self.assertFalse(is_srv)

        t_rcr = {"category": "Room Change Request", "notes": "Guest wants another room"}
        is_def, is_srv = classify_trace(t_rcr)
        self.assertTrue(is_def)
        self.assertFalse(is_srv)

        # Clear service
        t_allergy = {"category": "Allergies", "notes": "Strictly gluten free"}
        is_def, is_srv = classify_trace(t_allergy)
        self.assertFalse(is_def)
        self.assertTrue(is_srv)

        t_late = {"category": "Late Check Out", "notes": "Approved until 18:00"}
        is_def, is_srv = classify_trace(t_late)
        self.assertFalse(is_def)
        self.assertTrue(is_srv)

    def test_strict_repeat_issue_rooms_dietary_exclusion(self):
        # Room 7036 has 19 allergy entries
        traces = []
        for i in range(19):
            traces.append({
                "trace_id": f"trc_7036_{i}",
                "room_number": "7036",
                "guest_name": "Allergy Guest",
                "arrival": "2026-09-10",
                "departure": "2026-09-20",
                "tour_operator": "TUI",
                "category": "Allergies",
                "notes": "Severe gluten allergy and lactose intolerance",
                "status": "Checked In",
                "tags": ["gluten", "lactose"]
            })

        # Room 7030 has 2 physical defects
        traces.append({
            "trace_id": "trc_7030_1",
            "room_number": "7030",
            "guest_name": "Defect Guest 1",
            "arrival": "2026-09-10",
            "departure": "2026-09-17",
            "tour_operator": "TUI",
            "category": "Room Change Request",
            "notes": "no hot water and clogged shower",
            "status": "Checked In",
            "tags": ["no_hot_water", "water_plumbing"]
        })
        traces.append({
            "trace_id": "trc_7030_2",
            "room_number": "7030",
            "guest_name": "Defect Guest 2",
            "arrival": "2026-09-18",
            "departure": "2026-09-25",
            "tour_operator": "TUI",
            "category": "Feedback",
            "notes": "bad smell and toilet leak",
            "status": "Checked In",
            "tags": ["smell", "leak"]
        })

        # Room 6102 has only 1 physical defect (should not be repeat)
        traces.append({
            "trace_id": "trc_6102_1",
            "room_number": "6102",
            "guest_name": "Defect Guest 3",
            "arrival": "2026-09-10",
            "departure": "2026-09-17",
            "tour_operator": "TUI",
            "category": "Room Change Request",
            "notes": "a/c not working cold",
            "status": "Checked In",
            "tags": ["hvac"]
        })

        repeat_rooms = compute_repeat_issue_rooms(traces)

        # Strictly Room 7030 should be present, Room 7036 and 6102 must NOT be present
        repeat_room_numbers = [r["room_number"] for r in repeat_rooms]
        self.assertIn("7030", repeat_room_numbers)
        self.assertNotIn("7036", repeat_room_numbers, "Dietary room 7036 was falsely reported as a repeat defect room!")
        self.assertNotIn("6102", repeat_room_numbers, "Single defect room 6102 should not be reported as repeat")

        r7030 = next(r for r in repeat_rooms if r["room_number"] == "7030")
        self.assertEqual(r7030["total_traces"], 2)

    def test_fuse_inhouse_and_traces(self):
        in_house_manifest = {
            "7030": {
                "room": "7030",
                "guest_name": "Smith, John",
                "booking_id": "BK-101",
                "tour_operator": "TUI UK",
                "room_category": "Standard Sea View"
            },
            "7036": {
                "room": "7036",
                "guest_name": "Muller, Hans",
                "booking_id": "BK-102",
                "tour_operator": "Der Touristik",
                "room_category": "Junior Suite"
            },
            "5014": {
                "room": "5014",
                "guest_name": "Dupont, Jean",
                "booking_id": "BK-103",
                "tour_operator": "TUI France",
                "room_category": "Family Room"
            }
        }

        trace_list = [
            # Trace with room 7030 - physical defect
            {
                "trace_id": "trc_1",
                "room_number": "7030",
                "guest_name": "Smith",
                "booking_id": "",
                "tour_operator": "",
                "category": "Room Change Request",
                "notes": "A/C broken heating failure",
                "status": "Checked In"
            },
            # Trace matching by booking_id for 7036 - clear service trace
            {
                "trace_id": "trc_2",
                "room_number": "",
                "guest_name": "Muller",
                "booking_id": "BK-102",
                "tour_operator": "",
                "category": "Allergies",
                "notes": "Celiac disease, strict gluten free",
                "status": "Checked In"
            }
        ]

        fused = fuse_inhouse_and_traces(in_house_manifest, trace_list)

        # 1. Check trace enrichment
        enriched_traces = fused["enriched_traces"]
        self.assertEqual(len(enriched_traces), 2)
        # trc_1 should have tour_operator enriched
        self.assertEqual(enriched_traces[0]["tour_operator"], "TUI UK")
        # trc_2 should have room_number enriched to 7036
        self.assertEqual(enriched_traces[1]["room_number"], "7036")

        # 2. Check room states
        room_states = fused["room_states"]
        self.assertEqual(room_states["7030"], "Occupied with Active Physical Complaints")
        self.assertEqual(room_states["7036"], "Occupied with Clear Service Traces")
        self.assertEqual(room_states["5014"], "Occupied with Clean Record (No Traces)")

        # 3. Check resort incident ratio
        # Total occupied: 3. Occupied with physical complaints: 1 (7030).
        # Incident ratio: 1 / 3 * 100 = 33.3%
        self.assertAlmostEqual(fused["incident_ratio"], 33.3, places=1)
        self.assertEqual(fused["total_occupied_rooms"], 3)
        self.assertEqual(fused["occupied_with_defects"], 1)

    # -------------------------------------------------------------------------
    # 8. Extended Resort Operational Statistics & KPIs
    # -------------------------------------------------------------------------
    def test_extended_kpi_functions(self):
        traces = [
            {
                "trace_id": "t1",
                "room_number": "7030",
                "guest_name": "A",
                "booking_id": "BK-01",
                "category": "Room Change Request",
                "notes": "pipe leak flooded bathroom",
                "status": "Checked In"
            },
            {
                "trace_id": "t2",
                "room_number": "7031",
                "guest_name": "B",
                "booking_id": "BK-02",
                "category": "Room Change Request",
                "notes": "loud noise from generator",
                "status": "Checked In"
            },
            {
                "trace_id": "t3",
                "room_number": "7036",
                "guest_name": "C",
                "booking_id": "BK-03",
                "category": "Allergies",
                "notes": "celiac gluten free, severe peanut allergy",
                "status": "Checked In"
            }
        ]

        # 1. Normalized Block Defect Rate
        norm_rate = compute_normalized_block_defect_rate(traces)
        self.assertIn("rates", norm_rate)
        block7 = next((b for b in norm_rate["rates"] if b["block"] == "7"), None)
        self.assertIsNotNone(block7)
        self.assertEqual(block7["defects"], 2)
        self.assertGreater(block7["capacity"], 0)
        self.assertGreater(block7["defect_rate_pct"], 0)

        # 2. RCR Analytics with mock room moves file
        moves_file = os.path.join(self.temp_dir, "room_moves.json")
        with open(moves_file, "w", encoding="utf-8") as f:
            json.dump([
                {"booking_id": "BK-01", "old_room": "7030", "new_room": "7040", "status": "Moved"}
            ], f)

        rcr_metrics = compute_rcr_analytics(traces, room_moves_path=moves_file)
        self.assertEqual(rcr_metrics["total_rcr_logged"], 2)
        self.assertEqual(rcr_metrics["moves_executed"], 1)
        self.assertEqual(rcr_metrics["pending_in_house"], 1)
        self.assertEqual(rcr_metrics["resolution_rate_pct"], 50.0)

        # 3. Inter-departmental attribution
        dept_attr = compute_departmental_attribution(traces)
        # t1 is pipe leak -> Technical Maintenance
        # t2 is loud noise -> Front Office / Reception
        self.assertGreaterEqual(dept_attr["Technical Maintenance"], 1)
        self.assertGreaterEqual(dept_attr["Front Office / Reception"], 1)

        # 4. Dietary Risk Index
        in_house_manifest = {
            "7036": {"room": "7036", "guest_name": "C", "booking_id": "BK-03"}
        }
        dietary_risk = compute_dietary_risk_index(traces, in_house_manifest=in_house_manifest)
        self.assertGreaterEqual(dietary_risk["counts"]["Celiac / Gluten"], 1)
        self.assertGreaterEqual(dietary_risk["counts"]["Severe Nut / Peanut"], 1)
        self.assertEqual(dietary_risk["active_inhouse_alerts"], 1)
        self.assertEqual(len(dietary_risk["briefing_list"]), 1)
        self.assertEqual(dietary_risk["briefing_list"][0]["room_number"], "7036")

    # -------------------------------------------------------------------------
    # 9. PyQt6 Event Pass-Through & Scrolling Optimization
    # -------------------------------------------------------------------------
    def test_non_scrollable_figure_canvas_ignores_wheel(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QWheelEvent
        from PyQt6.QtCore import Qt, QPoint, QPointF

        app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])
        fig = Figure(figsize=(4, 3))
        canvas = NonScrollableFigureCanvas(fig)

        # Construct a simulated wheel event
        wheel_ev = QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        wheel_ev.accept()
        self.assertTrue(wheel_ev.isAccepted())

        canvas.wheelEvent(wheel_ev)
        self.assertFalse(wheel_ev.isAccepted(), "NonScrollableFigureCanvas must call event.ignore()!")

    def test_resort_graphics_view_wheel_modifier(self):
        from PyQt6.QtWidgets import QApplication, QGraphicsScene
        from PyQt6.QtGui import QWheelEvent
        from PyQt6.QtCore import Qt, QPoint, QPointF

        app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])
        scene = QGraphicsScene()
        view = ResortGraphicsView(scene)

        # Wheel event without Ctrl modifier -> should ignore
        ev_no_ctrl = QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        ev_no_ctrl.accept()
        view.wheelEvent(ev_no_ctrl)
        self.assertFalse(ev_no_ctrl.isAccepted(), "ResortGraphicsView must ignore wheel events without Ctrl!")

        # Wheel event with Ctrl modifier -> should accept
        ev_ctrl = QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        ev_ctrl.ignore()
        view.wheelEvent(ev_ctrl)
        self.assertTrue(ev_ctrl.isAccepted(), "ResortGraphicsView must accept wheel events with CtrlModifier!")

    # -------------------------------------------------------------------------
    # 10. Visual Analytics Overhaul Verification (Requirements 1-6)
    # -------------------------------------------------------------------------
    def test_allergy_exclusion_from_room_issues_and_heatmap(self):
        """Req 1: Verify Allergies, Offer, Birthday, Decoration, Flowers, Booking are excluded from room issues."""
        # 1. Verify constants
        self.assertIn("Allergies", EXCLUDED_ROOM_ISSUE_CATEGORIES)
        self.assertIn("Offer", EXCLUDED_ROOM_ISSUE_CATEGORIES)
        self.assertIn("Birthday", EXCLUDED_ROOM_ISSUE_CATEGORIES)
        self.assertIn("Room Change Request", ROOM_ISSUE_CATEGORIES)

        # 2. Test is_room_issue_trace()
        allergy_trace = {"category": "Allergies", "tags": ["celiac"], "notes": "Gluten free"}
        self.assertFalse(is_room_issue_trace(allergy_trace))

        late_co_trace = {"category": "Late Check Out", "tags": [], "notes": "Late check out requested"}
        self.assertFalse(is_room_issue_trace(late_co_trace))

        rcr_trace = {"category": "Room Change Request", "tags": ["ac / air conditioning"], "notes": "AC broken"}
        self.assertTrue(is_room_issue_trace(rcr_trace))

        # Trace with operational tag vs without
        trace_maint = {"category": "Trace", "tags": ["water / plumbing"], "notes": "Leaking pipe"}
        self.assertTrue(is_room_issue_trace(trace_maint))

        trace_outreach = {"category": "Trace", "tags": [], "notes": "gr asked about feedback"}
        self.assertFalse(is_room_issue_trace(trace_outreach))

        # 3. Test compute_repeat_issue_rooms with mixed items
        mock_traces = [
            {"room_number": "3010", "category": "Allergies", "tags": ["celiac"], "notes": "Gluten allergy"},
            {"room_number": "3010", "category": "Late Check Out", "tags": [], "notes": "Late checkout 14:00"},
            {"room_number": "3020", "category": "Room Change Request", "tags": ["ac / air conditioning"], "notes": "AC not working"},
            {"room_number": "3020", "category": "Room Change Request", "tags": ["smell"], "notes": "Bad smell in bathroom"},
        ]
        repeat_rooms = compute_repeat_issue_rooms(mock_traces)
        rooms_found = [r["room_number"] for r in repeat_rooms]
        self.assertNotIn("3010", rooms_found, "Allergy + Late CO room must NOT appear in repeat-issue rooms!")
        self.assertIn("3020", rooms_found, "Room with 2 RCRs must appear in repeat-issue rooms!")

    def test_rcr_enhanced_tagging_and_resolution_status(self):
        """Req 2: Verify AC, Floor Preference, Proximity Request, Furniture/Fixtures, quiet, and resolution_status."""
        # a) AC / Air Conditioning
        tags_ac = extract_rcr_tags("guest reports that ac is leaking and air con not cooling")
        self.assertTrue(any("ac" in t for t in tags_ac))

        # b) Floor Preference
        tags_floor = extract_rcr_tags("guest would prefer a high floor or upper floor")
        self.assertIn("floor_preference", tags_floor)

        # c) Proximity Request
        tags_prox = extract_rcr_tags("requesting room close to the main pool and next to restaurant")
        self.assertIn("proximity_request", tags_prox)

        # d) Furniture / Fixtures
        tags_furn = extract_rcr_tags("broken door handle and uncomfortable bed")
        self.assertIn("furniture_fixtures", tags_furn)

        # Noise with quiet
        tags_noise = extract_rcr_tags("room is very loud guest needs a quiet room")
        self.assertIn("noise", tags_noise)

        # e) Resolution status
        self.assertEqual(compute_rcr_resolution_status("they changed room to 4020"), "Resolved / Moved")
        self.assertEqual(compute_rcr_resolution_status("ok change to block 200"), "Resolved / Moved")
        self.assertEqual(compute_rcr_resolution_status("rec call n/a no answer"), "Attempted / No Answer")
        self.assertEqual(compute_rcr_resolution_status("they decide to not change room"), "Decided to Stay")
        self.assertEqual(compute_rcr_resolution_status("waiting for inspection"), "Pending / Unresolved")

    def test_trace_subcategories_and_primary_categories(self):
        """Req 3: Verify Trace sub-categorization and expanded PRIMARY_TRACE_CATEGORIES."""
        self.assertIn("Feedback", PRIMARY_TRACE_CATEGORIES)
        self.assertIn("Booking", PRIMARY_TRACE_CATEGORIES)
        self.assertIn("Decoration", PRIMARY_TRACE_CATEGORIES)
        self.assertIn("Birthday", PRIMARY_TRACE_CATEGORIES)
        self.assertIn("Special Requests", PRIMARY_TRACE_CATEGORIES)
        self.assertIn("Restaurants", PRIMARY_TRACE_CATEGORIES)
        self.assertIn("Flowers", PRIMARY_TRACE_CATEGORIES)

        self.assertEqual(classify_trace_subcategory("sent note to new room"), "Room Follow-up")
        self.assertEqual(classify_trace_subcategory("gr asked about feedback during survey"), "NPS / Feedback Outreach")
        self.assertEqual(classify_trace_subcategory("maintenance technician will fix"), "Maintenance Log")
        self.assertEqual(classify_trace_subcategory("guest very upset and complain"), "Complaint Log")
        self.assertEqual(classify_trace_subcategory("guest came to rec at front desk"), "Reception Interaction")
        self.assertEqual(classify_trace_subcategory("deliver extra water bottle"), "Special Request")
        self.assertEqual(classify_trace_subcategory("guest says everything is wonderful and satisfied"), "Positive Feedback")
        self.assertEqual(classify_trace_subcategory("just an informational note"), "Other / General")

    def test_lens_filtering_and_normalization(self):
        """Req 4: Verify 3-Lens category sets and category normalization."""
        from MODULES.trace_analytics import normalize_trace_category

        self.assertEqual(normalize_trace_category("RCR"), "Room Change Request")
        self.assertEqual(normalize_trace_category("Late C/O"), "Late Check Out")
        self.assertEqual(normalize_trace_category("Food Allergy"), "Allergies")

        self.assertIn("Room Change Request", LENS_CATEGORIES[LENS_ROOM_STAY])
        self.assertIn("Booking", LENS_CATEGORIES[LENS_ROOM_STAY])
        self.assertIn("Trace", LENS_CATEGORIES[LENS_GR_TRACES])
        self.assertIn("Feedback", LENS_CATEGORIES[LENS_GR_TRACES])
        self.assertIn("Allergies", LENS_CATEGORIES[LENS_DIETARY])

    def test_rcr_resolution_rate_and_feedback_sentiment(self):
        """Req 5: Verify RCR resolution breakdown and Feedback sentiment classification."""
        rcr_items = [
            {"category": "Room Change Request", "notes": "they changed to 5010", "tags": ["ac / air conditioning"]},
            {"category": "Room Change Request", "notes": "rec call n/a", "tags": ["noise complaint"]},
            {"category": "Room Change Request", "notes": "they decide to not change", "tags": ["view mismatch"]},
            {"category": "Room Change Request", "notes": "still checking with reception", "tags": ["smell"]},
        ]
        rcr_res = compute_rcr_analytics(rcr_items)
        breakdown = rcr_res["resolution_breakdown"]
        self.assertEqual(breakdown["Resolved / Moved"], 1)
        self.assertEqual(breakdown["Attempted / No Answer"], 1)
        self.assertEqual(breakdown["Decided to Stay"], 1)
        self.assertEqual(breakdown["Pending / Unresolved"], 1)

        self.assertEqual(classify_feedback_sentiment("The stay was wonderful and we love the hotel!"), "Positive")
        self.assertEqual(classify_feedback_sentiment("Very disappointed, not happy with the noise issue"), "Negative")
        self.assertEqual(classify_feedback_sentiment("Standard check-in completed"), "Neutral")

        mock_fb_traces = [
            {"category": "Feedback", "notes": "Great stay, happy guests", "status": "Closed"},
            {"category": "Feedback", "notes": "Bad experience, upset about room", "status": "Closed"},
            {"category": "Feedback", "notes": "Routine feedback logged", "status": "Open"},
        ]
        analytics = compute_visual_analytics_data(mock_fb_traces)
        sent = analytics["feedback_sentiment_split"]
        self.assertEqual(sent["total_feedback"], 3)
        self.assertEqual(sent["positive"], 1)
        self.assertEqual(sent["negative"], 1)
        self.assertEqual(sent["neutral"], 1)
        self.assertAlmostEqual(sent["positive_pct"], 33.33, places=1)

    def test_chart_canvas_pass_through_and_stats_widget_integration(self):
        """Req 6: Verify canvas focus policy, wheel pass-through filter, and StatsWidget integration."""
        from PyQt6.QtWidgets import QApplication
        from OPTIONS.stats_option import StatsWidget
        from OPTIONS._shared_widgets import ChartCardWidget

        app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

        # Test ChartCardWidget canvas setup
        card = ChartCardWidget(title="Test", subtitle="Sub", icon="📊")
        fig = Figure(figsize=(4, 3))
        canvas = NonScrollableFigureCanvas(fig)
        card.set_canvas(canvas)
        self.assertEqual(canvas.focusPolicy(), Qt.FocusPolicy.NoFocus)

        # Test StatsWidget initialization and 12 charts
        widget = StatsWidget()
        self.assertEqual(len(widget.chart_cards), 12, "StatsWidget must contain exactly 12 operational charts!")
        self.assertGreaterEqual(StatsWidget._canvas_creation_count, 12)

        # Test lens filtering on StatsWidget
        widget._on_lens_selected(LENS_ROOM_STAY)
        self.assertEqual(widget.current_lens, LENS_ROOM_STAY)
        # Chart 2 (Room Type Upgrade/Downgrade) should not be hidden
        self.assertFalse(widget.chart_cards[2].isHidden())
        # Chart 6 (Allergy Frequency) should be hidden under Room & Stay
        self.assertTrue(widget.chart_cards[6].isHidden())

        # Reset to All Operations
        widget._on_lens_selected(LENS_ALL)
        self.assertFalse(widget.chart_cards[6].isHidden())


if __name__ == "__main__":
    unittest.main()

