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

from data_manager import (
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
from plot_viewer import PlotGraphWindow, ResortNodeItem
from app import ConfigurationWidget, StatsWidget, GuestRelationApp


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


if __name__ == "__main__":
    unittest.main()
