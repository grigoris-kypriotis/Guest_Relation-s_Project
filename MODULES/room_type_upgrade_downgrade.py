"""
Room Type Upgrade/Downgrade Aggregation Module
==============================================
Calculates booked vs assigned room type discrepancies, upgrade/downgrade balance,
all-8 ladder code tallies, per-agency breakdowns, per-block breakdowns, and
identifies missing/unrecognized room type data issues.
"""

from typing import Dict, List, Any
from MODULES.room_type_ladder import ROOM_TYPE_LADDER, compare_room_types


def compute_room_type_upgrade_downgrade(reservations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes room type upgrade, downgrade, exact match counts, all 8 ladder code
    distributions, per-agency breakdowns, and per-block breakdowns.

    Guarantees:
      - booked_counts and assigned_counts ALWAYS contain exactly all 8 ROOM_TYPE_LADDER keys.
      - by_agency always contains 'Booking.com' pre-seeded.
      - by_block starts empty and only records blocks actually observed.
      - Missing or unrecognized room type codes are captured in data_issues without
        polluting the top-level counts.
      - upgrade + downgrade + exact_match + len(data_issues) == reservations_evaluated.
      - Return dictionary contains NO 'unknown' key.
    """
    booked_counts: Dict[str, int] = {code: 0 for code in ROOM_TYPE_LADDER}
    assigned_counts: Dict[str, int] = {code: 0 for code in ROOM_TYPE_LADDER}

    by_agency: Dict[str, Dict[str, int]] = {
        "Booking.com": {"upgrade": 0, "downgrade": 0, "exact_match": 0, "issues": 0}
    }
    by_block: Dict[str, Dict[str, int]] = {}
    data_issues: List[Dict[str, Any]] = []

    upgrade_count = 0
    downgrade_count = 0
    exact_match_count = 0

    if not reservations:
        return {
            "upgrade": 0,
            "downgrade": 0,
            "exact_match": 0,
            "reservations_evaluated": 0,
            "booked_counts": booked_counts,
            "assigned_counts": assigned_counts,
            "by_agency": by_agency,
            "by_block": by_block,
            "data_issues": data_issues,
        }

    for reservation in reservations:
        booked = str(reservation.get("room_booked") or "").strip()
        assigned = str(reservation.get("room_assigned") or "").strip()
        agency_raw = str(reservation.get("agency") or "").strip()
        agency_key = "Booking.com" if "booking.com" in agency_raw.lower() else (agency_raw if agency_raw else "Unspecified Agency")

        room_str = str(reservation.get("room") or "").strip()
        block_key = room_str[0] if room_str else None

        if agency_key not in by_agency:
            by_agency[agency_key] = {"upgrade": 0, "downgrade": 0, "exact_match": 0, "issues": 0}

        if block_key is not None and block_key not in by_block:
            by_block[block_key] = {"upgrade": 0, "downgrade": 0, "exact_match": 0, "issues": 0}

        if not booked or not assigned:
            data_issues.append({
                "booking_id": reservation.get("booking_id", ""),
                "room": reservation.get("room", ""),
                "reason": "empty_room_type",
            })
            by_agency[agency_key]["issues"] += 1
            if block_key is not None:
                by_block[block_key]["issues"] += 1
            continue

        direction = compare_room_types(booked, assigned)

        if direction == "unknown":
            data_issues.append({
                "booking_id": reservation.get("booking_id", ""),
                "room": reservation.get("room", ""),
                "reason": "unrecognized_room_type_code",
                "booked": booked,
                "assigned": assigned,
            })
            by_agency[agency_key]["issues"] += 1
            if block_key is not None:
                by_block[block_key]["issues"] += 1
            continue
        elif direction == "upgrade":
            upgrade_count += 1
            booked_counts[booked] += 1
            assigned_counts[assigned] += 1
            by_agency[agency_key]["upgrade"] += 1
            if block_key is not None:
                by_block[block_key]["upgrade"] += 1
        elif direction == "downgrade":
            downgrade_count += 1
            booked_counts[booked] += 1
            assigned_counts[assigned] += 1
            by_agency[agency_key]["downgrade"] += 1
            if block_key is not None:
                by_block[block_key]["downgrade"] += 1
        elif direction == "same":
            exact_match_count += 1
            booked_counts[booked] += 1
            assigned_counts[assigned] += 1
            by_agency[agency_key]["exact_match"] += 1
            if block_key is not None:
                by_block[block_key]["exact_match"] += 1

    reservations_evaluated = len(reservations)

    # Invariant assertion
    assert upgrade_count + downgrade_count + exact_match_count + len(data_issues) == reservations_evaluated

    return {
        "upgrade": upgrade_count,
        "downgrade": downgrade_count,
        "exact_match": exact_match_count,
        "reservations_evaluated": reservations_evaluated,
        "booked_counts": booked_counts,
        "assigned_counts": assigned_counts,
        "by_agency": by_agency,
        "by_block": by_block,
        "data_issues": data_issues,
    }
