"""
Deterministic field composition and parsing for CAKE MEMO composite DOCX columns.

This module standardizes the structured field shapes that later steps (document generation,
form UI, parsing) will depend on:

  - flavor (str): one of FLAVOR_DISPLAY's keys (e.g., 'strawberry', 'vanilla')
  - written_text (str): freeform text to be written on the cake
  - pax (int): number of people (used by form/document, not composed here)
  - qty (int): quantity (used by form/document, not composed here)
  - venue (str): one of VENUE_DISPLAY's keys (e.g., 'elia', 'il_gusto', 'room')
  - hour (int): 0-23
  - minute (int): 0-59
  - is_pm (bool): if True, display as PM; if False, as AM
  - charge_state (str): one of CHARGE_PAID, CHARGE_PENDING, CHARGE_COMPLIMENTARY
  - complimentary_by (str): name of person authorizing complimentary charge (if applicable)
  - room_number (str): guest's room identifier

These functions are pure, deterministic, and fully reversible (compose -> parse round-trip).
Used by CAKE MEMO document generation and form UI in later steps.
"""

import re
from typing import Tuple, Optional


FLAVOR_DISPLAY = {
    "strawberry": "STRAWBERRY",
    "chocolate": "CHOCOLATE",
    "vanilla": "VANILLA",
    "strawberry_vanilla": "STRAWBERRY & VANILLA",
    "chocolate_vanilla": "CHOCOLATE & VANILLA",
    "chocolate_strawberry": "CHOCOLATE & STRAWBERRY",
}


def compose_service_description(flavor_key: str, written_text: str) -> str:
    """
    Compose SERVICE DESCRIPTION column from flavor and optional written text.

    Args:
        flavor_key: one of FLAVOR_DISPLAY's keys (case-sensitive key, not display value)
        written_text: optional freeform text to be written on the cake

    Returns:
        Composed string, e.g. "STRAWBERRY CAKE" or "VANILLA CAKE, PLEASE WRITE ON IT: Happy Birthday"
    """
    flavor_display = FLAVOR_DISPLAY[flavor_key]
    if written_text and written_text.strip():
        return f"{flavor_display} CAKE, PLEASE WRITE ON IT: {written_text.strip()}"
    return f"{flavor_display} CAKE"


def parse_service_description(text: str) -> Tuple[Optional[str], str]:
    """
    Parse SERVICE DESCRIPTION column back to flavor key and written text.

    Args:
        text: composed string, e.g. "STRAWBERRY CAKE" or "VANILLA CAKE, PLEASE WRITE ON IT: Happy Birthday"

    Returns:
        (flavor_key, written_text) tuple. If text doesn't match the pattern, returns (None, "").
        Never raises. Case-insensitive matching against FLAVOR_DISPLAY values.
    """
    if not text or not isinstance(text, str):
        return (None, "")

    text = text.strip()
    if not text:
        return (None, "")

    # Pattern: ^(.+?) CAKE(?:, PLEASE WRITE ON IT: (.*))?$
    pattern = r"^(.+?)\s+CAKE(?:,\s+PLEASE\s+WRITE\s+ON\s+IT:\s*(.*))?$"
    match = re.match(pattern, text, re.IGNORECASE)
    if not match:
        return (None, "")

    flavor_part = match.group(1).strip()
    written_text = match.group(2).strip() if match.group(2) else ""

    # Case-insensitive lookup of flavor_part against FLAVOR_DISPLAY values
    flavor_key = None
    for key, display_value in FLAVOR_DISPLAY.items():
        if display_value.upper() == flavor_part.upper():
            flavor_key = key
            break

    if flavor_key is None:
        return (None, "")

    return (flavor_key, written_text)


VENUE_DISPLAY = {
    "elia": "ELIA",
    "ermis": "ERMIS",
    "ammos": "AMMOS",
    "il_gusto": "IL GUSTO",
    "room": "",  # blank per spec: room's venue name is omitted since Room Number already captures it
}


def compose_provided_at(venue_key: str, hour: int, minute: int, is_pm: bool) -> str:
    """
    Compose PROVIDED_AT column from venue, hour, minute, and AM/PM flag.

    Args:
        venue_key: one of VENUE_DISPLAY's keys (e.g., 'elia', 'il_gusto', 'room')
        hour: 0-23 (will be formatted as-is in the time string)
        minute: 0-59 (will be formatted as-is in the time string)
        is_pm: if True, append "PM"; if False, append "AM"

    Returns:
        Composed string, e.g. "IL GUSTO 19.30PM" (confirmed real example) or "19.30PM" for room venue.
        Always strips trailing/leading whitespace.
    """
    ampm = "PM" if is_pm else "AM"
    venue_display = VENUE_DISPLAY[venue_key]
    time_part = f"{hour:02d}.{minute:02d}{ampm}"

    if venue_display:
        return f"{venue_display} {time_part}"
    return time_part.strip()


def parse_provided_at(text: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[bool]]:
    """
    Parse PROVIDED_AT column back to venue key, hour, minute, and AM/PM flag.

    Args:
        text: composed string, e.g. "IL GUSTO 19.30PM" or "19.30PM"

    Returns:
        (venue_key, hour, minute, is_pm) tuple. If time pattern not found, returns (None, None, None, None).
        Never raises. Case-insensitive matching against VENUE_DISPLAY values.
    """
    if not text or not isinstance(text, str):
        return (None, None, None, None)

    text = text.strip()
    if not text:
        return (None, None, None, None)

    # Extract trailing (\d{1,2})\.(\d{2})(AM|PM) pattern (case-insensitive)
    pattern = r"(\d{1,2})\.(\d{2})(AM|PM)$"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return (None, None, None, None)

    try:
        hour = int(match.group(1))
        minute = int(match.group(2))
        is_pm = match.group(3).upper() == "PM"
    except (ValueError, IndexError):
        return (None, None, None, None)

    # Whatever text precedes the time pattern (stripped) is matched against VENUE_DISPLAY values
    venue_part = text[: match.start()].strip()

    venue_key = None
    if not venue_part:
        # Empty venue part means 'room' venue (blank display value)
        venue_key = "room"
    else:
        # Case-insensitive lookup against non-empty VENUE_DISPLAY values
        for key, display_value in VENUE_DISPLAY.items():
            if display_value and display_value.upper() == venue_part.upper():
                venue_key = key
                break

    if venue_key is None:
        return (None, None, None, None)

    return (venue_key, hour, minute, is_pm)


CHARGE_PAID = "paid"
CHARGE_PENDING = "pending"
CHARGE_COMPLIMENTARY = "complimentary"


def compose_charge(state: str, complimentary_by: str = "") -> str:
    """
    Compose CHARGE column from state and optional complimentary_by name.

    Args:
        state: one of CHARGE_PAID, CHARGE_PENDING, CHARGE_COMPLIMENTARY
        complimentary_by: if state is CHARGE_COMPLIMENTARY, the name of the authorizing person

    Returns:
        Composed string, e.g. "PAID", "PENDING", or "COMPLIMENTARY BY Maria Papadopoulou"
    """
    if state == CHARGE_COMPLIMENTARY:
        complimentary_by_clean = complimentary_by.strip() if complimentary_by else ""
        if complimentary_by_clean:
            return f"COMPLIMENTARY BY {complimentary_by_clean}"
        return "COMPLIMENTARY BY "
    if state == CHARGE_PENDING:
        return "PENDING"
    return "PAID"


def parse_charge(text: str) -> Tuple[str, str]:
    """
    Parse CHARGE column back to state and complimentary_by name.

    Args:
        text: composed string, e.g. "PAID", "PENDING", or "COMPLIMENTARY BY Maria Papadopoulou"

    Returns:
        (state, complimentary_by) tuple. Never raises. Case-insensitive matching.
        - If text starts with "COMPLIMENTARY": state=CHARGE_COMPLIMENTARY, complimentary_by = text after "BY" (stripped)
        - If text contains "PENDING": state=CHARGE_PENDING, complimentary_by=""
        - Otherwise (including legacy text like "PAID AT RECEPTION"): state=CHARGE_PAID, complimentary_by=""
    """
    if not text or not isinstance(text, str):
        return (CHARGE_PAID, "")

    text_upper = text.upper().strip()

    if text_upper.startswith("COMPLIMENTARY"):
        # Extract whatever follows "BY"
        if " BY " in text_upper:
            # Find the actual text after "BY" in the original string (preserve case)
            by_index = text_upper.find(" BY ")
            if by_index != -1:
                complimentary_by = text[by_index + 4:].strip()
                return (CHARGE_COMPLIMENTARY, complimentary_by)
        return (CHARGE_COMPLIMENTARY, "")

    if "PENDING" in text_upper:
        return (CHARGE_PENDING, "")

    return (CHARGE_PAID, "")
