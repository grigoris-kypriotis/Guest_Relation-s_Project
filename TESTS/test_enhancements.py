import os
import sys
import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

# Headless Qt environment for offscreen test
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from MODULES.data_manager import (
    InHouseDataManager,
    extract_inhouse_report_date,
    validate_inhouse_file_date,
    export_room_block_json_data,
    purge_hotel_database,
    HOTEL_DATASET_PATH,
    PLOT_DIR,
    MASTER_STATE_PATH,
    STATE_META_PATH
)
from MODULES.plot_viewer import PlotGraphWindow, ResortNodeItem, REAL_MAP_COORDINATES
from app import ConfigurationWidget, StatsWidget, GuestRelationApp, WorkspaceViewerDialog, ResortStatsDialog


class TestEnhancementsSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dm = InHouseDataManager()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Date Validation Tests
    # -------------------------------------------------------------------------
    def test_inhouse_date_validation_success_and_mismatch(self):
        today = date.today()
        yesterday = today - timedelta(days=1)

        # Create a CSV with today's date in metadata footer
        today_csv = os.path.join(self.temp_dir, "inhouse_today.csv")
        with open(today_csv, "w", encoding="utf-8") as f:
            f.write('"Δωμάτιο";"Αρ.";"Πελάτης";"Άφιξη";"Αναχώρηση"\n')
            f.write('"1101";"10001";"Test Guest";"10/09/2026";"20/09/2026"\n')
            f.write(f'"{today.strftime("%d/%m/%Y")}";"Page 1 of 1";;"12:00:00"\n')

        # Test valid
        valid, extracted, msg = validate_inhouse_file_date(today_csv, target_date=today)
        self.assertTrue(valid)
        self.assertEqual(extracted, today)

        # Create a CSV with yesterday's date
        old_csv = os.path.join(self.temp_dir, "inhouse_yesterday.csv")
        with open(old_csv, "w", encoding="utf-8") as f:
            f.write('"Δωμάτιο";"Αρ.";"Πελάτης";"Άφιξη";"Αναχώρηση"\n')
            f.write('"1101";"10001";"Test Guest";"10/09/2026";"20/09/2026"\n')
            f.write(f'"{yesterday.strftime("%d/%m/%Y")}";"Page 1 of 1";;"12:00:00"\n')

        # Test mismatch
        valid, extracted, msg = validate_inhouse_file_date(old_csv, target_date=today)
        self.assertFalse(valid)
        self.assertEqual(extracted, yesterday)
        expected_err = f"Validation Error: Selected report date [{yesterday.strftime('%Y-%m-%d')}] does not match current operational date [{today.strftime('%Y-%m-%d')}]."
        self.assertEqual(msg, expected_err)

    # -------------------------------------------------------------------------
    # 2. Database Purge Tests
    # -------------------------------------------------------------------------
    def test_purge_hotel_database(self):
        # Seed mock state
        dummy_state = {
            "99999": {
                "booking_id": "99999",
                "room": "1105",
                "guests": ["Purge Target"],
                "arrival": "10/09/2026",
                "departure": "25/09/2026"
            }
        }
        self.dm.save_master_state(dummy_state)
        self.dm.set_last_sync_date(date.today())

        state_before = self.dm.load_master_state()
        self.assertIn("99999", state_before)

        # Purge
        purge_res = purge_hotel_database()
        self.assertTrue(purge_res)

        state_after = self.dm.load_master_state()
        self.assertEqual(len(state_after), 0)

        meta = self.dm.load_metadata()
        self.assertIsNone(meta.get("last_sync_date"))
        self.assertEqual(meta.get("total_bookings"), 0)

    # -------------------------------------------------------------------------
    # 3. Room Block Exporter Tests
    # -------------------------------------------------------------------------
    def test_export_room_block_json_data(self):
        self.assertTrue(os.path.exists(HOTEL_DATASET_PATH), f"Dataset missing at {HOTEL_DATASET_PATH}")
        
        # Populate state with a known room
        test_state = {
            "10001": {
                "booking_id": "10001",
                "room": "1101",
                "guests": ["Occupant One"],
                "arrival": "10/09/2026",
                "departure": "20/09/2026"
            },
            "10002": {
                "booking_id": "10002",
                "room": "1102",
                "guests": ["Occupant Two"],
                "arrival": "10/09/2026",
                "departure": "20/09/2026"
            }
        }
        self.dm.save_master_state(test_state)

        result = export_room_block_json_data()
        self.assertGreater(result["total_exported"], 0)
        self.assertEqual(result["total_exported"], 24)  # 16 standard blocks + 8 suites

        # Inspect BLOCK_1100
        block_1100_json = os.path.join(PLOT_DIR, "BLOCK_1100", "BLOCK_1100.json")
        self.assertTrue(os.path.exists(block_1100_json))

        with open(block_1100_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("occupancy_metrics", data)
        metrics = data["occupancy_metrics"]
        self.assertEqual(metrics["occupied_rooms"], 2)
        self.assertGreater(metrics["total_rooms"], 0)
        self.assertIn("occupancy_percentage", metrics)
        self.assertIn("last_updated", metrics)

    # -------------------------------------------------------------------------
    # 4. Plot Window & Resort Canvas Tests
    # -------------------------------------------------------------------------
    def test_plot_graph_window_initialization(self):
        plot_win = PlotGraphWindow()
        self.assertIsNotNone(plot_win)
        self.assertEqual(len(plot_win.node_items), 44)
        
        # Verify node 1 (Block 1100)
        node_1 = plot_win.node_items.get(1)
        self.assertIsNotNone(node_1)
        self.assertEqual(node_1.node_data["name"], "BLOCK 1100")
        self.assertEqual(node_1.node_data["category"], "Rooms")
        
        # Verify node 17 (Reception)
        node_17 = plot_win.node_items.get(17)
        self.assertIsNotNone(node_17)
        self.assertIn("RECEPTION", node_17.node_data["name"])
        self.assertIn("Facilities", node_17.node_data["category"])

        # Test search filter
        plot_win.txt_search.setText("1100")
        plot_win._search_nodes("1100")
        self.assertTrue(node_1.is_highlighted)
        self.assertFalse(node_17.is_highlighted)
        plot_win.close()

    # -------------------------------------------------------------------------
    # 5. ConfigurationWidget & StatsWidget Tests
    # -------------------------------------------------------------------------
    def test_configuration_widget(self):
        cfg_w = ConfigurationWidget()
        self.assertIsNotNone(cfg_w)
        cfg_w.refresh_timestamp_display()
        # Ensure timestamp label exists and has text
        self.assertTrue(len(cfg_w.txt_timestamp.text()) > 0)

    def test_stats_widget(self):
        stats_w = StatsWidget()
        self.assertIsNotNone(stats_w)
        stats_w.refresh_stats()
        self.assertIsNotNone(stats_w.figure)
        self.assertIsNotNone(stats_w.canvas)

    # -------------------------------------------------------------------------
    # 6. Main App Startup (No Gatekeeper Popup)
    # -------------------------------------------------------------------------
    def test_main_app_direct_startup(self):
        app_win = GuestRelationApp()
        self.assertIsNotNone(app_win)
        self.assertIsNotNone(app_win.action_plot)
        self.assertIsNotNone(app_win.config_widget)
        self.assertIsNotNone(app_win.stats_widget)
        app_win.close()

    # -------------------------------------------------------------------------
    # 7. Real Map Coordinates & Node 44 (Ermis Gyro) Tests
    # -------------------------------------------------------------------------
    def test_real_map_coordinates_and_node_44(self):
        self.assertEqual(len(REAL_MAP_COORDINATES), 44)
        self.assertIn(44, REAL_MAP_COORDINATES)
        # Node 44 is Ermis Gyro Greek Restaurant located at (1874, 90) (top-right Sandy Villas)
        self.assertEqual(REAL_MAP_COORDINATES[44], (1874, 90))

        # Coastal nodes (West) should be positioned on the left (X <= 400)
        coastal_node_ids = [29, 43, 28, 27, 31, 25, 26]
        for nid in coastal_node_ids:
            self.assertIn(nid, REAL_MAP_COORDINATES)
            x, y = REAL_MAP_COORDINATES[nid]
            self.assertLessEqual(x, 400, f"Coastal node {nid} should have X <= 400, got {x}")

        # Sandy Villas & Pool Suites (Far East) should be on the right (X >= 1500)
        villas_node_ids = [33, 34, 35, 36, 37, 38, 39, 40, 44]
        for vid in villas_node_ids:
            self.assertIn(vid, REAL_MAP_COORDINATES)
            x, y = REAL_MAP_COORDINATES[vid]
            self.assertGreaterEqual(x, 1500, f"Villas node {vid} should have X >= 1500, got {x}")

    # -------------------------------------------------------------------------
    # 8. Crash-Proof Node Click & Empty Attributes Handling
    # -------------------------------------------------------------------------
    def test_plot_viewer_crash_proof_node_click(self):
        # Test malformed / empty node data
        empty_node = {"id": 999}
        item = ResortNodeItem(empty_node, 100, 100)
        self.assertIsNotNone(item)

        # Ensure no exception when clicking with various status bar callbacks
        clicked_msgs = []
        plot_win = PlotGraphWindow()
        plot_win._on_node_clicked(empty_node)  # Should execute safely without raising
        self.assertTrue(len(plot_win.lbl_status.text()) > 0)
        plot_win.close()

    # -------------------------------------------------------------------------
    # 9. ResortStatsDialog & StatsWidget Scrollable 2-Tab Structure
    # -------------------------------------------------------------------------
    def test_resort_stats_dialog_and_stats_widget_tabs(self):
        # StatsWidget structure
        stats_w = StatsWidget()
        self.assertEqual(stats_w.tabs.count(), 2)
        self.assertEqual(stats_w.tabs.tabText(0), "📈 Visual Analytics Suite")
        self.assertEqual(stats_w.tabs.tabText(1), "📋 Guest Manifest Table")
        self.assertIsNotNone(stats_w.analytics_scroll)
        self.assertIsNotNone(stats_w.card_capacity)
        self.assertIsNotNone(stats_w.card_occ)
        self.assertIsNotNone(stats_w.card_facilities)
        self.assertIsNotNone(stats_w.box_board)
        self.assertIsNotNone(stats_w.box_nat)
        self.assertIsNotNone(stats_w.box_rooms)

        # ResortStatsDialog structure
        stats_dlg = ResortStatsDialog(parent=None)
        self.assertEqual(stats_dlg.tabs.count(), 2)
        self.assertIsNotNone(stats_dlg.analytics_scroll)
        self.assertIsNotNone(stats_dlg.manifest_widget)
        stats_dlg.close()

    # -------------------------------------------------------------------------
    # 10. Database Purge Strips Dynamic Fields from HotelDataSet.json
    # -------------------------------------------------------------------------
    def test_purge_hotel_database_strips_dynamic_fields(self):
        # Inject dynamic fields into HotelDataSet.json
        with open(HOTEL_DATASET_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        records[0]["current_occupancy"] = 99
        records[0]["assigned_guests"] = ["Test Guest"]
        records[0]["live_status"] = "BUSY"

        with open(HOTEL_DATASET_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

        # Execute purge
        res = self.dm.purge_hotel_database()
        self.assertTrue(res.get("success", False))
        self.assertGreater(res.get("purged_count", 0), 0)

        # Verify dynamic fields were stripped
        with open(HOTEL_DATASET_PATH, "r", encoding="utf-8") as f:
            updated_records = json.load(f)

        self.assertNotIn("current_occupancy", updated_records[0])
        self.assertNotIn("assigned_guests", updated_records[0])
        self.assertNotIn("live_status", updated_records[0])
        self.assertIn("name", updated_records[0])  # Physical structure retained

    # -------------------------------------------------------------------------
    # 11. WorkspaceViewerDialog 99% Bounds & Outer Padding Tests
    # -------------------------------------------------------------------------
    def test_workspace_viewer_dialog_geometry(self):
        parent_widget = ConfigurationWidget()
        parent_widget.resize(1000, 800)
        viewer_dlg = WorkspaceViewerDialog("Offerlist Viewer", "<p>Content</p>", parent=parent_widget)
        viewer_dlg.show()
        # Verify 99% scale calculation
        expected_w = int(1000 * 0.99)
        expected_h = int(800 * 0.99)
        self.assertEqual(viewer_dlg.width(), expected_w)
        self.assertEqual(viewer_dlg.height(), expected_h)
        viewer_dlg.close()
        parent_widget.close()


if __name__ == "__main__":
    unittest.main()
