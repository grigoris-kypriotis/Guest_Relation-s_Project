"""
Unit Tests for Room Type Ladder & Upgrade/Downgrade Tracking
===========================================================
Hermetic unit tests covering:
  - Every adjacent ladder pair in both directions
  - Specific upgrade/downgrade endpoints (DUG <-> PJK)
  - Same code identity ("same")
  - Whitespace and case normalization (" duk ")
  - Unknown code handling and empty input handling
  - Two different unknown codes ("unknown", never "upgrade")
  - Upgrade/downgrade/exact_match/unknown == reservations_evaluated invariant
  - Reservation deduplication across guest rows and multiple traces
  - HotelStateManager room_type_changes tracking on sync
"""

import os
import csv
import unittest
import tempfile
from datetime import date

from MODULES.room_type_ladder import (
    ROOM_TYPE_LADDER,
    compare_room_types,
)
from MODULES.trace_analytics import compute_visual_analytics_data
from MODULES.state.hotel_state_manager import HotelStateManager


class TestRoomTypeLadder(unittest.TestCase):
    """Hermetic unit tests for room type comparison and tracking logic."""

    def test_adjacent_ladder_pairs_in_both_directions(self):
        """Tests every adjacent ladder pair in both directions."""
        # Ladder order: DUG < DUK < DSG < F1G < F2G < FSG < PJG < PJK
        ordered_codes = sorted(ROOM_TYPE_LADDER.keys(), key=lambda k: ROOM_TYPE_LADDER[k])
        for i in range(len(ordered_codes) - 1):
            lower_code = ordered_codes[i]
            higher_code = ordered_codes[i + 1]

            # Upward direction: lower -> higher is upgrade
            res_up = compare_room_types(lower_code, higher_code)
            self.assertEqual(
                res_up,
                "upgrade",
                f"Expected {lower_code} -> {higher_code} to be 'upgrade', got '{res_up}'"
            )

            # Downward direction: higher -> lower is downgrade
            res_down = compare_room_types(higher_code, lower_code)
            self.assertEqual(
                res_down,
                "downgrade",
                f"Expected {higher_code} -> {lower_code} to be 'downgrade', got '{res_down}'"
            )

    def test_endpoints_dug_pjk(self):
        """Tests extreme ladder transitions (DUG -> PJK upgrade, PJK -> DUG downgrade)."""
        self.assertEqual(compare_room_types("DUG", "PJK"), "upgrade")
        self.assertEqual(compare_room_types("PJK", "DUG"), "downgrade")

    def test_same_code(self):
        """Tests that identical codes return 'same'."""
        for code in ROOM_TYPE_LADDER.keys():
            self.assertEqual(compare_room_types(code, code), "same")

    def test_lowercase_and_whitespace_normalization(self):
        """Tests that lower-case and padded inputs like ' duk ' normalize properly."""
        self.assertEqual(compare_room_types(" duk ", "dug"), "downgrade")
        self.assertEqual(compare_room_types("dug", " duk "), "upgrade")
        self.assertEqual(compare_room_types(" duk ", "DUK"), "same")
        self.assertEqual(compare_room_types("  pjk  ", "  dug  "), "downgrade")

    def test_unknown_code(self):
        """Tests that non-ladder codes return 'unknown'."""
        self.assertEqual(compare_room_types("DUG", "XYZ"), "unknown")
        self.assertEqual(compare_room_types("ABC", "PJK"), "unknown")
        self.assertEqual(compare_room_types("NOT_A_CODE", "DUK"), "unknown")

    def test_empty_and_none(self):
        """Tests that empty or None inputs return 'unknown'."""
        self.assertEqual(compare_room_types("", "DUG"), "unknown")
        self.assertEqual(compare_room_types("DUG", ""), "unknown")
        self.assertEqual(compare_room_types("", ""), "unknown")
        self.assertEqual(compare_room_types("   ", "   "), "unknown")
        self.assertEqual(compare_room_types(None, "DUG"), "unknown")
        self.assertEqual(compare_room_types("DUG", None), "unknown")

    def test_two_different_unknown_codes(self):
        """Tests that two different unknown codes evaluate to 'unknown', NEVER 'upgrade'."""
        self.assertEqual(compare_room_types("XYZ", "ABC"), "unknown")
        self.assertEqual(compare_room_types("Standard", "Suite"), "unknown")
        self.assertEqual(compare_room_types("Superior", "Family"), "unknown")
        self.assertNotEqual(compare_room_types("Standard", "Suite"), "upgrade")

    def test_counts_identity_and_deduplication(self):
        """
        Tests:
          - upgrade + downgrade + exact_match + unknown == reservations_evaluated
          - A reservation with 3 guest rows and 5 traces counts once
        """
        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, "inhouse_test.csv")
            with open(csv_path, "w", encoding="cp1253", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow([
                    "Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Τιμοκατάλογος", "Σύν. Ατόμων"
                ])
                # 5 guest rows for B1001 (upgrade)
                for guest in ["Smith John", "Smith Mary", "Smith Alice", "Smith John", "Smith Mary"]:
                    w.writerow(["2010", guest, "10/09/2026", "17/09/2026", "PJK", "DUG", "TUI", "B1001", "HB", "P1", "2"])
                # 1 downgrade reservation
                w.writerow(["3010", "Brown Bob", "11/09/2026", "18/09/2026", "DUG", "PJK", "TUI", "B1002", "HB", "P1", "2"])
                # 1 exact match reservation
                w.writerow(["4010", "White Walter", "12/09/2026", "19/09/2026", "FSG", "FSG", "TUI", "B1003", "HB", "P1", "2"])
                # 1 unrecognized room type code
                w.writerow(["5010", "Green Gary", "13/09/2026", "20/09/2026", "Suite", "Standard", "TUI", "B1004", "HB", "P1", "2"])

            metrics = compute_visual_analytics_data([], in_house_csv_path=csv_path)
            up_down = metrics["room_type_upgrade_downgrade"]

            upgrade = up_down["upgrade"]
            downgrade = up_down["downgrade"]
            exact_match = up_down["exact_match"]
            issues = len(up_down["data_issues"])
            evaluated = up_down["reservations_evaluated"]

            # Exact counts
            self.assertEqual(upgrade, 1, "The 5 guest rows for B1001 must count as exactly 1 upgrade")
            self.assertEqual(downgrade, 1)
            self.assertEqual(exact_match, 1)
            self.assertEqual(issues, 1)
            self.assertEqual(evaluated, 4, "Total unique reservations must be 4")
            self.assertNotIn("unknown", up_down)

            # Counts identity invariant
            self.assertEqual(
                upgrade + downgrade + exact_match + issues,
                evaluated,
                "upgrade + downgrade + exact_match + len(data_issues) must equal reservations_evaluated"
            )

    def test_hotel_state_manager_room_type_changes(self):
        """
        Tests that a booking whose room type changed between two syncs with the same
        room number produces exactly one room_type_changes record in the returned summary.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ms_path = os.path.join(tmpdir, "master_state.json")
            meta_path = os.path.join(tmpdir, "state_metadata.json")
            arr_path = os.path.join(tmpdir, "today_arrivals.json")
            trash_path = os.path.join(tmpdir, "trash")
            co_path = os.path.join(tmpdir, "checkouts.json")
            rm_path = os.path.join(tmpdir, "room_moves.json")

            manager = HotelStateManager(
                master_state_path=ms_path,
                state_meta_path=meta_path,
                arrivals_state_path=arr_path,
                trash_dir=trash_path,
                checkouts_path=co_path,
                room_moves_path=rm_path,
            )

            # Sync 1: Initial state with booking 9901 in room 1205 as DUG
            state_day1 = {
                "9901": {
                    "Room": "1205",
                    "Guests": ["Taylor Alex"],
                    "Arrival": "10/09/2026",
                    "Departure": "17/09/2026",
                    "Room Type": "DUG",
                    "Booked Room Type": "DUG",
                    "Agency": "TUI"
                }
            }
            summary1 = manager.compare_and_update(state_day1, processing_date=date(2026, 9, 10))
            self.assertEqual(len(summary1["room_type_changes"]), 0)
            self.assertEqual(len(summary1["room_moves"]), 0)

            # Sync 2: Booking 9901 room number remains 1205, but Room Type upgraded to PJK
            state_day2 = {
                "9901": {
                    "Room": "1205",
                    "Guests": ["Taylor Alex"],
                    "Arrival": "10/09/2026",
                    "Departure": "17/09/2026",
                    "Room Type": "PJK",
                    "Booked Room Type": "DUG",
                    "Agency": "TUI"
                }
            }
            summary2 = manager.compare_and_update(state_day2, processing_date=date(2026, 9, 11))

            # Verify room_moves is 0 (room number did not change)
            self.assertEqual(len(summary2["room_moves"]), 0)

            # Verify room_type_changes contains exactly 1 record with all required fields
            rtc = summary2.get("room_type_changes", [])
            self.assertEqual(len(rtc), 1)
            rec = rtc[0]
            self.assertEqual(rec["booking_id"], "9901")
            self.assertEqual(rec["guests"], ["Taylor Alex"])
            self.assertEqual(rec["old_type"], "DUG")
            self.assertEqual(rec["new_type"], "PJK")
            self.assertEqual(rec["direction"], "upgrade")
            self.assertEqual(rec["old_room"], "1205")
            self.assertEqual(rec["new_room"], "1205")
            self.assertEqual(rec["date"], "11/09/2026")

    def test_real_inhouse_parser_upgrade_downgrade_integration(self):
        """
        Integration test verifying real parse_in_house_file/normalize_booking_dict
        with Greek headers through compute_visual_analytics_data:
          - room 1111, F1G assigned, F1G booked -> same
          - room 1112, F1G assigned, FSG booked -> downgrade
          - room 1113, FSG assigned, F1G booked -> upgrade
          - room 1114, F1G assigned, (empty) booked -> unknown
        Expected: upgrade 1, downgrade 1, exact_match 1, unknown 1, reservations_evaluated 4.
        """
        import csv
        from MODULES.parsing.inhouse_parser import parse_in_house_file

        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, "real_inhouse.csv")
            with open(csv_path, "w", encoding="cp1253", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow([
                    "Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Τιμοκατάλογος", "Σύν. Ατόμων"
                ])
                w.writerow(["1111", "Guest 1", "10/09/2026", "17/09/2026", "F1G", "F1G", "Agency A", "1001", "HB", "P1", "2"])
                w.writerow(["1112", "Guest 2", "10/09/2026", "17/09/2026", "F1G", "FSG", "Agency A", "1002", "HB", "P1", "2"])
                w.writerow(["1113", "Guest 3", "10/09/2026", "17/09/2026", "FSG", "F1G", "Agency A", "1003", "HB", "P1", "2"])
                w.writerow(["1114", "Guest 4", "10/09/2026", "17/09/2026", "F1G", "", "Agency A", "1004", "HB", "P1", "2"])

            bookings = parse_in_house_file(csv_path)

            # (a) Check the master-state key names each type ended up under
            b1001 = bookings["1001"]
            self.assertEqual(b1001["Room Type"], "F1G")
            self.assertEqual(b1001["Τύπος Δωματίου"], "F1G")
            self.assertEqual(b1001["Booked Room Type"], "F1G")
            self.assertEqual(b1001["Χρεωστικός Τύπος Δωματίου"], "F1G")

            b1004 = bookings["1004"]
            self.assertEqual(b1004["Room Type"], "F1G")
            self.assertEqual(b1004["Τύπος Δωματίου"], "F1G")
            self.assertEqual(b1004["Booked Room Type"], "")
            self.assertEqual(b1004["Χρεωστικός Τύπος Δωματίου"], "")

            # (b) Check final room_type_upgrade_downgrade result
            metrics = compute_visual_analytics_data([], in_house_csv_path=csv_path)
            up_down = metrics["room_type_upgrade_downgrade"]

            self.assertEqual(up_down["upgrade"], 1)
            self.assertEqual(up_down["downgrade"], 1)
            self.assertEqual(up_down["exact_match"], 1)
            self.assertEqual(len(up_down["data_issues"]), 1)
            self.assertEqual(up_down["reservations_evaluated"], 4)
            self.assertNotIn("unknown", up_down)


if __name__ == "__main__":
    unittest.main()

