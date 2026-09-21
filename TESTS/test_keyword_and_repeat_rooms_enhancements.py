"""
Unit Tests for Extended Trace Keywords, Repeat-Issue Room Guest Patterns,
and Trace Room Change Correlation Rate Metric.
"""

import unittest
from matplotlib.figure import Figure

from MODULES.trace_keywords import (
    PHYSICAL_DEFECT_TAGS,
    TRACE_SUBCATEGORY_KEYWORDS,
    classify_trace_subcategory,
    is_room_issue_trace,
)
from MODULES.room_change_detector import (
    compute_repeat_issue_rooms,
    compute_trace_room_change_correlation,
)
from MODULES.plot_viewer import TraceAnalyticsPlotEngine


class TestKeywordAndRepeatRoomsEnhancements(unittest.TestCase):
    """Test suite covering Part 2 keyword extensions and correlation/repeat enhancements."""

    # -------------------------------------------------------------------------
    # 1. Maintenance Subcategory & All Token Variants
    # -------------------------------------------------------------------------
    def test_maintenance_all_six_token_variants(self):
        r"""Confirm \bmaint\w*\b matches all six token variants found in Part 1."""
        variants = [
            "maint",
            "maints",
            "maintance",
            "maintanence",
            "maintanace",
            "maintenabnce",
            "maintenance",
        ]
        self.assertIn("maint", TRACE_SUBCATEGORY_KEYWORDS["Maintenance Log"])
        for variant in variants:
            note = f"Guest reported issue, {variant} informed immediately"
            subcat = classify_trace_subcategory(note)
            self.assertEqual(
                subcat,
                "Maintenance Log",
                f"Variant '{variant}' was not classified as Maintenance Log",
            )

    def test_maintenance_word_boundary_isolation(self):
        """Ensure word-boundary matching prevents false positives."""
        # Generic non-maintenance text should remain Other / General
        self.assertEqual(classify_trace_subcategory("Guest asked for information"), "Other / General")
        self.assertEqual(classify_trace_subcategory(""), "Other / General")

    # -------------------------------------------------------------------------
    # 2. Extended PHYSICAL_DEFECT_TAGS Categories
    # -------------------------------------------------------------------------
    def test_physical_defect_tags_categories_present(self):
        """Verify the new defect categories are registered in PHYSICAL_DEFECT_TAGS."""
        expected_categories = [
            "Pest/Insect",
            "Electronics/Safe",
            "Furniture/Bedding",
            "Cosmetic/Surface",
        ]
        for cat in expected_categories:
            self.assertIn(cat, PHYSICAL_DEFECT_TAGS)
            self.assertGreater(len(PHYSICAL_DEFECT_TAGS[cat]), 0)

    def test_representative_unmatched_notes_now_matched(self):
        """Verify representative notes from Part 1 are now recognized by is_room_issue_trace."""
        representative_notes = [
            # Pest / Insect
            ("found a cockroach in the room and we send the hk to spray", "Pest/Insect"),
            ("came to rec with pics and vids with ants in the room we inform hs", "Pest/Insect"),
            ("wasps nest outside the room, maint informed", "Pest/Insect"),
            ("she is not happy with her new room as it has no net for mosquitoes", "Pest/Insect"),
            # Safe Box
            ("the key from the sAFE IS MISING", "Electronics/Safe"),
            ("safe does not work. maints informed", "Electronics/Safe"),
            ("safe box doesnt work since yesterday", "Electronics/Safe"),
            # Fridge / Minibar
            ("came to reception stating they dont have water or a fridge", "Electronics/Safe"),
            ("called guest after a feedback that the fridge was not been replace", "Electronics/Safe"),
            # Blinds / Curtains
            ("the guest called at rec to tell that they don't have curtains and the light comes in", "Furniture/Bedding"),
            # Mattress / Bedding
            ("change the mattress maximum 90cm only", "Furniture/Bedding"),
            ("Guest came to the GR desk saying they are missing 1 blanket", "Furniture/Bedding"),
            ("GUEST SAID THE MATTRESSES ARE NOT COMFORTABLE", "Furniture/Bedding"),
            # Electrical / Hairdryer / Socket
            ("GR called and guest said there is still problem with the socket", "Electronics/Safe"),
            ("came to gr to report their hairdryer not working", "Electronics/Safe"),
            ("temporary power outage in room", "Electronics/Safe"),
            # Rust / Paint / Cosmetic
            ("they call at reception that their room smells like fresh paint", "Cosmetic/Surface"),
            ("THE SMALL CHILD STEPPED ON A RUSTY SCREW", "Cosmetic/Surface"),
            ("cracked mirror in bathroom", "Cosmetic/Surface"),
        ]

        for note, expected_category in representative_notes:
            trace = {"category": "Trace", "notes": note, "tags": []}
            self.assertTrue(
                is_room_issue_trace(trace),
                f"Failed to match room issue trace for: {note} ({expected_category})",
            )

    def test_safe_pattern_specificity_and_false_positive_prevention(self):
        """Verify safe patterns do not match generic feelings of safety but match defects."""
        should_not_match = [
            "the guest doesn't feel safe walking at night",
            "is it safe to leave valuables",
            "we made sure the pool area is safe",
        ]
        for phrase in should_not_match:
            trace = {"category": "Trace", "notes": phrase, "tags": []}
            self.assertFalse(
                is_room_issue_trace(trace),
                f"False positive matched for generic safe phrase: '{phrase}'",
            )

        should_match = [
            "safe does not work",
            "safe box beeping",
            "the key from the safe is missing",
        ]
        for phrase in should_match:
            trace = {"category": "Trace", "notes": phrase, "tags": []}
            self.assertTrue(
                is_room_issue_trace(trace),
                f"Failed to match safe defect phrase: '{phrase}'",
            )

    # -------------------------------------------------------------------------
    # 3. Repeat-Issue Rooms Guest Pattern (Same Guest vs Different Guests vs Unknown)
    # -------------------------------------------------------------------------
    def test_repeat_issue_rooms_same_guest(self):
        """Repeat traces with identical guest name should yield guest_pattern='same_guest'."""
        traces = [
            {
                "room_number": "1101",
                "guest_name": "Smith John",
                "category": "Trace",
                "notes": "Safe box is jammed",
                "tags": [],
            },
            {
                "room_number": "1101",
                "guest_name": "smith john",  # case-insensitive match
                "category": "Trace",
                "notes": "Safe box still jammed",
                "tags": [],
            },
        ]
        results = compute_repeat_issue_rooms(traces)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["room_number"], "1101")
        self.assertEqual(results[0]["guest_pattern"], "same_guest")

    def test_repeat_issue_rooms_different_guests(self):
        """Repeat traces with different guest names should yield guest_pattern='different_guests'."""
        traces = [
            {
                "room_number": "1102",
                "guest_name": "Smith John",
                "category": "Trace",
                "notes": "AC cold air not working",
                "tags": [],
            },
            {
                "room_number": "1102",
                "guest_name": "Taylor Jane",
                "category": "Trace",
                "notes": "AC making loud noise",
                "tags": [],
            },
        ]
        results = compute_repeat_issue_rooms(traces)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["room_number"], "1102")
        self.assertEqual(results[0]["guest_pattern"], "different_guests")

    def test_repeat_issue_rooms_unknown_guest(self):
        """Repeat traces where any guest name is missing/empty should yield guest_pattern='unknown'."""
        traces = [
            {
                "room_number": "1103",
                "guest_name": "Smith John",
                "category": "Trace",
                "notes": "Bathroom drain clogged",
                "tags": [],
            },
            {
                "room_number": "1103",
                "guest_name": "",  # missing name
                "category": "Trace",
                "notes": "Bathroom shower leak",
                "tags": [],
            },
        ]
        results = compute_repeat_issue_rooms(traces)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["room_number"], "1103")
        self.assertEqual(results[0]["guest_pattern"], "unknown")

    # -------------------------------------------------------------------------
    # 4. Trace & Room Change Correlation Rate Metric
    # -------------------------------------------------------------------------
    def test_trace_room_change_correlation_prior_trace_rate(self):
        """Verify prior_trace_rate calculation and division-by-zero protection."""
        # 3 rooms with prior traces, 1 room zero prior -> 3 / (3 + 1) * 100 = 75.0%
        traces = [
            # Room 201: has non-RCR trace + RCR trace -> with prior
            {"room_number": "201", "category": "Trace", "notes": "Safe jammed"},
            {"room_number": "201", "category": "Room Change Request", "notes": "Move request"},
            # Room 202: has non-RCR trace + RCR trace -> with prior
            {"room_number": "202", "category": "Trace", "notes": "AC issue"},
            {"room_number": "202", "category": "Room Change Request", "notes": "Move request"},
            # Room 203: has non-RCR trace + RCR trace -> with prior
            {"room_number": "203", "category": "Trace", "notes": "No hot water"},
            {"room_number": "203", "category": "Room Change Request", "notes": "Move request"},
            # Room 204: ONLY RCR trace -> zero prior
            {"room_number": "204", "category": "Room Change Request", "notes": "Move request immediately"},
        ]
        corr = compute_trace_room_change_correlation(traces)
        self.assertEqual(corr["rooms_with_prior_traces"], 3)
        self.assertEqual(corr["rooms_zero_prior_traces"], 1)
        self.assertEqual(corr["prior_trace_rate"], 75.0)

    def test_trace_room_change_correlation_zero_division(self):
        """Verify zero division guard returns 0.0 when no RCR rooms exist."""
        corr = compute_trace_room_change_correlation([])
        self.assertEqual(corr["rooms_with_prior_traces"], 0)
        self.assertEqual(corr["rooms_zero_prior_traces"], 0)
        self.assertEqual(corr["prior_trace_rate"], 0.0)

    # -------------------------------------------------------------------------
    # 5. Chart Rendering Verification
    # -------------------------------------------------------------------------
    def test_render_repeat_issue_rooms_chart(self):
        """Verify repeat-issue rooms renders cleanly with same_guest and different_guests."""
        fig = Figure(figsize=(8, 4))
        mock_data = {
            "repeat_issue_rooms": [
                {
                    "room_number": "1204",
                    "total_traces": 4,
                    "top_tags": ["Plumbing", "Safe"],
                    "guest_pattern": "different_guests",
                },
                {
                    "room_number": "1353",
                    "total_traces": 3,
                    "top_tags": ["Pest"],
                    "guest_pattern": "same_guest",
                },
                {
                    "room_number": "1410",
                    "total_traces": 2,
                    "top_tags": ["AC"],
                    "guest_pattern": "unknown",
                },
            ]
        }
        TraceAnalyticsPlotEngine.render_repeat_issue_rooms(fig, mock_data)
        self.assertGreater(len(fig.axes), 0)

    def test_render_trace_room_change_correlation_chart(self):
        """Verify correlation chart renders cleanly with top KPI rate panel."""
        fig = Figure(figsize=(8, 5))
        mock_data = {
            "trace_room_change_correlation": {
                "rooms_with_prior_traces": 30,
                "rooms_zero_prior_traces": 10,
                "offers_assigned_prior_group": 12,
                "offers_assigned_zero_group": 4,
                "total_offers_assigned": 16,
                "formally_approved_room_changes": 25,
                "prior_trace_rate": 75.0,
            }
        }
        TraceAnalyticsPlotEngine.render_trace_room_change_correlation(fig, mock_data)
        self.assertEqual(len(fig.axes), 2)  # top rate panel + bottom bars panel


if __name__ == "__main__":
    unittest.main()
