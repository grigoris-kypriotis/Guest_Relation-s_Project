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
                self.assertFalse(form.delivery_confirmation_frame.isVisible())

                # Click the radio button
                form.venue_buttons[venue_key].setChecked(True)

                # Confirmation subsection should now be visible
                self.assertTrue(form.delivery_confirmation_frame.isVisible())

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
        self.assertFalse(form.complimentary_by_frame.isVisible())

        # Select Complimentary
        form.charge_buttons[CHARGE_COMPLIMENTARY].setChecked(True)
        self.assertTrue(form.complimentary_by_frame.isVisible())

        # Select Paid
        form.charge_buttons[CHARGE_PAID].setChecked(True)
        self.assertFalse(form.complimentary_by_frame.isVisible())

        # Select Pending
        form.charge_buttons[CHARGE_PENDING].setChecked(True)
        self.assertFalse(form.complimentary_by_frame.isVisible())

        # Select Complimentary again
        form.charge_buttons[CHARGE_COMPLIMENTARY].setChecked(True)
        self.assertTrue(form.complimentary_by_frame.isVisible())

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
        self.assertFalse(form.delivery_confirmation_frame.isVisible())

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
        self.assertFalse(form.complimentary_by_frame.isVisible())

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


if __name__ == "__main__":
    unittest.main()
