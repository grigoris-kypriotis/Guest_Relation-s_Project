"""
Unit Tests for Stage 5a Defect Fixes & Module Separation
========================================================
Validates fixes for:
  - Defect #1: is_room_issue_trace requiring verified/operational signal for RCR traces.
  - Defect #2: compute_rcr_analytics avoiding stale room-number reuse false positives.
  - Defect #3: compute_rcr_analytics removing bare "stay" substring false positive in decline_terms.
"""

import os
import json
import shutil
import tempfile
import unittest

from MODULES.trace_keywords import (
    is_room_issue_trace,
    classify_trace_subcategory,
    PHYSICAL_DEFECT_TAGS,
    ROOM_ISSUE_CATEGORIES,
    EXCLUDED_ROOM_ISSUE_CATEGORIES,
)
from MODULES.room_change_detector import (
    compute_repeat_issue_rooms,
    compute_rcr_analytics,
    compute_trace_room_change_correlation,
)
from MODULES.trace_analytics import (
    is_room_issue_trace as reexported_is_room_issue_trace,
    compute_rcr_analytics as reexported_compute_rcr_analytics,
)


class TestStage5aDefectFixes(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_stage5a_")
        self.moves_file = os.path.join(self.temp_dir, "room_moves.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Defect #1: is_room_issue_trace validation on RCR
    # -------------------------------------------------------------------------
    def test_defect_1_rcr_without_verified_tag_is_not_room_issue(self):
        """Untagged RCR or RCR with only unclassified tags must not count as room issue."""
        # Bare RCR with no tags
        bare_rcr = {
            "category": "Room Change Request",
            "tags": [],
            "notes": "Guest would like to change room to be near friends."
        }
        self.assertFalse(is_room_issue_trace(bare_rcr))
        self.assertFalse(reexported_is_room_issue_trace(bare_rcr))

        # RCR with only unclassified/trace tag
        unclass_rcr = {
            "category": "Room Change Request",
            "tags": ["unclassified", "trace"],
            "notes": "Spoke to reception regarding room move."
        }
        self.assertFalse(is_room_issue_trace(unclass_rcr))

        # RCR with verified operational defect tag -> must count
        tagged_rcr = {
            "category": "Room Change Request",
            "tags": ["ac_air_conditioning"],
            "notes": "AC unit leaking water."
        }
        self.assertTrue(is_room_issue_trace(tagged_rcr))

        # RCR with explicit room defect flag -> must count
        flagged_rcr = {
            "category": "Room Change Request",
            "tags": [],
            "notes": "Defective door lock.",
            "is_room_defect": True
        }
        self.assertTrue(is_room_issue_trace(flagged_rcr))

    # -------------------------------------------------------------------------
    # Defect #2: Room-number reuse across non-overlapping dates
    # -------------------------------------------------------------------------
    def test_defect_2_room_reuse_non_overlapping_dates_not_matched(self):
        """Historical move in room 101 from 2024 must NOT match 2026 stay in room 101."""
        historical_moves = [
            {
                "booking_id": "BK-2024-OLD",
                "old_room": "101",
                "new_room": "102",
                "arrival": "2024-05-01",
                "departure": "2024-05-10",
                "date": "2024-05-04"
            },
            {
                # Unverifiable move: arrival and departure are empty strings
                "booking_id": "",
                "old_room": "202",
                "new_room": "203",
                "arrival": "",
                "departure": "",
                "date": "2026-06-01"
            },
            {
                # Valid move for room 303 in July 2026
                "booking_id": "BK-2026-303",
                "old_room": "303",
                "new_room": "304",
                "arrival": "2026-07-01",
                "departure": "2026-07-10",
                "date": "2026-07-03"
            }
        ]
        with open(self.moves_file, "w", encoding="utf-8") as f:
            json.dump(historical_moves, f)

        traces = [
            # Trace A: Room 101 in 2026 (booking BK-2026-NEW). Historical move was in 2024.
            {
                "booking_id": "BK-2026-NEW",
                "room_number": "101",
                "category": "Room Change Request",
                "arrival": "2026-06-01",
                "departure": "2026-06-10",
                "notes": "Shower pressure is weak.",
                "tags": ["water_plumbing"]
            },
            # Trace B: Room 202 with unverifiable move (empty arrival/departure in moves file)
            {
                "booking_id": "",
                "room_number": "202",
                "category": "Room Change Request",
                "arrival": "2026-06-01",
                "departure": "2026-06-10",
                "notes": "Noisy AC unit.",
                "tags": ["ac"]
            },
            # Trace C: Room 303 matching BK-2026-303 (primary match on booking_id)
            {
                "booking_id": "BK-2026-303",
                "room_number": "303",
                "category": "Room Change Request",
                "arrival": "2026-07-01",
                "departure": "2026-07-10",
                "notes": "Moved successfully.",
                "tags": ["view_mismatch"]
            }
        ]

        analytics = compute_rcr_analytics(traces, room_moves_path=self.moves_file)

        # Only Trace C should be executed; Trace A and B must NOT be matched!
        self.assertEqual(analytics["total_rcr_logged"], 3)
        self.assertEqual(analytics["moves_executed"], 1)
        self.assertEqual(analytics["pending_in_house"], 2)

    def test_defect_2_fallback_room_matching_with_overlapping_date_window(self):
        """When booking_id is missing on trace, match succeeds if date window overlaps."""
        moves = [
            {
                "booking_id": "BK-MOVE-404",
                "old_room": "404",
                "new_room": "405",
                "arrival": "2026-08-01",
                "departure": "2026-08-12",
                "date": "2026-08-05"
            }
        ]
        with open(self.moves_file, "w", encoding="utf-8") as f:
            json.dump(moves, f)

        # Trace has no booking_id, but room 404 and overlapping dates
        trace_overlapping = {
            "booking_id": "",
            "room_number": "404",
            "category": "Room Change Request",
            "arrival": "2026-08-01",
            "departure": "2026-08-12",
            "notes": "Guest changed room due to balcony lock.",
            "tags": ["furniture_fixtures"]
        }

        analytics = compute_rcr_analytics([trace_overlapping], room_moves_path=self.moves_file)
        self.assertEqual(analytics["moves_executed"], 1)

    # -------------------------------------------------------------------------
    # Defect #3: Bare "stay" in decline_terms false positive
    # -------------------------------------------------------------------------
    def test_defect_3_extend_their_stay_not_counted_as_declined(self):
        """Traces containing phrases like 'extend their stay' must not count as moves_declined."""
        with open(self.moves_file, "w", encoding="utf-8") as f:
            json.dump([], f)

        traces = [
            # 1. False-positive phrase: "extend their stay"
            {
                "booking_id": "BK-STAY-1",
                "room_number": "501",
                "category": "Room Change Request",
                "notes": "Guest wishes to extend their stay if a ground floor room becomes available.",
                "tags": ["floor_preference"]
            },
            # 2. Genuine decline: "decided to stay"
            {
                "booking_id": "BK-STAY-2",
                "room_number": "502",
                "category": "Room Change Request",
                "notes": "Offered room 503 but guest decided to stay in current room.",
                "tags": ["noise"]
            },
            # 3. Genuine decline: "declined"
            {
                "booking_id": "BK-STAY-3",
                "room_number": "503",
                "category": "Room Change Request",
                "notes": "Guest declined the proposed alternative room.",
                "tags": ["view_mismatch"]
            }
        ]

        analytics = compute_rcr_analytics(traces, room_moves_path=self.moves_file)

        self.assertEqual(analytics["total_rcr_logged"], 3)
        # BK-STAY-1 must be pending_in_house, NOT declined!
        # BK-STAY-2 and BK-STAY-3 are genuine declines -> moves_declined == 2
        self.assertEqual(analytics["moves_declined"], 2)
        self.assertEqual(analytics["pending_in_house"], 1)


if __name__ == "__main__":
    unittest.main()
