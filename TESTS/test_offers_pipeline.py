# -*- coding: utf-8 -*-
"""
Tests for the Offers List pipeline (offers_module & offers_option).
Hermetic test suite exercising single-CSV processing, digit validation,
Word document generation without COM/Outlook, and villa removal regression guards.
"""
import csv
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import MODULES.offers_module as om
from MODULES.offers_module import (
    extract_excel_data,
    identify_digit_type,
    generate_word_document,
    execute_offers_pipeline,
    write_arrival_record,
    get_last_record_failures,
    classify_order,
)
from MODULES.offers.keyword_rules import classify_order as classify_order_direct
from MODULES.common import paths_config


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


if __name__ == "__main__":
    unittest.main()
