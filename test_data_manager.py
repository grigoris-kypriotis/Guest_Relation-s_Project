"""
Unit tests for data_manager.py:
Tests In-House CSV parsing, grouping, meal-plan exclusion, room move detection,
check-in, check-out, Arrivals CSV parsing (Sandy Beach & Sandy Villas),
arrivals state management, and cleanup manager.
"""

import os
import json
import shutil
import tempfile
import unittest
from datetime import date

from data_manager import InHouseDataManager


class TestInHouseDataManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_inhouse_")
        self.master_state_path = os.path.join(self.test_dir, "master_state.json")
        self.state_meta_path = os.path.join(self.test_dir, "state_meta.json")
        self.arrivals_state_path = os.path.join(self.test_dir, "arrivals_state.json")
        self.trash_dir = os.path.join(self.test_dir, "TRASH")

        self.dm = InHouseDataManager(
            master_state_path=self.master_state_path,
            state_meta_path=self.state_meta_path,
            arrivals_state_path=self.arrivals_state_path,
            trash_dir=self.trash_dir
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

        # Sample Villas Arrivals CSV
        villas_csv = (
            '"112";;"MARGGRAF SILKE";"105,00";"4/9/2026 12:00:00 ";"85933";"P1P";"P1P";"OPEN TRAVEL SERVICES AG";"2";"0";;"0";"0";"0";"AI";"8:50 "\n'
            '"Reloc. from";;;;;;;;;;\n'
        )
        villas_path = os.path.join(self.test_dir, "ARRIVAL_LIST_SANDY_VILLAS_28-08-2026.csv")
        with open(villas_path, "w", encoding="utf-8-sig") as f:
            f.write(villas_csv)

        prop_villas, arrivals_villas = self.dm.parse_arrivals_csv(villas_path)
        self.assertEqual(prop_villas, "SANDY VILLAS")
        self.assertEqual(len(arrivals_villas), 1)
        self.assertEqual(arrivals_villas["85933"]["room"], "112")

        # Update Arrivals State for Villas
        self.dm.update_arrivals_state(prop_villas, arrivals_villas)

        # Verify combined state
        combined = self.dm.load_arrivals_state()
        self.assertEqual(len(combined["SANDY BEACH"]), 2)
        self.assertEqual(len(combined["SANDY VILLAS"]), 1)
        self.assertIn("83570", combined["SANDY BEACH"])
        self.assertIn("85933", combined["SANDY VILLAS"])

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

    def test_database_directory_structure_and_dismantle_subdirectories(self):
        from data_manager import (
            DATABASE_DIR, MASTER_STATE_PATH, STATE_META_PATH,
            CHECKOUT_HISTORY_PATH, ROOM_MOVES_HISTORY_PATH,
            BOOKING_CALLS_TODAY_DIR, ensure_workspace_directories
        )

        # 1. Verify paths are inside DATABASE_DIR
        self.assertTrue(MASTER_STATE_PATH.startswith(DATABASE_DIR))
        self.assertTrue(STATE_META_PATH.startswith(DATABASE_DIR))
        self.assertTrue(CHECKOUT_HISTORY_PATH.startswith(DATABASE_DIR))
        self.assertTrue(ROOM_MOVES_HISTORY_PATH.startswith(DATABASE_DIR))
        self.assertTrue(BOOKING_CALLS_TODAY_DIR.startswith(DATABASE_DIR))

        # 2. Verify history files filenames directly in DATABASE/
        self.assertEqual(os.path.basename(CHECKOUT_HISTORY_PATH), "check_out_history.json")
        self.assertEqual(os.path.basename(ROOM_MOVES_HISTORY_PATH), "room_moves_history.json")

        # 3. Verify that no subdirectories for checkout history or room moves history remain
        sub_checkout = os.path.join(DATABASE_DIR, "CHECKOUT HISTORY")
        sub_roommoves = os.path.join(DATABASE_DIR, "ROOM MOVES HISTORY")
        self.assertFalse(os.path.exists(sub_checkout), "CHECKOUT HISTORY directory should not exist")
        self.assertFalse(os.path.exists(sub_roommoves), "ROOM MOVES HISTORY directory should not exist")


if __name__ == "__main__":
    unittest.main()

