"""
In-House CSV Reader & Reservation Grouping Module
=================================================
Independent parser for cp1253 semicolon-delimited In-House CSV exports.
Re-derives column-to-index mapping from every header row encountered,
filters invalid/3-digit room records, and groups guest rows by booking ID.
"""

import csv
from typing import Dict, List, Any


HEADER_FIELD_MAP = {
    "Δωμάτιο": "room",
    "Πελάτης": "guest",
    "Άφιξη": "arrival",
    "Αναχώρηση": "departure",
    "Τύπος Δωματίου": "room_assigned",
    "Χρεωστικός Τύπος Δωματίου": "room_booked",
    "Χρεώστης": "agency",
    "Αρ.": "booking_id",
    "Τύπος Γεύματος": "meal_type",
    "Τιμοκατάλογος": "price_list",
    "Σύν. Ατόμων": "pax",
}


def parse_inhouse_csv(file_path: str) -> List[Dict[str, Any]]:
    """
    Reads a cp1253, semicolon-delimited, multi-page in-house list CSV.
    A row is a HEADER row if its first non-empty cell (stripped) equals 'Δωμάτιο' exactly.
    Re-derives the column-name-to-index mapping from EVERY header row encountered.
    Yields one dict per valid guest row.

    Skips:
      - Header rows themselves
      - Fully blank rows
      - Totals rows (first non-empty cell starts with 'Totals:')
      - Rows where room is empty, not all-ASCII digits, or exactly 3 digits long (Sandy Villas).
    """
    guest_rows: List[Dict[str, Any]] = []
    col_to_field: Dict[int, str] = {}

    with open(file_path, mode="r", encoding="cp1253", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        for row in reader:
            if not row:
                continue

            cleaned = [c.replace('\ufeff', '').strip() for c in row]
            non_empty = [c for c in cleaned if c]
            if not non_empty:
                continue

            # Header row check
            if non_empty[0] == "Δωμάτιο":
                col_to_field = {}
                for idx, cell in enumerate(cleaned):
                    if cell in HEADER_FIELD_MAP:
                        col_to_field[idx] = HEADER_FIELD_MAP[cell]
                continue

            # Totals row check
            if non_empty[0].startswith("Totals:"):
                continue

            if not col_to_field:
                continue

            guest_row: Dict[str, Any] = {
                "room": "",
                "guest": "",
                "arrival": "",
                "departure": "",
                "room_assigned": "",
                "room_booked": "",
                "agency": "",
                "booking_id": "",
                "meal_type": "",
                "price_list": "",
                "pax": "",
            }

            for idx, field in col_to_field.items():
                if idx < len(cleaned):
                    guest_row[field] = cleaned[idx]

            room_val = guest_row["room"].strip()
            # Must be non-empty, all-ASCII-digits, and not exactly 3 digits (3-digit rooms are Sandy Villas)
            if not room_val or not room_val.isdigit() or not room_val.isascii() or len(room_val) == 3:
                continue

            guest_rows.append(guest_row)

    return guest_rows


def group_guest_rows_to_reservations(guest_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Groups guest rows by booking_id ('Αρ.') into one reservation dict per booking.
    Rows with an empty booking_id each become their own synthetic single-guest reservation.

    Within a group:
      - room, room_assigned, room_booked, agency, arrival, departure, meal_type, price_list
        all come from the FIRST row in file order for that booking_id.
      - pax = FIRST row's pax value only (never summed, never overwritten).
      - guest_count = number of guest rows in the group.
    """
    reservations: List[Dict[str, Any]] = []
    booking_map: Dict[str, int] = {}

    for row in guest_rows:
        b_id = str(row.get("booking_id") or "").strip()
        if not b_id:
            # Synthetic single-guest reservation
            res = {
                "booking_id": "",
                "room": row.get("room", ""),
                "room_assigned": row.get("room_assigned", ""),
                "room_booked": row.get("room_booked", ""),
                "agency": row.get("agency", ""),
                "arrival": row.get("arrival", ""),
                "departure": row.get("departure", ""),
                "meal_type": row.get("meal_type", ""),
                "price_list": row.get("price_list", ""),
                "pax": row.get("pax", ""),
                "guest_count": 1,
            }
            reservations.append(res)
        else:
            if b_id in booking_map:
                idx = booking_map[b_id]
                reservations[idx]["guest_count"] += 1
            else:
                res = {
                    "booking_id": b_id,
                    "room": row.get("room", ""),
                    "room_assigned": row.get("room_assigned", ""),
                    "room_booked": row.get("room_booked", ""),
                    "agency": row.get("agency", ""),
                    "arrival": row.get("arrival", ""),
                    "departure": row.get("departure", ""),
                    "meal_type": row.get("meal_type", ""),
                    "price_list": row.get("price_list", ""),
                    "pax": row.get("pax", ""),
                    "guest_count": 1,
                }
                booking_map[b_id] = len(reservations)
                reservations.append(res)

    return reservations
