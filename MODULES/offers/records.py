"""
Per-arrival JSON record writer for guest relation tracking.
Idempotently creates/updates individual booking records with arrival/room/move data.
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional

# Import RECORDS_DIR as a bare name for hermetic test monkeypatch compatibility
from MODULES.common import paths_config


def _calculate_length_of_stay(arrival_date: str, departure_date: str) -> Optional[int]:
    """
    Calculate length of stay in nights from dd/mm formatted dates (no year).

    Heuristic for year determination (to handle crossing into next year):
    - Assume current year for arrival
    - If departure month < arrival month, assume departure is in the next year
    - This handles year-crossing stays (e.g., arrival Dec, departure Jan)

    Args:
        arrival_date: Date in dd/mm format (e.g., "20/11")
        departure_date: Date in dd/mm format (e.g., "05/01")

    Returns:
        Number of nights (integer), or None if dates can't be parsed or result is unreasonable.
    """
    try:
        # Extract day and month from dd/mm format
        arr_match = re.match(r"(\d{1,2})/(\d{1,2})", arrival_date)
        dep_match = re.match(r"(\d{1,2})/(\d{1,2})", departure_date)

        if not arr_match or not dep_match:
            return None

        arr_day, arr_month = int(arr_match.group(1)), int(arr_match.group(2))
        dep_day, dep_month = int(dep_match.group(1)), int(dep_match.group(2))

        # Validate day/month ranges (basic sanity check)
        if not (1 <= arr_day <= 31 and 1 <= arr_month <= 12):
            return None
        if not (1 <= dep_day <= 31 and 1 <= dep_month <= 12):
            return None

        # Assume current year for arrival
        year = datetime.now().year

        # Create datetime objects
        arr_dt = datetime(year, arr_month, arr_day)

        # If departure month < arrival month, assume next year (crosses year boundary)
        if dep_month < arr_month:
            dep_dt = datetime(year + 1, dep_month, dep_day)
        else:
            dep_dt = datetime(year, dep_month, dep_day)

        # Calculate nights
        delta = dep_dt - arr_dt
        nights = delta.days

        # Sanity check: reject unreasonable values (negative or > 365 nights)
        if nights < 0 or nights > 365:
            return None

        return nights

    except (ValueError, AttributeError, TypeError):
        return None


def write_arrival_record(arrival: dict, hotel_state_manager=None) -> None:
    """
    Idempotently create/update a per-arrival JSON record.

    Follows the merge-never-overwrite pattern from trace_analytics.py:
    - Reads existing file if present (tolerates JSON errors)
    - Only overwrites fields if they're empty/missing in the existing file
    - Never touches the 'traces' field (that's owned by another feature)
    - Preserves any unknown top-level keys already in the file

    Args:
        arrival: Dict with keys: booking_id, room_number, guest_name,
                 arrival_date (dd/mm), departure_date (dd/mm), agency
        hotel_state_manager: HotelStateManager instance (optional, for loading room moves).
                           If None, room_moves will be an empty list.
    """
    booking_id = arrival.get("booking_id", "").strip()

    # Skip silently if booking_id is empty/missing
    if not booking_id:
        return

    # Get RECORDS_DIR from paths_config module reference (for test monkeypatching)
    records_dir = paths_config.RECORDS_DIR
    os.makedirs(records_dir, exist_ok=True)

    target_path = os.path.join(records_dir, f"{booking_id}.json")

    # Read existing file (tolerate parse errors)
    existing_record = {}
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                existing_record = json.load(f)
        except Exception:
            existing_record = {}

    # Prepare new fields (only write if not already present/non-empty)
    record_data = {}

    # Always preserve existing data unless we have a new non-empty value
    for key in existing_record:
        if key != "traces":  # Never touch traces
            record_data[key] = existing_record[key]

    # Write fields, only overwriting if existing value is empty/missing
    def set_if_empty(key: str, value: Any) -> None:
        if key not in record_data or not record_data[key]:
            record_data[key] = value

    set_if_empty("booking_id", booking_id)
    set_if_empty("room_number", arrival.get("room_number", "").strip())
    set_if_empty("arrival_date", arrival.get("arrival_date", "").strip())
    set_if_empty("departure_date", arrival.get("departure_date", "").strip())

    # Calculate length_of_stay if not already present
    if "length_of_stay" not in record_data or record_data.get("length_of_stay") is None:
        arrival_date = arrival.get("arrival_date", "").strip()
        departure_date = arrival.get("departure_date", "").strip()
        los = _calculate_length_of_stay(arrival_date, departure_date)
        record_data["length_of_stay"] = los

    set_if_empty("guest_name", arrival.get("guest_name", "").strip())
    set_if_empty("tour_operator", arrival.get("agency", "").strip())

    # Load room_moves if not already present and hotel_state_manager is available
    if ("room_moves" not in record_data or not record_data.get("room_moves")) and hotel_state_manager:
        try:
            all_moves = hotel_state_manager.load_room_moves_history()
            filtered_moves = [m for m in all_moves if m.get("booking_id") == booking_id]
            record_data["room_moves"] = filtered_moves
        except Exception:
            record_data["room_moves"] = []
    elif "room_moves" not in record_data:
        record_data["room_moves"] = []

    # Initialize traces if not already present (never populate, never overwrite existing)
    # If traces already exist in the existing record, keep them untouched
    if "traces" not in record_data:
        record_data["traces"] = existing_record.get("traces", [])

    # Preserve any unknown top-level keys from existing file
    for key, value in existing_record.items():
        if key not in record_data:
            record_data[key] = value

    # Write atomically to file
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(record_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        # Don't crash the pipeline on write failure; let caller decide logging
        raise RuntimeError(f"Failed to write record {booking_id}: {e}") from e
