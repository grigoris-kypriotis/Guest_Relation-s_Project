"""
Unit & Regression Tests for Room Type Upgrade/Downgrade Rebuild
===============================================================
Tests:
  1. Two-page fixture CSV with shifted columns on page 2.
  2. Identity: upgrade + downgrade + exact_match + len(data_issues) == reservations_evaluated.
  3. All 8 ladder codes pre-seeded in booked_counts and assigned_counts.
  4. Empty-room-type routing to data_issues and exclusion from counters.
  5. 3-digit room filtering (Sandy Villas exclusion).
  6. Multi-guest-row deduplication and first-row pax preservation.
  7. Booking.com substring grouping in by_agency.
  8. Empty-input return dict specification.
  9. _resolve_todays_inhouse_backup resolution logic.
"""

import os
import csv
import time
import tempfile
import unittest
from unittest.mock import patch

from MODULES.room_type_ladder import ROOM_TYPE_LADDER
from MODULES.parsing.inhouse_csv_reader import parse_inhouse_csv, group_guest_rows_to_reservations
from MODULES.room_type_upgrade_downgrade import compute_room_type_upgrade_downgrade
from OPTIONS.stats_option import _resolve_todays_inhouse_backup


class TestRoomTypeUpgradeDowngradeRebuild(unittest.TestCase):
    """Test suite covering the 9 required upgrade/downgrade specifications."""

    def test_two_page_fixture_csv_shifted_columns(self):
        """
        1. Two-page fixture CSV: page 2 has an extra empty column after the room
        number, shifting later columns — assert parse_inhouse_csv reads page 2's
        data correctly (not shifted) using the header-name mapping.
        """
        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, "two_page.csv")
            with open(csv_path, "w", encoding="cp1253", newline="") as f:
                w = csv.writer(f, delimiter=";")
                # Page 1 header
                w.writerow([
                    "Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Τιμοκατάλογος", "Σύν. Ατόμων"
                ])
                # Page 1 data
                w.writerow(["1010", "Guest One", "10/09/2026", "17/09/2026", "DUK", "DUG", "TUI", "1001", "HB", "P1", "2"])

                # Page 2 header with extra empty column after room
                w.writerow([
                    "Δωμάτιο", "", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Τιμοκατάλογος", "Σύν. Ατόμων"
                ])
                # Page 2 data with shifted layout
                w.writerow(["2020", "", "Guest Two", "11/09/2026", "18/09/2026", "FSG", "F1G", "DERTOUR", "1002", "AI", "P2", "3"])

            guest_rows = parse_inhouse_csv(csv_path)
            self.assertEqual(len(guest_rows), 2)

            r2 = guest_rows[1]
            self.assertEqual(r2["room"], "2020")
            self.assertEqual(r2["guest"], "Guest Two")
            self.assertEqual(r2["arrival"], "11/09/2026")
            self.assertEqual(r2["departure"], "18/09/2026")
            self.assertEqual(r2["room_assigned"], "FSG")
            self.assertEqual(r2["room_booked"], "F1G")
            self.assertEqual(r2["agency"], "DERTOUR")
            self.assertEqual(r2["booking_id"], "1002")
            self.assertEqual(r2["meal_type"], "AI")
            self.assertEqual(r2["price_list"], "P2")
            self.assertEqual(r2["pax"], "3")

    def test_identity_upgrade_downgrade_exact_match_issues_equals_evaluated(self):
        """
        2. Identity test: for a fixture set of reservations, assert
        upgrade + downgrade + exact_match + len(data_issues) == reservations_evaluated.
        """
        reservations = [
            {"booking_id": "1", "room": "1001", "room_booked": "DUG", "room_assigned": "PJK", "agency": "Direct"},   # upgrade
            {"booking_id": "2", "room": "2001", "room_booked": "PJK", "room_assigned": "DUG", "agency": "Direct"},   # downgrade
            {"booking_id": "3", "room": "3001", "room_booked": "FSG", "room_assigned": "FSG", "agency": "Direct"},   # exact match
            {"booking_id": "4", "room": "4001", "room_booked": "", "room_assigned": "DUG", "agency": "Direct"},      # data issue (empty)
            {"booking_id": "5", "room": "5001", "room_booked": "UNK", "room_assigned": "DUG", "agency": "Direct"},   # data issue (unrecognized)
        ]

        result = compute_room_type_upgrade_downgrade(reservations)
        self.assertEqual(result["upgrade"], 1)
        self.assertEqual(result["downgrade"], 1)
        self.assertEqual(result["exact_match"], 1)
        self.assertEqual(len(result["data_issues"]), 2)
        self.assertEqual(result["reservations_evaluated"], 5)
        self.assertEqual(
            result["upgrade"] + result["downgrade"] + result["exact_match"] + len(result["data_issues"]),
            result["reservations_evaluated"]
        )

    def test_all_8_codes_pre_seeded_in_booked_and_assigned_counts(self):
        """
        3. All-8-codes test: assert booked_counts and assigned_counts always have
        exactly the 8 ROOM_TYPE_LADDER keys, even with a fixture containing only 2
        distinct codes.
        """
        reservations = [
            {"booking_id": "1", "room": "1001", "room_booked": "DUG", "room_assigned": "DUK", "agency": "TUI"}
        ]
        result = compute_room_type_upgrade_downgrade(reservations)
        expected_keys = set(ROOM_TYPE_LADDER.keys())
        self.assertEqual(set(result["booked_counts"].keys()), expected_keys)
        self.assertEqual(set(result["assigned_counts"].keys()), expected_keys)
        self.assertEqual(len(result["booked_counts"]), 8)
        self.assertEqual(len(result["assigned_counts"]), 8)
        self.assertEqual(result["booked_counts"]["DUG"], 1)
        self.assertEqual(result["assigned_counts"]["DUK"], 1)
        self.assertEqual(result["booked_counts"]["PJK"], 0)

    def test_empty_room_type_routing_to_data_issues(self):
        """
        4. Empty-room-type fixture: a reservation with an empty room_booked or
        room_assigned goes to data_issues with reason "empty_room_type" and is
        excluded from all three top-level counters.
        """
        reservations = [
            {"booking_id": "101", "room": "1010", "room_booked": "", "room_assigned": "DUG", "agency": "Alpha"},
            {"booking_id": "102", "room": "1020", "room_booked": "FSG", "room_assigned": "", "agency": "Beta"},
        ]
        result = compute_room_type_upgrade_downgrade(reservations)
        self.assertEqual(result["upgrade"], 0)
        self.assertEqual(result["downgrade"], 0)
        self.assertEqual(result["exact_match"], 0)
        self.assertEqual(len(result["data_issues"]), 2)
        for issue in result["data_issues"]:
            self.assertEqual(issue["reason"], "empty_room_type")
        self.assertEqual(result["by_agency"]["Alpha"]["issues"], 1)
        self.assertEqual(result["by_agency"]["Beta"]["issues"], 1)

    def test_three_digit_room_filtering(self):
        """
        5. 3-digit room fixture: rows with a 3-digit room number never reach
        group_guest_rows_to_reservations output at all.
        """
        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, "villas.csv")
            with open(csv_path, "w", encoding="cp1253", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow([
                    "Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Τιμοκατάλογος", "Σύν. Ατόμων"
                ])
                # 3-digit rooms (Sandy Villas) - should be skipped
                w.writerow(["101", "Villas Guest 1", "10/09/2026", "17/09/2026", "DUG", "DUG", "TUI", "901", "HB", "P1", "2"])
                w.writerow(["205", "Villas Guest 2", "10/09/2026", "17/09/2026", "DUK", "DUK", "TUI", "902", "HB", "P1", "2"])
                # 4-digit room (Sandy Beach) - should be kept
                w.writerow(["1010", "Beach Guest", "10/09/2026", "17/09/2026", "FSG", "FSG", "TUI", "903", "HB", "P1", "2"])

            guest_rows = parse_inhouse_csv(csv_path)
            self.assertEqual(len(guest_rows), 1)
            reservations = group_guest_rows_to_reservations(guest_rows)
            self.assertEqual(len(reservations), 1)
            self.assertEqual(reservations[0]["room"], "1010")

    def test_multi_guest_row_fixture_dedup_and_pax(self):
        """
        6. Multi-guest-row fixture: 4 guest rows sharing one Αρ. produce exactly ONE
        reservation, and its pax equals the FIRST row's pax value, not a sum and
        not a later row's value.
        """
        guest_rows = [
            {"booking_id": "RES777", "room": "1050", "guest": "Guest 1", "room_assigned": "PJK", "room_booked": "DUG", "agency": "TUI", "pax": "4"},
            {"booking_id": "RES777", "room": "1050", "guest": "Guest 2", "room_assigned": "PJK", "room_booked": "DUG", "agency": "TUI", "pax": "0"},
            {"booking_id": "RES777", "room": "1050", "guest": "Guest 3", "room_assigned": "PJK", "room_booked": "DUG", "agency": "TUI", "pax": "0"},
            {"booking_id": "RES777", "room": "1050", "guest": "Guest 4", "room_assigned": "PJK", "room_booked": "DUG", "agency": "TUI", "pax": "0"},
        ]
        reservations = group_guest_rows_to_reservations(guest_rows)
        self.assertEqual(len(reservations), 1)
        r = reservations[0]
        self.assertEqual(r["booking_id"], "RES777")
        self.assertEqual(r["pax"], "4")
        self.assertEqual(r["guest_count"], 4)

    def test_booking_com_agency_substring_grouping(self):
        """
        7. Booking.com fixture: an agency string like "BOOKING.COM LTD" or
        "somebooking.com-reseller" groups under the "Booking.com" key in by_agency
        (case-insensitive substring match).
        """
        reservations = [
            {"booking_id": "1", "room": "1001", "room_booked": "DUG", "room_assigned": "DUK", "agency": "BOOKING.COM LTD"},
            {"booking_id": "2", "room": "1002", "room_booked": "DUG", "room_assigned": "DUG", "agency": "somebooking.com-reseller"},
        ]
        result = compute_room_type_upgrade_downgrade(reservations)
        self.assertIn("Booking.com", result["by_agency"])
        bcom = result["by_agency"]["Booking.com"]
        self.assertEqual(bcom["upgrade"], 1)
        self.assertEqual(bcom["exact_match"], 1)

    def test_empty_input_specification(self):
        """
        8. Empty-input test: compute_room_type_upgrade_downgrade([]) returns exactly
        the specified empty-case dict, including by_agency containing only
        "Booking.com" at zero and by_block as an empty dict.
        """
        expected = {
            "upgrade": 0,
            "downgrade": 0,
            "exact_match": 0,
            "reservations_evaluated": 0,
            "booked_counts": {code: 0 for code in ROOM_TYPE_LADDER},
            "assigned_counts": {code: 0 for code in ROOM_TYPE_LADDER},
            "by_agency": {"Booking.com": {"upgrade": 0, "downgrade": 0, "exact_match": 0, "issues": 0}},
            "by_block": {},
            "data_issues": []
        }
        result = compute_room_type_upgrade_downgrade([])
        self.assertEqual(result, expected)

    def test_resolve_todays_inhouse_backup(self):
        """
        9. _resolve_todays_inhouse_backup test: with a temp DATA_BACKUP_DIR containing
        multiple files with different mtimes, assert it returns the most recently
        modified one; with an empty or missing directory, assert it returns None.
        """
        with tempfile.TemporaryDirectory() as td:
            # Case A: empty directory -> returns None
            with patch("OPTIONS.stats_option.DATA_BACKUP_DIR", td):
                self.assertIsNone(_resolve_todays_inhouse_backup())

                # Case B: multiple files -> returns newest by mtime
                f1 = os.path.join(td, "backup_old.csv")
                f2 = os.path.join(td, "backup_newest.csv")
                with open(f1, "w") as f:
                    f.write("old")
                time.sleep(0.05)
                with open(f2, "w") as f:
                    f.write("newest")

                resolved = _resolve_todays_inhouse_backup()
                self.assertEqual(resolved, f2)

            # Case C: non-existent directory -> returns None
            missing_dir = os.path.join(td, "does_not_exist")
            with patch("OPTIONS.stats_option.DATA_BACKUP_DIR", missing_dir):
                self.assertIsNone(_resolve_todays_inhouse_backup())


if __name__ == "__main__":
    unittest.main()
