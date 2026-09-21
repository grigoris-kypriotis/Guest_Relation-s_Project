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
from MODULES.plot_viewer import PlotGraphWindow, PlotViewerWidget, ResortNodeItem, REAL_MAP_COORDINATES
from app import ConfigurationWidget, StatsWidget, GuestRelationApp, WorkspaceViewerDialog, ResortStatsDialog
from OPTIONS.configuration_option import load_app_settings, save_app_settings, APP_SETTINGS_PATH
from OPTIONS.system_data_option import SystemDataOptionWidget


class TestEnhancementsSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_enh_")
        self.temp_db = os.path.join(self.temp_dir, "DATABASE")
        self.temp_hotel_state = os.path.join(self.temp_db, "HOTEL STATE")
        self.temp_sandy_beach = os.path.join(self.temp_db, "SANDY BEACH")
        self.temp_beach_arr = os.path.join(self.temp_sandy_beach, "ARRIVALS")
        self.temp_beach_dep = os.path.join(self.temp_sandy_beach, "DEPARTURE")
        self.temp_checkouts = os.path.join(self.temp_db, "CHECK OUT HISTORY")
        self.temp_moves = os.path.join(self.temp_db, "ROOM MOVES")
        self.temp_calls = os.path.join(self.temp_db, "BOOKING CALLS FOR TODAY")
        self.temp_plot = os.path.join(self.temp_dir, "PLOT")
        self.temp_rooms = os.path.join(self.temp_dir, "ROOMS")
        self.temp_trash = os.path.join(self.temp_dir, "TRASH")
        self.temp_backup = os.path.join(self.temp_dir, "DATA_BACKUP")
        self.temp_output = os.path.join(self.temp_dir, "OUTPUT")

        for d in [
            self.temp_db, self.temp_hotel_state, self.temp_sandy_beach,
            self.temp_beach_arr, self.temp_beach_dep, self.temp_checkouts,
            self.temp_moves, self.temp_calls, self.temp_plot, self.temp_rooms,
            self.temp_trash, self.temp_backup, self.temp_output
        ]:
            os.makedirs(d, exist_ok=True)

        if os.path.exists(HOTEL_DATASET_PATH):
            shutil.copy2(HOTEL_DATASET_PATH, os.path.join(self.temp_plot, "HotelDataSet.json"))
        if os.path.exists(APP_SETTINGS_PATH):
            shutil.copy2(APP_SETTINGS_PATH, os.path.join(self.temp_db, "app_settings.json"))

        import sys
        import MODULES.common.paths_config as pc
        import MODULES.data_manager as dm_mod
        import MODULES.state.hotel_state_manager as hsm_mod
        import MODULES.admin.database_admin as dba_mod
        import OPTIONS.stats_option as stats_opt
        import OPTIONS.configuration_option as cfg_opt

        target_mods = {
            pc, dm_mod, hsm_mod, dba_mod, stats_opt, cfg_opt,
            sys.modules.get("TESTS.test_enhancements"),
            sys.modules.get("test_enhancements"),
            sys.modules.get(__name__),
        }
        target_mods.discard(None)

        self._patches = []
        def patch_val(module, attr, val):
            if hasattr(module, attr):
                self._patches.append((module, attr, getattr(module, attr)))
                setattr(module, attr, val)

        temp_dataset = os.path.join(self.temp_plot, "HotelDataSet.json")
        temp_master = os.path.join(self.temp_hotel_state, "master_state.json")
        temp_meta = os.path.join(self.temp_hotel_state, "state_metadata.json")
        temp_arrivals = os.path.join(self.temp_beach_arr, "today_arrivals.json")
        temp_checkouts = os.path.join(self.temp_checkouts, "checkouts.json")
        temp_moves = os.path.join(self.temp_moves, "room_moves.json")
        temp_calls = os.path.join(self.temp_calls, "booking_calls_for_today.json")
        temp_settings = os.path.join(self.temp_db, "app_settings.json")

        for mod in target_mods:
            patch_val(mod, "DATABASE_DIR", self.temp_db)
            patch_val(mod, "HOTEL_DATASET_PATH", temp_dataset)
            patch_val(mod, "MASTER_STATE_PATH", temp_master)
            patch_val(mod, "STATE_META_PATH", temp_meta)
            patch_val(mod, "MASTER_STATE_ROOT_PATH", temp_master)
            patch_val(mod, "STATE_META_ROOT_PATH", temp_meta)
            patch_val(mod, "ARRIVALS_BEACH_PATH", temp_arrivals)
            patch_val(mod, "CHECKOUTS_JSON", temp_checkouts)
            patch_val(mod, "CHECKOUTS_TODAY_JSON", temp_checkouts)
            patch_val(mod, "CHECKOUT_HISTORY_PATH", temp_checkouts)
            patch_val(mod, "ROOM_MOVES_JSON", temp_moves)
            patch_val(mod, "ROOM_MOVES_YESTERDAY_JSON", temp_moves)
            patch_val(mod, "ROOM_MOVES_HISTORY_PATH", temp_moves)
            patch_val(mod, "BOOKING_CALLS_TODAY_JSON", temp_calls)
            patch_val(mod, "ROOMS_DIR", self.temp_rooms)
            patch_val(mod, "PLOT_DIR", self.temp_plot)
            patch_val(mod, "TRASH_DIR", self.temp_trash)
            patch_val(mod, "HOTEL_STATE_DIR", self.temp_hotel_state)
            patch_val(mod, "OUTPUT_DIR", self.temp_output)
            patch_val(mod, "APP_SETTINGS_PATH", temp_settings)

        self.dm = InHouseDataManager(
            master_state_path=temp_master,
            state_meta_path=temp_meta,
            arrivals_state_path=temp_arrivals,
            trash_dir=self.temp_trash,
            checkouts_path=temp_checkouts,
            room_moves_path=temp_moves
        )

    def tearDown(self):
        for mod, attr, orig_val in reversed(self._patches):
            setattr(mod, attr, orig_val)
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
        self.assertEqual(result["total_exported"], 16)  # 16 standard blocks

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
        self.assertEqual(len(plot_win.node_items), 36)
        
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
        self.assertEqual(len(REAL_MAP_COORDINATES), 36)
        self.assertIn(44, REAL_MAP_COORDINATES)
        # Node 44 is Ermis Gyro Greek Restaurant located at (1874, 90) (top-right)
        self.assertEqual(REAL_MAP_COORDINATES[44], (1874, 90))

        # Coastal nodes (West) should be positioned on the left (X <= 400)
        coastal_node_ids = [29, 43, 28, 27, 31, 25, 26]
        for nid in coastal_node_ids:
            self.assertIn(nid, REAL_MAP_COORDINATES)
            x, y = REAL_MAP_COORDINATES[nid]
            self.assertLessEqual(x, 400, f"Coastal node {nid} should have X <= 400, got {x}")

        # Far East nodes should be on the right (X >= 1500)
        far_east_node_ids = [41, 44]
        for vid in far_east_node_ids:
            self.assertIn(vid, REAL_MAP_COORDINATES)
            x, y = REAL_MAP_COORDINATES[vid]
            self.assertGreaterEqual(x, 1500, f"Far East node {vid} should have X >= 1500, got {x}")

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
        # StatsWidget structure (Decoupled Visual Analytics Suite)
        stats_w = StatsWidget()
        self.assertEqual(stats_w.tabs.count(), 1)
        self.assertEqual(stats_w.tabs.tabText(0), "📈 Visual Analytics Suite")
        self.assertIsNotNone(stats_w.analytics_scroll)
        self.assertIsNotNone(stats_w.card_capacity)
        self.assertIsNotNone(stats_w.card_occ)
        self.assertIsNotNone(stats_w.card_facilities)
        self.assertIsNotNone(stats_w.box_nat)
        self.assertIsNotNone(stats_w.box_rooms)

        # ResortStatsDialog structure
        stats_dlg = ResortStatsDialog(parent=None)
        self.assertEqual(stats_dlg.tabs.count(), 1)
        self.assertIsNotNone(stats_dlg.analytics_scroll)
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

    # -------------------------------------------------------------------------
    # 12. Plot Workspace Embedding & Room Moves Menu Tests
    # -------------------------------------------------------------------------
    def test_plot_viewer_widget_and_workspace_embedding(self):
        viewer = PlotViewerWidget()
        self.assertIsNotNone(viewer)
        self.assertEqual(len(viewer.node_items), 36)
        viewer.activate()
        viewer.refresh_plot()
        viewer.close()

        app_win = GuestRelationApp()
        self.assertIn("PLOT", app_win.option_widgets)
        self.assertIs(app_win.option_widgets["PLOT"], app_win.plot_widget)
        
        # Test switching to PLOT embeds in stacked_content without opening separate window
        app_win.select_category("PLOT")
        self.assertIs(app_win.stacked_content.currentWidget(), app_win.plot_widget)
        self.assertTrue(app_win.sidebar.btn_hamburger.property("active"))
        app_win.close()

    def test_room_moves_menu_action_and_navigation(self):
        app_win = GuestRelationApp()
        self.assertIsNotNone(app_win.action_moves)
        self.assertEqual(app_win.action_moves.text(), "Room Moves")
        
        # Triggering the action switches stacked_content to moves_widget
        app_win.action_moves.trigger()
        self.assertIs(app_win.stacked_content.currentWidget(), app_win.moves_widget)
        self.assertTrue(app_win.sidebar.btn_hamburger.property("active"))
        app_win.close()

    # -------------------------------------------------------------------------
    # 13. Configuration Settings Persistence & Signal Emission Tests
    # -------------------------------------------------------------------------
    def test_configuration_settings_persistence_and_signals(self):
        cfg_w = ConfigurationWidget()
        cfg_w.spin_beach_rooms.setValue(670)
        
        signal_emitted = []
        cfg_w.data_updated.connect(lambda: signal_emitted.append(True))
        
        cfg_w.save_configuration()
        self.assertTrue(os.path.exists(APP_SETTINGS_PATH))
        settings = load_app_settings()
        self.assertEqual(settings["properties"]["sandy_beach_rooms"], 670)
        self.assertTrue(len(signal_emitted) > 0)
        cfg_w.close()

    # -------------------------------------------------------------------------
    # 14. StatsWidget Vertical Stacking, Progress Bar & Async Data Fetching
    # -------------------------------------------------------------------------
    def test_stats_widget_vertical_stacking_and_async_data(self):
        stats_w = StatsWidget()
        self.assertIsNotNone(stats_w.progress_occ)
        self.assertEqual(stats_w.progress_occ.maximum(), 100)
        
        # Test background data fetching method directly
        data = stats_w._fetch_all_stats_data()
        self.assertIn("total_physical_rooms", data)
        self.assertIn("block_percentages", data)
        self.assertIn("target_blocks", data)
        self.assertIn("occ_pct", data)
        self.assertEqual(len(data["target_blocks"]), 16)
        
        # Apply data and verify UI update
        stats_w._apply_stats_data(data)
        self.assertIn("%", stats_w.card_occ.lbl_main.text())
        self.assertIn("Rooms", stats_w.card_capacity.lbl_main.text())
        self.assertIsNotNone(stats_w.figure)
        stats_w.close()

    # -------------------------------------------------------------------------
    # 15. Plot Viewer Node Click Inspection & Rich Attributes
    # -------------------------------------------------------------------------
    def test_plot_viewer_node_click_inspection(self):
        viewer = PlotViewerWidget()
        viewer.resize(1000, 800)
        viewer.show()
        
        # Click node 1 (Block 1100)
        node_1 = viewer.node_items[1]
        viewer.open_node_inspector(node_1.node_data, node_id=1)
        self.assertIsNotNone(viewer.active_popup)
        self.assertEqual(viewer.active_popup.node_name, "BLOCK 1100")
        self.assertEqual(viewer.selected_id, 1)
        self.assertTrue(node_1.is_selected_node)
        
        viewer._close_popup()
        self.assertIsNone(viewer.active_popup)
        self.assertFalse(node_1.is_selected_node)
        viewer.close()

    # -------------------------------------------------------------------------
    # 16. Canonical English Header Normalization
    # -------------------------------------------------------------------------
    def test_canonical_english_header_normalization(self):
        # Greek input booking
        greek_booking = {
            "Δωμάτιο": "1111",
            "Πελάτες": ["John Doe", "Jane Doe"],
            "Άφιξη": "18/9/2026",
            "Αναχώρηση": "25/9/2026",
            "Τύπος Δωματίου": "F1G",
            "Χρεωστικός Τύπος Δωματίου": "F1G",
            "Χρεώστης": "TUI FRANCE",
            "Αγορά": "FRANCE",
            "Σύν. Ατόμων": "2",
            "Αρ. Παιδ": "0",
            "Τύπος Γεύματος": "All Inclusive"
        }
        norm_greek = InHouseDataManager.normalize_booking_dict("1001", greek_booking)
        self.assertEqual(norm_greek["Room"], "1111")
        self.assertEqual(norm_greek["Δωμάτιο"], "1111")
        self.assertEqual(norm_greek["Guests"], ["John Doe", "Jane Doe"])
        self.assertEqual(norm_greek["Arrival"], "18/9/2026")
        self.assertEqual(norm_greek["Departure"], "25/9/2026")
        self.assertEqual(norm_greek["Room Type"], "F1G")
        self.assertEqual(norm_greek["Agency"], "TUI FRANCE")
        self.assertEqual(norm_greek["Meal Plan"], "All Inclusive")

        # English input booking
        english_booking = {
            "Room": "2105",
            "Guests": ["Alice Smith"],
            "Arrival": "18/9/2026",
            "Departure": "22/9/2026",
            "Room Type": "D1G",
            "Agency": "BOOKING.COM",
            "Market": "UK",
            "Adults": "1",
            "Children": "0"
        }
        norm_eng = InHouseDataManager.normalize_booking_dict("1002", english_booking)
        self.assertEqual(norm_eng["Room"], "2105")
        self.assertEqual(norm_eng["Δωμάτιο"], "2105")
        self.assertEqual(norm_eng["Guests"], ["Alice Smith"])
        self.assertEqual(norm_eng["Πελάτες"], ["Alice Smith"])
        self.assertEqual(norm_eng["Arrival"], "18/9/2026")
        self.assertEqual(norm_eng["Departure"], "22/9/2026")
        self.assertEqual(norm_eng["Room Type"], "D1G")
        self.assertEqual(norm_eng["Agency"], "BOOKING.COM")

    # -------------------------------------------------------------------------
    # 17. SystemDataOptionWidget Filter Controls & Live Arrivals
    # -------------------------------------------------------------------------
    def test_system_data_option_filtering_and_arrivals(self):
        # Seed test state to ensure hermetic execution regardless of purge tests
        today_s = date.today().strftime("%d/%m/%Y")
        test_state = {
            "1001": {
                "Room": "1111",
                "Guests": ["John Doe"],
                "Arrival": today_s,
                "Departure": "25/09/2026",
                "Room Type": "F1G",
                "Agency": "SUNWEB"
            },
            "1002": {
                "Room": "2105",
                "Guests": ["Jane Smith"],
                "Arrival": today_s,
                "Departure": "26/09/2026",
                "Room Type": "D1G",
                "Agency": "TUI"
            }
        }
        self.dm.save_master_state(test_state)
        self.dm.set_last_sync_date(date.today())

        sys_w = SystemDataOptionWidget()
        self.assertIsNotNone(sys_w.cmb_room_filter)
        self.assertIsNotNone(sys_w.txt_filter)
        self.assertIsNotNone(sys_w.btn_filter)
        self.assertIsNotNone(sys_w.btn_clear_filter)

        # Check English table headers
        master_headers = [sys_w.table_master.horizontalHeaderItem(c).text() for c in range(sys_w.table_master.columnCount())]
        self.assertIn("Room", master_headers)
        self.assertIn("Booking ID", master_headers)
        self.assertIn("Guest Name(s)", master_headers)
        self.assertIn("Arrival", master_headers)
        self.assertIn("Departure", master_headers)

        arrivals_headers = [sys_w.table_beach_arrivals.horizontalHeaderItem(c).text() for c in range(sys_w.table_beach_arrivals.columnCount())]
        self.assertIn("Room", arrivals_headers)
        self.assertIn("Guest Name(s)", arrivals_headers)
        self.assertIn("Arrival", arrivals_headers)

        # Verify arrivals have records
        self.assertGreater(sys_w.table_beach_arrivals.rowCount(), 0)

        # Test filter by room block
        total_rows = sys_w.table_master.rowCount()
        self.assertGreater(total_rows, 0)
        sys_w.cmb_room_filter.setCurrentText("Block 1100s")
        sys_w._apply_filter()
        hidden_count = sum(1 for r in range(total_rows) if sys_w.table_master.isRowHidden(r))
        self.assertGreater(hidden_count, 0)

        # Test clear filter
        sys_w._clear_filter()
        all_visible = all(not sys_w.table_master.isRowHidden(r) for r in range(total_rows))
        self.assertTrue(all_visible)

        # Test text search filter
        sys_w.txt_filter.setText("SUNWEB")
        sys_w._apply_filter()
        sys_w._clear_filter()
        sys_w.close()

    # -------------------------------------------------------------------------
    # 18. StatsWidget Scrollable Visual Dashboard & Block Meters
    # -------------------------------------------------------------------------
    def test_stats_widget_scrollable_dashboard_and_block_meters(self):
        # Seed test state for hermetic execution
        test_state = {
            "1001": {
                "Room": "1111",
                "Guests": ["John Doe"],
                "Arrival": "18/9/2026",
                "Departure": "25/9/2026",
                "Room Type": "F1G",
                "Agency": "SUNWEB"
            }
        }
        self.dm.save_master_state(test_state)
        self.dm.set_last_sync_date(date.today())

        stats_w = StatsWidget()
        # Verify scroll area
        self.assertIsNotNone(stats_w.analytics_scroll)
        self.assertTrue(stats_w.analytics_scroll.widgetResizable())

        # Verify Block visual meter cards
        self.assertGreaterEqual(len(stats_w.block_card_widgets), 16)
        self.assertIn("BLOCK 1100", stats_w.block_card_widgets)
        card_1100 = stats_w.block_card_widgets["BLOCK 1100"]
        self.assertIsNotNone(card_1100.pbar)
        self.assertIsNotNone(card_1100.lbl_pct)

        # Verify ManifestWidget decoupled table
        from OPTIONS.manifest_option import ManifestWidget
        man_w = ManifestWidget()
        self.assertIsNotNone(man_w.table_inhouse)
        self.assertGreater(man_w.table_inhouse.rowCount(), 0)
        manifest_headers = [man_w.table_inhouse.horizontalHeaderItem(c).text() for c in range(man_w.table_inhouse.columnCount())]
        self.assertEqual(manifest_headers[0], "Room")
        self.assertEqual(manifest_headers[1], "Booking ID")
        self.assertEqual(manifest_headers[2], "Guest Name(s)")

        # Verify search filter on manifest table
        man_w.txt_search.setText("1111")
        man_w._filter_table()
        visible_1111 = [r for r in range(man_w.table_inhouse.rowCount()) if not man_w.table_inhouse.isRowHidden(r)]
        self.assertGreater(len(visible_1111), 0)

        man_w.txt_search.clear()
        man_w._filter_table()
        man_w.close()
        stats_w.close()

    # -------------------------------------------------------------------------
    # 19. StatsWidget Horizontal Scroll, Refresh Feedback, and Trace Reset
    # -------------------------------------------------------------------------
    def test_stats_scrolling_refresh_and_trace_engine(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QSizePolicy
        from MODULES.common.paths_config import DATABASE_DIR

        stats_w = StatsWidget()
        resort_dlg = ResortStatsDialog()

        # 1. Verify horizontal scrollbar policy is always off
        self.assertEqual(
            stats_w.analytics_scroll.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.assertEqual(
            resort_dlg.analytics_scroll.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # 2. Verify chart cards and canvases have expanding horizontal size policy
        for card in stats_w.chart_cards.values():
            self.assertEqual(card.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)
        for canvas in stats_w.chart_canvases.values():
            self.assertEqual(canvas.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)

        # 3. Test Refresh Stats Button feedback and recovery
        stats_w._on_refresh_stats_clicked()
        self.assertEqual(stats_w.btn_refresh.text(), "🔄 Refresh Stats")
        self.assertTrue(stats_w.btn_refresh.isEnabled())
        self.assertIn("Live State (Refreshed at", stats_w.lbl_status.text())

        # 4. Test Clear Trace and reset_traces
        self.assertIsNotNone(stats_w.btn_clear_trace)
        stats_w.active_trace_path = "non_existent_trace_file.xlsx"
        stats_w._on_clear_trace_file()
        self.assertIsNone(stats_w.active_trace_path)
        self.assertEqual(stats_w.lbl_trace_file.text(), "No trace file loaded")

        stats_w.active_trace_path = "another_trace.csv"
        stats_w.reset_traces(clear_file_path=True)
        self.assertIsNone(stats_w.active_trace_path)
        self.assertEqual(stats_w.lbl_trace_file.text(), "No trace file loaded")

        # 5. Test _fetch_all_stats_data does not auto-scan when active_trace_path is None
        stats_w.active_trace_path = None
        data = stats_w._fetch_all_stats_data()
        self.assertEqual(data.get("unified_dataset", {}).get("traces", []), [])

        # 6. Test purge_hotel_database cleans raw trace files and trace cache
        trace_dummy = os.path.join(DATABASE_DIR, "test_trace_export.xlsx")
        cache_dummy = os.path.join(DATABASE_DIR, "trace_cache.json")
        with open(trace_dummy, "w") as f:
            f.write("dummy trace content")
        with open(cache_dummy, "w") as f:
            f.write("{}")

        self.assertTrue(os.path.exists(trace_dummy))
        self.assertTrue(os.path.exists(cache_dummy))

        res = purge_hotel_database()
        self.assertTrue(res.get("success"))
        self.assertFalse(os.path.exists(trace_dummy))
        self.assertFalse(os.path.exists(cache_dummy))

        # 7. Test app cross-widget wiring
        app_main = GuestRelationApp()
        app_main.stats_widget.active_trace_path = "some_path.xlsx"
        app_main.config_widget.data_updated.emit()
        self.assertIsNone(app_main.stats_widget.active_trace_path)
        self.assertEqual(app_main.stats_widget.lbl_trace_file.text(), "No trace file loaded")

        stats_w.close()
        resort_dlg.close()
        app_main.close()


if __name__ == "__main__":
    unittest.main()



