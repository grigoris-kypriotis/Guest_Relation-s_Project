"""
Room Type Ladder & Comparison Engine
====================================
Maintains the official room type ladder and evaluates room category
upgrades, downgrades, exact matches, and unknown designations.
"""

from typing import Literal

ROOM_TYPE_LADDER = {
    "DUG": 1,
    "DUK": 2,
    "DSG": 3,
    "F1G": 4,
    "F2G": 5,
    "FSG": 6,
    "PJG": 7,
    "PJK": 8,
}  # worst to best


def compare_room_types(
    booked: str,
    assigned: str,
) -> Literal["upgrade", "downgrade", "same", "unknown"]:
    """
    Compares booked vs assigned room types using the official ROOM_TYPE_LADDER.

    Rules:
      - strip() and upper() both inputs.
      - Match the WHOLE code only, never a substring.
      - If either is empty or not in the ladder, return "unknown".
      - If equal, return "same".
      - Else compare ranks (higher assigned rank = "upgrade", lower = "downgrade").
      - A tie between different codes returns "unknown", NEVER "upgrade".
    """
    b = (booked or "").strip().upper()
    a = (assigned or "").strip().upper()

    if not b or not a:
        return "unknown"

    if b not in ROOM_TYPE_LADDER or a not in ROOM_TYPE_LADDER:
        return "unknown"

    if b == a:
        return "same"

    rank_b = ROOM_TYPE_LADDER[b]
    rank_a = ROOM_TYPE_LADDER[a]

    if rank_a > rank_b:
        return "upgrade"
    elif rank_a < rank_b:
        return "downgrade"
    else:
        # A tie between different codes returns unknown, never upgrade
        return "unknown"
