"""
Unit and regression tests for In-House parser (MODULES/parsing/inhouse_parser.py).
Tests multi-page CSV exports with column shifts, repeated headers, single-page,
and headerless fallbacks. Hermetic test environment using temporary directories.
"""

import os
import csv
import tempfile
import unittest

from MODULES.parsing.inhouse_parser import parse_in_house_csv, process_in_house_rows


class TestInHouseParserHeaderHandling(unittest.TestCase):
    """Test suite for header detection and page-shift resilience in process_in_house_rows."""

    def test_two_page_shifted_header_correct_field_alignment(self):
        """
        Test 1: Two-page fixture CSV where page 2's header row has an extra empty
        column after the first column (reproducing real PMS export shift), followed
        by data rows in the shifted layout.
        Assert page 2 data rows are parsed with CORRECT field values without misalignment.
        """
        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, "two_page_shifted.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";")
                # Page 1 Header (standard layout)
                w.writerow([
                    "Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Αγορά", "Σύν. Ατόμων"
                ])
                # Page 1 Data Row
                w.writerow([
                    "1010", "John Doe", "10/09/2026", "17/09/2026",
                    "DUK", "DUG", "TUI", "1001", "HB", "UK", "2"
                ])
                # Page 2 Repeated Header (shifted by 1 extra empty column after col 0)
                w.writerow([
                    "Δωμάτιο", "", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Αγορά", "Σύν. Ατόμων"
                ])
                # Page 2 Data Row (shifted layout matching repeated header)
                w.writerow([
                    "1020", "", "Jane Smith", "11/09/2026", "18/09/2026",
                    "FSG", "F1G", "DERTOUR", "1002", "AI", "DE", "2"
                ])

            bookings = parse_in_house_csv(csv_path)

            # Assert both reservations exist
            self.assertIn("1001", bookings)
            self.assertIn("1002", bookings)

            # Assert page 2 data row field values landed in the correct canonical keys
            b2 = bookings["1002"]
            self.assertEqual(b2["Booking ID"], "1002")
            self.assertEqual(b2["Room"], "1020")
            self.assertEqual(b2["Guests"], ["Jane Smith"])
            self.assertEqual(b2["Room Type"], "FSG")
            self.assertEqual(b2["Τύπος Δωματίου"], "FSG")
            self.assertEqual(b2["Booked Room Type"], "F1G")
            self.assertEqual(b2["Χρεωστικός Τύπος Δωματίου"], "F1G")
            self.assertEqual(b2["Agency"], "DERTOUR")
            self.assertEqual(b2["Arrival"], "11/09/2026")
            self.assertEqual(b2["Departure"], "18/09/2026")
            self.assertEqual(b2["Market"], "DE")

            # Also verify page 1 data row remains intact
            b1 = bookings["1001"]
            self.assertEqual(b1["Booking ID"], "1001")
            self.assertEqual(b1["Room"], "1010")
            self.assertEqual(b1["Guests"], ["John Doe"])
            self.assertEqual(b1["Room Type"], "DUK")
            self.assertEqual(b1["Booked Room Type"], "DUG")
            self.assertEqual(b1["Agency"], "TUI")

    def test_two_page_repeated_header_no_spurious_booking_entry(self):
        """
        Test 2: Regression test using the two-page fixture: assert that page 2's
        repeated header row itself does NOT appear as a spurious booking entry
        in the output dict.
        """
        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, "two_page_repeated_header.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow([
                    "Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Αγορά", "Σύν. Ατόμων"
                ])
                w.writerow([
                    "1010", "John Doe", "10/09/2026", "17/09/2026",
                    "DUK", "DUG", "TUI", "1001", "HB", "UK", "2"
                ])
                w.writerow([
                    "Δωμάτιο", "", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Αγορά", "Σύν. Ατόμων"
                ])
                w.writerow([
                    "1020", "", "Jane Smith", "11/09/2026", "18/09/2026",
                    "FSG", "F1G", "DERTOUR", "1002", "AI", "DE", "2"
                ])

            bookings = parse_in_house_csv(csv_path)

            # Exactly the two real bookings should be present; no spurious entries from the repeated header
            self.assertEqual(len(bookings), 2)
            self.assertEqual(set(bookings.keys()), {"1001", "1002"})
            for spurious_key in ["Αρ.", "Booking ID", "Δωμάτιο", ""]:
                self.assertNotIn(spurious_key, bookings)

    def test_single_page_normal_case_parsing_unchanged(self):
        """
        Test 3: Single-page fixture (no repeated header) to confirm normal-case
        parsing is unchanged from before this fix.
        """
        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, "single_page.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow([
                    "Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση",
                    "Τύπος Δωματίου", "Χρεωστικός Τύπος Δωματίου",
                    "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Αγορά", "Σύν. Ατόμων"
                ])
                w.writerow([
                    "2001", "Alice Wonder", "01/09/2026", "08/09/2026",
                    "DUG", "DUG", "Direct", "5001", "BB", "GR", "1"
                ])
                w.writerow([
                    "2002", "Bob Builder", "02/09/2026", "09/09/2026",
                    "PJK", "PJG", "Expedia", "5002", "FB", "US", "2"
                ])

            bookings = parse_in_house_csv(csv_path)

            self.assertEqual(len(bookings), 2)
            self.assertIn("5001", bookings)
            self.assertIn("5002", bookings)

            b1 = bookings["5001"]
            self.assertEqual(b1["Room"], "2001")
            self.assertEqual(b1["Guests"], ["Alice Wonder"])
            self.assertEqual(b1["Room Type"], "DUG")
            self.assertEqual(b1["Booked Room Type"], "DUG")
            self.assertEqual(b1["Agency"], "Direct")

            b2 = bookings["5002"]
            self.assertEqual(b2["Room"], "2002")
            self.assertEqual(b2["Guests"], ["Bob Builder"])
            self.assertEqual(b2["Room Type"], "PJK")
            self.assertEqual(b2["Booked Room Type"], "PJG")
            self.assertEqual(b2["Agency"], "Expedia")

    def test_headerless_fallback_trigger_and_parsing(self):
        """
        Test 4: Headerless fixture (matching the existing fallback logic's expected shape)
        to confirm the fallback path still triggers correctly when no header row is ever found.
        """
        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, "headerless.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";")
                # No header row at all - starts directly with data rows matching fallback signature
                # Col 0: 3-4 digit room, Col 2: dd/mm/yyyy date, Col 7: digit booking ID
                w.writerow([
                    "3001", "Headerless Guest 1", "15/09/2026", "22/09/2026",
                    "DSG", "DSG", "Hotelbeds", "7001", "AI", "DE", "2"
                ])
                w.writerow([
                    "3002", "Headerless Guest 2", "16/09/2026", "23/09/2026",
                    "F2G", "F1G", "Booking.com", "7002", "BB", "FR", "2"
                ])

            bookings = parse_in_house_csv(csv_path)

            self.assertEqual(len(bookings), 2)
            self.assertIn("7001", bookings)
            self.assertIn("7002", bookings)

            b1 = bookings["7001"]
            self.assertEqual(b1["Booking ID"], "7001")
            self.assertEqual(b1["Room"], "3001")
            self.assertEqual(b1["Guests"], ["Headerless Guest 1"])
            self.assertEqual(b1["Room Type"], "DSG")
            self.assertEqual(b1["Booked Room Type"], "DSG")
            self.assertEqual(b1["Agency"], "Hotelbeds")
            self.assertEqual(b1["Arrival"], "15/09/2026")
            self.assertEqual(b1["Departure"], "22/09/2026")

            b2 = bookings["7002"]
            self.assertEqual(b2["Booking ID"], "7002")
            self.assertEqual(b2["Room"], "3002")
            self.assertEqual(b2["Guests"], ["Headerless Guest 2"])
            self.assertEqual(b2["Room Type"], "F2G")
            self.assertEqual(b2["Booked Room Type"], "F1G")
            self.assertEqual(b2["Agency"], "Booking.com")


if __name__ == "__main__":
    unittest.main()
