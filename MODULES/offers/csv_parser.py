"""
Header-driven CSV parser for arrivals data (fixes 7000/8000 column-shift bug).
Imports bilingual header normalization dictionaries from inhouse_parser.py.
"""

import os
import csv
import re
from typing import Dict, Tuple, List, Any

from MODULES.parsing.inhouse_parser import (
    CANONICAL_HEADER_MAP,
    BOOKING_ID_KEYS,
    ROOM_KEYS,
    GUEST_NAME_KEYS,
    ARRIVAL_KEYS,
    DEPARTURE_KEYS,
)


def identify_digit_type(file_path):
    """
    Identify if a CSV's first column contains 3-digit or 4-digit room numbers.

    Args:
        file_path: Path to the CSV file

    Returns:
        3 if 3-digit rooms found, 4 if 4-digit rooms found, 0 otherwise
    """
    with open(file_path, mode='r', encoding='utf-8-sig', errors='ignore') as f:
        reader = csv.reader(f, delimiter=';')
        for i, row in enumerate(reader):
            if i >= 50: break
            if not row: continue
            col_a = row[0].strip(' "\'')
            if len(col_a) == 3 and col_a.isdigit(): return 3
            if len(col_a) == 4 and col_a.isdigit(): return 4
    return 0


def _extract_date(text: str) -> str:
    """
    Extract and format a date from text using regex, or return stripped text.
    Pattern: matches d/m, d-m, or d.m (1-2 digit day, 1-2 digit month).
    Returns formatted as dd/mm, or the stripped original text if no match.
    """
    if not text:
        return ""
    text = text.strip()
    date_match = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})", text)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        return f"{day:02d}/{month:02d}"
    return text


def extract_excel_data(csv_path) -> Tuple[List[Dict[str, Any]], List, List[Dict[str, Any]]]:
    """
    Extract offer-relevant data from a CSV arrivals file using header-driven column mapping.

    Fixes the 7000/8000 room block bug where an extra blank field shifts columns by rebuilding
    the column-to-field mapping from every header row detected (per inhouse_csv_reader pattern).

    Args:
        csv_path: Path to the CSV file

    Returns:
        Tuple of (offer_rows, minibar_data, all_arrivals) where:
          - offer_rows: list of dicts with keys {RoomNo, DepDate, Pax, Order} for ST/HB classified rows
          - minibar_data: empty list (out of scope)
          - all_arrivals: list of dicts with all arrival data for later JSON record writing
    """
    csv_path = os.path.abspath(csv_path)
    offer_rows = []
    all_arrivals = []
    col_to_field: Dict[int, str] = {}

    with open(csv_path, mode='r', encoding='utf-8-sig', errors='ignore') as f:
        rows = list(csv.reader(f, delimiter=';'))

    row_count = len(rows)
    for r in range(row_count):
        row = rows[r]
        next_row = rows[r + 1] if (r + 1) < row_count else []

        # Clean the row (strip BOM and whitespace)
        cleaned_row = [cell.replace('﻿', '').strip() for cell in row]

        # Header detection: check if any cell matches BOOKING_ID_KEYS
        is_header = any(
            any(alias.lower() == cell.lower() for alias in BOOKING_ID_KEYS)
            for cell in cleaned_row
        )

        if is_header:
            # Re-derive column mapping from this header row
            col_to_field = {}
            for idx, cell in enumerate(cleaned_row):
                canonical_name = CANONICAL_HEADER_MAP.get(cell.strip().lower())
                if canonical_name:
                    col_to_field[idx] = canonical_name
            continue

        # Skip any row until a header has been seen
        if not col_to_field:
            continue

        # Skip if this is also a header row (defensive check)
        if is_header:
            continue

        # Build field_values dict from col_to_field mapping
        field_values = {}
        for idx, field in col_to_field.items():
            if idx < len(cleaned_row):
                field_values[field] = cleaned_row[idx]

        # Extract field values
        room_val = field_values.get("Room", "")
        booking_id = field_values.get("Booking ID", "")
        guest_name = field_values.get("Guests", "")
        arrival_raw = field_values.get("Arrival", "")
        departure_raw = field_values.get("Departure", "")
        agency_val = field_values.get("Agency", "")

        # Parse dates
        arrival_date = _extract_date(arrival_raw)
        dep_date = _extract_date(departure_raw)

        # Determine if this is a room or booking row
        is_room = bool(re.match(r"^\d{3,4}$", room_val))
        is_booking = bool(re.search(r"(?i)BOOKING\.COM", agency_val))

        # Get description/remarks from next row (free-text, not header-mapped)
        desc = next_row[0].strip() if len(next_row) > 0 else ""

        # Extract pax from Adults/Children columns
        pax = 0
        if "Adults" in col_to_field.values():
            for idx, field in col_to_field.items():
                if field == "Adults" and idx < len(cleaned_row):
                    adults_text = cleaned_row[idx]
                    if re.search(r'\d', adults_text):
                        pax += int(re.sub(r'\D', '', adults_text))
        if "Children" in col_to_field.values():
            for idx, field in col_to_field.items():
                if field == "Children" and idx < len(cleaned_row):
                    children_text = cleaned_row[idx]
                    if re.search(r'\d', children_text):
                        pax += int(re.sub(r'\D', '', children_text))

        # Classify order by keywords
        order_str = None
        if re.search(r"(?i)Anniversary|Birthday|Honeymoon|Brthd|VIP", desc):
            order_str = "HB"
        elif re.search(r"(?i)Fruit", desc):
            order_str = "ST"

        # Handle Booking.com branch
        if is_booking:
            room_no = room_val.split()[0] if (not is_room and room_val) else room_val
            if not room_no:
                continue
            offer_rows.append({"RoomNo": room_no, "DepDate": dep_date, "Pax": pax, "Order": "ST"})
            # Record in all_arrivals for JSON records
            if is_room or is_booking:
                all_arrivals.append({
                    "booking_id": booking_id,
                    "room_number": room_no,
                    "guest_name": guest_name,
                    "arrival_date": arrival_date,
                    "departure_date": dep_date,
                    "agency": agency_val,
                })

        # Handle room branch (is_room, not already Booking.com)
        elif is_room:
            if not room_val:
                continue
            if order_str:
                offer_rows.append({"RoomNo": room_val, "DepDate": dep_date, "Pax": pax, "Order": order_str})
            # Record in all_arrivals for JSON records
            all_arrivals.append({
                "booking_id": booking_id,
                "room_number": room_val,
                "guest_name": guest_name,
                "arrival_date": arrival_date,
                "departure_date": dep_date,
                "agency": agency_val,
            })

    return offer_rows, [], all_arrivals
