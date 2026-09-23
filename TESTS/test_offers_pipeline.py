# -*- coding: utf-8 -*-
"""
Tests for the Offers List pipeline (offers_module & offers_option).
Hermetic test suite exercising single-CSV processing, digit validation,
Word document generation without COM/Outlook, and villa removal regression guards.
"""
import csv
import os
import shutil
import tempfile
import unittest

import MODULES.offers_module as om
from MODULES.offers_module import (
    extract_excel_data,
    identify_digit_type,
    generate_word_document,
    execute_offers_pipeline,
)


def create_synthetic_beach_csv(file_path: str) -> str:
    """
    Builds a synthetic beach arrivals CSV with invented guests only.
    Uses real bilingual headers that canonical_header_map recognizes.
    Exercises:
      - Booking.com arrival (ST)
      - Anniversary celebration (HB)
      - Birthday greeting (HB)
      - VIP Welcome (HB)
      - Complimentary Fruit (ST)
      - Standard room without special offer
    """
    with open(file_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        # Header row: use Greek headers from CANONICAL_HEADER_MAP
        # Δωμάτιο (Room), Πελάτης (Guests), Άφιξη (Arrival), Αναχώρηση (Departure),
        # Χρεώστης (Agency), Αρ. (Booking ID), Ενήλικες (Adults), Παιδιά (Children)
        writer.writerow(["Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση", "Χρεώστης", "Αρ.", "Ενήλικες", "Παιδιά"])

        # Row 1: Booking.com -> Order: ST (2 adults, 1 child)
        writer.writerow(["1101", "Guest Alpha", "20/09/2026", "27/09/2026", "BOOKING.COM", "BK001", "2", "1"])
        writer.writerow(["Booking.com arrival notes"])

        # Row 2: Anniversary -> Order: HB (2 adults)
        writer.writerow(["1202", "Guest Beta", "20/09/2026", "28/09/2026", "TUI", "BK002", "2", "0"])
        writer.writerow(["Anniversary celebration cake requested"])

        # Row 3: Birthday -> Order: HB (1 adult)
        writer.writerow(["1303", "Guest Gamma", "20/09/2026", "29/09/2026", "DER", "BK003", "1", "0"])
        writer.writerow(["Birthday greeting card"])

        # Row 4: VIP -> Order: HB (2 adults)
        writer.writerow(["1404", "Guest Delta", "20/09/2026", "30/09/2026", "HOTELBEDS", "BK004", "2", "0"])
        writer.writerow(["VIP 2 Guest Welcome"])

        # Row 5: Fruit -> Order: ST (3 adults)
        writer.writerow(["1505", "Guest Epsilon", "20/09/2026", "01/10/2026", "ALLTOURS", "BK005", "3", "0"])
        writer.writerow(["Fruit basket on arrival"])

        # Row 6: Non-order room (standard, 2 adults)
        writer.writerow(["1606", "Guest Zeta", "20/09/2026", "02/10/2026", "TUI", "BK006", "2", "0"])
        writer.writerow(["Room inspection passed, quiet room request"])
    return file_path


def create_synthetic_villas_csv(file_path: str) -> str:
    """Builds a synthetic 3-digit arrivals CSV (invented data)."""
    with open(file_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Room", "Guest", "Arr", "Dep", "25/09/2026"])
        writer.writerow(["Header note"])
        writer.writerow(["101", "Guest Villa One", "20/09/2026", "27/09/2026", "27/09/2026"])
        writer.writerow(["Villa guest remark"])
        writer.writerow(["205", "Guest Villa Two", "20/09/2026", "28/09/2026", "28/09/2026"])
        writer.writerow(["Villa guest remark 2"])
    return file_path


def create_synthetic_shifted_block_csv(file_path: str) -> str:
    """
    Builds a CSV reproducing the real 7000/8000 block bug:
    a header row with an EXTRA BLANK FIELD after the room number,
    shifting all subsequent columns by one position for that block only.

    Fixture: normal block + shifted 7000 block, demonstrating that
    Booking.com/keyword detection works correctly despite the shift.
    """
    with open(file_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")

        # === NORMAL BLOCK (standard column layout) ===
        writer.writerow(["Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση", "Χρεώστης", "Αρ.", "Ενήλικες", "Παιδιά"])
        writer.writerow(["1101", "Normal Guest", "20/09/2026", "25/09/2026", "TUI", "BK001", "2", "0"])
        writer.writerow(["Standard room"])

        # === SHIFTED 7000 BLOCK (extra blank field after room number) ===
        # Header: Δωμάτιο, [BLANK], Πελάτης, Άφιξη, Αναχώρηση, Χρεώστης, Αρ., Ενήλικες, Παιδιά
        # This shift matches the real 7000/8000 bug
        writer.writerow(["Δωμάτιο", "", "Πελάτης", "Άφιξη", "Αναχώρηση", "Χρεώστης", "Αρ.", "Ενήλικες", "Παιδιά"])

        # Booking.com arrival in shifted block: should still be detected as ST
        # Room col0=7101, Booking ID now at col5 instead of col5, Agency at col4 (BOOKING.COM)
        writer.writerow(["7101", "", "Booking Guest", "20/09/2026", "27/09/2026", "BOOKING.COM", "BK002", "2", "1"])
        writer.writerow(["Booking.com in shifted block"])

        # Fruit basket in shifted block: should still be detected and classified as ST
        writer.writerow(["7202", "", "Fruit Guest", "20/09/2026", "29/09/2026", "ALLTOURS", "BK003", "2", "0"])
        writer.writerow(["Fruit basket on arrival"])

    return file_path


class TestOffersPipelineCharacterization(unittest.TestCase):
    """
    Stage 6f Characterization test asserting extract_excel_data produces
    the exact same structured data before and after villa removal.
    """

    EXPECTED_LITERAL = [
        {"RoomNo": "1101", "DepDate": "27/09", "Pax": 3, "Order": "ST"},
        {"RoomNo": "1202", "DepDate": "28/09", "Pax": 2, "Order": "HB"},
        {"RoomNo": "1303", "DepDate": "29/09", "Pax": 1, "Order": "HB"},
        {"RoomNo": "1404", "DepDate": "30/09", "Pax": 2, "Order": "HB"},
        {"RoomNo": "1505", "DepDate": "01/10", "Pax": 3, "Order": "ST"},
    ]

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.temp_dir, "test_arrivals.csv")
        create_synthetic_beach_csv(self.csv_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_characterization_extract_excel_data(self):
        # extract_excel_data now returns (offer_rows, minibar_data, all_arrivals)
        offer_rows, minibar_data, all_arrivals = extract_excel_data(self.csv_path)
        self.assertEqual(offer_rows, self.EXPECTED_LITERAL)


class TestOffersPipelineHermetic(unittest.TestCase):
    """
    Hermetic unit tests for the updated single-CSV Offers pipeline.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_arrivals = os.path.join(self.temp_dir, "arrivals")
        self.temp_output = os.path.join(self.temp_dir, "output")
        os.makedirs(self.temp_arrivals, exist_ok=True)
        os.makedirs(self.temp_output, exist_ok=True)

        self.orig_arrivals = om.ARRIVALS_FOLDER
        self.orig_final = om.FINAL_FOLDER
        om.ARRIVALS_FOLDER = self.temp_arrivals
        om.FINAL_FOLDER = self.temp_output

    def tearDown(self):
        om.ARRIVALS_FOLDER = self.orig_arrivals
        om.FINAL_FOLDER = self.orig_final
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_single_4digit_csv_accepted(self):
        """Req 1: A single 4-digit CSV is accepted and pipeline succeeds."""
        csv_path = os.path.join(self.temp_dir, "beach_arrivals.csv")
        create_synthetic_beach_csv(csv_path)

        ok, msg, path = execute_offers_pipeline(selected_csvs=[csv_path])
        self.assertTrue(ok)
        self.assertIn("Success", msg)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))

    def test_3digit_csv_rejected(self):
        """Req 2: A 3-digit CSV is rejected with 'CSV validation failed.'."""
        csv_path = os.path.join(self.temp_dir, "villas_arrivals.csv")
        create_synthetic_villas_csv(csv_path)

        ok, msg, path = execute_offers_pipeline(selected_csvs=[csv_path])
        self.assertFalse(ok)
        self.assertEqual(msg, "CSV validation failed.")
        self.assertIsNone(path)

    def test_two_csvs_rejected_missing_csvs(self):
        """Req 3: A list of 2 CSVs returns 'MISSING_CSVS'."""
        f1 = os.path.join(self.temp_dir, "arrivals_1.csv")
        f2 = os.path.join(self.temp_dir, "arrivals_2.csv")
        create_synthetic_beach_csv(f1)
        create_synthetic_beach_csv(f2)

        ok, msg, path = execute_offers_pipeline(selected_csvs=[f1, f2])
        self.assertFalse(ok)
        self.assertEqual(msg, "MISSING_CSVS")
        self.assertIsNone(path)

    def test_no_sandy_villas_directory_created(self):
        """Req 4: After a successful run, no SANDY VILLAS directory exists under the arrivals folder."""
        csv_path = os.path.join(self.temp_dir, "beach_arrivals.csv")
        create_synthetic_beach_csv(csv_path)

        ok, msg, path = execute_offers_pipeline(selected_csvs=[csv_path])
        self.assertTrue(ok)

        villas_dir = os.path.join(self.temp_arrivals, "SANDY VILLAS")
        self.assertFalse(os.path.exists(villas_dir))

    def test_generate_word_document_last_column_empty(self):
        """
        Req 5: Generates a Word document hermetically with python-docx and asserts
        every cell of the last table column in all data rows is empty.
        """
        data = [
            {"RoomNo": "1101", "DepDate": "27/09", "Pax": 3, "Order": "ST"},
            {"RoomNo": "1202", "DepDate": "28/09", "Pax": 2, "Order": "HB"},
        ]
        minibar = []
        out_docx = os.path.join(self.temp_dir, "test_doc.docx")

        generate_word_document(data, minibar, "20/09", out_docx, "2026")
        self.assertTrue(os.path.exists(out_docx))

        import docx
        doc = docx.Document(out_docx)
        self.assertGreater(len(doc.tables), 0)
        table = doc.tables[0]

        # Verify all data rows have an empty cell in the last column
        for r_idx, row in enumerate(table.rows[1:], 1):
            last_cell_text = row.cells[-1].text.strip()
            self.assertEqual(
                last_cell_text,
                "",
                f"Data row {r_idx} last column cell was not empty: '{last_cell_text}'"
            )

    def test_shifted_block_booking_com_detection(self):
        """
        Regression test for 7000/8000 shifted-column bug:
        Booking.com detection must work correctly even when the header
        row (and all data rows) have an extra blank field after room number,
        shifting all subsequent columns by one position.
        """
        csv_path = os.path.join(self.temp_dir, "shifted_arrivals.csv")
        create_synthetic_shifted_block_csv(csv_path)

        offer_rows, _, all_arrivals = extract_excel_data(csv_path)

        # Should have classified 2 ST orders from the shifted block:
        # - Booking.com arrival (room 7101)
        # - Fruit basket arrival (room 7202)
        st_orders = [r for r in offer_rows if r["Order"] == "ST"]
        self.assertEqual(len(st_orders), 2, f"Expected 2 ST orders, got {len(st_orders)}: {st_orders}")

        # Verify the Booking.com order from the shifted block was detected (room 7101)
        booking_com_rows = [r for r in st_orders if r["RoomNo"] == "7101"]
        self.assertEqual(len(booking_com_rows), 1, "Booking.com from shifted block should be detected")

        # Verify the Fruit order from the shifted block was detected (room 7202)
        fruit_rows = [r for r in st_orders if r["RoomNo"] == "7202"]
        self.assertEqual(len(fruit_rows), 1, "Fruit order from shifted block should be detected")

    def test_shifted_block_all_arrivals_captured(self):
        """
        Regression test: all_arrivals should contain every room/booking arrival,
        regardless of keyword classification, even in shifted blocks.
        """
        csv_path = os.path.join(self.temp_dir, "shifted_arrivals.csv")
        create_synthetic_shifted_block_csv(csv_path)

        offer_rows, _, all_arrivals = extract_excel_data(csv_path)

        # Should have 3 total arrivals: 1 normal block + 2 from shifted block
        self.assertEqual(len(all_arrivals), 3, f"Should capture 3 arrivals, got {len(all_arrivals)}: {all_arrivals}")

        # Verify room 7101 (Booking.com from shifted) is in all_arrivals
        room_7101 = [a for a in all_arrivals if a["room_number"] == "7101"]
        self.assertEqual(len(room_7101), 1, "Room 7101 from shifted block should be in all_arrivals")

        # Verify room 7202 (Fruit from shifted) is in all_arrivals
        room_7202 = [a for a in all_arrivals if a["room_number"] == "7202"]
        self.assertEqual(len(room_7202), 1, "Room 7202 from shifted block should be in all_arrivals")


if __name__ == "__main__":
    unittest.main()
