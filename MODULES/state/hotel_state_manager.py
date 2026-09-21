"""
Hotel State Management & Comparison Engine
==========================================
Manages master_state.json, state_metadata.json, arrivals/departures state,
checkouts history, and room moves history. Implements the core comparison engine
that identifies room moves (strictly excluding room merges) and checkouts.
"""

import os
import json
import shutil
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

from MODULES.common.paths_config import (
    MASTER_STATE_PATH,
    STATE_META_PATH,
    ARRIVALS_BEACH_PATH,
    DEPARTURES_BEACH_PATH,
    TRASH_DIR,
    CHECKOUTS_JSON,
    ROOM_MOVES_JSON,
    ROOM_MOVES_LOG_PATH,
    DEFAULT_PROPERTY,
    DATABASE_DIR,
    ROOMS_DIR,
    HOTEL_DATASET_PATH,
    save_and_archive_json,
    ensure_workspace_directories,
)
from MODULES.parsing.inhouse_parser import normalize_booking_dict
from MODULES.room_type_ladder import compare_room_types


class HotelStateManager:
    """
    State Persistence & Comparison Engine:
      - Maintains master_state.json and state_metadata.json in DATABASE/HOTEL STATE/.
      - Compares successive in-house states to detect room moves (excluding merges) and checkouts.
      - Tracks historical checkouts and room move audits.
      - Manages Gatekeeper missing date calculations.
    """

    normalize_booking_dict = staticmethod(normalize_booking_dict)

    def __init__(
        self,
        master_state_path: Optional[str] = None,
        state_meta_path: Optional[str] = None,
        arrivals_state_path: Optional[str] = None,
        trash_dir: Optional[str] = None,
        checkouts_path: Optional[str] = None,
        room_moves_path: Optional[str] = None
    ):
        ensure_workspace_directories()
        self.master_state_path = os.path.abspath(master_state_path or MASTER_STATE_PATH)
        self.state_meta_path = os.path.abspath(state_meta_path or STATE_META_PATH)
        self.arrivals_state_path = os.path.abspath(arrivals_state_path or ARRIVALS_BEACH_PATH)
        self.trash_dir = os.path.abspath(trash_dir or TRASH_DIR)
        self.checkouts_path = os.path.abspath(checkouts_path or CHECKOUTS_JSON)
        self.room_moves_path = os.path.abspath(room_moves_path or ROOM_MOVES_JSON)

    # -------------------------------------------------------------------------
    # In-House State Persistence (HOTEL STATE/master_state.json)
    # -------------------------------------------------------------------------
    def load_master_state(self) -> Dict[str, Dict[str, Any]]:
        """Loads master_state.json and automatically normalizes entries with canonical English keys."""
        target = self.master_state_path
        if not os.path.exists(target):
            return {}
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                return {
                    k: normalize_booking_dict(k, v)
                    for k, v in data.items()
                    if not k.startswith("_") and isinstance(v, dict)
                }
        except Exception as e:
            print(f"[HotelStateManager] Error loading master state: {e}")
            return {}

    def normalize_master_state(self) -> int:
        """Persists normalized English and Greek keys to master_state.json."""
        state = self.load_master_state()
        if state:
            self.save_master_state(state)
        return len(state)

    def save_master_state(self, state: Dict[str, Dict[str, Any]]):
        """Atomically saves the active in-house guests to DATABASE/HOTEL STATE/master_state.json."""
        normalized = {k: normalize_booking_dict(k, v) for k, v in state.items()}
        save_and_archive_json(normalized, self.master_state_path)

    # -------------------------------------------------------------------------
    # Trace List Ingestion & Room Mapping Integration
    # -------------------------------------------------------------------------
    def scan_for_trace_files(self, search_dir: Optional[str] = None) -> List[str]:
        """Scans DATABASE/ (or specified directory) to locate trace list export files."""
        from MODULES.trace_analytics import scan_for_trace_files as _scan
        return _scan(search_dir or DATABASE_DIR)

    def parse_trace_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parses a trace list file (.csv, .xlsx, .xls) and normalizes trace records."""
        from MODULES.trace_analytics import parse_trace_file as _parse
        return _parse(file_path)

    def generate_room_json_mappings(
        self,
        trace_items: Optional[List[Dict[str, Any]]] = None,
        file_path: Optional[str] = None,
        rooms_dir: Optional[str] = None,
        include_all_schema_rooms: bool = False
    ) -> Dict[str, Any]:
        """Generates or updates ROOMS/<room_number>.json mapping files idempotently."""
        from MODULES.trace_analytics import (
            parse_trace_file as _parse,
            generate_room_json_mappings as _gen,
            scan_for_trace_files as _scan
        )
        if trace_items is None:
            target_path = file_path
            if not target_path:
                detected = _scan(DATABASE_DIR)
                target_path = detected[0] if detected else None
            if not target_path:
                return {"error": "No trace file specified or detected"}
            trace_items = _parse(target_path)

        target_rooms_dir = rooms_dir or ROOMS_DIR
        return _gen(trace_items, rooms_dir=target_rooms_dir, include_all_schema_rooms=include_all_schema_rooms)

    def get_trace_analytics_data(
        self,
        trace_items: Optional[List[Dict[str, Any]]] = None,
        file_path: Optional[str] = None,
        room_moves_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Computes statistical aggregations for the Visual Analytics Charts and extended KPIs."""
        from MODULES.trace_analytics import (
            parse_trace_file as _parse,
            compute_visual_analytics_data as _calc,
            scan_for_trace_files as _scan
        )
        if trace_items is None:
            target_path = file_path
            if not target_path:
                detected = _scan(DATABASE_DIR)
                target_path = detected[0] if detected else None
            if not target_path:
                in_house_manifest = self.load_master_state()
                return _calc([], in_house_manifest=in_house_manifest, hotel_dataset_path=HOTEL_DATASET_PATH, room_moves_path=room_moves_path or self.room_moves_path)
            trace_items = _parse(target_path)

        in_house_manifest = self.load_master_state()
        return _calc(
            trace_items,
            in_house_manifest=in_house_manifest,
            hotel_dataset_path=HOTEL_DATASET_PATH,
            room_moves_path=room_moves_path or self.room_moves_path
        )

    def fuse_inhouse_and_traces(
        self,
        in_house_data: Optional[Dict[str, Any]] = None,
        trace_items: Optional[List[Dict[str, Any]]] = None,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executes bidirectional synchronization and joint fusion of In-House list and Traces."""
        from MODULES.trace_analytics import (
            fuse_inhouse_and_traces as _fuse,
            parse_trace_file as _parse,
            scan_for_trace_files as _scan
        )
        if in_house_data is None:
            in_house_data = self.load_master_state()
            if not in_house_data and os.path.exists(DATABASE_DIR):
                from MODULES.parsing.inhouse_parser import parse_in_house_file as _parse_ih
                in_house_files = [f for f in os.listdir(DATABASE_DIR) if "in_house" in f.lower() or "παραμένοντες" in f.lower()]
                if in_house_files:
                    in_house_data = _parse_ih(os.path.join(DATABASE_DIR, in_house_files[0]))

        if trace_items is None:
            target_path = file_path
            if not target_path:
                detected = _scan(DATABASE_DIR)
                target_path = detected[0] if detected else None
            if target_path and os.path.exists(target_path):
                trace_items = _parse(target_path)
            else:
                trace_items = []

        return _fuse(in_house_data or {}, trace_items or [], hotel_dataset_path=HOTEL_DATASET_PATH)

    # -------------------------------------------------------------------------
    # Metadata Persistence
    # -------------------------------------------------------------------------
    def load_metadata(self) -> Dict[str, Any]:
        """Loads system metadata (last_sync_date, last_updated_at, total_bookings)."""
        target = self.state_meta_path
        if not os.path.exists(target):
            return {"last_sync_date": None, "last_updated_at": None, "total_bookings": 0}
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "last_sync_date" not in data and "last_processed_date" in data:
                        data["last_sync_date"] = data["last_processed_date"]
                    return data
        except Exception:
            pass
        return {"last_sync_date": None, "last_updated_at": None, "total_bookings": 0}

    def save_metadata(self, meta: Dict[str, Any]):
        """Persists system metadata to DATABASE/HOTEL STATE/state_metadata.json."""
        save_and_archive_json(meta, self.state_meta_path)

    def get_last_sync_date(self) -> Optional[date]:
        """Returns the last synchronized in-house date, or None if no synchronization has occurred."""
        meta = self.load_metadata()
        last_str = meta.get("last_sync_date") or meta.get("last_processed_date")
        if last_str:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(last_str, fmt).date()
                except ValueError:
                    pass
        return None

    get_last_processed_date = get_last_sync_date

    def set_last_sync_date(self, target_date: date):
        """Updates last_sync_date, last_updated_at, and total_bookings in state_metadata.json."""
        meta = self.load_metadata()
        meta["last_sync_date"] = target_date.strftime("%Y-%m-%d")
        meta["last_processed_date"] = target_date.strftime("%Y-%m-%d")
        meta["last_updated_at"] = datetime.now().isoformat()
        master = self.load_master_state()
        meta["total_bookings"] = len(master)
        self.save_metadata(meta)

    set_last_processed_date = set_last_sync_date

    # -------------------------------------------------------------------------
    # Arrivals & Departures State Persistence
    # -------------------------------------------------------------------------
    def load_arrivals_state(self) -> Dict[str, Any]:
        """Loads arrivals state for Sandy Beach from today_arrivals.json."""
        beach_data = {}
        target = self.arrivals_state_path
        if os.path.exists(target):
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    beach_data = data
            except Exception:
                pass

        res = {
            "_metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_beach": len(beach_data),
                "total_arrivals": len(beach_data)
            },
            "SANDY BEACH": beach_data
        }
        return res

    def save_arrivals_state(self, arrivals_data: Dict[str, Any]):
        """Persists Sandy Beach arrivals into today_arrivals.json."""
        beach_data = arrivals_data.get("SANDY BEACH", arrivals_data)
        save_and_archive_json(beach_data, self.arrivals_state_path)

    def load_departures_state(self, property_name: str = DEFAULT_PROPERTY) -> Dict[str, Any]:
        """Loads departures state from DATABASE/SANDY BEACH/DEPARTURE/departures_today.json."""
        target_path = DEPARTURES_BEACH_PATH
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {
            "property": "sandy_beach",
            "date": date.today().strftime("%Y-%m-%d"),
            "total_departures": 0,
            "departures": []
        }

    def save_departures_state(self, departures_data: Dict[str, Any], property_name: str = DEFAULT_PROPERTY):
        """Saves departures state into DATABASE/SANDY BEACH/DEPARTURE/departures_today.json."""
        save_and_archive_json(departures_data, DEPARTURES_BEACH_PATH)

    def load_checkouts_history(self) -> Dict[str, Any]:
        """Loads checkout records from DATABASE/CHECK OUT HISTORY/checkouts.json."""
        target = self.checkouts_path
        records = []
        if os.path.exists(target):
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict) and "records" in data:
                        records = data["records"]
            except Exception:
                records = []

        return {
            "property": DEFAULT_PROPERTY,
            "last_updated": datetime.now().isoformat(),
            "total_records": len(records),
            "records": records
        }

    def load_room_moves_history(self) -> List[Dict[str, Any]]:
        """Loads room moves from DATABASE/ROOM MOVES/room_moves.json."""
        target = self.room_moves_path
        if os.path.exists(target):
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "moves" in data:
                        return data["moves"]
            except Exception:
                pass
        return []

    # -------------------------------------------------------------------------
    # Gatekeeper Missing Dates Calculation
    # -------------------------------------------------------------------------
    def get_missing_dates(self, reference_date: Optional[date] = None) -> List[date]:
        """
        Determines sequential calendar dates from the day after last_sync_date
        up to reference_date (defaults to today).
        """
        if reference_date is None:
            reference_date = date.today()

        last_date = self.get_last_sync_date()
        if last_date is None:
            return [reference_date]

        if last_date >= reference_date:
            return []

        missing = []
        current = last_date + timedelta(days=1)
        while current <= reference_date:
            missing.append(current)
            current += timedelta(days=1)
        return missing

    # -------------------------------------------------------------------------
    # Comparison Engine & In-House State Synchronizer with Room Merge Exclusion
    # -------------------------------------------------------------------------
    def compare_and_update(self, new_bookings: Dict[str, Dict[str, Any]],
                           processing_date: date) -> Dict[str, Any]:
        """
        Compares new_bookings against master_state.json.
        Detects:
          - Room Move (Booking ID exists, old_room != new_room).
            EXCLUSION FILTER: If two different rooms from yesterday's state are moved
            into the same single room number today (or if multiple bookings are consolidated
            into one room), classify and flag this as a Room Merge and strictly exclude
            it from standard room_moves.json.
          - Check-out (Booking ID in master_state, missing from new_bookings).
          - Check-in (Booking ID not in master_state, present in new_bookings).
        Updates master_state.json, checkouts.json, room_moves.json, and state_metadata.json.
        """
        current_state = self.load_master_state()
        date_str = processing_date.strftime("%d/%m/%Y")

        candidate_moves = []
        room_type_changes = []
        check_outs = []
        check_ins = []
        unchanged_count = 0

        # 1. Compare new bookings with current state
        for booking_id, new_data in new_bookings.items():
            new_room = str(new_data.get("Room") or new_data.get("Δωμάτιο", "")).strip()

            if booking_id in current_state:
                old_data = current_state[booking_id]
                old_room = str(old_data.get("Room") or old_data.get("Δωμάτιο", "")).strip()

                old_type = str(old_data.get("Room Type") or old_data.get("Τύπος Δωματίου") or old_data.get("Τύπος Δωμ", "")).strip()
                new_type = str(new_data.get("Room Type") or new_data.get("Τύπος Δωματίου") or new_data.get("Τύπος Δωμ", "")).strip()
                if old_type != new_type:
                    guests = new_data.get("Guests") or new_data.get("Πελάτες", [])
                    direction = compare_room_types(old_type, new_type)
                    room_type_changes.append({
                        "booking_id": booking_id,
                        "guests": guests,
                        "old_type": old_type,
                        "new_type": new_type,
                        "direction": direction,
                        "old_room": old_room,
                        "new_room": new_room,
                        "date": date_str
                    })

                if old_room and new_room and old_room != new_room:
                    guests = new_data.get("Guests") or new_data.get("Πελάτες", [])
                    arr = str(new_data.get("Arrival") or new_data.get("Άφιξη", "")).strip()
                    dep = str(new_data.get("Departure") or new_data.get("Αναχώρηση", "")).strip()
                    move_info = {
                        "booking_id": booking_id,
                        "guests": guests,
                        "Πελάτες": guests,
                        "old_room": old_room,
                        "new_room": new_room,
                        "arrival": arr,
                        "departure": dep,
                        "date": date_str,
                        "timestamp": datetime.now().isoformat()
                    }
                    candidate_moves.append(move_info)
                else:
                    unchanged_count += 1
            else:
                guests = new_data.get("Guests") or new_data.get("Πελάτες", [])
                arr = str(new_data.get("Arrival") or new_data.get("Άφιξη", "")).strip()
                dep = str(new_data.get("Departure") or new_data.get("Αναχώρηση", "")).strip()
                check_in_info = {
                    "booking_id": booking_id,
                    "guests": guests,
                    "Πελάτες": guests,
                    "room": new_room,
                    "Room": new_room,
                    "Δωμάτιο": new_room,
                    "arrival": arr,
                    "departure": dep,
                    "date": date_str
                }
                check_ins.append(check_in_info)

        # 2. Room Merge Detection & Exclusion Filter
        merged_room_numbers = set()

        # Check a: multiple candidate moves targeting the same new_room with different old_rooms
        new_room_to_old_rooms: Dict[str, set] = {}
        for cm in candidate_moves:
            new_room_to_old_rooms.setdefault(cm["new_room"], set()).add(cm["old_room"])

        for nr, old_rms in new_room_to_old_rooms.items():
            if len(old_rms) > 1:
                merged_room_numbers.add(nr)

        # Check b: multiple bookings in new_bookings now share the same new_room
        new_room_to_all_bookings: Dict[str, List[str]] = {}
        for b_id, b_data in new_bookings.items():
            rm = str(b_data.get("Room") or b_data.get("Δωμάτιο", "")).strip()
            if rm:
                new_room_to_all_bookings.setdefault(rm, []).append(b_id)

        for nr, b_ids in new_room_to_all_bookings.items():
            if len(b_ids) > 1:
                yesterday_rooms = set()
                moved_in = False
                for b_id in b_ids:
                    if b_id in current_state:
                        prev_rm = str(current_state[b_id].get("Room") or current_state[b_id].get("Δωμάτιο", "")).strip()
                        if prev_rm:
                            yesterday_rooms.add(prev_rm)
                            if prev_rm != nr:
                                moved_in = True
                if len(yesterday_rooms) > 1 or moved_in:
                    merged_room_numbers.add(nr)

        # Separate standard room moves from room merges
        room_moves = []
        room_merges = []
        for cm in candidate_moves:
            if cm["new_room"] in merged_room_numbers:
                cm["is_room_merge"] = True
                room_merges.append(cm)
            else:
                room_moves.append(cm)

        # 3. Detect Check-outs
        for booking_id, old_data in current_state.items():
            if booking_id not in new_bookings:
                guests = old_data.get("Guests") or old_data.get("Πελάτες", [])
                room = str(old_data.get("Room") or old_data.get("Δωμάτιο", "")).strip()
                dep = str(old_data.get("Departure") or old_data.get("Αναχώρηση", "")).strip()
                check_out_info = {
                    "booking_id": booking_id,
                    "property": DEFAULT_PROPERTY,
                    "guests": guests,
                    "Πελάτες": guests,
                    "room": room,
                    "Room": room,
                    "Δωμάτιο": room,
                    "departure": dep,
                    "checkout_date": date_str,
                    "archived_at": datetime.now().isoformat()
                }
                check_outs.append(check_out_info)

        # 4. Commit new state to master_state.json and update metadata
        self.save_master_state(new_bookings)
        self.set_last_sync_date(processing_date)

        # 4.1 Automated Room Block Exporter synchronization
        try:
            from MODULES.admin.database_admin import export_room_block_json_data as _export_blocks
            _export_blocks()
        except Exception as exp_err:
            print(f"[HotelStateManager] Warning during auto room block export: {exp_err}")

        # 4.2 Auto-populate Today's Arrivals from day arrivals or check-ins
        day_arrivals = {}
        for b_id, b_data in new_bookings.items():
            arr_val = str(b_data.get("Arrival") or b_data.get("Άφιξη", "")).strip()
            is_arr_today = False
            if arr_val:
                parts = arr_val.split("/")
                if len(parts) == 3:
                    try:
                        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                        if y < 100:
                            y += 2000
                        if (d, m, y) == (processing_date.day, processing_date.month, processing_date.year):
                            is_arr_today = True
                    except Exception:
                        pass
                if not is_arr_today and (arr_val == date_str or arr_val == processing_date.strftime("%Y-%m-%d")):
                    is_arr_today = True

            if is_arr_today:
                day_arrivals[b_id] = {
                    "room": str(b_data.get("Room") or b_data.get("Δωμάτιο", "")).strip(),
                    "Room": str(b_data.get("Room") or b_data.get("Δωμάτιο", "")).strip(),
                    "guests": b_data.get("Guests") or b_data.get("Πελάτες", []),
                    "adults": str(b_data.get("Adults") or b_data.get("Σύν. Ατόμων", "1")),
                    "children": str(b_data.get("Children") or b_data.get("Αρ. Παιδ", "0")),
                    "arrival": arr_val,
                    "departure": str(b_data.get("Departure") or b_data.get("Αναχώρηση", "")),
                    "agency": str(b_data.get("Agency") or b_data.get("Χρεώστης", "")),
                    "room_type": str(b_data.get("Room Type") or b_data.get("Τύπος Δωματίου", ""))
                }

        if day_arrivals:
            self.save_arrivals_state(day_arrivals)
        elif check_ins:
            ci_arrivals = {
                ci["booking_id"]: {
                    "room": ci["room"],
                    "Room": ci["room"],
                    "guests": ci["guests"],
                    "adults": "1",
                    "children": "0",
                    "arrival": ci["arrival"],
                    "departure": ci["departure"],
                    "agency": "Direct",
                    "room_type": "Standard"
                }
                for ci in check_ins
            }
            self.save_arrivals_state(ci_arrivals)

        # 5. Record Check-outs to History
        if check_outs:
            self._archive_checkouts(check_outs)
            dep_payload = {
                "property": DEFAULT_PROPERTY,
                "date": date_str,
                "total_departures": len(check_outs),
                "departures": check_outs
            }
            self.save_departures_state(dep_payload, property_name=DEFAULT_PROPERTY)

        # 6. Record standard Room Moves (Excluding Merges)
        if room_moves:
            self._record_room_moves(room_moves)

        summary = {
            "date": date_str,
            "total_in_house": len(new_bookings),
            "room_moves": room_moves,
            "room_merges": room_merges,
            "room_type_changes": room_type_changes,
            "check_ins": check_ins,
            "check_outs": check_outs,
            "unchanged": unchanged_count
        }
        return summary

    # -------------------------------------------------------------------------
    # Audit & History Logging
    # -------------------------------------------------------------------------
    def _archive_checkouts(self, checkouts: List[Dict[str, Any]]):
        """Archives checkouts into checkouts.json with deduplication."""
        existing = self.load_checkouts_history()
        records = existing.get("records", [])

        seen = {(r.get("booking_id"), r.get("checkout_date")) for r in records}
        for co in checkouts:
            if "property" not in co:
                co["property"] = DEFAULT_PROPERTY
            key = (co.get("booking_id"), co.get("checkout_date"))
            if key not in seen:
                seen.add(key)
                records.append(co)

        payload = {
            "property": DEFAULT_PROPERTY,
            "last_updated": datetime.now().isoformat(),
            "total_records": len(records),
            "records": records
        }
        try:
            save_and_archive_json(payload, self.checkouts_path)
        except Exception as e:
            print(f"[HotelStateManager] Error archiving checkouts: {e}")

    def _record_room_moves(self, room_moves: List[Dict[str, Any]]):
        """Records standard room moves into room_moves.json and text log."""
        try:
            with open(ROOM_MOVES_LOG_PATH, "a", encoding="utf-8") as f:
                for rm in room_moves:
                    guests_str = ", ".join(rm.get("guests", []))
                    line = (
                        f"[{rm['date']} {datetime.now().strftime('%H:%M:%S')}] "
                        f"ROOM MOVE: Booking #{rm['booking_id']} ({guests_str}) "
                        f"moved from Room {rm['old_room']} ➔ {rm['new_room']} "
                        f"(Dep: {rm.get('departure', '')})\n"
                    )
                    f.write(line)
        except Exception as e:
            print(f"[HotelStateManager] Error writing room moves log: {e}")

        history = self.load_room_moves_history()
        seen = {(m.get("booking_id"), m.get("old_room"), m.get("new_room"), m.get("date")) for m in history}
        for rm in room_moves:
            k = (rm.get("booking_id"), rm.get("old_room"), rm.get("new_room"), rm.get("date"))
            if k not in seen:
                seen.add(k)
                history.append(rm)

        try:
            save_and_archive_json(history, self.room_moves_path)
        except Exception as e:
            print(f"[HotelStateManager] Error writing room moves history JSON: {e}")

    # -------------------------------------------------------------------------
    # Cleanup Manager
    # -------------------------------------------------------------------------
    def cleanup_file(self, file_path: str, mode: str = "trash") -> str:
        """Moves processed CSV file into TRASH/ with timestamped suffix."""
        if not os.path.exists(file_path):
            return file_path

        os.makedirs(self.trash_dir, exist_ok=True)
        base_name = os.path.basename(file_path)
        name_part, ext = os.path.splitext(base_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_filename = f"{name_part}_PROCESSED_{timestamp}{ext}"
        dest_path = os.path.join(self.trash_dir, dest_filename)

        try:
            shutil.move(file_path, dest_path)
            return dest_path
        except Exception:
            shutil.copy2(file_path, dest_path)
            try:
                os.remove(file_path)
            except Exception:
                pass
            return dest_path
