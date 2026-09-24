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


if __name__ == "__main__":
    unittest.main()
