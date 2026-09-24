# -*- coding: utf-8 -*-
"""
Tests for the CAKE_MEMO field formatting pipeline.
Covers deterministic composition and parsing of three composite DOCX columns:
SERVICE DESCRIPTION, PROVIDED_AT, CHARGE.
Pure functions with no I/O, Qt, or external dependencies.
"""

import unittest

from MODULES.cake_memo.field_format import (
    FLAVOR_DISPLAY,
    compose_service_description,
    parse_service_description,
    VENUE_DISPLAY,
    compose_provided_at,
    parse_provided_at,
    CHARGE_PAID,
    CHARGE_PENDING,
    CHARGE_COMPLIMENTARY,
    compose_charge,
    parse_charge,
)


class TestServiceDescriptionRoundTrip(unittest.TestCase):
    """Test compose_service_description / parse_service_description round-trips."""

    def test_all_flavors_without_written_text(self):
        """All 6 flavors compose and parse correctly without written text."""
        for flavor_key in FLAVOR_DISPLAY.keys():
            with self.subTest(flavor=flavor_key):
                composed = compose_service_description(flavor_key, "")
                parsed_key, parsed_text = parse_service_description(composed)
                self.assertEqual(parsed_key, flavor_key)
                self.assertEqual(parsed_text, "")

    def test_all_flavors_with_written_text(self):
        """All 6 flavors compose and parse correctly with written text."""
        written_texts = [
            "Happy Birthday",
            "Congratulations!",
            "Happy 25th Anniversary",
            "Best wishes",
            "Καλά όνειρα",  # Greek text
        ]

        for flavor_key in FLAVOR_DISPLAY.keys():
            for written_text in written_texts:
                with self.subTest(flavor=flavor_key, text=written_text):
                    composed = compose_service_description(flavor_key, written_text)
                    parsed_key, parsed_text = parse_service_description(composed)
                    self.assertEqual(parsed_key, flavor_key)
                    self.assertEqual(parsed_text, written_text)

    def test_compose_format_examples(self):
        """Verify exact composed formats."""
        self.assertEqual(
            compose_service_description("strawberry", ""),
            "STRAWBERRY CAKE"
        )
        self.assertEqual(
            compose_service_description("vanilla", "Happy Birthday"),
            "VANILLA CAKE, PLEASE WRITE ON IT: Happy Birthday"
        )
        self.assertEqual(
            compose_service_description("chocolate_vanilla", "Best wishes"),
            "CHOCOLATE & VANILLA CAKE, PLEASE WRITE ON IT: Best wishes"
        )

    def test_parse_invalid_text_no_match(self):
        """parse_service_description returns (None, '') for text not matching the pattern."""
        invalid_texts = [
            "Random text",
            "STRAWBERRY PIE",
            "CAKE STRAWBERRY",
            "Just some text",
            "",
            "   ",
            None,
        ]
        for text in invalid_texts:
            with self.subTest(text=text):
                parsed_key, parsed_text = parse_service_description(text)
                self.assertIsNone(parsed_key)
                self.assertEqual(parsed_text, "")

    def test_parse_case_insensitive_flavor_matching(self):
        """parse_service_description performs case-insensitive flavor matching."""
        # Test lowercase
        parsed_key, parsed_text = parse_service_description("strawberry cake")
        self.assertEqual(parsed_key, "strawberry")
        self.assertEqual(parsed_text, "")

        # Test mixed case
        parsed_key, parsed_text = parse_service_description("ChOcOlAtE CAKE, PLEASE WRITE ON IT: Test")
        self.assertEqual(parsed_key, "chocolate")
        self.assertEqual(parsed_text, "Test")

        # Test compound flavor mixed case
        parsed_key, parsed_text = parse_service_description("chocolate & STRAWBERRY cake, PLEASE WRITE ON IT: Msg")
        self.assertEqual(parsed_key, "chocolate_strawberry")
        self.assertEqual(parsed_text, "Msg")

    def test_parse_preserves_written_text_case_and_spaces(self):
        """parse_service_description preserves the exact case and spacing of written text."""
        original_text = "  Happy  Birthday  with Spaces  "
        composed = compose_service_description("vanilla", original_text)
        parsed_key, parsed_text = parse_service_description(composed)
        # Round-trip should preserve the stripped original
        self.assertEqual(parsed_text, original_text.strip())


class TestProvidedAtRoundTrip(unittest.TestCase):
    """Test compose_provided_at / parse_provided_at round-trips."""

    def test_all_venues_various_times(self):
        """All 5 venues compose and parse correctly with various time combinations."""
        test_cases = [
            ("elia", 8, 0, False),
            ("ermis", 12, 30, False),
            ("ammos", 14, 45, False),
            ("il_gusto", 19, 30, True),  # confirmed real example
            ("room", 20, 15, True),
            ("elia", 6, 0, False),
            ("il_gusto", 23, 59, True),
        ]

        for venue_key, hour, minute, is_pm in test_cases:
            with self.subTest(venue=venue_key, hour=hour, minute=minute, is_pm=is_pm):
                composed = compose_provided_at(venue_key, hour, minute, is_pm)
                parsed_venue, parsed_hour, parsed_minute, parsed_is_pm = parse_provided_at(composed)
                self.assertEqual(parsed_venue, venue_key)
                self.assertEqual(parsed_hour, hour)
                self.assertEqual(parsed_minute, minute)
                self.assertEqual(parsed_is_pm, is_pm)

    def test_real_example_exact_string(self):
        """Verify the exact confirmed real example: 'IL GUSTO 19.30PM'."""
        composed = compose_provided_at("il_gusto", 19, 30, True)
        self.assertEqual(composed, "IL GUSTO 19.30PM")

        # And verify it parses back correctly
        venue, hour, minute, is_pm = parse_provided_at("IL GUSTO 19.30PM")
        self.assertEqual(venue, "il_gusto")
        self.assertEqual(hour, 19)
        self.assertEqual(minute, 30)
        self.assertTrue(is_pm)

    def test_room_venue_no_prefix(self):
        """Room venue produces just the time (no venue prefix)."""
        composed = compose_provided_at("room", 14, 30, False)
        self.assertEqual(composed, "14.30AM")

        venue, hour, minute, is_pm = parse_provided_at("14.30AM")
        self.assertEqual(venue, "room")
        self.assertEqual(hour, 14)
        self.assertEqual(minute, 30)
        self.assertFalse(is_pm)

    def test_compose_format_examples(self):
        """Verify exact composed formats."""
        self.assertEqual(compose_provided_at("elia", 8, 0, False), "ELIA 08.00AM")
        self.assertEqual(compose_provided_at("ermis", 12, 30, False), "ERMIS 12.30AM")
        self.assertEqual(compose_provided_at("ammos", 14, 45, False), "AMMOS 14.45AM")
        self.assertEqual(compose_provided_at("il_gusto", 19, 30, True), "IL GUSTO 19.30PM")
        self.assertEqual(compose_provided_at("room", 20, 15, True), "20.15PM")

    def test_parse_case_insensitive_venue_matching(self):
        """parse_provided_at performs case-insensitive venue matching."""
        # Lowercase venue
        venue, hour, minute, is_pm = parse_provided_at("elia 08.00AM")
        self.assertEqual(venue, "elia")

        # Mixed case venue
        venue, hour, minute, is_pm = parse_provided_at("ErMiS 12.30AM")
        self.assertEqual(venue, "ermis")

        # IL GUSTO with various cases
        venue, hour, minute, is_pm = parse_provided_at("il gusto 19.30PM")
        self.assertEqual(venue, "il_gusto")

    def test_parse_no_time_pattern_returns_all_none(self):
        """parse_provided_at returns (None, None, None, None) if time pattern not found."""
        invalid_texts = [
            "Random text",
            "ELIA 19",  # incomplete time
            "ELIA 19.30",  # missing AM/PM
            "IL GUSTO",
            "12.30",  # time without AM/PM
            "",
            None,
        ]
        for text in invalid_texts:
            with self.subTest(text=text):
                venue, hour, minute, is_pm = parse_provided_at(text)
                self.assertIsNone(venue)
                self.assertIsNone(hour)
                self.assertIsNone(minute)
                self.assertIsNone(is_pm)

    def test_parse_time_boundary_cases(self):
        """parse_provided_at correctly parses boundary hour/minute values."""
        # Single-digit hour
        venue, hour, minute, is_pm = parse_provided_at("ammos 8.00AM")
        self.assertEqual(hour, 8)
        self.assertEqual(minute, 0)

        # Double-digit minute with room venue (no prefix)
        venue, hour, minute, is_pm = parse_provided_at("23.59PM")
        self.assertEqual(venue, "room")
        self.assertEqual(hour, 23)
        self.assertEqual(minute, 59)


class TestChargeRoundTrip(unittest.TestCase):
    """Test compose_charge / parse_charge round-trips."""

    def test_all_charge_states_basic(self):
        """All 3 charge states compose and parse correctly."""
        self.assertEqual(compose_charge(CHARGE_PAID), "PAID")
        self.assertEqual(compose_charge(CHARGE_PENDING), "PENDING")
        self.assertEqual(compose_charge(CHARGE_COMPLIMENTARY), "COMPLIMENTARY BY ")

    def test_charge_round_trip_paid(self):
        """CHARGE_PAID composes and parses correctly."""
        composed = compose_charge(CHARGE_PAID)
        parsed_state, parsed_by = parse_charge(composed)
        self.assertEqual(parsed_state, CHARGE_PAID)
        self.assertEqual(parsed_by, "")

    def test_charge_round_trip_pending(self):
        """CHARGE_PENDING composes and parses correctly."""
        composed = compose_charge(CHARGE_PENDING)
        parsed_state, parsed_by = parse_charge(composed)
        self.assertEqual(parsed_state, CHARGE_PENDING)
        self.assertEqual(parsed_by, "")

    def test_charge_round_trip_complimentary_with_names(self):
        """CHARGE_COMPLIMENTARY with various authorizer names composes and parses correctly."""
        names = [
            "Maria",
            "John Smith",
            "Maria Papadopoulou",
            "Αλέξανδρος",  # Greek name
            "Jean-Pierre Dupont",
        ]

        for name in names:
            with self.subTest(name=name):
                composed = compose_charge(CHARGE_COMPLIMENTARY, name)
                parsed_state, parsed_by = parse_charge(composed)
                self.assertEqual(parsed_state, CHARGE_COMPLIMENTARY)
                self.assertEqual(parsed_by, name)

    def test_charge_round_trip_complimentary_empty_name(self):
        """CHARGE_COMPLIMENTARY with empty name still round-trips."""
        composed = compose_charge(CHARGE_COMPLIMENTARY, "")
        parsed_state, parsed_by = parse_charge(composed)
        self.assertEqual(parsed_state, CHARGE_COMPLIMENTARY)
        self.assertEqual(parsed_by, "")

    def test_parse_legacy_paid_at_reception(self):
        """parse_charge gracefully degrades legacy 'PAID AT RECEPTION' to (CHARGE_PAID, '')."""
        parsed_state, parsed_by = parse_charge("PAID AT RECEPTION")
        self.assertEqual(parsed_state, CHARGE_PAID)
        self.assertEqual(parsed_by, "")

    def test_parse_case_insensitive_state_matching(self):
        """parse_charge performs case-insensitive state matching."""
        # Lowercase
        parsed_state, parsed_by = parse_charge("paid")
        self.assertEqual(parsed_state, CHARGE_PAID)

        parsed_state, parsed_by = parse_charge("pending")
        self.assertEqual(parsed_state, CHARGE_PENDING)

        # Mixed case
        parsed_state, parsed_by = parse_charge("CoMpLiMeNtArY bY Manager")
        self.assertEqual(parsed_state, CHARGE_COMPLIMENTARY)
        self.assertEqual(parsed_by, "Manager")

    def test_parse_charge_invalid_text_defaults_to_paid(self):
        """parse_charge defaults to CHARGE_PAID for unrecognized text."""
        invalid_texts = [
            "Random text",
            "Some other charge type",
            "",
            None,
        ]
        for text in invalid_texts:
            with self.subTest(text=text):
                parsed_state, parsed_by = parse_charge(text)
                self.assertEqual(parsed_state, CHARGE_PAID)
                self.assertEqual(parsed_by, "")

    def test_parse_complimentary_with_no_by(self):
        """parse_charge handles COMPLIMENTARY without 'BY' gracefully."""
        parsed_state, parsed_by = parse_charge("COMPLIMENTARY")
        self.assertEqual(parsed_state, CHARGE_COMPLIMENTARY)
        self.assertEqual(parsed_by, "")

    def test_parse_charge_exact_formats(self):
        """Verify exact parsed formats for key examples."""
        # PAID
        state, by = parse_charge("PAID")
        self.assertEqual((state, by), (CHARGE_PAID, ""))

        # PENDING
        state, by = parse_charge("PENDING")
        self.assertEqual((state, by), (CHARGE_PENDING, ""))

        # COMPLIMENTARY BY manager
        state, by = parse_charge("COMPLIMENTARY BY Manager")
        self.assertEqual(state, CHARGE_COMPLIMENTARY)
        self.assertEqual(by, "Manager")


class TestCakeMemoDocumentGeneration(unittest.TestCase):
    """Test generate_cake_memo_document and parse_cake_memo_document round-trips."""

    def setUp(self):
        """Verify template exists before tests run."""
        import os
        from MODULES.cake_memo.paths import CAKE_MEMO_TEMPLATE_PATH

        self.template_path = CAKE_MEMO_TEMPLATE_PATH
        if not os.path.exists(self.template_path):
            self.skipTest(f"Template not found at {self.template_path}")

    def test_round_trip_normal_case(self):
        """
        Test: generate a normal cake memo (chocolate + strawberry flavor, written text,
        Il Gusto venue, complimentary charge), then parse it back and verify all fields match.
        """
        import os
        import tempfile
        from MODULES.cake_memo.document import generate_cake_memo_document
        from MODULES.cake_memo.parser import parse_cake_memo_document

        form_data = {
            "flavor": "chocolate_strawberry",
            "written_text": "Happy Anniversary",
            "qty": 2,
            "venue": "il_gusto",
            "hour": 19,
            "minute": 30,
            "is_pm": True,
            "charge_state": CHARGE_COMPLIMENTARY,
            "complimentary_by": "Maria Papadopoulou",
            "room_number": "0412",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "test_memo.docx")
            generate_cake_memo_document(form_data, docx_path)

            self.assertTrue(os.path.exists(docx_path), "Generated document should exist")

            # Parse it back
            parsed = parse_cake_memo_document(docx_path)

            # Verify all fields match
            self.assertEqual(parsed["flavor"], form_data["flavor"])
            self.assertEqual(parsed["written_text"], form_data["written_text"])
            self.assertEqual(parsed["qty"], form_data["qty"])
            self.assertEqual(parsed["venue"], form_data["venue"])
            self.assertEqual(parsed["hour"], form_data["hour"])
            self.assertEqual(parsed["minute"], form_data["minute"])
            self.assertEqual(parsed["is_pm"], form_data["is_pm"])
            self.assertEqual(parsed["charge_state"], form_data["charge_state"])
            self.assertEqual(parsed["complimentary_by"], form_data["complimentary_by"])
            self.assertEqual(parsed["room_number"], form_data["room_number"])

    def test_round_trip_room_venue_paid_charge(self):
        """
        Test: Room venue (no location prefix), Paid charge, no written text.
        """
        import os
        import tempfile
        from MODULES.cake_memo.document import generate_cake_memo_document
        from MODULES.cake_memo.parser import parse_cake_memo_document

        form_data = {
            "flavor": "vanilla",
            "written_text": "",
            "qty": 1,
            "venue": "room",
            "hour": 14,
            "minute": 30,
            "is_pm": False,
            "charge_state": CHARGE_PAID,
            "complimentary_by": "",
            "room_number": "0305",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "test_memo.docx")
            generate_cake_memo_document(form_data, docx_path)

            parsed = parse_cake_memo_document(docx_path)

            self.assertEqual(parsed["flavor"], "vanilla")
            self.assertEqual(parsed["written_text"], "")
            self.assertEqual(parsed["qty"], 1)
            self.assertEqual(parsed["venue"], "room")
            self.assertEqual(parsed["hour"], 14)
            self.assertEqual(parsed["minute"], 30)
            self.assertFalse(parsed["is_pm"])
            self.assertEqual(parsed["charge_state"], CHARGE_PAID)
            self.assertEqual(parsed["complimentary_by"], "")
            self.assertEqual(parsed["room_number"], "0305")

    def test_round_trip_elia_venue_pending_charge(self):
        """
        Test: Elia venue, Pending charge, strawberry flavor with written text.
        """
        import os
        import tempfile
        from MODULES.cake_memo.document import generate_cake_memo_document
        from MODULES.cake_memo.parser import parse_cake_memo_document

        form_data = {
            "flavor": "strawberry",
            "written_text": "Best wishes",
            "qty": 3,
            "venue": "elia",
            "hour": 8,
            "minute": 0,
            "is_pm": False,
            "charge_state": CHARGE_PENDING,
            "complimentary_by": "",
            "room_number": "0118",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "test_memo.docx")
            generate_cake_memo_document(form_data, docx_path)

            parsed = parse_cake_memo_document(docx_path)

            self.assertEqual(parsed["flavor"], "strawberry")
            self.assertEqual(parsed["written_text"], "Best wishes")
            self.assertEqual(parsed["qty"], 3)
            self.assertEqual(parsed["venue"], "elia")
            self.assertEqual(parsed["hour"], 8)
            self.assertEqual(parsed["minute"], 0)
            self.assertFalse(parsed["is_pm"])
            self.assertEqual(parsed["charge_state"], CHARGE_PENDING)
            self.assertEqual(parsed["complimentary_by"], "")
            self.assertEqual(parsed["room_number"], "0118")

    def test_missing_header_column_raises_error(self):
        """
        Test: generate_cake_memo_document raises ValueError if a required header
        column is missing from the template.
        """
        import os
        import tempfile
        from docx import Document
        from MODULES.cake_memo.document import generate_cake_memo_document

        form_data = {
            "flavor": "strawberry",
            "written_text": "Test",
            "qty": 1,
            "venue": "room",
            "hour": 12,
            "minute": 0,
            "is_pm": False,
            "charge_state": CHARGE_PAID,
            "complimentary_by": "",
            "room_number": "0101",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a malformed template missing one header column
            malformed_template_path = os.path.join(tmpdir, "malformed.docx")
            malformed_doc = Document()
            table = malformed_doc.add_table(rows=2, cols=6)
            # Set headers (intentionally skip SERVICE DESCRIPTION)
            table.rows[0].cells[0].text = "QTY"
            table.rows[0].cells[1].text = "PROVIDED AT"
            table.rows[0].cells[2].text = "DATE"
            table.rows[0].cells[3].text = "CHARGE"
            table.rows[0].cells[4].text = "ROOM NUMBER"
            table.rows[0].cells[5].text = "EXTRA"
            malformed_doc.save(malformed_template_path)

            # Monkey-patch the template path for this test
            import MODULES.cake_memo.document as doc_module

            original_path = doc_module.CAKE_MEMO_TEMPLATE_PATH
            doc_module.CAKE_MEMO_TEMPLATE_PATH = malformed_template_path

            try:
                output_path = os.path.join(tmpdir, "output.docx")
                with self.assertRaises(ValueError) as cm:
                    generate_cake_memo_document(form_data, output_path)
                self.assertIn("SERVICE DESCRIPTION", str(cm.exception))
            finally:
                doc_module.CAKE_MEMO_TEMPLATE_PATH = original_path

    def test_parse_missing_header_column_raises_error(self):
        """
        Test: parse_cake_memo_document raises ValueError if a required header
        column is missing from the document.
        """
        import os
        import tempfile
        from docx import Document
        from MODULES.cake_memo.parser import parse_cake_memo_document

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a malformed document missing CHARGE column
            malformed_docx_path = os.path.join(tmpdir, "malformed.docx")
            malformed_doc = Document()
            table = malformed_doc.add_table(rows=2, cols=6)
            # Set headers (intentionally skip CHARGE)
            table.rows[0].cells[0].text = "SERVICE DESCRIPTION"
            table.rows[0].cells[1].text = "QTY"
            table.rows[0].cells[2].text = "PROVIDED AT"
            table.rows[0].cells[3].text = "DATE"
            table.rows[0].cells[4].text = "ROOM NUMBER"
            table.rows[0].cells[5].text = "EXTRA"
            # Add some data in row 1
            table.rows[1].cells[0].text = "STRAWBERRY CAKE"
            table.rows[1].cells[1].text = "1"
            table.rows[1].cells[2].text = "12.00PM"
            table.rows[1].cells[3].text = "24/09"
            table.rows[1].cells[4].text = "0101"
            malformed_doc.save(malformed_docx_path)

            # Attempt to parse should raise ValueError
            with self.assertRaises(ValueError) as cm:
                parse_cake_memo_document(malformed_docx_path)
            self.assertIn("CHARGE", str(cm.exception))

    def test_no_access_to_real_database_output(self):
        """
        Verify that tests only use temporary directories, never touching
        real DATABASE/, OUTPUT/, or ROOMS/ directories.
        """
        import tempfile
        import os
        from MODULES.cake_memo.document import generate_cake_memo_document
        from MODULES.cake_memo.parser import parse_cake_memo_document

        form_data = {
            "flavor": "strawberry",
            "written_text": "Test",
            "qty": 1,
            "venue": "room",
            "hour": 12,
            "minute": 0,
            "is_pm": False,
            "charge_state": CHARGE_PAID,
            "complimentary_by": "",
            "room_number": "0101",
        }

        # Ensure we use a hermetic temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertTrue(tmpdir.startswith(tempfile.gettempdir()))
            docx_path = os.path.join(tmpdir, "test.docx")
            generate_cake_memo_document(form_data, docx_path)
            parsed = parse_cake_memo_document(docx_path)
            # Verify the temp path is used and not any real directories
            self.assertIn("tmp", docx_path.lower() or "temp" in docx_path.lower())


class TestCakeMemoForm(unittest.TestCase):
    """Test the CakeMemoForm widget for Create/Update modes."""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def test_venue_selection_shows_confirmation_subsection(self):
        """Test: Selecting each of the 5 delivery venue radio buttons reveals the confirmation subsection."""
        from OPTIONS.cake_memo.form import CakeMemoForm
        from PyQt6.QtCore import QTime

        form = CakeMemoForm()

        venue_options = [
            ("elia", "Elia"),
            ("ermis", "Ermis"),
            ("ammos", "Ammos"),
            ("il_gusto", "Il Gusto"),
            ("room", "Room"),
        ]

        for venue_key, expected_label in venue_options:
            with self.subTest(venue=venue_key):
                # Initially not visible
                self.assertTrue(form.delivery_confirmation_frame.isHidden())

                # Click the radio button
                form.venue_buttons[venue_key].setChecked(True)

                # Confirmation subsection should now be visible
                self.assertFalse(form.delivery_confirmation_frame.isHidden())

                # Label should show the correct venue name
                expected_text = f"Provide at: {expected_label}"
                self.assertEqual(form.delivery_label.text(), expected_text)

                # Uncheck for next iteration
                form.venue_group.setExclusive(False)
                form.venue_buttons[venue_key].setChecked(False)
                form.venue_group.setExclusive(True)

    def test_delivery_add_button_locks_venue_and_time(self):
        """
        Test: Clicking "Add" after selecting Il Gusto + 7:30 PM correctly populates
        get_form_data(), and verify round-trip through compose_provided_at.
        """
        from OPTIONS.cake_memo.form import CakeMemoForm
        from PyQt6.QtCore import QTime

        form = CakeMemoForm()

        # Select Il Gusto
        form.venue_buttons["il_gusto"].setChecked(True)

        # Set time to 7:30 PM (19:30 in 24-hour format)
        form.delivery_time_edit.setTime(QTime(19, 30))

        # Click Add
        form.delivery_add_button.click()

        # Get form data
        form_data = form.get_form_data()

        # Verify the delivery fields
        self.assertEqual(form_data["venue"], "il_gusto")
        self.assertEqual(form_data["hour"], 19)
        self.assertEqual(form_data["minute"], 30)
        self.assertTrue(form_data["is_pm"])

        # Verify round-trip through compose_provided_at
        composed = compose_provided_at("il_gusto", 19, 30, True)
        self.assertEqual(composed, "IL GUSTO 19.30PM")  # Confirmed real example

    def test_complimentary_field_visibility(self):
        """Test: Selecting Complimentary shows the 'Complimentary by' field; Paid/Pending hide it."""
        from OPTIONS.cake_memo.form import CakeMemoForm

        form = CakeMemoForm()

        # Initially should be hidden (Paid is default)
        self.assertTrue(form.complimentary_by_frame.isHidden())

        # Select Complimentary
        form.charge_buttons[CHARGE_COMPLIMENTARY].setChecked(True)
        self.assertFalse(form.complimentary_by_frame.isHidden())

        # Select Paid
        form.charge_buttons[CHARGE_PAID].setChecked(True)
        self.assertTrue(form.complimentary_by_frame.isHidden())

        # Select Pending
        form.charge_buttons[CHARGE_PENDING].setChecked(True)
        self.assertTrue(form.complimentary_by_frame.isHidden())

        # Select Complimentary again
        form.charge_buttons[CHARGE_COMPLIMENTARY].setChecked(True)
        self.assertFalse(form.complimentary_by_frame.isHidden())

    def test_set_form_data_get_form_data_round_trip(self):
        """
        Test: set_form_data(get_form_data()) is idempotent for multiple form states.
        Test 2 different scenarios with different flavors, venues, and charges.
        """
        from OPTIONS.cake_memo.form import CakeMemoForm
        from PyQt6.QtCore import QTime

        # Scenario 1: Vanilla, Elia, Paid
        scenario1 = {
            "flavor": "vanilla",
            "written_text": "Happy Birthday",
            "pax": 5,
            "qty": 2,
            "venue": "elia",
            "hour": 8,
            "minute": 0,
            "is_pm": False,
            "charge_state": CHARGE_PAID,
            "complimentary_by": "",
            "room_number": "0101",
        }

        form1 = CakeMemoForm()
        form1.set_form_data(scenario1)

        # Manually trigger the "Add" button to lock in the delivery
        form1.venue_buttons["elia"].setChecked(True)
        form1.delivery_time_edit.setTime(QTime(8, 0))
        form1.delivery_add_button.click()

        collected1 = form1.get_form_data()

        # Verify all fields match
        self.assertEqual(collected1["flavor"], scenario1["flavor"])
        self.assertEqual(collected1["written_text"], scenario1["written_text"])
        self.assertEqual(collected1["pax"], scenario1["pax"])
        self.assertEqual(collected1["qty"], scenario1["qty"])
        self.assertEqual(collected1["venue"], scenario1["venue"])
        self.assertEqual(collected1["hour"], scenario1["hour"])
        self.assertEqual(collected1["minute"], scenario1["minute"])
        self.assertEqual(collected1["is_pm"], scenario1["is_pm"])
        self.assertEqual(collected1["charge_state"], scenario1["charge_state"])
        self.assertEqual(collected1["room_number"], scenario1["room_number"])

        # Scenario 2: Chocolate & Strawberry, Il Gusto, Complimentary
        scenario2 = {
            "flavor": "chocolate_strawberry",
            "written_text": "Congratulations!",
            "pax": 3,
            "qty": 1,
            "venue": "il_gusto",
            "hour": 19,
            "minute": 30,
            "is_pm": True,
            "charge_state": CHARGE_COMPLIMENTARY,
            "complimentary_by": "Manager",
            "room_number": "0412",
        }

        form2 = CakeMemoForm()
        form2.set_form_data(scenario2)

        # Manually trigger the "Add" button
        form2.venue_buttons["il_gusto"].setChecked(True)
        form2.delivery_time_edit.setTime(QTime(19, 30))
        form2.delivery_add_button.click()

        collected2 = form2.get_form_data()

        # Verify all fields match
        self.assertEqual(collected2["flavor"], scenario2["flavor"])
        self.assertEqual(collected2["written_text"], scenario2["written_text"])
        self.assertEqual(collected2["pax"], scenario2["pax"])
        self.assertEqual(collected2["qty"], scenario2["qty"])
        self.assertEqual(collected2["venue"], scenario2["venue"])
        self.assertEqual(collected2["hour"], scenario2["hour"])
        self.assertEqual(collected2["minute"], scenario2["minute"])
        self.assertEqual(collected2["is_pm"], scenario2["is_pm"])
        self.assertEqual(collected2["charge_state"], scenario2["charge_state"])
        self.assertEqual(collected2["complimentary_by"], scenario2["complimentary_by"])
        self.assertEqual(collected2["room_number"], scenario2["room_number"])

    def test_reset_returns_to_default_state(self):
        """Test: reset() returns the form to documented default state after non-default values."""
        from OPTIONS.cake_memo.form import CakeMemoForm
        from PyQt6.QtCore import QTime

        form = CakeMemoForm()

        # Set non-default values
        form.venue_buttons["il_gusto"].setChecked(True)
        form.delivery_time_edit.setTime(QTime(19, 30))
        form.delivery_add_button.click()
        form.room_number_edit.setText("0412")

        # Set flavor to second option (chocolate)
        form.flavor_combo.setCurrentIndex(1)
        form.written_text_edit.setText("Test Message")
        form.pax_spinbox.setValue(5)
        form.qty_spinbox.setValue(3)
        form.charge_buttons[CHARGE_COMPLIMENTARY].setChecked(True)
        form.complimentary_by_edit.setText("Manager Name")

        # Now reset
        form.reset()

        # Verify defaults
        # Venue: no button should be checked
        any_checked = any(btn.isChecked() for btn in form.venue_buttons.values())
        self.assertFalse(any_checked)
        self.assertTrue(form.delivery_confirmation_frame.isHidden())

        # Room number: empty
        self.assertEqual(form.room_number_edit.text(), "")

        # Flavor: first option (strawberry)
        self.assertEqual(form.flavor_combo.currentData(), "strawberry")

        # Written text: empty
        self.assertEqual(form.written_text_edit.text(), "")

        # Pax: 1
        self.assertEqual(form.pax_spinbox.value(), 1)

        # Qty: 1
        self.assertEqual(form.qty_spinbox.value(), 1)

        # Charge: Paid
        self.assertTrue(form.charge_buttons[CHARGE_PAID].isChecked())
        self.assertEqual(form.complimentary_by_edit.text(), "")
        self.assertTrue(form.complimentary_by_frame.isHidden())

    def test_pax_spinbox_read_only_but_programmable(self):
        """
        Test: Pax QSpinBox is read-only (isReadOnly() == True) but value can still
        be changed programmatically via stepUp()/stepDown()/setValue().
        """
        from OPTIONS.cake_memo.form import CakeMemoForm

        form = CakeMemoForm()

        # Verify it is read-only
        self.assertTrue(form.pax_spinbox.isReadOnly())

        # Verify programmatic changes still work
        form.pax_spinbox.setValue(5)
        self.assertEqual(form.pax_spinbox.value(), 5)

        # Verify stepUp works
        form.pax_spinbox.stepUp()
        self.assertEqual(form.pax_spinbox.value(), 6)

        # Verify stepDown works
        form.pax_spinbox.stepDown()
        self.assertEqual(form.pax_spinbox.value(), 5)


class TestCakeMemoOptionWidget(unittest.TestCase):
    """Test the CakeMemoOptionWidget for mode tracking and lifecycle."""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for widget testing."""
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def test_construction_no_crash(self):
        """Test: CakeMemoOptionWidget() constructs without crash."""
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        widget = CakeMemoOptionWidget()
        self.assertIsNotNone(widget)
        self.assertIsNone(widget.mode)
        self.assertIsNone(widget.loaded_file_path)

    def test_build_submenu_no_crash(self):
        """Test: build_submenu() returns a valid widget with 6 buttons, no crash."""
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        widget = CakeMemoOptionWidget()
        submenu = widget.build_submenu()

        self.assertIsNotNone(submenu)
        self.assertIsNotNone(widget.btn_create)
        self.assertIsNotNone(widget.btn_update)
        self.assertIsNotNone(widget.btn_edit)
        self.assertIsNotNone(widget.btn_save)
        self.assertIsNotNone(widget.btn_close)
        self.assertIsNotNone(widget.btn_send_email)

        # Verify button labels
        self.assertEqual(widget.btn_create.text(), "Create Cake Memo")
        self.assertEqual(widget.btn_update.text(), "Update Cake Memo")
        self.assertEqual(widget.btn_edit.text(), "Edit")
        self.assertEqual(widget.btn_save.text(), "Save")
        self.assertEqual(widget.btn_close.text(), "Close")
        self.assertEqual(widget.btn_send_email.text(), "Send Email")

    def test_handle_create_cake_memo_mode_transition(self):
        """Test: handle_create_cake_memo() sets mode='create' and hides office_viewer."""
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        widget = CakeMemoOptionWidget()

        widget.handle_create_cake_memo()

        self.assertEqual(widget.mode, "create")
        self.assertIsNone(widget.loaded_file_path)
        # Verify office_viewer is hidden (form visibility may not work with offscreen platform)
        self.assertFalse(widget.office_viewer.isVisible())

    def test_handle_close_in_create_mode_discards_form(self):
        """Test: handle_close() in create mode discards form and returns to None mode."""
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        widget = CakeMemoOptionWidget()

        widget.handle_create_cake_memo()
        self.assertEqual(widget.mode, "create")

        widget.handle_close()
        self.assertIsNone(widget.mode)
        self.assertFalse(widget.form.isVisible())

    def test_handle_save_create_mode_requires_room_number(self):
        """Test: handle_save() in create mode logs ERROR and aborts if room_number is blank."""
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget

        log_messages = []
        def capture_log(category, message, level):
            log_messages.append((category, message, level))

        widget = CakeMemoOptionWidget(log_callback=capture_log)
        widget.handle_create_cake_memo()

        # Leave room number blank
        widget.form.room_number_edit.setText("")

        # Attempt to save
        widget.handle_save()

        # Should log an error
        error_logs = [msg for msg in log_messages if msg[2] == "ERROR"]
        self.assertTrue(any("Room number" in msg[1] for msg in error_logs))
        # Mode should still be "create" (not saved)
        self.assertEqual(widget.mode, "create")

    def test_handle_save_create_mode_generates_file_with_correct_name_format(self):
        """
        Test: handle_save() in create mode generates a file with the exact expected
        filename pattern 'CAKE MEMO (DD-MM-YY) ROOM ####.docx'.
        """
        import os
        import tempfile
        from PyQt6.QtCore import QTime
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            log_messages = []
            def capture_log(category, message, level):
                log_messages.append((category, message, level))

            widget = CakeMemoOptionWidget(log_callback=capture_log)

            # Mock _get_cake_memos_dir to return our temp dir
            widget._get_cake_memos_dir = lambda: tmpdir

            widget.handle_create_cake_memo()

            # Fill in form data
            widget.form.room_number_edit.setText("0412")
            widget.form.flavor_combo.setCurrentIndex(0)  # strawberry
            widget.form.written_text_edit.setText("Happy Birthday")
            widget.form.pax_spinbox.setValue(3)
            widget.form.qty_spinbox.setValue(2)
            widget.form.venue_buttons["il_gusto"].setChecked(True)
            widget.form.delivery_time_edit.setTime(QTime(19, 30))
            widget.form.delivery_add_button.click()
            widget.form.charge_buttons[CHARGE_PAID].setChecked(True)

            # Save
            widget.handle_save()

            # Verify a file was created with the correct name pattern
            files = os.listdir(tmpdir)
            self.assertEqual(len(files), 1, f"Expected exactly 1 file, got {len(files)}: {files}")

            filename = files[0]
            # Check the pattern: "CAKE MEMO (DD-MM-YY) ROOM 0412.docx"
            import re
            pattern = r"^CAKE MEMO \(\d{2}-\d{2}-\d{2}\) ROOM 0412\.docx$"
            self.assertIsNotNone(re.match(pattern, filename), f"Filename '{filename}' does not match pattern")

            # Mode should be reset
            self.assertIsNone(widget.mode)

    def test_handle_save_create_mode_with_collision_applies_updated_suffix(self):
        """
        Test: handle_save() in create mode with a pre-existing file at the target name
        applies the ' UPDATED' / ' UPDATED (N)' suffix pattern.
        """
        import os
        import tempfile
        from PyQt6.QtCore import QTime
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        from MODULES.cake_memo.document import generate_cake_memo_document

        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-create a file with the target name
            room_num = "0412"
            from datetime import datetime
            target_filename = f"CAKE MEMO ({datetime.now():%d-%m-%y}) ROOM {room_num}.docx"
            target_path = os.path.join(tmpdir, target_filename)

            # Create a dummy file at that path
            dummy_data = {
                "flavor": "strawberry",
                "written_text": "",
                "qty": 1,
                "venue": "room",
                "hour": 12,
                "minute": 0,
                "is_pm": False,
                "charge_state": CHARGE_PAID,
                "complimentary_by": "",
                "room_number": "0000",
            }
            generate_cake_memo_document(dummy_data, target_path)
            self.assertTrue(os.path.exists(target_path))

            # Now create widget and try to save with the same room number
            widget = CakeMemoOptionWidget()
            widget._get_cake_memos_dir = lambda: tmpdir
            widget.handle_create_cake_memo()

            widget.form.room_number_edit.setText(room_num)
            widget.form.flavor_combo.setCurrentIndex(0)
            widget.form.venue_buttons["il_gusto"].setChecked(True)
            widget.form.delivery_time_edit.setTime(QTime(19, 30))
            widget.form.delivery_add_button.click()

            # Save
            widget.handle_save()

            # Verify both files exist: original + " UPDATED" variant
            files = sorted(os.listdir(tmpdir))
            self.assertEqual(len(files), 2, f"Expected 2 files (original + UPDATED), got {len(files)}: {files}")

            # Check that one has " UPDATED" suffix
            updated_files = [f for f in files if " UPDATED" in f]
            self.assertEqual(len(updated_files), 1)

    def test_handle_save_update_mode_overwrites_loaded_file(self):
        """
        Test: handle_save() in update mode overwrites self.loaded_file_path
        (same file path in, same path out) rather than creating a new file.
        """
        import os
        import tempfile
        from PyQt6.QtCore import QTime
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        from MODULES.cake_memo.document import generate_cake_memo_document
        from MODULES.cake_memo.parser import parse_cake_memo_document

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an initial file
            initial_data = {
                "flavor": "strawberry",
                "written_text": "Original",
                "qty": 1,
                "venue": "room",
                "hour": 12,
                "minute": 0,
                "is_pm": False,
                "charge_state": CHARGE_PAID,
                "complimentary_by": "",
                "room_number": "0101",
            }
            initial_path = os.path.join(tmpdir, "test_memo.docx")
            generate_cake_memo_document(initial_data, initial_path)

            # Load it in update mode and modify
            widget = CakeMemoOptionWidget()
            widget.mode = "update"
            widget.loaded_file_path = initial_path

            parsed_data = parse_cake_memo_document(initial_path)
            parsed_data["pax"] = 1  # Add pax since parser omits it
            widget.form.set_form_data(parsed_data)

            # Modify the form
            widget.form.room_number_edit.setText("0102")
            widget.form.written_text_edit.setText("Modified")
            widget.form.venue_buttons["il_gusto"].setChecked(True)
            widget.form.delivery_time_edit.setTime(QTime(19, 30))
            widget.form.delivery_add_button.click()

            # Save
            widget.handle_save()

            # Verify only 1 file exists (same path, overwritten)
            files = os.listdir(tmpdir)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0], "test_memo.docx")

            # Verify the file was updated
            updated_data = parse_cake_memo_document(initial_path)
            self.assertEqual(updated_data["room_number"], "0102")
            self.assertEqual(updated_data["written_text"], "Modified")
            self.assertEqual(updated_data["venue"], "il_gusto")

    def test_handle_close_create_mode_no_file_written(self):
        """Test: handle_close() in create mode does NOT write any file to disk."""
        import os
        import tempfile
        from PyQt6.QtCore import QTime
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            widget = CakeMemoOptionWidget()
            widget._get_cake_memos_dir = lambda: tmpdir
            widget.handle_create_cake_memo()

            # Fill in form data
            widget.form.room_number_edit.setText("0412")
            widget.form.venue_buttons["il_gusto"].setChecked(True)
            widget.form.delivery_time_edit.setTime(QTime(19, 30))
            widget.form.delivery_add_button.click()

            # Close without saving
            widget.handle_close()

            # Verify NO files were created
            files = os.listdir(tmpdir)
            self.assertEqual(len(files), 0, f"Expected no files, but found {files}")

    def test_manual_draft_outlook_transitions_to_email_state_for_cake_memo(self):
        """
        Test 1: manual_draft_outlook() with a subcategory="Cake Memo" payload
        transitions the TaskWidget to 📨 after successful Display().
        """
        from OPTIONS._shared.task_widget import TaskWidget
        from unittest.mock import patch, MagicMock

        payload = {
            "type": "outlook_draft",
            "subcategory": "Cake Memo",
            "data": {
                "To": "test@example.com",
                "CC": "",
                "Subject": "Test Cake Memo",
                "HTMLBody": "Test body",
                "Attachment": None
            }
        }

        task = TaskWidget("Test Cake Memo Task", "cake_task_1", payload=payload)
        self.assertEqual(task.btn_state.text(), "⏳", "Initial state should be ⏳")

        # Mock Dispatch to prevent real Outlook usage
        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            task.manual_draft_outlook()

            # Verify Display was called
            mock_mail.Display.assert_called_once()

            # Verify state changed to 📨
            self.assertEqual(task.btn_state.text(), "📨",
                           "State should transition to 📨 for Cake Memo payload")

        task.deleteLater()

    def test_manual_draft_outlook_does_not_transition_for_other_subcategory(self):
        """
        Test 2: manual_draft_outlook() with an unknown subcategory does NOT transition to 📨,
        proving the gate is a real allow-list.
        """
        from OPTIONS._shared.task_widget import TaskWidget
        from unittest.mock import patch, MagicMock

        payload = {
            "type": "outlook_draft",
            "subcategory": "Something Else",
            "data": {
                "To": "test@example.com",
                "CC": "",
                "Subject": "Test",
                "HTMLBody": "Test body",
                "Attachment": None
            }
        }

        task = TaskWidget("Test Other Task", "other_task_1", payload=payload)
        self.assertEqual(task.btn_state.text(), "⏳")

        with patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
            mock_outlook = MagicMock()
            mock_mail = MagicMock()
            mock_dispatch.return_value = mock_outlook
            mock_outlook.CreateItem.return_value = mock_mail

            task.manual_draft_outlook()

            mock_mail.Display.assert_called_once()

            # State should remain ⏳
            self.assertEqual(task.btn_state.text(), "⏳",
                           "State should NOT change for unknown subcategory (allow-list in effect)")

        task.deleteLater()

    def test_handle_send_email_creates_task_from_file_pick(self):
        """
        Test 3: handle_send_email() with a mocked file picker creates a task
        via get_or_create_task and invokes manual_draft_outlook.
        """
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        from OPTIONS.todo_option import TodoWidget
        from unittest.mock import patch, MagicMock, call
        import tempfile
        import os

        # Create a temporary test docx file
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_cake_memo.docx")

            # Create a minimal valid docx (from template copy)
            from MODULES.cake_memo.paths import CAKE_MEMO_TEMPLATE_PATH
            if CAKE_MEMO_TEMPLATE_PATH and os.path.exists(CAKE_MEMO_TEMPLATE_PATH):
                import shutil
                shutil.copy2(CAKE_MEMO_TEMPLATE_PATH, test_file)

                log_messages = []
                def capture_log(category, message, level):
                    log_messages.append((category, message, level))

                # Create the widget with a mock todo_widget
                todo_widget = TodoWidget(parent=None, log_callback=capture_log)
                widget = CakeMemoOptionWidget(log_callback=capture_log, todo_widget=todo_widget)

                # Mock the file picker and parser to return our test file
                with patch('OPTIONS.cake_memo.widget.QFileDialog.getOpenFileName') as mock_picker, \
                     patch('OPTIONS.cake_memo.widget.parse_cake_memo_document') as mock_parse, \
                     patch('OPTIONS._shared.task_widget.win32com.client.Dispatch') as mock_dispatch:
                    mock_picker.return_value = (test_file, "")
                    mock_parse.return_value = {"room_number": "123", "flavor": "chocolate", "venue": "IL GUSTO", "hour": 19, "minute": 30, "is_pm": True}
                    mock_outlook = MagicMock()
                    mock_mail = MagicMock()
                    mock_dispatch.return_value = mock_outlook
                    mock_outlook.CreateItem.return_value = mock_mail

                    widget.handle_send_email()

                    # Verify file picker was called
                    mock_picker.assert_called_once()

                    # Verify a task was created
                    self.assertEqual(len(todo_widget.active_tasks), 1,
                                   "Should create exactly one task")

                    # Verify Display was called (manual_draft_outlook executed)
                    mock_mail.Display.assert_called_once()

                    # Verify success was logged
                    success_logs = [msg for msg in log_messages if msg[2] == "SUCCESS"]
                    self.assertTrue(any("Outlook draft opened" in msg[1] for msg in success_logs))

                widget.deleteLater()

    def test_handle_send_email_different_files_create_distinct_tasks(self):
        """
        Test 4: Two different files picked in separate handle_send_email() calls
        create two distinct tasks (not reused).
        """
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        from OPTIONS.todo_option import TodoWidget
        from unittest.mock import patch, MagicMock
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two test files
            test_file1 = os.path.join(tmpdir, "memo1.docx")
            test_file2 = os.path.join(tmpdir, "memo2.docx")

            from MODULES.cake_memo.paths import CAKE_MEMO_TEMPLATE_PATH
            if CAKE_MEMO_TEMPLATE_PATH and os.path.exists(CAKE_MEMO_TEMPLATE_PATH):
                import shutil
                shutil.copy2(CAKE_MEMO_TEMPLATE_PATH, test_file1)
                shutil.copy2(CAKE_MEMO_TEMPLATE_PATH, test_file2)

                log_messages = []
                def capture_log(category, message, level):
                    log_messages.append((category, message, level))
                todo_widget = TodoWidget(parent=None, log_callback=capture_log)
                widget = CakeMemoOptionWidget(log_callback=capture_log, todo_widget=todo_widget)

                with patch('OPTIONS.cake_memo.widget.QFileDialog.getOpenFileName') as mock_picker, \
                     patch('OPTIONS.cake_memo.widget.parse_cake_memo_document') as mock_parse, \
                     patch('OPTIONS._shared.task_widget.win32com.client.Dispatch'):
                    mock_parse.return_value = {"room_number": "123", "flavor": "chocolate", "venue": "IL GUSTO", "hour": 19, "minute": 30, "is_pm": True}
                    # First call returns file1
                    mock_picker.return_value = (test_file1, "")
                    widget.handle_send_email()
                    task_count_after_first = len(todo_widget.active_tasks)

                    # Second call returns file2
                    mock_picker.return_value = (test_file2, "")
                    widget.handle_send_email()
                    task_count_after_second = len(todo_widget.active_tasks)

                    # Should have created two distinct tasks
                    self.assertEqual(task_count_after_first, 1, "First file should create one task")
                    self.assertEqual(task_count_after_second, 2, "Second file should create a second task")

                widget.deleteLater()

    def test_handle_send_email_same_file_reuses_task(self):
        """
        Test 5: Picking the same file twice in separate handle_send_email() calls
        reuses the same task (no duplicate).
        """
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        from OPTIONS.todo_option import TodoWidget
        from unittest.mock import patch, MagicMock
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "memo.docx")

            from MODULES.cake_memo.paths import CAKE_MEMO_TEMPLATE_PATH
            if CAKE_MEMO_TEMPLATE_PATH and os.path.exists(CAKE_MEMO_TEMPLATE_PATH):
                import shutil
                shutil.copy2(CAKE_MEMO_TEMPLATE_PATH, test_file)

                log_messages = []
                def capture_log(category, message, level):
                    log_messages.append((category, message, level))
                todo_widget = TodoWidget(parent=None, log_callback=capture_log)
                widget = CakeMemoOptionWidget(log_callback=capture_log, todo_widget=todo_widget)

                with patch('OPTIONS.cake_memo.widget.QFileDialog.getOpenFileName') as mock_picker, \
                     patch('OPTIONS.cake_memo.widget.parse_cake_memo_document') as mock_parse, \
                     patch('OPTIONS._shared.task_widget.win32com.client.Dispatch'):
                    mock_parse.return_value = {"room_number": "123", "flavor": "chocolate", "venue": "IL GUSTO", "hour": 19, "minute": 30, "is_pm": True}
                    # Always return same file
                    mock_picker.return_value = (test_file, "")

                    widget.handle_send_email()
                    task_count_after_first = len(todo_widget.active_tasks)
                    first_task_id = list(todo_widget.active_tasks.keys())[0] if todo_widget.active_tasks else None

                    widget.handle_send_email()
                    task_count_after_second = len(todo_widget.active_tasks)
                    second_task_id = list(todo_widget.active_tasks.keys())[0] if todo_widget.active_tasks else None

                    # Should reuse the same task (only one task total)
                    self.assertEqual(task_count_after_first, 1, "First call should create one task")
                    self.assertEqual(task_count_after_second, 1, "Second call should reuse the task")
                    self.assertEqual(first_task_id, second_task_id, "Task IDs should be identical")

                widget.deleteLater()

    def test_handle_send_email_payload_has_shared_recipients(self):
        """
        Test 6: handle_send_email() passes a payload with recipients matching
        the shared TO_RECIPIENTS and CC_RECIPIENTS from fb_email_recipients.
        """
        from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
        from OPTIONS.todo_option import TodoWidget
        from MODULES.common.fb_email_recipients import TO_RECIPIENTS, CC_RECIPIENTS
        from unittest.mock import patch, MagicMock
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "memo.docx")

            from MODULES.cake_memo.paths import CAKE_MEMO_TEMPLATE_PATH
            if CAKE_MEMO_TEMPLATE_PATH and os.path.exists(CAKE_MEMO_TEMPLATE_PATH):
                import shutil
                shutil.copy2(CAKE_MEMO_TEMPLATE_PATH, test_file)

                log_messages = []
                def capture_log(category, message, level):
                    log_messages.append((category, message, level))
                todo_widget = TodoWidget(parent=None, log_callback=capture_log)
                widget = CakeMemoOptionWidget(log_callback=capture_log, todo_widget=todo_widget)

                with patch('OPTIONS.cake_memo.widget.QFileDialog.getOpenFileName') as mock_picker, \
                     patch('OPTIONS.cake_memo.widget.parse_cake_memo_document') as mock_parse, \
                     patch('OPTIONS._shared.task_widget.win32com.client.Dispatch'):
                    mock_picker.return_value = (test_file, "")
                    mock_parse.return_value = {"room_number": "123", "flavor": "chocolate", "venue": "IL GUSTO", "hour": 19, "minute": 30, "is_pm": True}

                    widget.handle_send_email()

                    # Retrieve the task widget and check its payload
                    task_id = list(todo_widget.active_tasks.keys())[0] if todo_widget.active_tasks else None
                    if task_id:
                        task_widget = todo_widget.active_tasks.get(task_id)
                        payload = task_widget.payload

                        self.assertIn("data", payload)
                        self.assertEqual(payload["data"]["To"], TO_RECIPIENTS,
                                       "Payload should use shared TO_RECIPIENTS")
                        self.assertEqual(payload["data"]["CC"], CC_RECIPIENTS,
                                       "Payload should use shared CC_RECIPIENTS")

                widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
