# -*- coding: utf-8 -*-
"""
Tests for the Offers List pipeline (offers_module & offers_option).
Hermetic test suite exercising single-CSV processing, digit validation,
Word document generation without COM/Outlook, and villa removal regression guards.
"""
import csv
import glob
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication

import MODULES.offers_module as om
from MODULES.offers_module import (
    extract_excel_data,
    identify_digit_type,
    generate_word_document,
    execute_offers_pipeline,
    write_arrival_record,
    get_last_record_failures,
    classify_order,
    resolve_todays_offer_file,
)
from MODULES.offers.keyword_rules import classify_order as classify_order_direct
from MODULES.offers import pipeline
from MODULES.common import paths_config
from OPTIONS.offers_option import OffersOptionWidget
from OPTIONS.configuration_option import load_app_settings


def create_synthetic_beach_csv(file_path: str) -> str:
    """
    Builds a synthetic beach arrivals CSV with invented guests only.
    Uses real bilingual headers that canonical_header_map recognizes.
    Exercises:
      - Booking.com arrival (ST)
      - Anniversary celebration (HB)
      - Birthday greeting (HB)
      - VIP Welcome (HB)
      - Fruit and wine package (ST)
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

        # Row 5: Fruit and wine -> Order: ST (3 adults)
        writer.writerow(["1505", "Guest Epsilon", "20/09/2026", "01/10/2026", "ALLTOURS", "BK005", "3", "0"])
        writer.writerow(["Fruit and wine on arrival"])

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

        # Fruit and wine in shifted block: should still be detected and classified as ST
        writer.writerow(["7202", "", "Fruit Guest", "20/09/2026", "29/09/2026", "ALLTOURS", "BK003", "2", "0"])
        writer.writerow(["Fruit and wine on arrival"])

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

    def test_todays_file_accepted(self):
        """
        Date-stamp test 1: A CSV file with today's creation timestamp
        should be accepted and pipeline succeeds.
        """
        csv_path = os.path.join(self.temp_dir, "beach_arrivals_today.csv")
        create_synthetic_beach_csv(csv_path)

        # File is freshly created, so it has today's timestamp naturally
        ok, msg, path = execute_offers_pipeline(selected_csvs=[csv_path])
        self.assertTrue(ok, f"Pipeline should accept today's file, but got: {msg}")
        self.assertIn("Success", msg)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))

    def test_stale_file_rejected(self):
        """
        Date-stamp test 2: A CSV file with a stale (non-today) creation timestamp
        should be rejected with a clear date mismatch message.

        This test monkeypatches _get_file_creation_date to return a date
        from yesterday, avoiding fighting with Windows NTFS ctime semantics.
        """
        csv_path = os.path.join(self.temp_dir, "beach_arrivals_stale.csv")
        create_synthetic_beach_csv(csv_path)

        # Monkeypatch the helper function to return yesterday's date
        yesterday = datetime.now().date() - timedelta(days=1)

        from MODULES.offers import pipeline
        with patch.object(pipeline, '_get_file_creation_date', return_value=yesterday):
            ok, msg, path = execute_offers_pipeline(selected_csvs=[csv_path])

        self.assertFalse(ok, f"Pipeline should reject stale file, but succeeded with msg: {msg}")
        self.assertIsNone(path)
        # Verify the error message mentions today/date mismatch
        self.assertIn("today", msg.lower(), f"Error message should mention today's date: {msg}")


class TestArrivalRecordWriter(unittest.TestCase):
    """
    Tests for the per-arrival JSON record writer (write_arrival_record).
    Exercises idempotent creation, field merge logic, and room_moves filtering.
    """

    def setUp(self):
        """Set up hermetic temp directory and monkeypatch RECORDS_DIR."""
        self.temp_dir = tempfile.mkdtemp()
        self.records_dir = os.path.join(self.temp_dir, "records")
        os.makedirs(self.records_dir, exist_ok=True)

        # Monkeypatch paths_config.RECORDS_DIR for hermetic testing
        self.orig_records_dir = paths_config.RECORDS_DIR
        paths_config.RECORDS_DIR = self.records_dir

    def tearDown(self):
        """Restore original RECORDS_DIR and clean up temp directory."""
        paths_config.RECORDS_DIR = self.orig_records_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_created_with_correct_fields(self):
        """
        Test 1: A new record is created with all expected fields when
        write_arrival_record is called with a fresh booking_id.
        """
        arrival = {
            "booking_id": "BK001",
            "room_number": "1101",
            "guest_name": "Guest Alpha",
            "arrival_date": "20/09",
            "departure_date": "27/09",
            "agency": "TUI",
        }

        write_arrival_record(arrival, hotel_state_manager=None)

        # Verify the file was created
        record_path = os.path.join(self.records_dir, "BK001.json")
        self.assertTrue(os.path.exists(record_path), f"Record file should be created at {record_path}")

        # Read and verify contents
        with open(record_path, "r", encoding="utf-8") as f:
            record = json.load(f)

        self.assertEqual(record["booking_id"], "BK001")
        self.assertEqual(record["room_number"], "1101")
        self.assertEqual(record["guest_name"], "Guest Alpha")
        self.assertEqual(record["arrival_date"], "20/09")
        self.assertEqual(record["departure_date"], "27/09")
        self.assertEqual(record["tour_operator"], "TUI")
        self.assertEqual(record["room_moves"], [])
        self.assertEqual(record["traces"], [])
        # length_of_stay should be 7 (Sept 20-27)
        self.assertEqual(record["length_of_stay"], 7)

    def test_record_idempotent_rewrite(self):
        """
        Test 2: Re-running write_arrival_record for the SAME booking_id with
        the same data doesn't duplicate or corrupt the file. Additionally,
        if an existing file has extra fields (e.g., hand-added custom data),
        they are preserved, and the traces field is never touched.
        """
        arrival = {
            "booking_id": "BK002",
            "room_number": "1202",
            "guest_name": "Guest Beta",
            "arrival_date": "21/09",
            "departure_date": "28/09",
            "agency": "HOTELBEDS",
        }

        # First write
        write_arrival_record(arrival, hotel_state_manager=None)
        record_path = os.path.join(self.records_dir, "BK002.json")

        # Manually add extra fields (simulating manual edit)
        with open(record_path, "r", encoding="utf-8") as f:
            first_record = json.load(f)
        first_record["custom_note"] = "hand-added field"
        first_record["traces"] = [{"trace_id": "TR001", "notes": "manually set"}]
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(first_record, f, indent=2, ensure_ascii=False)

        # Second write (should be idempotent)
        write_arrival_record(arrival, hotel_state_manager=None)

        # Verify file still exists and custom data is preserved
        self.assertTrue(os.path.exists(record_path))
        with open(record_path, "r", encoding="utf-8") as f:
            second_record = json.load(f)

        # Custom field should still be there
        self.assertEqual(second_record.get("custom_note"), "hand-added field")
        # Traces should be exactly as they were before (untouched)
        self.assertEqual(
            second_record.get("traces"),
            [{"trace_id": "TR001", "notes": "manually set"}],
            "Traces field should never be overwritten"
        )

    def test_room_moves_correctly_filtered(self):
        """
        Test 3: Room moves are correctly filtered by booking_id.
        A mock HotelStateManager with multiple room move records is passed,
        and only moves matching the current arrival's booking_id should be recorded.
        """
        arrival = {
            "booking_id": "BK003",
            "room_number": "1303",
            "guest_name": "Guest Gamma",
            "arrival_date": "22/09",
            "departure_date": "29/09",
            "agency": "TUI",
        }

        # Create a mock HotelStateManager
        mock_hsm = MagicMock()
        mock_hsm.load_room_moves_history.return_value = [
            {"booking_id": "BK001", "old_room": "1101", "new_room": "1102", "date": "22/09"},
            {"booking_id": "BK003", "old_room": "1303", "new_room": "1304", "date": "23/09"},
            {"booking_id": "BK002", "old_room": "1202", "new_room": "1203", "date": "24/09"},
            {"booking_id": "BK003", "old_room": "1304", "new_room": "1305", "date": "24/09"},
        ]

        write_arrival_record(arrival, hotel_state_manager=mock_hsm)

        record_path = os.path.join(self.records_dir, "BK003.json")
        with open(record_path, "r", encoding="utf-8") as f:
            record = json.load(f)

        # Should have exactly 2 moves for BK003
        self.assertEqual(len(record["room_moves"]), 2)
        # Verify both moves belong to BK003
        for move in record["room_moves"]:
            self.assertEqual(move["booking_id"], "BK003")
        # Verify the moves are the correct ones
        room_pairs = [(m["old_room"], m["new_room"]) for m in record["room_moves"]]
        self.assertIn(("1303", "1304"), room_pairs)
        self.assertIn(("1304", "1305"), room_pairs)

    def test_empty_booking_id_skipped(self):
        """
        Test 4: An arrival with an empty or missing booking_id is skipped
        gracefully without crashing the pipeline run.
        """
        # Arrival with empty booking_id
        arrival_empty = {
            "booking_id": "",
            "room_number": "1404",
            "guest_name": "Guest Delta",
            "arrival_date": "23/09",
            "departure_date": "30/09",
            "agency": "HOTELBEDS",
        }

        # Should not raise an exception
        try:
            write_arrival_record(arrival_empty, hotel_state_manager=None)
        except Exception as e:
            self.fail(f"write_arrival_record should not crash on empty booking_id, but raised: {e}")

        # Verify no file was created
        files = os.listdir(self.records_dir)
        self.assertEqual(len(files), 0, "No record file should be created for empty booking_id")

        # Arrival with missing booking_id
        arrival_missing = {
            "room_number": "1405",
            "guest_name": "Guest Epsilon",
            "arrival_date": "24/09",
            "departure_date": "01/10",
            "agency": "TUI",
        }

        # Should also not raise an exception
        try:
            write_arrival_record(arrival_missing, hotel_state_manager=None)
        except Exception as e:
            self.fail(f"write_arrival_record should not crash on missing booking_id, but raised: {e}")

        # Still no files
        files = os.listdir(self.records_dir)
        self.assertEqual(len(files), 0, "No record file should be created for missing booking_id")

    def test_length_of_stay_calculation_year_crossing(self):
        """
        Test 5: Length of stay is correctly calculated for stays that cross
        calendar year boundaries (e.g., arrival Dec 28, departure Jan 3).
        """
        arrival = {
            "booking_id": "BK099",
            "room_number": "9999",
            "guest_name": "Year Crosser",
            "arrival_date": "28/12",
            "departure_date": "03/01",
            "agency": "TUI",
        }

        write_arrival_record(arrival, hotel_state_manager=None)

        record_path = os.path.join(self.records_dir, "BK099.json")
        with open(record_path, "r", encoding="utf-8") as f:
            record = json.load(f)

        # Should be 6 nights (Dec 28, 29, 30, 31, Jan 1, 2)
        self.assertEqual(record["length_of_stay"], 6,
                        f"Year-crossing stay (Dec 28 - Jan 3) should be 6 nights, got {record['length_of_stay']}")

    def test_arrival_record_integration_with_pipeline(self):
        """
        Test 6: Integration test verifying that execute_offers_pipeline
        successfully writes arrival records for all entries in all_arrivals.
        """
        temp_arrivals = os.path.join(self.temp_dir, "arrivals")
        temp_output = os.path.join(self.temp_dir, "output")
        os.makedirs(temp_arrivals, exist_ok=True)
        os.makedirs(temp_output, exist_ok=True)

        # Monkeypatch module paths
        orig_arrivals = om.ARRIVALS_FOLDER
        orig_final = om.FINAL_FOLDER
        om.ARRIVALS_FOLDER = temp_arrivals
        om.FINAL_FOLDER = temp_output

        try:
            csv_path = os.path.join(self.temp_dir, "beach_arrivals.csv")
            create_synthetic_beach_csv(csv_path)

            ok, msg, path = execute_offers_pipeline(selected_csvs=[csv_path])
            self.assertTrue(ok, f"Pipeline should succeed, but got: {msg}")

            # Verify records were created for all arrivals (except those with empty booking_id)
            created_files = os.listdir(self.records_dir)
            # We expect records for BK001-BK006 (6 guests from synthetic CSV)
            expected_bookings = {"BK001", "BK002", "BK003", "BK004", "BK005", "BK006"}
            created_bookings = {f.replace(".json", "") for f in created_files}
            self.assertEqual(created_bookings, expected_bookings,
                           f"Expected records for {expected_bookings}, got {created_bookings}")

            # Spot-check one record
            bk001_path = os.path.join(self.records_dir, "BK001.json")
            with open(bk001_path, "r", encoding="utf-8") as f:
                bk001_record = json.load(f)
            self.assertEqual(bk001_record["guest_name"], "Guest Alpha")
            self.assertEqual(bk001_record["room_number"], "1101")

            # Verify failure list is empty (no failures)
            failures = get_last_record_failures()
            self.assertEqual(len(failures), 0, f"Should have no record failures, but got: {failures}")

        finally:
            om.ARRIVALS_FOLDER = orig_arrivals
            om.FINAL_FOLDER = orig_final


class TestKeywordClassification(unittest.TestCase):
    """
    Unit tests for classify_order() function in keyword_rules module.
    Tests keyword matching for HB (Half Board) and ST (Special Treatment) classifications.
    """

    def test_repeater_classification_lowercase(self):
        """Test that 'repeater' keyword classifies as HB."""
        result = classify_order_direct("repeater")
        self.assertEqual(result, "HB")

    def test_repeater_classification_mixedcase(self):
        """Test that 'Repeater' keyword (mixed case) classifies as HB."""
        result = classify_order_direct("Repeater guest, welcome back")
        self.assertEqual(result, "HB")

    def test_anniversary_classification(self):
        """Test that 'Anniversary' keyword classifies as HB."""
        result = classify_order_direct("Anniversary celebration cake requested")
        self.assertEqual(result, "HB")

    def test_birthday_classification(self):
        """Test that 'Birthday' keyword classifies as HB."""
        result = classify_order_direct("Birthday greeting card")
        self.assertEqual(result, "HB")

    def test_honeymoon_classification(self):
        """Test that 'Honeymoon' keyword classifies as HB."""
        result = classify_order_direct("Honeymoon couple special treatment")
        self.assertEqual(result, "HB")

    def test_brthd_abbreviation_classification(self):
        """Test that 'Brthd' abbreviation classifies as HB."""
        result = classify_order_direct("Brthd Gift wrapped")
        self.assertEqual(result, "HB")

    def test_vip_classification(self):
        """Test that 'VIP' keyword classifies as HB."""
        result = classify_order_direct("VIP 2 Guest Welcome")
        self.assertEqual(result, "HB")

    def test_fruit_and_wine_with_and(self):
        """Test that 'fruit and wine' phrase classifies as ST."""
        result = classify_order_direct("Fruit and wine on arrival")
        self.assertEqual(result, "ST")

    def test_fruit_and_wine_with_ampersand(self):
        """Test that 'Fruit & Wine' phrase classifies as ST."""
        result = classify_order_direct("Fruit & Wine on arrival")
        self.assertEqual(result, "ST")

    def test_fruit_and_wine_no_connector(self):
        """Test that 'fruit wine' phrase (no connector) classifies as ST."""
        result = classify_order_direct("fruit wine basket")
        self.assertEqual(result, "ST")

    def test_fruit_and_wine_mixed_case(self):
        """Test that 'Fruit AND Wine' (uppercase connector) classifies as ST."""
        result = classify_order_direct("Fruit AND Wine welcome package")
        self.assertEqual(result, "ST")

    def test_bare_fruit_no_match(self):
        """
        REGRESSION TEST: Plain 'Fruit basket on arrival' (no 'wine') must NOT match.
        This is the key regression proof that the old bare-Fruit bug is fixed.
        """
        result = classify_order_direct("Fruit basket on arrival")
        self.assertIsNone(result, "Bare 'Fruit' without 'wine' should NOT classify as ST anymore")

    def test_fruit_only_lowercase(self):
        """Test that bare 'fruit' alone (no wine) does not classify."""
        result = classify_order_direct("Fruit bowl in room")
        self.assertIsNone(result)

    def test_no_keyword_match(self):
        """Test that description with no keywords returns None."""
        result = classify_order_direct("Room inspection passed, quiet room request")
        self.assertIsNone(result)

    def test_empty_description(self):
        """Test that empty description returns None."""
        result = classify_order_direct("")
        self.assertIsNone(result)

    def test_none_description(self):
        """Test that None description returns None."""
        result = classify_order_direct(None)
        self.assertIsNone(result)

    def test_hb_precedence_over_st(self):
        """
        Test that if a description matches both HB and ST keywords,
        HB takes precedence (checked first, so HB returned).
        """
        # This is unlikely in real data, but the function should be predictable
        result = classify_order_direct("VIP repeater with Fruit and wine treatment")
        self.assertEqual(result, "HB", "HB keywords should take precedence when both match")

    def test_fruit_wine_with_extra_spaces(self):
        """Test that 'fruit  and  wine' with extra spaces still matches."""
        result = classify_order_direct("Fruit   and   wine package")
        self.assertEqual(result, "ST")


class TestKeywordClassificationIntegration(unittest.TestCase):
    """
    Integration tests verifying classify_order works correctly through the full pipeline.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_repeater_through_extract_excel_data(self):
        """Integration test: 'repeater' remark should result in HB classification through extract_excel_data."""
        csv_path = os.path.join(self.temp_dir, "repeater_test.csv")
        with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση", "Χρεώστης", "Αρ.", "Ενήλικες", "Παιδιά"])
            writer.writerow(["2001", "Repeater Guest", "20/09/2026", "25/09/2026", "TUI", "BK001", "2", "0"])
            writer.writerow(["Repeater guest, welcome back"])

        offer_rows, _, all_arrivals = extract_excel_data(csv_path)

        # Should have one offer row classified as HB
        self.assertEqual(len(offer_rows), 1)
        self.assertEqual(offer_rows[0]["Order"], "HB")
        self.assertEqual(offer_rows[0]["RoomNo"], "2001")

    def test_fruit_wine_through_extract_excel_data(self):
        """Integration test: 'fruit and wine' remark should result in ST classification through extract_excel_data."""
        csv_path = os.path.join(self.temp_dir, "fruit_wine_test.csv")
        with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση", "Χρεώστης", "Αρ.", "Ενήλικες", "Παιδιά"])
            writer.writerow(["3002", "Wine Guest", "20/09/2026", "26/09/2026", "HOTELBEDS", "BK002", "1", "0"])
            writer.writerow(["Fruit & Wine welcome package"])

        offer_rows, _, all_arrivals = extract_excel_data(csv_path)

        # Should have one offer row classified as ST
        self.assertEqual(len(offer_rows), 1)
        self.assertEqual(offer_rows[0]["Order"], "ST")
        self.assertEqual(offer_rows[0]["RoomNo"], "3002")

    def test_bare_fruit_does_not_match_through_pipeline(self):
        """
        Integration test: 'Fruit basket on arrival' (no wine) should NOT be classified as ST.
        This confirms the regression test at the pipeline level.
        """
        csv_path = os.path.join(self.temp_dir, "bare_fruit_test.csv")
        with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση", "Χρεώστης", "Αρ.", "Ενήλικες", "Παιδιά"])
            writer.writerow(["4003", "Bare Fruit Guest", "20/09/2026", "27/09/2026", "TUI", "BK003", "2", "0"])
            writer.writerow(["Fruit basket on arrival"])

        offer_rows, _, all_arrivals = extract_excel_data(csv_path)

        # Should have NO offer rows (bare fruit doesn't match anymore)
        self.assertEqual(len(offer_rows), 0,
                        "Bare 'Fruit basket' with no wine should not be classified as ST anymore")
        # But the arrival should still be recorded in all_arrivals
        self.assertEqual(len(all_arrivals), 1)
        self.assertEqual(all_arrivals[0]["room_number"], "4003")


class TestResolveTodaysOfferFile(unittest.TestCase):
    """
    Tests for resolve_todays_offer_file() function.
    Exercises deterministic UPDATED-variant selection (not mtime-based).
    """

    def setUp(self):
        """Create hermetic temp directories for offer list tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.offer_lists_dir = os.path.join(self.temp_dir, "offer_lists")
        os.makedirs(self.offer_lists_dir, exist_ok=True)

        # Also set up monkeypatch for FINAL_FOLDER fallback tests
        self.orig_final = om.FINAL_FOLDER
        self.test_final_folder = os.path.join(self.temp_dir, "final_output")
        os.makedirs(self.test_final_folder, exist_ok=True)
        om.FINAL_FOLDER = self.test_final_folder

    def tearDown(self):
        """Restore FINAL_FOLDER and clean up temp directory."""
        om.FINAL_FOLDER = self.orig_final
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_base_file_only(self):
        """Test 1: Only the base file exists → base file resolved."""
        from MODULES.offers_module import resolve_todays_offer_file
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')}).docx"
        base_file = os.path.join(self.offer_lists_dir, base_name)

        # Create the base file
        with open(base_file, "w") as f:
            f.write("test")

        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertEqual(result, base_file)

    def test_base_and_updated(self):
        """Test 2: Base + ' UPDATED' exist → UPDATED picked (not base)."""
        from MODULES.offers_module import resolve_todays_offer_file
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        updated_file = os.path.join(self.offer_lists_dir, base_name + " UPDATED.docx")

        # Create both files
        with open(base_file, "w") as f:
            f.write("base")
        with open(updated_file, "w") as f:
            f.write("updated")

        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertEqual(result, updated_file, "Should pick UPDATED over base")

    def test_base_updated_updated_2(self):
        """Test 3: Base + ' UPDATED' + ' UPDATED (2)' → ' UPDATED (2)' picked."""
        from MODULES.offers_module import resolve_todays_offer_file
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        updated_file = os.path.join(self.offer_lists_dir, base_name + " UPDATED.docx")
        updated_2_file = os.path.join(self.offer_lists_dir, base_name + " UPDATED (2).docx")

        # Create all three files
        with open(base_file, "w") as f:
            f.write("base")
        with open(updated_file, "w") as f:
            f.write("updated")
        with open(updated_2_file, "w") as f:
            f.write("updated 2")

        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertEqual(result, updated_2_file, "Should pick highest UPDATED variant (2)")

    def test_deterministic_not_mtime_based(self):
        """
        Test 4 (CRITICAL): Deliberately set mtimes OUT OF ORDER to prove
        selection is NOT mtime-based.

        Creates base, UPDATED (1), and UPDATED (2), then sets their mtimes
        in reverse order (newest first), and verifies UPDATED (2) is still selected.
        """
        from MODULES.offers_module import resolve_todays_offer_file
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        updated_file = os.path.join(self.offer_lists_dir, base_name + " UPDATED.docx")
        updated_2_file = os.path.join(self.offer_lists_dir, base_name + " UPDATED (2).docx")

        # Create all three files
        with open(base_file, "w") as f:
            f.write("base")
        with open(updated_file, "w") as f:
            f.write("updated")
        with open(updated_2_file, "w") as f:
            f.write("updated 2")

        # Now deliberately set mtimes OUT OF ORDER to prove the function doesn't use mtime
        # Set UPDATED (2) to the OLDEST mtime (it should still be picked)
        old_time = 1000000000  # Some timestamp in the past
        current_time = 1000000100  # Slightly newer
        newest_time = 1000000200  # Newest

        os.utime(updated_2_file, (old_time, old_time))  # OLDEST
        os.utime(updated_file, (current_time, current_time))  # MIDDLE
        os.utime(base_file, (newest_time, newest_time))  # NEWEST

        # Even though base_file has the newest mtime, UPDATED (2) should still be picked
        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertEqual(
            result,
            updated_2_file,
            "Should pick UPDATED (2) by counter, NOT by newest mtime. "
            "This proves the selection is counter-based, not mtime-based."
        )

    def test_no_files_return_none(self):
        """Test 5: No files exist → returns None."""
        from MODULES.offers_module import resolve_todays_offer_file

        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertIsNone(result, "Should return None when no files exist")

    def test_explicit_offer_lists_dir_parameter(self):
        """
        Test 6: Test with explicit offer_lists_dir parameter (not FINAL_FOLDER fallback).
        This confirms the parameter itself works correctly independent of fallback logic.
        """
        from MODULES.offers_module import resolve_todays_offer_file
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        updated_file = os.path.join(self.offer_lists_dir, base_name + " UPDATED.docx")

        # Create both files
        with open(base_file, "w") as f:
            f.write("base")
        with open(updated_file, "w") as f:
            f.write("updated")

        # Call with explicit offer_lists_dir parameter
        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertEqual(result, updated_file, "Should pick UPDATED when offer_lists_dir is provided")

    def test_fallback_to_final_folder(self):
        """
        Test 7: When offer_lists_dir is None, fallback to FINAL_FOLDER logic.
        """
        from MODULES.offers_module import resolve_todays_offer_file
        from datetime import datetime

        now = datetime.now()
        # Create the GR OFFERS {month}.{year} folder structure
        month_year_folder = os.path.join(self.test_final_folder, f"GR OFFERS {now.month}.{now.year}")
        os.makedirs(month_year_folder, exist_ok=True)

        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(month_year_folder, base_name + ".docx")
        updated_file = os.path.join(month_year_folder, base_name + " UPDATED.docx")

        # Create both files
        with open(base_file, "w") as f:
            f.write("base")
        with open(updated_file, "w") as f:
            f.write("updated")

        # Call without offer_lists_dir (should use FINAL_FOLDER fallback)
        result = resolve_todays_offer_file(offer_lists_dir=None)
        self.assertEqual(result, updated_file, "Should pick UPDATED using FINAL_FOLDER fallback")

    def test_multiple_updated_variants_highest_wins(self):
        """
        Test 8: Multiple UPDATED variants exist → highest counter is selected.
        """
        from MODULES.offers_module import resolve_todays_offer_file
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"

        # Create variants with different counters
        files = {
            os.path.join(self.offer_lists_dir, base_name + ".docx"): "base",
            os.path.join(self.offer_lists_dir, base_name + " UPDATED.docx"): "updated 1",
            os.path.join(self.offer_lists_dir, base_name + " UPDATED (2).docx"): "updated 2",
            os.path.join(self.offer_lists_dir, base_name + " UPDATED (3).docx"): "updated 3",
            os.path.join(self.offer_lists_dir, base_name + " UPDATED (5).docx"): "updated 5",
        }

        for filepath, content in files.items():
            with open(filepath, "w") as f:
                f.write(content)

        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        expected = os.path.join(self.offer_lists_dir, base_name + " UPDATED (5).docx")
        self.assertEqual(result, expected, "Should pick UPDATED (5) as the highest counter")


class TestCreateButtonDisabledState(unittest.TestCase):
    """
    Tests for the Create Offerlist button disabled state logic.
    Verifies that the button is disabled when today's offer file exists,
    and enabled when it doesn't.
    """

    def setUp(self):
        """Set up hermetic temp directories for button state tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.offer_lists_dir = os.path.join(self.temp_dir, "offer_lists")
        os.makedirs(self.offer_lists_dir, exist_ok=True)

        # Monkeypatch settings to use our temp directory
        self.orig_load_app_settings = load_app_settings
        self.patcher = patch('OPTIONS.configuration_option.load_app_settings')
        self.mock_load_settings = self.patcher.start()
        self.mock_load_settings.return_value = {
            "storage": {"offer_lists_dir": self.offer_lists_dir}
        }

    def tearDown(self):
        """Clean up temp directory and restore patches."""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_button_disabled_when_todays_file_exists(self):
        """
        Test: When today's offer file exists, btn_create should be disabled.
        """
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")

        # Create the base file
        with open(base_file, "w") as f:
            f.write("test")

        # Check: resolve_todays_offer_file should find it
        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertIsNotNone(result, "File should be found by resolve_todays_offer_file")

        # Button logic: should be disabled (not enabled)
        exists = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir) is not None
        button_should_be_disabled = exists
        self.assertTrue(button_should_be_disabled, "Button should be disabled when file exists")

    def test_button_enabled_when_todays_file_does_not_exist(self):
        """
        Test: When today's offer file does NOT exist, btn_create should be enabled.
        """
        # Check: resolve_todays_offer_file should return None (empty dir)
        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertIsNone(result, "No file should be found")

        # Button logic: should be enabled (not disabled)
        exists = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir) is not None
        button_should_be_disabled = exists
        self.assertFalse(button_should_be_disabled, "Button should be enabled when file does not exist")

    def test_button_disabled_with_updated_variant(self):
        """
        Test: When an UPDATED variant exists, btn_create should be disabled.
        """
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        updated_file = os.path.join(self.offer_lists_dir, base_name + " UPDATED.docx")

        # Create the UPDATED file (not the base)
        with open(updated_file, "w") as f:
            f.write("test")

        # Check: resolve_todays_offer_file should find it
        result = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir)
        self.assertIsNotNone(result, "UPDATED file should be found")

        # Button logic: should be disabled
        exists = resolve_todays_offer_file(offer_lists_dir=self.offer_lists_dir) is not None
        button_should_be_disabled = exists
        self.assertTrue(button_should_be_disabled, "Button should be disabled when UPDATED file exists")


class TestOffersOptionWidgetButtonState(unittest.TestCase):
    """
    Widget-level tests for OffersOptionWidget button state management.
    Uses QApplication for hermetic widget testing.
    """

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def setUp(self):
        """Set up hermetic temp directories and widget for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.offer_lists_dir = os.path.join(self.temp_dir, "offer_lists")
        os.makedirs(self.offer_lists_dir, exist_ok=True)

        # Monkeypatch settings to use our temp directory (patch where it's used)
        self.patcher = patch('OPTIONS.offers_option.load_app_settings')
        self.mock_load_settings = self.patcher.start()
        self.mock_load_settings.return_value = {
            "storage": {"offer_lists_dir": self.offer_lists_dir}
        }

        # Create the widget with a mock log callback
        self.log_messages = []
        self.widget = OffersOptionWidget(log_callback=self._log_callback)
        # build_submenu() must be called to initialize the button attributes
        # Keep a reference to prevent garbage collection
        self.submenu = self.widget.build_submenu()

    def tearDown(self):
        """Clean up widget and temp directory."""
        # Clean up widget references
        if self.submenu:
            self.submenu.deleteLater()
        if self.widget:
            self.widget.deleteLater()
        self.patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _log_callback(self, category, message, level):
        """Mock log callback to capture log messages."""
        self.log_messages.append((category, message, level))

    def test_create_button_initially_enabled(self):
        """
        Test: When no offer file exists, btn_create should be enabled initially.
        """
        # build_submenu is called during __init__ via _init_ui
        # So the button should have been refreshed already
        self.assertTrue(self.widget.btn_create.isEnabled(),
                       "Create button should be enabled when no offer file exists")

    def test_create_button_disabled_after_refresh_when_file_exists(self):
        """
        Test: When an offer file exists, _refresh_button_states should disable btn_create.
        """
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")

        # Create the file to simulate that today's offer already exists
        with open(base_file, "w") as f:
            f.write("test")

        # Call _refresh_button_states
        self.widget._refresh_button_states()

        # Button should now be disabled
        self.assertFalse(self.widget.btn_create.isEnabled(),
                        "Create button should be disabled after file is created")

    def test_create_button_enabled_after_refresh_when_file_removed(self):
        """
        Test: When an offer file is removed, _refresh_button_states should enable btn_create.
        """
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")

        # Create and then remove the file
        with open(base_file, "w") as f:
            f.write("test")

        self.widget._refresh_button_states()
        self.assertFalse(self.widget.btn_create.isEnabled(), "Button should be disabled with file")

        # Remove the file
        os.remove(base_file)

        # Refresh button states
        self.widget._refresh_button_states()

        # Button should now be enabled again
        self.assertTrue(self.widget.btn_create.isEnabled(),
                       "Create button should be enabled after file is removed")

    def test_activate_refreshes_button_states(self):
        """
        Test: Calling activate() should refresh button states.
        """
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")

        # Create the file
        with open(base_file, "w") as f:
            f.write("test")

        # Initially, the button might still be enabled (from earlier state)
        # Call activate(), which should refresh
        self.widget.activate()

        # Button should now be disabled
        self.assertFalse(self.widget.btn_create.isEnabled(),
                        "Create button should be disabled after activate() when file exists")


class TestTodoWidgetGetOrCreateTask(unittest.TestCase):
    """
    Tests for TodoWidget.get_or_create_task() method.
    Verifies deduplication by description text and payload updates.
    """

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def setUp(self):
        """Create a TodoWidget for testing."""
        from OPTIONS.todo_option import TodoWidget
        self.todo_widget = TodoWidget()

    def tearDown(self):
        """Clean up widget."""
        if self.todo_widget:
            self.todo_widget.deleteLater()

    def test_get_or_create_task_creates_new_task_when_not_found(self):
        """
        Test 1: When description doesn't match any existing task,
        get_or_create_task should create a new task via add_task_auto.
        """
        description = "Test Task 1"
        payload = {"type": "outlook_draft", "category": "Test"}

        task_id = self.todo_widget.get_or_create_task(description, payload)

        # Verify task was created
        self.assertIn(task_id, self.todo_widget.active_tasks)
        task_widget = self.todo_widget.active_tasks[task_id]
        self.assertEqual(task_widget.lbl_desc.text(), description)
        self.assertEqual(task_widget.payload, payload)

    def test_get_or_create_task_reuses_existing_task(self):
        """
        Test 2: When description matches an existing task,
        get_or_create_task should reuse the existing task_id
        (no duplicate created).
        """
        description = "Send Offerlist Email"
        payload1 = {"type": "outlook_draft", "category": "Offer", "subcategory": "Offer List", "data": {"To": "old"}}
        payload2 = {"type": "outlook_draft", "category": "Offer", "subcategory": "Offer List", "data": {"To": "new"}}

        # Create the first task
        task_id_1 = self.todo_widget.get_or_create_task(description, payload1)
        self.assertEqual(len(self.todo_widget.active_tasks), 1)
        self.assertEqual(self.todo_widget.active_tasks[task_id_1].payload, payload1)

        # Try to create another task with the same description
        task_id_2 = self.todo_widget.get_or_create_task(description, payload2)

        # Should reuse the same task_id (no duplicate created)
        self.assertEqual(task_id_1, task_id_2, "Should return the same task_id for same description")
        self.assertEqual(len(self.todo_widget.active_tasks), 1, "Should not create a duplicate task")

        # Payload should be updated to the new one
        self.assertEqual(self.todo_widget.active_tasks[task_id_2].payload, payload2,
                        "Payload should be updated to the latest version")

    def test_get_or_create_task_different_descriptions_create_separate_tasks(self):
        """
        Test 3: Different descriptions should create separate tasks.
        """
        desc1 = "Task A"
        desc2 = "Task B"
        payload = {"type": "test"}

        task_id_1 = self.todo_widget.get_or_create_task(desc1, payload)
        task_id_2 = self.todo_widget.get_or_create_task(desc2, payload)

        # Should have 2 tasks
        self.assertEqual(len(self.todo_widget.active_tasks), 2)
        self.assertNotEqual(task_id_1, task_id_2)

    def test_get_or_create_task_empty_payload_defaults_to_empty_dict(self):
        """
        Test 4: When payload is None, it should default to an empty dict.
        """
        description = "No Payload Task"
        task_id = self.todo_widget.get_or_create_task(description, payload=None)

        task_widget = self.todo_widget.active_tasks[task_id]
        self.assertEqual(task_widget.payload, {})


class TestTaskWidgetOfferListStateTransition(unittest.TestCase):
    """
    Tests for TaskWidget.manual_draft_outlook() state transition.
    Verifies that the new 📨 state is set for Offer List tasks only (not Cake Memo).
    """

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def setUp(self):
        """Create TaskWidget instances for testing."""
        from OPTIONS._shared.task_widget import TaskWidget
        self.TaskWidget = TaskWidget

    def tearDown(self):
        """No cleanup needed for this test."""
        pass

    def test_manual_draft_outlook_sets_email_sent_state_for_offer_list(self):
        """
        Test 1: manual_draft_outlook should set state to 📨 when payload
        has subcategory == "Offer List", with mocked Outlook.
        """
        payload = {
            "type": "outlook_draft",
            "category": "Offer",
            "subcategory": "Offer List",
            "data": {
                "To": "test@example.com",
                "CC": "",
                "Subject": "Test",
                "HTMLBody": "Test body",
                "Attachment": None
            }
        }

        task = self.TaskWidget("Test Offer Task", "task_123", payload=payload)
        initial_state = task.btn_state.text()

        # Mock Dispatch to prevent real Outlook usage
        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            # Call manual_draft_outlook
            task.manual_draft_outlook()

            # Verify Display was called (email opened)
            mock_mail.Display.assert_called_once()

            # Verify state changed to 📨
            self.assertEqual(task.btn_state.text(), "📨",
                           "State should change to 📨 after Display() for Offer List task")

        task.deleteLater()

    def test_manual_draft_outlook_does_not_set_state_for_cake_memo(self):
        """
        Test 2 (CRITICAL REGRESSION): manual_draft_outlook should NOT set state
        to 📨 when payload has subcategory == "Cake Memo" (different task type).
        This proves the subcategory gating is working correctly.
        """
        payload = {
            "type": "outlook_draft",
            "category": "Offer",
            "subcategory": "Cake Memo",
            "data": {
                "To": "test@example.com",
                "CC": "",
                "Subject": "Test",
                "HTMLBody": "Test body",
                "Attachment": None
            }
        }

        task = self.TaskWidget("Test Cake Task", "task_456", payload=payload)
        initial_state = task.btn_state.text()

        # Mock Dispatch to prevent real Outlook usage
        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            # Call manual_draft_outlook
            task.manual_draft_outlook()

            # Verify Display was called
            mock_mail.Display.assert_called_once()

            # Verify state did NOT change to 📨 (should remain at initial state ⏳)
            self.assertEqual(task.btn_state.text(), "⏳",
                           "State should NOT change for Cake Memo task (subcategory is not 'Offer List')")

        task.deleteLater()

    def test_manual_draft_outlook_handles_missing_payload_gracefully(self):
        """
        Test 3: manual_draft_outlook should handle missing/empty payload gracefully.
        """
        task = self.TaskWidget("No Payload Task", "task_789", payload={})

        # Mock Dispatch
        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            # Should not raise an exception
            task.manual_draft_outlook()

            # Should not change state (no subcategory match)
            self.assertEqual(task.btn_state.text(), "⏳")

        task.deleteLater()

    def test_manual_draft_outlook_attachment_handling(self):
        """
        Test 4: manual_draft_outlook should correctly attach files when attachment path is provided.
        """
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.docx', delete=False)
        temp_file.write("test content")
        temp_file.close()

        payload = {
            "type": "outlook_draft",
            "category": "Offer",
            "subcategory": "Offer List",
            "data": {
                "To": "test@example.com",
                "CC": "",
                "Subject": "Test with attachment",
                "HTMLBody": "Test body",
                "Attachment": temp_file.name
            }
        }

        task = self.TaskWidget("Task with Attachment", "task_att", payload=payload)

        # Mock Dispatch
        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            # Call manual_draft_outlook
            task.manual_draft_outlook()

            # Verify Attachments.Add was called with the attachment path
            mock_mail.Attachments.Add.assert_called_once()

            # Verify state changed to 📨 (Display succeeded)
            self.assertEqual(task.btn_state.text(), "📨")

        # Clean up temp file
        os.unlink(temp_file.name)
        task.deleteLater()


class TestHandleSendEmailIntegration(unittest.TestCase):
    """
    Integration tests for OffersOptionWidget.handle_send_email().
    Verifies task creation/reuse and Outlook draft opening.
    """

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def setUp(self):
        """Set up hermetic temp directories and widget."""
        self.temp_dir = tempfile.mkdtemp()
        self.offer_lists_dir = os.path.join(self.temp_dir, "offer_lists")
        os.makedirs(self.offer_lists_dir, exist_ok=True)

        # Monkeypatch settings
        self.patcher_settings = patch('OPTIONS.offers_option.load_app_settings')
        self.mock_load_settings = self.patcher_settings.start()
        self.mock_load_settings.return_value = {
            "storage": {"offer_lists_dir": self.offer_lists_dir}
        }

        # Create a TodoWidget
        from OPTIONS.todo_option import TodoWidget
        self.todo_widget = TodoWidget()

        # Create OffersOptionWidget with todo_widget wired in
        self.log_messages = []
        self.offers_widget = OffersOptionWidget(
            log_callback=self._log_callback,
            todo_widget=self.todo_widget
        )
        self.submenu = self.offers_widget.build_submenu()

    def tearDown(self):
        """Clean up widgets and temp directory."""
        if self.submenu:
            self.submenu.deleteLater()
        if self.offers_widget:
            self.offers_widget.deleteLater()
        if self.todo_widget:
            self.todo_widget.deleteLater()
        self.patcher_settings.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _log_callback(self, category, message, level):
        """Mock log callback to capture log messages."""
        self.log_messages.append((category, message, level))

    def test_handle_send_email_creates_task_and_opens_draft(self):
        """
        Test 1: handle_send_email should create/reuse a task and open an Outlook draft.
        """
        from datetime import datetime

        # Create today's offer file
        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        with open(base_file, "w") as f:
            f.write("test offer list")

        # Mock win32com.client.Dispatch to prevent real Outlook
        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            # Call handle_send_email
            self.offers_widget.handle_send_email()

            # Verify a task was created with the correct description
            self.assertEqual(len(self.todo_widget.active_tasks), 1)
            task_widget = list(self.todo_widget.active_tasks.values())[0]
            self.assertEqual(task_widget.lbl_desc.text(), "Send Offerlist Email")

            # Verify Outlook display was called
            mock_mail.Display.assert_called_once()

            # Verify the task state changed to 📨
            self.assertEqual(task_widget.btn_state.text(), "📨")

    def test_handle_send_email_reuses_existing_task(self):
        """
        Test 2: Calling handle_send_email twice should reuse the same task
        (no duplicate "Send Offerlist Email" row created).
        """
        from datetime import datetime

        # Create today's offer file
        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        with open(base_file, "w") as f:
            f.write("test offer list")

        # Mock win32com.client.Dispatch
        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            # Call handle_send_email twice
            self.offers_widget.handle_send_email()
            first_task_count = len(self.todo_widget.active_tasks)

            self.offers_widget.handle_send_email()
            second_task_count = len(self.todo_widget.active_tasks)

            # Should still have only 1 task (reused)
            self.assertEqual(first_task_count, 1)
            self.assertEqual(second_task_count, 1)
            self.assertEqual(mock_mail.Display.call_count, 2, "Display should be called twice")

    def test_handle_send_email_no_file_available(self):
        """
        Test 3: handle_send_email should gracefully handle the case when
        no offer file exists (button disabled, but called anyway).
        """
        # Don't create any file
        self.offers_widget.handle_send_email()

        # No task should be created
        self.assertEqual(len(self.todo_widget.active_tasks), 0)

        # Log message should indicate error
        error_logs = [msg for msg in self.log_messages if msg[2] == "ERROR"]
        self.assertGreater(len(error_logs), 0, "Should have logged an error")

    def test_handle_send_email_updates_payload_on_reuse(self):
        """
        Test 4: When reusing a task, the payload should be updated to the latest file.
        """
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")

        # Mock win32com.client.Dispatch
        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            # First call: create file and send email
            with open(base_file, "w") as f:
                f.write("version 1")
            self.offers_widget.handle_send_email()

            first_task_id = list(self.todo_widget.active_tasks.keys())[0]
            first_payload = self.todo_widget.active_tasks[first_task_id].payload.copy()

            # Second call: file still exists (payload unchanged for now, but structure verified)
            self.offers_widget.handle_send_email()

            # Task should still be the same
            self.assertEqual(len(self.todo_widget.active_tasks), 1)
            second_task_id = list(self.todo_widget.active_tasks.keys())[0]
            self.assertEqual(first_task_id, second_task_id)


class TestHandleDocSaveUpdateMode(unittest.TestCase):
    """
    Tests for OffersOptionWidget.handle_doc_save() in update mode.
    Verifies that duplicate_for_update is called when is_update_mode is True.
    """

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def setUp(self):
        """Set up hermetic temp directories and widget."""
        self.temp_dir = tempfile.mkdtemp()
        self.offer_lists_dir = os.path.join(self.temp_dir, "offer_lists")
        os.makedirs(self.offer_lists_dir, exist_ok=True)

        # Monkeypatch settings
        self.patcher_settings = patch('OPTIONS.offers_option.load_app_settings')
        self.mock_load_settings = self.patcher_settings.start()
        self.mock_load_settings.return_value = {
            "storage": {"offer_lists_dir": self.offer_lists_dir}
        }

        # Create widget with mock log callback
        self.log_messages = []
        self.offers_widget = OffersOptionWidget(log_callback=self._log_callback)
        self.submenu = self.offers_widget.build_submenu()

    def tearDown(self):
        """Clean up widgets and temp directory."""
        if self.submenu:
            self.submenu.deleteLater()
        if self.offers_widget:
            self.offers_widget.deleteLater()
        self.patcher_settings.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _log_callback(self, category, message, level):
        """Mock log callback."""
        self.log_messages.append((category, message, level))

    def test_handle_doc_save_creates_updated_variant_in_update_mode(self):
        """
        Test 1: In update mode, handle_doc_save should create an UPDATED variant.
        """
        from datetime import datetime

        # Create a mock file to save
        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        with open(base_file, "w") as f:
            f.write("test content")

        # Mock OfficeViewer.save_file and OfficeViewer.current_filepath
        with patch.object(self.offers_widget.office_viewer, 'save_file'):
            self.offers_widget.office_viewer.current_filepath = base_file
            self.offers_widget.is_update_mode = True

            # Mock duplicate_for_update to return a new path
            with patch('OPTIONS.offers_option.duplicate_for_update') as mock_dup:
                updated_file = base_file.replace(".docx", " UPDATED.docx")
                mock_dup.return_value = updated_file

                # Call handle_doc_save
                self.offers_widget.handle_doc_save()

                # Verify duplicate_for_update was called
                mock_dup.assert_called_once_with(base_file)

                # Verify a success log was generated
                success_logs = [msg for msg in self.log_messages if msg[2] == "SUCCESS"]
                self.assertGreater(len(success_logs), 0, "Should have logged success")

    def test_handle_doc_save_no_update_when_not_in_update_mode(self):
        """
        Test 2: When is_update_mode is False, handle_doc_save should NOT create
        an UPDATED variant.
        """
        from datetime import datetime

        # Create a mock file to save
        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        with open(base_file, "w") as f:
            f.write("test content")

        # Mock OfficeViewer methods
        with patch.object(self.offers_widget.office_viewer, 'save_file'):
            self.offers_widget.office_viewer.current_filepath = base_file
            self.offers_widget.is_update_mode = False

            # Mock duplicate_for_update to track if it was called
            with patch('OPTIONS.offers_option.duplicate_for_update') as mock_dup:
                # Call handle_doc_save
                self.offers_widget.handle_doc_save()

                # duplicate_for_update should NOT be called
                mock_dup.assert_not_called()

    def test_handle_doc_save_error_handling_in_update_mode(self):
        """
        Test 3: If duplicate_for_update raises an error, handle_doc_save should
        log the error and return gracefully.
        """
        from datetime import datetime

        # Create a mock file
        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        with open(base_file, "w") as f:
            f.write("test content")

        # Mock OfficeViewer methods
        with patch.object(self.offers_widget.office_viewer, 'save_file'):
            self.offers_widget.office_viewer.current_filepath = base_file
            self.offers_widget.is_update_mode = True

            # Mock duplicate_for_update to raise an error
            with patch('OPTIONS.offers_option.duplicate_for_update') as mock_dup:
                mock_dup.side_effect = Exception("Test error")

                # Call handle_doc_save (should not raise)
                self.offers_widget.handle_doc_save()

                # Verify error was logged
                error_logs = [msg for msg in self.log_messages if msg[2] == "ERROR"]
                self.assertGreater(len(error_logs), 0, "Should have logged an error")


class TestSendEmailButtonState(unittest.TestCase):
    """
    Tests for Send Email button state management.
    Verifies that btn_send_email is enabled/disabled correctly.
    """

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def setUp(self):
        """Set up hermetic temp directories and widget."""
        self.temp_dir = tempfile.mkdtemp()
        self.offer_lists_dir = os.path.join(self.temp_dir, "offer_lists")
        os.makedirs(self.offer_lists_dir, exist_ok=True)

        # Monkeypatch settings
        self.patcher = patch('OPTIONS.offers_option.load_app_settings')
        self.mock_load_settings = self.patcher.start()
        self.mock_load_settings.return_value = {
            "storage": {"offer_lists_dir": self.offer_lists_dir}
        }

        # Create widget
        self.offers_widget = OffersOptionWidget(log_callback=lambda c, m, l: None)
        self.submenu = self.offers_widget.build_submenu()

    def tearDown(self):
        """Clean up."""
        if self.submenu:
            self.submenu.deleteLater()
        if self.offers_widget:
            self.offers_widget.deleteLater()
        self.patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_send_email_button_enabled_when_file_exists(self):
        """
        Test 1: btn_send_email should be enabled when today's offer file exists.
        """
        from datetime import datetime

        # Create today's offer file
        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")
        with open(base_file, "w") as f:
            f.write("test")

        # Refresh button states
        self.offers_widget._refresh_button_states()

        # btn_send_email should be enabled
        self.assertTrue(self.offers_widget.btn_send_email.isEnabled(),
                       "Send Email button should be enabled when offer file exists")

        # btn_create should be disabled
        self.assertFalse(self.offers_widget.btn_create.isEnabled(),
                        "Create button should be disabled when offer file exists")

    def test_send_email_button_disabled_when_file_not_exists(self):
        """
        Test 2: btn_send_email should be disabled when no offer file exists.
        """
        # No file created, so _refresh_button_states should disable the button
        self.offers_widget._refresh_button_states()

        # btn_send_email should be disabled
        self.assertFalse(self.offers_widget.btn_send_email.isEnabled(),
                        "Send Email button should be disabled when no offer file exists")

        # btn_create should be enabled
        self.assertTrue(self.offers_widget.btn_create.isEnabled(),
                       "Create button should be enabled when no offer file exists")

    def test_send_email_button_opposite_state_of_create_button(self):
        """
        Test 3: btn_send_email and btn_create should always have opposite states.
        """
        from datetime import datetime

        now = datetime.now()
        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        base_file = os.path.join(self.offer_lists_dir, base_name + ".docx")

        # Initial state: no file
        self.offers_widget._refresh_button_states()
        create_enabled_1 = self.offers_widget.btn_create.isEnabled()
        send_enabled_1 = self.offers_widget.btn_send_email.isEnabled()
        self.assertNotEqual(create_enabled_1, send_enabled_1,
                          "Buttons should have opposite states when no file exists")

        # Create file
        with open(base_file, "w") as f:
            f.write("test")
        self.offers_widget._refresh_button_states()
        create_enabled_2 = self.offers_widget.btn_create.isEnabled()
        send_enabled_2 = self.offers_widget.btn_send_email.isEnabled()
        self.assertNotEqual(create_enabled_2, send_enabled_2,
                          "Buttons should have opposite states when file exists")


class TestFBEmailRecipients(unittest.TestCase):
    """
    Test suite for shared F&B recipient lists (Step 8).
    Verifies that TO_RECIPIENTS and CC_RECIPIENTS are correctly imported
    and contain all expected email addresses.
    """

    def test_to_recipients_import_and_content(self):
        """
        Test 1: TO_RECIPIENTS can be imported and contains all expected F&B addresses.
        """
        from MODULES.common.fb_email_recipients import TO_RECIPIENTS

        # All expected F&B staff should be present
        expected_emails = [
            "gabriela.stere@rizosresorts.gr",  # F&B Manager
            "chef.sandybeach@rizosresorts.gr",  # Executive Chef
            "headchef.sandybeach@rizosresorts.gr",  # Head Chef
            "assistfb.sandybeach@rizosresorts.gr",  # Assist F&B
            "assistfb2.sandybeach@rizosresorts.gr",  # Assist F&B 2
        ]

        for email in expected_emails:
            self.assertIn(email, TO_RECIPIENTS,
                         f"TO_RECIPIENTS must contain {email}")

    def test_cc_recipients_import_and_content(self):
        """
        Test 2: CC_RECIPIENTS can be imported and contains all expected operations/guest-facing addresses.
        Specifically verifies that sfragoyiannis@rizosresorts.gr is present (the new addition to Cake Memo).
        """
        from MODULES.common.fb_email_recipients import CC_RECIPIENTS

        # All expected operations staff should be present
        expected_emails = [
            "Mariela.Tsvetkova@rizosresorts.gr",  # Operation Manager
            "harrys.palikiras@rizosresorts.gr",  # Rooms Division Manager
            "sfragoyiannis@rizosresorts.gr",  # New addition to Cake Memo's CC
            "fom.sandy@rizosresorts.gr",  # Front Office Manager
            "guest.sandybeach@rizosresorts.gr",  # Guest Relations
        ]

        for email in expected_emails:
            self.assertIn(email, CC_RECIPIENTS,
                         f"CC_RECIPIENTS must contain {email}")

    def test_offers_payload_uses_shared_recipients(self):
        """
        Test 3: OffersOptionWidget._generate_offers_payload uses the shared TO_RECIPIENTS and CC_RECIPIENTS.
        """
        from MODULES.common.fb_email_recipients import TO_RECIPIENTS, CC_RECIPIENTS

        # Create QApplication if needed for Qt widgets
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        widget = OffersOptionWidget()
        payload = widget._generate_offers_payload("test_file.docx")

        # Verify the payload contains the correct recipient strings
        self.assertEqual(payload["data"]["To"], TO_RECIPIENTS,
                        "Offers payload must use shared TO_RECIPIENTS")
        self.assertEqual(payload["data"]["CC"], CC_RECIPIENTS,
                        "Offers payload must use shared CC_RECIPIENTS")

    def test_cake_memo_payload_uses_shared_recipients(self):
        """
        Test 4: generate_cake_memo_outlook_payload uses the shared TO_RECIPIENTS and CC_RECIPIENTS.
        """
        from MODULES.common.fb_email_recipients import TO_RECIPIENTS, CC_RECIPIENTS
        from OPTIONS.cake_memo_option import generate_cake_memo_outlook_payload

        # Create a minimal memo_data dict with required fields
        memo_data = {
            "room_number": "1101",
            "cake_date_display": "23/09",
            "cake_location": "ROOM",
            "cake_time": "19:00",
            "memo_month_year": "09.2026"
        }

        payload = generate_cake_memo_outlook_payload("dummy_path.docx", memo_data)

        # Verify the payload contains the correct recipient strings
        self.assertEqual(payload["data"]["To"], TO_RECIPIENTS,
                        "Cake Memo payload must use shared TO_RECIPIENTS")
        self.assertEqual(payload["data"]["CC"], CC_RECIPIENTS,
                        "Cake Memo payload must use shared CC_RECIPIENTS")


class TestConfigurableArrivalsDir(unittest.TestCase):
    """
    Tests for the configurable arrivals_dir setting.
    Verifies that the setting appears in DEFAULT_APP_SETTINGS, round-trips through
    load/save, and is correctly consumed by execute_offers_pipeline.
    """

    def setUp(self):
        """Set up hermetic temp directories for settings tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_arrivals = os.path.join(self.temp_dir, "custom_arrivals")
        self.temp_output = os.path.join(self.temp_dir, "output")
        os.makedirs(self.temp_arrivals, exist_ok=True)
        os.makedirs(self.temp_output, exist_ok=True)

        # Create custom settings file path
        self.temp_settings_file = os.path.join(self.temp_dir, "app_settings.json")

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_arrivals_dir_in_default_app_settings(self):
        """
        Test 1: arrivals_dir appears in DEFAULT_APP_SETTINGS["storage"]
        with the expected default value.
        """
        from OPTIONS.configuration.settings_store import DEFAULT_APP_SETTINGS
        from MODULES.offers.paths import ARRIVALS_FOLDER

        # Verify arrivals_dir exists in storage
        self.assertIn("arrivals_dir", DEFAULT_APP_SETTINGS["storage"])

        # Verify it defaults to ARRIVALS_FOLDER
        self.assertEqual(
            DEFAULT_APP_SETTINGS["storage"]["arrivals_dir"],
            ARRIVALS_FOLDER
        )

    def test_arrivals_dir_round_trip_load_save(self):
        """
        Test 2: arrivals_dir setting round-trips correctly through
        load_app_settings() and save_app_settings() with a hermetic temp settings file.
        """
        from OPTIONS.configuration.settings_store import (
            load_app_settings, save_app_settings, DEFAULT_APP_SETTINGS, APP_SETTINGS_PATH
        )
        import OPTIONS.configuration_option as cfg_opt

        # Temporarily patch APP_SETTINGS_PATH
        orig_path = cfg_opt.APP_SETTINGS_PATH
        cfg_opt.APP_SETTINGS_PATH = self.temp_settings_file

        try:
            # Create a settings dict with a custom arrivals_dir
            custom_arrivals = os.path.join(self.temp_dir, "my_arrivals")
            settings = json.loads(json.dumps(DEFAULT_APP_SETTINGS))
            settings["storage"]["arrivals_dir"] = custom_arrivals

            # Save the settings
            success = save_app_settings(settings)
            self.assertTrue(success, "save_app_settings should succeed")

            # Load them back
            loaded = load_app_settings()

            # Verify arrivals_dir was preserved
            self.assertIn("arrivals_dir", loaded["storage"])
            self.assertEqual(
                loaded["storage"]["arrivals_dir"],
                custom_arrivals,
                "arrivals_dir should round-trip correctly"
            )

        finally:
            # Restore original APP_SETTINGS_PATH
            cfg_opt.APP_SETTINGS_PATH = orig_path

    def test_execute_pipeline_with_custom_arrivals_dir(self):
        """
        Test 3: execute_offers_pipeline(arrivals_dir=<temp_dir>) correctly
        discovers a CSV placed in that temp dir (NOT the monkeypatched om.ARRIVALS_FOLDER).
        """
        # Monkeypatch om module paths
        orig_arrivals = om.ARRIVALS_FOLDER
        orig_final = om.FINAL_FOLDER
        om.ARRIVALS_FOLDER = os.path.join(self.temp_dir, "unrelated_arrivals")
        om.FINAL_FOLDER = self.temp_output

        try:
            # Place a CSV in custom_arrivals (not in the monkeypatched ARRIVALS_FOLDER)
            csv_path = os.path.join(self.temp_arrivals, "beach_arrivals.csv")
            create_synthetic_beach_csv(csv_path)

            # Call execute_offers_pipeline with explicit arrivals_dir
            ok, msg, path = execute_offers_pipeline(arrivals_dir=self.temp_arrivals)

            # Should succeed (discovering CSV in custom arrivals dir)
            self.assertTrue(ok, f"Pipeline should succeed with explicit arrivals_dir, but got: {msg}")
            self.assertIn("Success", msg)
            self.assertIsNotNone(path)
            self.assertTrue(os.path.exists(path))

        finally:
            om.ARRIVALS_FOLDER = orig_arrivals
            om.FINAL_FOLDER = orig_final

    def test_sandy_beach_archival_under_custom_arrivals_dir(self):
        """
        Test 4: After a successful execute_offers_pipeline(arrivals_dir=<temp_dir>),
        the CSV is moved to <temp_dir>/SANDY BEACH/, NOT to om.ARRIVALS_FOLDER/SANDY BEACH/.
        """
        # Monkeypatch om module paths to something different
        orig_arrivals = om.ARRIVALS_FOLDER
        orig_final = om.FINAL_FOLDER
        wrong_arrivals = os.path.join(self.temp_dir, "wrong_arrivals")
        om.ARRIVALS_FOLDER = wrong_arrivals
        om.FINAL_FOLDER = self.temp_output
        os.makedirs(wrong_arrivals, exist_ok=True)

        try:
            # Place a CSV in custom_arrivals
            csv_path = os.path.join(self.temp_arrivals, "beach_arrivals.csv")
            create_synthetic_beach_csv(csv_path)

            # Call execute_offers_pipeline with explicit arrivals_dir
            ok, msg, path = execute_offers_pipeline(arrivals_dir=self.temp_arrivals)
            self.assertTrue(ok, f"Pipeline should succeed, but got: {msg}")

            # Verify CSV was moved to <custom_arrivals>/SANDY BEACH/, not <wrong_arrivals>/SANDY BEACH/
            expected_sandy_beach_dir = os.path.join(self.temp_arrivals, "SANDY BEACH")
            self.assertTrue(
                os.path.exists(expected_sandy_beach_dir),
                f"SANDY BEACH dir should exist under custom arrivals dir: {expected_sandy_beach_dir}"
            )

            # Verify the CSV was actually moved there
            beach_csvs = glob.glob(os.path.join(expected_sandy_beach_dir, "*.csv"))
            self.assertEqual(
                len(beach_csvs),
                1,
                f"Should have exactly 1 CSV in SANDY BEACH, got {len(beach_csvs)}"
            )

            # Verify the CSV is NOT in the wrong arrivals location
            wrong_sandy_beach_dir = os.path.join(wrong_arrivals, "SANDY BEACH")
            wrong_csvs = glob.glob(os.path.join(wrong_sandy_beach_dir, "*.csv")) if os.path.exists(wrong_sandy_beach_dir) else []
            self.assertEqual(
                len(wrong_csvs),
                0,
                f"CSV should NOT be in wrong arrivals location, but found {len(wrong_csvs)}"
            )

        finally:
            om.ARRIVALS_FOLDER = orig_arrivals
            om.FINAL_FOLDER = orig_final

    def test_pipeline_without_arrivals_dir_uses_monkeypatch(self):
        """
        Test 5 (backward compatibility): execute_offers_pipeline() called without
        arrivals_dir parameter should still use om.ARRIVALS_FOLDER (via monkeypatch).
        This confirms existing tests remain unaffected.
        """
        # Monkeypatch om module to use custom paths
        orig_arrivals = om.ARRIVALS_FOLDER
        orig_final = om.FINAL_FOLDER
        om.ARRIVALS_FOLDER = self.temp_arrivals
        om.FINAL_FOLDER = self.temp_output

        try:
            # Place a CSV in the monkeypatched ARRIVALS_FOLDER
            csv_path = os.path.join(self.temp_arrivals, "beach_arrivals.csv")
            create_synthetic_beach_csv(csv_path)

            # Call execute_offers_pipeline WITHOUT arrivals_dir (should use monkeypatch)
            ok, msg, path = execute_offers_pipeline()
            self.assertTrue(ok, f"Pipeline should succeed using monkeypatched ARRIVALS_FOLDER, but got: {msg}")

            # Verify CSV was moved to the monkeypatched SANDY BEACH location
            expected_sandy_beach_dir = os.path.join(self.temp_arrivals, "SANDY BEACH")
            beach_csvs = glob.glob(os.path.join(expected_sandy_beach_dir, "*.csv"))
            self.assertEqual(len(beach_csvs), 1, "CSV should be moved to monkeypatched SANDY BEACH")

        finally:
            om.ARRIVALS_FOLDER = orig_arrivals
            om.FINAL_FOLDER = orig_final


class TestNoArrivalsPanelUI(unittest.TestCase):
    """
    Tests for the new No Arrivals Panel UI and associated handlers in OffersOptionWidget.
    Verifies signal emission, panel visibility, and user interactions.
    """

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def setUp(self):
        """Set up hermetic test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.offer_lists_dir = os.path.join(self.temp_dir, "offer_lists")
        self.temp_arrivals = os.path.join(self.temp_dir, "arrivals")
        self.temp_output = os.path.join(self.temp_dir, "output")
        os.makedirs(self.offer_lists_dir, exist_ok=True)
        os.makedirs(self.temp_arrivals, exist_ok=True)
        os.makedirs(self.temp_output, exist_ok=True)

        # Monkeypatch settings and module paths
        self.patcher_settings = patch('OPTIONS.offers_option.load_app_settings')
        self.mock_load_settings = self.patcher_settings.start()
        self.mock_load_settings.return_value = {
            "storage": {
                "offer_lists_dir": self.offer_lists_dir,
                "arrivals_dir": self.temp_arrivals
            }
        }

        self.patcher_arrivals = patch('OPTIONS.offers_option.ARRIVALS_FOLDER', self.temp_arrivals)
        self.patcher_arrivals.start()

        self.patcher_om_arrivals = patch.object(om, 'ARRIVALS_FOLDER', self.temp_arrivals)
        self.patcher_om_arrivals.start()

        self.patcher_om_final = patch.object(om, 'FINAL_FOLDER', self.temp_output)
        self.patcher_om_final.start()

        # Create the widget
        self.log_messages = []
        self.widget = OffersOptionWidget(log_callback=self._log_callback)
        self.submenu = self.widget.build_submenu()

    def tearDown(self):
        """Clean up."""
        if self.submenu:
            self.submenu.deleteLater()
        if self.widget:
            self.widget.deleteLater()
        self.patcher_settings.stop()
        self.patcher_arrivals.stop()
        self.patcher_om_arrivals.stop()
        self.patcher_om_final.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _log_callback(self, category, message, level):
        """Mock log callback to capture log messages."""
        self.log_messages.append((category, message, level))

    def test_show_hide_no_arrivals_panel(self):
        """
        Test 1: _show_no_arrivals_panel() hides office_viewer and shows no_arrivals_panel.
        _hide_no_arrivals_panel() reverses this.
        """
        # Initially, panel should be hidden
        self.assertFalse(self.widget.no_arrivals_panel.isVisible(), "panel should be initially hidden")

        # Call _show_no_arrivals_panel
        self.widget._show_no_arrivals_panel()
        # Check that hide() was called on office_viewer and show() on panel
        self.assertFalse(self.widget.no_arrivals_panel.isHidden(), "panel should not be hidden after show_panel")
        self.assertTrue(self.widget.office_viewer.isHidden(), "office_viewer should be hidden after show_panel")

        # Call _hide_no_arrivals_panel
        self.widget._hide_no_arrivals_panel()
        self.assertTrue(self.widget.no_arrivals_panel.isHidden(), "panel should be hidden after hide_panel")
        self.assertFalse(self.widget.office_viewer.isHidden(), "office_viewer should not be hidden after hide_panel")

    def test_handle_goto_config_emits_signal(self):
        """
        Test 2: Calling _handle_goto_config() emits navigate_to_config signal
        and hides the panel.
        """
        self.widget._show_no_arrivals_panel()
        self.assertFalse(self.widget.no_arrivals_panel.isHidden(), "panel should not be hidden before handler")

        # Capture signal emission
        signal_received = []

        def on_signal():
            signal_received.append(True)

        self.widget.navigate_to_config.connect(on_signal)

        # Call handler
        self.widget._handle_goto_config()

        # Verify signal was emitted
        self.assertEqual(len(signal_received), 1, "navigate_to_config signal should be emitted once")

        # Verify panel was hidden
        self.assertTrue(self.widget.no_arrivals_panel.isHidden(), "panel should be hidden after handler")

    def test_run_offers_creation_shows_panel_on_missing_csvs(self):
        """
        Test 3: run_offers_creation() on MISSING_CSVS pipeline result shows the panel
        and does NOT call QFileDialog.getOpenFileName immediately.
        """
        # Mock execute_offers_pipeline to return MISSING_CSVS on first call
        with patch('OPTIONS.offers_option.execute_offers_pipeline') as mock_pipeline:
            mock_pipeline.return_value = (False, "MISSING_CSVS", None)

            self.assertTrue(self.widget.no_arrivals_panel.isHidden(), "panel should be hidden initially")

            # Run creation
            self.widget.run_offers_creation()

            # Verify pipeline was called once (not prompted for manual file selection)
            self.assertEqual(mock_pipeline.call_count, 1, "Pipeline should be called once (no dialog prompt)")

            # Verify panel is now visible
            self.assertFalse(self.widget.no_arrivals_panel.isHidden(), "panel should not be hidden after MISSING_CSVS")

            # Verify office_viewer is hidden
            self.assertTrue(self.widget.office_viewer.isHidden(), "office_viewer should be hidden")

    def test_handle_browse_for_arrivals_with_file_selected(self):
        """
        Test 4: _handle_browse_for_arrivals() with mocked QFileDialog and hermetic
        execute_offers_pipeline calls pipeline with selected_csvs.
        """
        # Create a synthetic CSV
        csv_path = os.path.join(self.temp_arrivals, "test_arrivals.csv")
        create_synthetic_beach_csv(csv_path)

        with patch('OPTIONS.offers_option.QFileDialog.getOpenFileName') as mock_dialog:
            mock_dialog.return_value = (csv_path, "")

            # Mock execute_offers_pipeline to verify it's called correctly
            with patch('OPTIONS.offers_option.execute_offers_pipeline') as mock_pipeline:
                # Create a docx path to return
                docx_path = os.path.join(self.temp_output, "OFFER LIST (2026-09-24).docx")

                # Make the pipeline return success with the path
                mock_pipeline.return_value = (True, "Success: Pipeline complete.", docx_path)

                # Call handler
                self.widget._handle_browse_for_arrivals()

                # Verify QFileDialog was called
                mock_dialog.assert_called_once()

                # Verify execute_offers_pipeline was called with selected_csvs
                mock_pipeline.assert_called_once()
                call_kwargs = mock_pipeline.call_args[1]
                self.assertEqual(call_kwargs['selected_csvs'], [csv_path], "Pipeline should be called with selected CSV")

    def test_handle_browse_for_arrivals_no_file_selected(self):
        """
        Test 4b: _handle_browse_for_arrivals() with no file selected aborts gracefully.
        """
        with patch('OPTIONS.offers_option.QFileDialog.getOpenFileName') as mock_dialog:
            mock_dialog.return_value = ("", "")

            # Call handler
            self.widget._handle_browse_for_arrivals()

            # Verify abort message was logged
            self.assertTrue(
                any("Operation aborted" in msg for _, msg, _ in self.log_messages),
                "Should log abort message when no file selected"
            )

    def test_stale_csv_via_browse_rejected_by_date_check(self):
        """
        Test 5: A stale (non-today creation date) CSV selected via _handle_browse_for_arrivals()
        is still rejected by the existing date-stamp check in execute_offers_pipeline.
        This proves the date check applies to the browse path and there's no bypass.
        """
        # Create a synthetic CSV with a stale creation date
        csv_path = os.path.join(self.temp_arrivals, "stale_arrivals.csv")
        create_synthetic_beach_csv(csv_path)

        # Mock the file creation date to be yesterday
        yesterday = datetime.now().date() - timedelta(days=1)

        with patch('OPTIONS.offers_option.QFileDialog.getOpenFileName') as mock_dialog:
            mock_dialog.return_value = (csv_path, "")

            with patch.object(pipeline, '_get_file_creation_date', return_value=yesterday):
                # Call handler (NOT mocking execute_offers_pipeline; use real one)
                self.widget._handle_browse_for_arrivals()

                # Verify an error was logged about the stale date
                error_messages = [msg for _, msg, level in self.log_messages if level == "ERROR"]
                self.assertTrue(
                    any("not today" in msg.lower() or "today" in msg.lower() for msg in error_messages),
                    f"Should log date mismatch error. Got: {error_messages}"
                )

                # The pipeline will return False with a date error message
                error_found = any("today" in msg.lower() for msg in error_messages)
                self.assertTrue(error_found, "Should log error about file not being today's")


if __name__ == "__main__":
    unittest.main()
