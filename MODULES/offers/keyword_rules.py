"""
Keyword-based order classification rules for arrivals.
Classifies remarks text to determine HB (Half Board) or ST (Special Treatment) offers.
"""

import re
from typing import Optional


def classify_order(description: str) -> Optional[str]:
    """
    Classify an arrival's remarks text to determine order type.

    Args:
        description: Free-text remarks from the arrivals row

    Returns:
        'HB' for Half Board occasions (anniversary, birthday, honeymoon, VIP, repeater)
        'ST' for Special Treatment (fruit and wine packages)
        None if no keywords match
    """
    if not description:
        return None

    # Check for HB keywords first (case-insensitive)
    # Includes: Anniversary, Birthday, Honeymoon, Brthd (abbreviation), VIP, repeater
    if re.search(r"(?i)Anniversary|Birthday|Honeymoon|Brthd|VIP|repeater", description):
        return "HB"

    # Check for fruit and wine pattern (case-insensitive)
    # Matches: "fruit and wine", "fruit & wine", "fruit wine" (connector optional)
    if re.search(r"(?i)fruit\s*(?:and|&)?\s*wine", description):
        return "ST"

    return None
