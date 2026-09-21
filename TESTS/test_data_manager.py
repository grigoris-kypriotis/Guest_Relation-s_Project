"""
Unit tests for data_manager.py:
Tests In-House CSV parsing, grouping, meal-plan exclusion, room move detection,
check-in, check-out, Arrivals CSV parsing (Sandy Beach),
arrivals state management, and cleanup manager.
"""

import os
import json
import shutil
import tempfile
import unittest
from datetime import date
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from MODULES.data_manager import InHouseDataManager


class TestInHouseDataManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_inhouse_")
        self.master_state_path = os.path.join(self.test_dir, "master_state.json")
        self.state_meta_path = os.path.join(self.test_dir, "state_meta.json")
        self.arrivals_state_path = os.path.join(self.test_dir, "arrivals_state.json")
        self.trash_dir = os.path.join(self.test_dir, "TRASH")
        self.checkouts_path = os.path.join(self.test_dir, "checkouts.json")
        self.room_moves_path = os.path.join(self.test_dir, "room_moves.json")

        self.dm = InHouseDataManager(
            master_state_path=self.master_state_path,
            state_meta_path=self.state_meta_path,
            arrivals_state_path=self.arrivals_state_path,
            trash_dir=self.trash_dir,
            checkouts_path=self.checkouts_path,
            room_moves_path=self.room_moves_path
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_inhouse_csv_grouping_and_exclusion(self):
        csv_content = (
            '"Αρ.";"Δωμάτιο";"Άφιξη";"Αναχώρηση";"Τύπος Δωματίου";"Χρεωστικός Τύπος Δωματίου";"Χρεώστης";"Τιμοκατάλογος";"Σύν. Ατόμων";"Τύπος Γεύματος";"Πελάτης"\n'
            '"56995";"1101";"10/9/2026";"17/9/2026";"F1G";"F1G";"TUI FRANCE";"TUI FRANCE 2026";"2";"AI";"Vaglio Fabrice Jean Jacques"\n'
            '"56995";"1101";"10/9/2026";"17/9/2026";"F1G";"F1G";"TUI FRANCE";"TUI FRANCE 2026";"2";"AI";"Lesache Huguette Irma"\n'
            '"84317";"1205";"02/9/2026";"15/9/2026";"F1G";"F1G";"EXPEDIA";"EXPEDIA 2026";"1";"HB";"Alik Nataliia"\n'
        )
        csv_path = os.path.join(self.test_dir, "inhouse_day1.csv")
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write(csv_content)

        parsed = self.dm.parse_in_house_csv(csv_path)

        # 1. Booking ID key existence
        self.assertIn("56995", parsed)
        self.assertIn("84317", parsed)

        # 2. Meal Plan column excluded
        self.assertNotIn("Τύπος Γεύματος", parsed["56995"])
        self.assertNotIn("meal plan", [k.lower() for k in parsed["56995"].keys()])

        # 3. Guests grouped into list
        self.assertEqual(len(parsed["56995"]["Πελάτες"]), 2)
        self.assertEqual(parsed["56995"]["Πελάτες"][0], "Vaglio Fabrice Jean Jacques")
        self.assertEqual(parsed["56995"]["Πελάτες"][1], "Lesache Huguette Irma")

        # 4. Other columns preserved
        self.assertEqual(parsed["56995"]["Δωμάτιο"], "1101")
        self.assertEqual(parsed["56995"]["Χρεώστης"], "TUI FRANCE")
        self.assertEqual(parsed["56995"]["Σύν. Ατόμων"], "2")

    def test_room_move_detection_and_checkout(self):
        day1_csv = (
            '"Αρ.";"Δωμάτιο";"Άφιξη";"Αναχώρηση";"Πελάτης"\n'
            '"56995";"1101";"10/9/2026";"17/9/2026";"Vaglio Fabrice"\n'
            '"84317";"1205";"02/9/2026";"15/9/2026";"Alik Nataliia"\n'
        )
        csv_path1 = os.path.join(self.test_dir, "inhouse_day1.csv")
        with open(csv_path1, "w", encoding="utf-8-sig") as f:
            f.write(day1_csv)

        parsed1 = self.dm.parse_in_house_csv(csv_path1)
        summary1 = self.dm.compare_and_update(parsed1, processing_date=date(2026, 9, 10))

        self.assertEqual(len(summary1["check_ins"]), 2)
        self.assertEqual(len(summary1["room_moves"]), 0)
        self.assertEqual(len(summary1["check_outs"]), 0)

        state1 = self.dm.load_master_state()
        self.assertEqual(state1["56995"]["Δωμάτιο"], "1101")
        self.assertEqual(self.dm.get_last_processed_date(), date(2026, 9, 10))

        # Day 2:
        # - 56995 moves from Room 1101 to 1402 (ROOM MOVE)
        # - 84317 checked out (absent from CSV) (CHECK-OUT)
        # - 99001 arrives in Room 1101 (CHECK-IN)
        day2_csv = (
            '"Αρ.";"Δωμάτιο";"Άφιξη";"Αναχώρηση";"Πελάτης"\n'
            '"56995";"1402";"10/9/2026";"17/9/2026";"Vaglio Fabrice"\n'
            '"99001";"1101";"11/9/2026";"18/9/2026";"Smith John"\n'
        )
        csv_path2 = os.path.join(self.test_dir, "inhouse_day2.csv")
        with open(csv_path2, "w", encoding="utf-8-sig") as f:
            f.write(day2_csv)

        parsed2 = self.dm.parse_in_house_csv(csv_path2)
        summary2 = self.dm.compare_and_update(parsed2, processing_date=date(2026, 9, 11))

        self.assertEqual(len(summary2["room_moves"]), 1)
        rm = summary2["room_moves"][0]
        self.assertEqual(rm["booking_id"], "56995")
        self.assertEqual(rm["old_room"], "1101")
        self.assertEqual(rm["new_room"], "1402")

        self.assertEqual(len(summary2["check_outs"]), 1)
        self.assertEqual(summary2["check_outs"][0]["booking_id"], "84317")

        self.assertEqual(len(summary2["check_ins"]), 1)
        self.assertEqual(summary2["check_ins"][0]["booking_id"], "99001")

        state2 = self.dm.load_master_state()
        self.assertEqual(state2["56995"]["Δωμάτιο"], "1402")
        self.assertNotIn("84317", state2)
        self.assertIn("99001", state2)

    def test_arrivals_parsing_and_state_management(self):
        # Sample Beach Arrivals CSV
        beach_csv = (
            '"";;"Nazari Samira";"90,00";"3/9/2026 12:00:00 ";"83570";"F1G";"DUG";"EXPEDIA";"2";"0";;"1";"0";"0";"AI";"2:00 "\n'
            '"ONLY TAX (was in room 1411)";;;;;;;;;;\n'
            '\n'
            '"1205";;"Alik Nataliia";"75,00";"2/9/2026 12:00:00 ";"84317";"F1G";"F1G";"EXPEDIA";"3";"0";;"1";"0";"0";"AI";"2:00 "\n'
            '"only tax";;;;;;;;;;\n'
        )
        beach_path = os.path.join(self.test_dir, "ARRIVAL_LIST_SANDY_BEACH_28-08-2026.csv")
        with open(beach_path, "w", encoding="utf-8-sig") as f:
            f.write(beach_csv)

        prop, arrivals_beach = self.dm.parse_arrivals_csv(beach_path)
        self.assertEqual(prop, "SANDY BEACH")
        self.assertEqual(len(arrivals_beach), 2)
        self.assertIn("83570", arrivals_beach)
        self.assertEqual(arrivals_beach["83570"]["room"], "1411")  # Extracted from notes
        self.assertEqual(arrivals_beach["84317"]["room"], "1205")

        # Update Arrivals State for Beach
        self.dm.update_arrivals_state(prop, arrivals_beach)

        # Verify state
        combined = self.dm.load_arrivals_state()
        self.assertEqual(len(combined["SANDY BEACH"]), 2)
        self.assertIn("83570", combined["SANDY BEACH"])

    def test_cleanup_manager_both_file_types(self):
        test_inhouse = os.path.join(self.test_dir, "daily_inhouse.csv")
        test_arrivals = os.path.join(self.test_dir, "daily_arrivals.csv")
        with open(test_inhouse, "w") as f:
            f.write("test inhouse")
        with open(test_arrivals, "w") as f:
            f.write("test arrivals")

        dest1 = self.dm.cleanup_file(test_inhouse, mode="trash")
        dest2 = self.dm.cleanup_file(test_arrivals, mode="trash")

        self.assertFalse(os.path.exists(test_inhouse))
        self.assertFalse(os.path.exists(test_arrivals))
        self.assertTrue(os.path.exists(dest1))
        self.assertTrue(os.path.exists(dest2))

    def test_database_directory_structure_and_designated_subdirectories(self):
        from MODULES.data_manager import (
            DATABASE_DIR, HOTEL_STATE_DIR, MASTER_STATE_PATH, STATE_META_PATH,
            CHECKOUT_HISTORY_DIR, CHECKOUTS_JSON,
            ROOM_MOVES_DIR, ROOM_MOVES_JSON,
            SANDY_BEACH_ARRIVALS_DIR, ARRIVALS_BEACH_PATH,
            BOOKING_CALLS_TODAY_DIR, BOOKING_CALLS_TODAY_JSON,
            ensure_workspace_directories
        )

        ensure_workspace_directories()

        # 1. Verify paths are inside DATABASE_DIR
        self.assertTrue(MASTER_STATE_PATH.startswith(DATABASE_DIR))
        self.assertTrue(STATE_META_PATH.startswith(DATABASE_DIR))
        self.assertTrue(CHECKOUTS_JSON.startswith(DATABASE_DIR))
        self.assertTrue(ROOM_MOVES_JSON.startswith(DATABASE_DIR))
        self.assertTrue(ARRIVALS_BEACH_PATH.startswith(DATABASE_DIR))
        self.assertTrue(BOOKING_CALLS_TODAY_JSON.startswith(DATABASE_DIR))

        # 2. Verify state files reside in HOTEL STATE/
        self.assertEqual(os.path.dirname(MASTER_STATE_PATH), HOTEL_STATE_DIR)
        self.assertEqual(os.path.dirname(STATE_META_PATH), HOTEL_STATE_DIR)

        # 3. Verify domain archives reside in designated subdirectories
        self.assertEqual(os.path.dirname(CHECKOUTS_JSON), CHECKOUT_HISTORY_DIR)
        self.assertEqual(os.path.basename(CHECKOUT_HISTORY_DIR).upper(), "CHECK OUT HISTORY")

        self.assertEqual(os.path.dirname(ROOM_MOVES_JSON), ROOM_MOVES_DIR)
        self.assertEqual(os.path.basename(ROOM_MOVES_DIR).upper(), "ROOM MOVES")

        self.assertEqual(os.path.dirname(ARRIVALS_BEACH_PATH), SANDY_BEACH_ARRIVALS_DIR)
        self.assertTrue(os.path.exists(CHECKOUT_HISTORY_DIR))
        self.assertTrue(os.path.exists(ROOM_MOVES_DIR))

        # 4. Verify canonical files exist inside designated subdirectories
        self.assertTrue(os.path.exists(MASTER_STATE_PATH))
        self.assertTrue(os.path.exists(STATE_META_PATH))
        self.assertTrue(os.path.exists(CHECKOUTS_JSON))
        self.assertTrue(os.path.exists(ROOM_MOVES_JSON))

    def test_room_merge_detection_and_exclusion(self):
        # Day 1: Two separate bookings in rooms 1101 and 1102
        day1_bookings = {
            "5001": {"Δωμάτιο": "1101", "Πελάτες": ["Guest A"], "Άφιξη": "10/09/2026", "Αναχώρηση": "17/09/2026"},
            "5002": {"Δωμάτιο": "1102", "Πελάτες": ["Guest B"], "Άφιξη": "10/09/2026", "Αναχώρηση": "17/09/2026"},
            "5003": {"Δωμάτιο": "1201", "Πελάτες": ["Guest C"], "Άφιξη": "10/09/2026", "Αναχώρηση": "17/09/2026"}
        }
        self.dm.save_master_state(day1_bookings)

        # Day 2:
        # - 5001 and 5002 both move into Room 1300 (MERGE!)
        # - 5003 moves into Room 1205 (REGULAR ROOM MOVE)
        day2_bookings = {
            "5001": {"Δωμάτιο": "1300", "Πελάτες": ["Guest A"], "Άφιξη": "10/09/2026", "Αναχώρηση": "17/09/2026"},
            "5002": {"Δωμάτιο": "1300", "Πελάτες": ["Guest B"], "Άφιξη": "10/09/2026", "Αναχώρηση": "17/09/2026"},
            "5003": {"Δωμάτιο": "1205", "Πελάτες": ["Guest C"], "Άφιξη": "10/09/2026", "Αναχώρηση": "17/09/2026"}
        }

        summary = self.dm.compare_and_update(day2_bookings, processing_date=date(2026, 9, 11))

        # Merges must be detected (2 booking candidate moves merged into Room 1300)
        self.assertIn("room_merges", summary)
        self.assertEqual(len(summary["room_merges"]), 2)
        for merge in summary["room_merges"]:
            self.assertEqual(merge["new_room"], "1300")
            self.assertTrue(merge.get("is_room_merge"))
        
        merged_ids = {m["booking_id"] for m in summary["room_merges"]}
        self.assertEqual(merged_ids, {"5001", "5002"})

        # Room moves must EXCLUDE merged rooms (only 5003 should be in room_moves)
        self.assertEqual(len(summary["room_moves"]), 1)
        self.assertEqual(summary["room_moves"][0]["booking_id"], "5003")
        self.assertEqual(summary["room_moves"][0]["new_room"], "1205")

    def test_parse_headerless_inhouse_csv(self):
        csv_content = (
            '"1101";"Vaglio Fabrice Jean Jacques";"10/9/2026";"17/9/2026";"F1G";"F1G";"TUI FRANCE";"56995";"AI";"TUI FRANCE 2026";"0"\n'
            '"1101";"Lesache Huguette Irma";"10/9/2026";"17/9/2026";"F1G";"F1G";"TUI FRANCE";"56995";"AI";"TUI FRANCE 2026";"2"\n'
            '"1102";"Macavei Alina";"9/9/2026";"16/9/2026";"F1G";"DUG";"RAINBOW TOURS S.A.";"74358";"AI";"RAINBOW 2026";"2"\n'
        )
        csv_path = os.path.join(self.test_dir, "headerless_inhouse.csv")
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write(csv_content)

        parsed = self.dm.parse_in_house_csv(csv_path)
        self.assertIn("56995", parsed)
        self.assertIn("74358", parsed)
        self.assertEqual(parsed["56995"]["Δωμάτιο"], "1101")
        self.assertEqual(len(parsed["56995"]["Πελάτες"]), 2)

    def test_save_and_archive_json(self):
        from MODULES.data_manager import (
            save_and_archive_json, DATABASE_DIR,
            CHECKOUT_HISTORY_DIR, ROOM_MOVES_DIR, BOOKING_CALLS_TODAY_DIR, HOTEL_STATE_DIR
        )

        test_payload = {
            "title": "Test Archiving",
            "count": 42,
            "characters": "Ελληνικά / UTF-8 & Special Chars: öäü"
        }

        # 1. Save directly with auto-routing to HOTEL STATE/
        saved_path = save_and_archive_json(test_payload, "master_state.json", base_dir=self.test_dir)
        self.assertTrue(os.path.exists(saved_path))
        self.assertEqual(os.path.dirname(saved_path), os.path.join(self.test_dir, "HOTEL STATE"))

        # Verify UTF-8 formatting and indentation
        with open(saved_path, "r", encoding="utf-8") as f:
            content = f.read()
            loaded = json.loads(content)
            self.assertEqual(loaded["count"], 42)
            self.assertIn("Ελληνικά", content)
            self.assertIn("\n    ", content)  # 4 spaces indentation

        # 2. Save with explicit subfolder in isolated test directory
        sub_saved_path = save_and_archive_json(test_payload, "test_sub_record.json", subfolder="CHECK OUT HISTORY", base_dir=self.test_dir)
        self.assertTrue(os.path.exists(sub_saved_path))
        self.assertEqual(os.path.basename(os.path.dirname(sub_saved_path)).upper(), "CHECK OUT HISTORY")

        # 3. Automatic routing without explicit subfolder in isolated test directory
        auto_co = save_and_archive_json(test_payload, "checkouts.json", base_dir=self.test_dir)
        self.assertEqual(os.path.basename(os.path.dirname(auto_co)).upper(), "CHECK OUT HISTORY")

        auto_rm = save_and_archive_json(test_payload, "room_moves.json", base_dir=self.test_dir)
        self.assertEqual(os.path.basename(os.path.dirname(auto_rm)).upper(), "ROOM MOVES")

        auto_bc = save_and_archive_json(test_payload, "booking_calls_for_today.json", base_dir=self.test_dir)
        self.assertEqual(os.path.basename(os.path.dirname(auto_bc)).upper(), "BOOKING CALLS FOR TODAY")

    def test_template_resolution_protocol(self):
        from MODULES.data_manager import resolve_template_path, TEMPLATES_DIR
        # 1. Booking calls template
        bc_tpl = resolve_template_path("booking_calls")
        self.assertIsNotNone(bc_tpl)
        self.assertTrue(bc_tpl.lower().endswith(".xlsx"))
        self.assertIn("booking calls template", bc_tpl.lower())

        # 2. Offer list template
        ol_tpl = resolve_template_path("offer_list")
        self.assertIsNotNone(ol_tpl)
        self.assertTrue(ol_tpl.lower().endswith(".docx"))
        self.assertIn("offer list template", ol_tpl.lower())

        # 3. Check memo template with cake memo fallback
        cm_tpl = resolve_template_path("check_memo")
        self.assertIsNotNone(cm_tpl)
        self.assertTrue(cm_tpl.lower().endswith(".docx"))
        self.assertTrue("check memo template" in cm_tpl.lower() or "cake memo template" in cm_tpl.lower())

    def test_property_abstraction_and_schema_tagging(self):
        from MODULES.data_manager import (
            get_property_dir, get_property_arrivals_path, get_property_departures_path,
            CHECKOUTS_JSON
        )
        beach_dir = get_property_dir("sandy_beach")
        self.assertTrue(str(beach_dir).lower().endswith("sandy beach"))

        beach_arr = get_property_arrivals_path("sandy_beach")
        self.assertTrue(str(beach_arr).lower().endswith(os.path.join("arrivals", "today_arrivals.json").lower()))

        beach_dep = get_property_departures_path("sandy_beach")
        self.assertTrue(str(beach_dep).lower().endswith(os.path.join("departure", "departures_today.json").lower()))

        # Checkouts property tagging verification
        from unittest.mock import patch, mock_open
        mock_co = '{"property": "sandy_beach", "records": [], "total_records": 0}'
        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open(read_data=mock_co)):
            co_data = self.dm.load_checkouts_history()
            self.assertIn("property", co_data)
            self.assertEqual(co_data["property"], "sandy_beach")
            self.assertIn("records", co_data)

    def test_get_missing_dates_with_configured_sync_date(self):
        # 1. When last_sync_date is None, returns reference_date (today)
        ref_date = date(2026, 9, 16)
        self.assertEqual(self.dm.get_missing_dates(reference_date=ref_date), [ref_date])

        # 2. When last_sync_date is configured (e.g. 2026-09-13), returns sequence starting from next day
        self.dm.save_metadata({"last_sync_date": "2026-09-13", "total_bookings": 0})
        missing = self.dm.get_missing_dates(reference_date=ref_date)
        self.assertEqual(missing, [date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16)])

        # 3. When last_sync_date >= reference_date, returns empty list
        self.dm.save_metadata({"last_sync_date": "2026-09-16", "total_bookings": 100})
        self.assertEqual(self.dm.get_missing_dates(reference_date=ref_date), [])


if __name__ == "__main__":
    unittest.main()

