"""
Data Manager Module: Ingestion, State Management, Room-Move Detection & Gatekeeper
===================================================================================
Handles daily 'In-House List' and 'Arrivals' CSV exports for Sandy Beach, maintains
DATABASE/HOTEL STATE/master_state.json and state_metadata.json, standardizes strictly
on the centralized DATABASE/ directory topology, detects room moves (strictly excluding
room merges) and checkouts, and enforces sequential Gatekeeper startup validation.
"""

import os
import sys
import csv
import json
import shutil
import re
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QProgressBar, QFrame, QScrollArea, QWidget,
    QApplication, QTextEdit, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATABASE_DIR = os.path.join(BASE_DIR, "DATABASE")
TEMPLATES_DIR = os.path.join(BASE_DIR, "TEMPLATES")
OUTPUT_DIR = os.path.join(BASE_DIR, "OUTPUT")
TRASH_DIR = os.path.join(BASE_DIR, "TRASH")
TODAYS_LIST_DIR = os.path.join(OUTPUT_DIR, "TODAYS_LIST")
BOOKING_CALLS_DIR = os.path.join(BASE_DIR, "BOOKING CALLS")
PLOT_DIR = os.path.join(BASE_DIR, "PLOT")
HOTEL_DATASET_PATH = os.path.join(PLOT_DIR, "HotelDataSet.json")

# Standardized Target Directories inside DATABASE/
HOTEL_STATE_DIR = os.path.join(DATABASE_DIR, "HOTEL STATE")
BOOKING_CALLS_TODAY_DIR = os.path.join(DATABASE_DIR, "BOOKING CALLS FOR TODAY")
CHECKOUT_HISTORY_DIR = os.path.join(DATABASE_DIR, "CHECK OUT HISTORY")
ROOM_MOVES_DIR = os.path.join(DATABASE_DIR, "ROOM MOVES")
SANDY_BEACH_DIR = os.path.join(DATABASE_DIR, "SANDY BEACH")
SANDY_BEACH_ARRIVALS_DIR = os.path.join(SANDY_BEACH_DIR, "ARRIVALS")
SANDY_BEACH_DEPARTURE_DIR = os.path.join(SANDY_BEACH_DIR, "DEPARTURE")

# Standardized Target JSON Artifacts
MASTER_STATE_PATH = os.path.join(HOTEL_STATE_DIR, "master_state.json")
STATE_META_PATH = os.path.join(HOTEL_STATE_DIR, "state_metadata.json")
BOOKING_CALLS_TODAY_JSON = os.path.join(BOOKING_CALLS_TODAY_DIR, "booking_calls_for_today.json")
CHECKOUTS_JSON = os.path.join(CHECKOUT_HISTORY_DIR, "checkouts.json")
ROOM_MOVES_JSON = os.path.join(ROOM_MOVES_DIR, "room_moves.json")
ARRIVALS_BEACH_PATH = os.path.join(SANDY_BEACH_ARRIVALS_DIR, "today_arrivals.json")
DEPARTURES_BEACH_PATH = os.path.join(SANDY_BEACH_DEPARTURE_DIR, "departures_today.json")

# Backward Compatibility Aliases
MASTER_STATE_ROOT_PATH = MASTER_STATE_PATH
STATE_META_ROOT_PATH = STATE_META_PATH
CHECKOUTS_TODAY_JSON = CHECKOUTS_JSON
CHECKOUT_HISTORY_PATH = CHECKOUTS_JSON
ROOM_MOVES_YESTERDAY_JSON = ROOM_MOVES_JSON
ROOM_MOVES_HISTORY_PATH = ROOM_MOVES_JSON
ROOM_MOVES_LOG_PATH = os.path.join(TODAYS_LIST_DIR, "room_moves.log")

DEFAULT_PROPERTY = "sandy_beach"
active_property = DEFAULT_PROPERTY


def get_property_dir(property_name: str = DEFAULT_PROPERTY, base_dir: Optional[Union[str, Path]] = None) -> Path:
    """Returns the Path directory for the specified property (standardized on 'SANDY BEACH')."""
    db_root = Path(base_dir) if base_dir else Path(DATABASE_DIR)
    norm = property_name.upper().replace("_", " ")
    return db_root / norm


def get_property_arrivals_path(property_name: str = DEFAULT_PROPERTY, base_dir: Optional[Union[str, Path]] = None) -> Path:
    """Returns the Path to today_arrivals.json for the specified property."""
    return get_property_dir(property_name, base_dir) / "ARRIVALS" / "today_arrivals.json"


def get_property_departures_path(property_name: str = DEFAULT_PROPERTY, base_dir: Optional[Union[str, Path]] = None) -> Path:
    """Returns the Path to departures_today.json for the specified property."""
    return get_property_dir(property_name, base_dir) / "DEPARTURE" / "departures_today.json"


def resolve_template_path(template_type: str, base_templates_dir: Optional[Union[str, Path]] = None) -> Optional[str]:
    """
    Template Resolution Protocol:
      - 'booking_calls': searches TEMPLATES/BOOKING CALLS TEMPLATE/ for BOOKING CALLS.xlsx
      - 'cake_memo' / 'check_memo': searches TEMPLATES/CAKE MEMO TEMPLATE/ for CAKE MEMO.docx
                                    with fallback to check memo template.
      - 'offer_list': searches TEMPLATES/OFFER LIST TEMPLATE/ for OFFER LIST TEMPLATE.docx
    Returns the resolved absolute path as a string, or None if not found.
    """
    root_tpl = Path(base_templates_dir) if base_templates_dir else Path(TEMPLATES_DIR)

    def find_dir(parent: Path, name: str) -> Optional[Path]:
        if not parent.exists():
            return None
        target_lower = name.lower()
        for item in parent.iterdir():
            if item.is_dir() and item.name.lower() == target_lower:
                return item
        return parent / name

    def find_file(directory: Path, filename: str, ext: str) -> Optional[Path]:
        if not directory.exists() or not directory.is_dir():
            return None
        for item in directory.iterdir():
            if item.is_file() and item.name.lower() == filename.lower():
                return item
        for item in directory.iterdir():
            if item.is_file() and item.name.lower().endswith(ext.lower()):
                return item
        return None

    ttype = template_type.lower().strip()
    if "booking" in ttype or "call" in ttype:
        d = find_dir(root_tpl, "booking calls template")
        if d:
            f = find_file(d, "BOOKING CALLS.xlsx", ".xlsx")
            if f:
                return str(f.resolve())
            return str((d / "BOOKING CALLS.xlsx").resolve())
        return str((root_tpl / "booking calls template" / "BOOKING CALLS.xlsx").resolve())

    elif "offer" in ttype:
        d = find_dir(root_tpl, "offer list template")
        if d:
            f = find_file(d, "OFFER LIST TEMPLATE.docx", ".docx")
            if f:
                return str(f.resolve())
            return str((d / "OFFER LIST TEMPLATE.docx").resolve())
        return str((root_tpl / "offer list template" / "OFFER LIST TEMPLATE.docx").resolve())

    elif "cake" in ttype or "check" in ttype or "memo" in ttype:
        # Prioritize cake memo template
        primary_dir = find_dir(root_tpl, "cake memo template")
        if primary_dir and primary_dir.exists():
            f = find_file(primary_dir, "CAKE MEMO.docx", ".docx")
            if f:
                return str(f.resolve())
        fallback_dir = find_dir(root_tpl, "check memo template")
        if fallback_dir and fallback_dir.exists():
            f = find_file(fallback_dir, "CHECK MEMO.docx", ".docx")
            if f:
                return str(f.resolve())
            f2 = find_file(fallback_dir, "CAKE MEMO.docx", ".docx")
            if f2:
                return str(f2.resolve())
        return str((root_tpl / "cake memo template" / "CAKE MEMO.docx").resolve())

    return None


def safe_rmtree(path: str):
    """Safely removes a directory even if it has Windows ReadOnly attributes."""
    if not os.path.exists(path):
        return
    import stat
    def on_exc(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    try:
        shutil.rmtree(path, onexc=on_exc)
    except Exception:
        pass


def save_and_archive_json(data: Any, target_filename: str, subfolder: Optional[str] = None, base_dir: Optional[str] = None) -> str:
    """
    Centralized, synchronous, and atomic JSON persistence helper.
    Ensures all writes occur strictly within canonical subdirectories of DATABASE/.
    No redundant DATABASE/DATABASE/ or root mirroring.
    Writes atomically via a .tmp file using encoding='utf-8', indent=4, ensure_ascii=False.
    Returns the absolute path to the saved file.
    """
    base_name = os.path.basename(target_filename)
    root = base_dir if base_dir else DATABASE_DIR

    # Automatic routing if subfolder is not explicitly specified and target is relative
    if subfolder is None and not os.path.isabs(target_filename):
        lower_name = base_name.lower()
        if "master_state" in lower_name:
            subfolder = "HOTEL STATE"
            base_name = "master_state.json"
        elif "state_meta" in lower_name:
            subfolder = "HOTEL STATE"
            base_name = "state_metadata.json"
        elif "booking" in lower_name or "call" in lower_name:
            subfolder = "BOOKING CALLS FOR TODAY"
            base_name = "booking_calls_for_today.json"
        elif "checkout" in lower_name or "check_out" in lower_name:
            subfolder = "CHECK OUT HISTORY"
            base_name = "checkouts.json"
        elif "room_move" in lower_name or "room move" in lower_name:
            subfolder = "ROOM MOVES"
            base_name = "room_moves.json"
        elif "arrival" in lower_name:
            subfolder = "SANDY BEACH/ARRIVALS"
            base_name = "today_arrivals.json"
        elif "departure" in lower_name:
            subfolder = "SANDY BEACH/DEPARTURE"
            base_name = "departures_today.json"
    elif subfolder:
        norm_sub = subfolder.strip().replace("\\", "/").upper()
        if norm_sub in ["BOOKING CALLS FOR TODAY", "BOOKING_CALLS_FOR_TODAY", "BOOKING CALLS"]:
            subfolder = "BOOKING CALLS FOR TODAY"
        elif norm_sub in ["CHECK OUT HISTORY", "CHECK_OUT_HISTORY", "CHECKOUT HISTORY"]:
            subfolder = "CHECK OUT HISTORY"
        elif norm_sub in ["ROOM MOVES", "ROOM_MOVES", "ROOM MOVES HISTORY"]:
            subfolder = "ROOM MOVES"
        elif "HOTEL STATE" in norm_sub or norm_sub == "DATABASE":
            subfolder = "HOTEL STATE"
        elif "SANDY BEACH" in norm_sub and "ARRIVAL" in norm_sub:
            subfolder = "SANDY BEACH/ARRIVALS"
        elif "SANDY BEACH" in norm_sub and "DEPARTURE" in norm_sub:
            subfolder = "SANDY BEACH/DEPARTURE"

    if os.path.isabs(target_filename):
        target_path = target_filename
        target_dir = os.path.dirname(target_path)
    else:
        if subfolder:
            target_dir = os.path.join(root, subfolder)
        else:
            target_dir = root
        target_path = os.path.join(target_dir, base_name)

    os.makedirs(target_dir, exist_ok=True)
    import time
    import uuid
    temp_path = os.path.join(target_dir, f".{base_name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        replaced = False
        for attempt in range(4):
            try:
                if os.path.exists(target_path):
                    os.replace(temp_path, target_path)
                else:
                    os.rename(temp_path, target_path)
                replaced = True
                break
            except (PermissionError, OSError):
                if attempt < 3:
                    time.sleep(0.05)

        if not replaced:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise e
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    return target_path


def ensure_workspace_directories():
    """
    Initializes and enforces the canonical centralized directory topology:
      - DATABASE/HOTEL STATE/master_state.json
      - DATABASE/HOTEL STATE/state_metadata.json
      - DATABASE/BOOKING CALLS FOR TODAY/booking_calls_for_today.json
      - DATABASE/CHECK OUT HISTORY/checkouts.json
      - DATABASE/ROOM MOVES/room_moves.json
      - DATABASE/SANDY BEACH/ARRIVALS/today_arrivals.json
      - DATABASE/SANDY BEACH/DEPARTURE/
    Cleans up redundant DATABASE/DATABASE/ and legacy mirrors.
    """
    dirs_to_create = [
        DATABASE_DIR,
        HOTEL_STATE_DIR,
        BOOKING_CALLS_TODAY_DIR,
        CHECKOUT_HISTORY_DIR,
        ROOM_MOVES_DIR,
        SANDY_BEACH_DIR,
        SANDY_BEACH_ARRIVALS_DIR,
        SANDY_BEACH_DEPARTURE_DIR,
        TEMPLATES_DIR,
        os.path.join(TEMPLATES_DIR, "BOOKING CALLS TEMPLATE"),
        os.path.join(TEMPLATES_DIR, "CAKE MEMO TEMPLATE"),
        os.path.join(TEMPLATES_DIR, "OFFER LIST TEMPLATE"),
        OUTPUT_DIR,
        os.path.join(OUTPUT_DIR, "OFFERS"),
        os.path.join(OUTPUT_DIR, "CAKE_MEMOS"),
        TODAYS_LIST_DIR,
        TRASH_DIR,
        BOOKING_CALLS_DIR,
        PLOT_DIR
    ]
    for d in dirs_to_create:
        os.makedirs(d, exist_ok=True)

    # 1. Clean up redundant DATABASE/DATABASE/ if present
    redundant_db = os.path.join(DATABASE_DIR, "DATABASE")
    if os.path.exists(redundant_db):
        safe_rmtree(redundant_db)

    # 2. Clean up redundant mirror files in DATABASE/ root
    for rf_name in ["master_state.json", "state_metadata.json"]:
        rf = os.path.join(DATABASE_DIR, rf_name)
        if os.path.exists(rf):
            try:
                os.remove(rf)
            except Exception:
                pass

    # 3. Ensure master_state.json
    if not os.path.exists(MASTER_STATE_PATH):
        save_and_archive_json({}, "master_state.json", subfolder="HOTEL STATE")

    # 4. Ensure state_metadata.json
    if not os.path.exists(STATE_META_PATH):
        meta_payload = {
            "last_sync_date": None,
            "last_updated_at": None,
            "total_bookings": 0
        }
        save_and_archive_json(meta_payload, "state_metadata.json", subfolder="HOTEL STATE")

    # 5. Ensure checkouts.json
    if not os.path.exists(CHECKOUTS_JSON):
        save_and_archive_json([], "checkouts.json", subfolder="CHECK OUT HISTORY")

    # 6. Ensure room_moves.json
    if not os.path.exists(ROOM_MOVES_JSON):
        save_and_archive_json([], "room_moves.json", subfolder="ROOM MOVES")

    # 7. Ensure booking_calls_for_today.json
    if not os.path.exists(BOOKING_CALLS_TODAY_JSON):
        save_and_archive_json([], "booking_calls_for_today.json", subfolder="BOOKING CALLS FOR TODAY")

    # 8. Ensure today_arrivals.json for Sandy Beach
    if not os.path.exists(ARRIVALS_BEACH_PATH):
        save_and_archive_json({}, "today_arrivals.json", subfolder="SANDY BEACH/ARRIVALS")


class InHouseDataManager:
    """
    Main Data Manager Engine:
      - Ingests In-House and Arrivals CSV exports for Sandy Beach.
      - Maintains master_state.json and state_metadata.json in DATABASE/HOTEL STATE/.
      - Detects room moves while strictly classifying and excluding room merges.
      - Detects check-outs and records them into checkouts.json.
      - Enforces Gatekeeper sequential in-house synchronization.
    """

    BOOKING_ID_KEYS = ["Αρ.", "Αρ", "Booking ID", "Reservation ID", "Res ID", "Αριθμός Κράτησης"]
    ROOM_KEYS = ["Δωμάτιο", "Room", "Room No", "Room Number", "Δωμ."]
    GUEST_NAME_KEYS = ["Πελάτης", "Guest", "Guest Name", "Όνομα Πελάτη"]
    ARRIVAL_KEYS = ["Άφιξη", "Arrival", "Arr Date"]
    DEPARTURE_KEYS = ["Αναχώρηση", "Departure", "Dep Date"]
    EXCLUDED_COLUMNS = ["τύπος γεύματος", "meal plan", "meal", "γεύμα"]

    def __init__(
        self,
        master_state_path: str = MASTER_STATE_PATH,
        state_meta_path: str = STATE_META_PATH,
        arrivals_state_path: str = ARRIVALS_BEACH_PATH,
        trash_dir: str = TRASH_DIR,
        checkouts_path: str = CHECKOUTS_JSON,
        room_moves_path: str = ROOM_MOVES_JSON
    ):
        ensure_workspace_directories()
        self.master_state_path = os.path.abspath(master_state_path)
        self.state_meta_path = os.path.abspath(state_meta_path)
        self.arrivals_state_path = os.path.abspath(arrivals_state_path)
        self.trash_dir = os.path.abspath(trash_dir)
        self.checkouts_path = os.path.abspath(checkouts_path)
        self.room_moves_path = os.path.abspath(room_moves_path)

    # -------------------------------------------------------------------------
    # In-House State Persistence (HOTEL STATE/master_state.json)
    # -------------------------------------------------------------------------
    def load_master_state(self) -> Dict[str, Dict[str, Any]]:
        """Loads master_state.json from DATABASE/HOTEL STATE/master_state.json."""
        target = self.master_state_path
        if not os.path.exists(target):
            return {}
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}
        except Exception as e:
            print(f"[InHouseDataManager] Error loading master state: {e}")
            return {}

    def save_master_state(self, state: Dict[str, Dict[str, Any]]):
        """Atomically saves the active in-house guests to DATABASE/HOTEL STATE/master_state.json."""
        save_and_archive_json(state, self.master_state_path)

    def load_metadata(self) -> Dict[str, Any]:
        """Loads system metadata (last_sync_date, last_updated_at, total_bookings)."""
        target = self.state_meta_path
        if not os.path.exists(target):
            return {"last_sync_date": None, "last_updated_at": None, "total_bookings": 0}
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Ensure last_sync_date is normalized
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

    # Backward compatibility alias
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

    # Backward compatibility alias
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
        villas_cache = getattr(self, "_villas_arrivals_cache", None)
        if villas_cache is not None:
            res["SANDY VILLAS"] = villas_cache
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
        master_state = self.load_master_state()

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
    # CSV Detection & Parsing Utilities
    # -------------------------------------------------------------------------
    @staticmethod
    def _detect_encoding_and_delimiter(file_path: str) -> Tuple[str, str]:
        """Detects the file encoding and CSV delimiter (; vs , vs \\t)."""
        encodings = ["utf-8-sig", "utf-8", "cp1253", "iso-8859-7", "latin1"]
        raw_sample = b""
        with open(file_path, "rb") as f:
            raw_sample = f.read(8192)

        detected_enc = "utf-8-sig"
        decoded_text = ""
        for enc in encodings:
            try:
                decoded_text = raw_sample.decode(enc)
                detected_enc = enc
                break
            except (UnicodeDecodeError, LookupError):
                continue

        delimiter = ";"
        first_lines = decoded_text.splitlines()[:5]
        sample_text = "\n".join(first_lines)
        semicolons = sample_text.count(";")
        commas = sample_text.count(",")
        tabs = sample_text.count("\t")

        if semicolons >= commas and semicolons >= tabs and semicolons > 0:
            delimiter = ";"
        elif commas > semicolons and commas >= tabs:
            delimiter = ","
        elif tabs > semicolons and tabs > commas:
            delimiter = "\t"

        return detected_enc, delimiter

    def _process_in_house_rows(self, raw_rows: Any) -> Dict[str, Dict[str, Any]]:
        """Core parsing engine for in-house rows (CSV or Excel)."""
        bookings: Dict[str, Dict[str, Any]] = {}
        header = None

        for raw_row in raw_rows:
            if not raw_row:
                continue

            cleaned_row = [str(cell).strip().strip('"\'') for cell in raw_row]

            if header is None:
                is_header = any(
                    any(alias.lower() == cell.lower() for alias in self.BOOKING_ID_KEYS)
                    for cell in cleaned_row
                )
                if is_header:
                    header = cleaned_row
                    continue

                # Fallback for headerless In-House exports (Room in col 0, Date in col 2, Booking ID in col 7 or 9)
                if len(cleaned_row) >= 8 and re.match(r"^\d{3,4}$", cleaned_row[0]) and re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", cleaned_row[2]):
                    if len(cleaned_row) > 7 and cleaned_row[7].isdigit():
                        header = ["Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση", "Τύπος Δωμ", "Κρατηθείς Τύπος", "Χρεώστης", "Αρ.", "Τύπος Γεύματος", "Αγορά", "Αρ. Ενηλ"]
                    elif len(cleaned_row) > 9 and cleaned_row[9].isdigit():
                        header = ["Δωμάτιο", "Πελάτης", "Άφιξη", "Αναχώρηση", "Τύπος Δωμ", "Κρατηθείς Τύπος", "Χρεώστης", "col7", "col8", "Αρ.", "Τύπος Γεύματος", "Αγορά", "Αρ. Ενηλ"]
                    if header:
                        while len(header) < len(cleaned_row):
                            header.append(f"col_{len(header)}")
                else:
                    continue

            if not any(cleaned_row):
                continue

            row_dict = {}
            for idx, col_name in enumerate(header):
                if idx < len(cleaned_row):
                    row_dict[col_name] = cleaned_row[idx]
                else:
                    row_dict[col_name] = ""

            # Identify Booking ID
            booking_id = None
            for key_alias in self.BOOKING_ID_KEYS:
                for col in header:
                    if col.strip().lower() == key_alias.lower():
                        val = row_dict.get(col, "").strip()
                        if val:
                            booking_id = val
                            break
                if booking_id:
                    break

            if not booking_id:
                continue

            # Identify Guest Name
            guest_name = ""
            for key_alias in self.GUEST_NAME_KEYS:
                for col in header:
                    if col.strip().lower() == key_alias.lower():
                        guest_name = row_dict.get(col, "").strip()
                        break
                if guest_name:
                    break

            # Prepare fields for JSON, omitting "Τύπος Γεύματος" and guest col
            if booking_id not in bookings:
                booking_entry: Dict[str, Any] = {}
                for col, val in row_dict.items():
                    col_clean = col.strip()
                    if col_clean.lower() in self.EXCLUDED_COLUMNS:
                        continue
                    if any(col_clean.lower() == alias.lower() for alias in self.GUEST_NAME_KEYS):
                        continue
                    if any(col_clean.lower() == alias.lower() for alias in self.BOOKING_ID_KEYS):
                        continue
                    booking_entry[col_clean] = val

                booking_entry["Πελάτες"] = []
                bookings[booking_id] = booking_entry

            if guest_name and guest_name not in bookings[booking_id]["Πελάτες"]:
                bookings[booking_id]["Πελάτες"].append(guest_name)

        return bookings

    def parse_in_house_csv(self, file_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Parses an in-house list CSV file.
        - Groups multiple rows by Booking ID ('Αρ.')
        - Excludes 'Τύπος Γεύματος' (Meal Plan)
        - Aggregates guest names ('Πελάτης') into 'Πελάτες' list
        - Strips whitespace from keys and values
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        encoding, delimiter = self._detect_encoding_and_delimiter(file_path)
        with open(file_path, mode="r", encoding=encoding, errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)
            return self._process_in_house_rows(reader)

    def parse_in_house_excel(self, file_path: str) -> Dict[str, Dict[str, Any]]:
        """Parses an in-house list Excel file (.xlsx or .xls)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        rows: List[List[str]] = []

        if ext == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                if row is None:
                    continue
                rows.append([str(c).strip() if c is not None else "" for c in row])
            wb.close()
        elif ext == ".xls":
            import xlrd
            wb = xlrd.open_workbook(file_path)
            ws = wb.sheet_by_index(0)
            for r in range(ws.nrows):
                row_vals = []
                for c in range(ws.ncols):
                    cell = ws.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        try:
                            dt = xlrd.xldate_as_datetime(cell.value, wb.datemode)
                            row_vals.append(dt.strftime("%d/%m/%Y"))
                            continue
                        except Exception:
                            pass
                    val = cell.value
                    if isinstance(val, float) and val.is_integer():
                        row_vals.append(str(int(val)))
                    else:
                        row_vals.append(str(val).strip() if val is not None else "")
                rows.append(row_vals)
        else:
            raise ValueError(f"Unsupported Excel format: {ext}")

        return self._process_in_house_rows(rows)

    def parse_in_house_file(self, file_path: str) -> Dict[str, Dict[str, Any]]:
        """Unified parser accepting .csv, .xlsx, and .xls in-house files."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".xlsx", ".xls"]:
            return self.parse_in_house_excel(file_path)
        return self.parse_in_house_csv(file_path)

    # Alias for backward compatibility
    parse_isws_csv = parse_in_house_csv
    parse_isws_csv = parse_in_house_csv

    def detect_property_from_file(self, file_path: str) -> str:
        """Auto-detects property. Standardized to SANDY BEACH."""
        return "SANDY BEACH"

    def parse_arrivals_csv(self, file_path: str, property_name: Optional[str] = None) -> Tuple[str, Dict[str, Dict[str, Any]]]:
        """
        Parses hotel Arrivals CSV export.
        Returns: (detected_property_name, arrivals_dict_keyed_by_booking_id)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        encoding, delimiter = self._detect_encoding_and_delimiter(file_path)
        arrivals: Dict[str, Dict[str, Any]] = {}
        detected_prop = property_name.upper().replace("_", " ") if property_name else ("SANDY VILLAS" if "VILLAS" in os.path.basename(file_path).upper() else "SANDY BEACH")

        with open(file_path, mode="r", encoding=encoding, errors="replace") as f:
            rows = list(csv.reader(f, delimiter=delimiter))

        row_count = len(rows)
        r = 0
        while r < row_count:
            row = rows[r]
            if not row or not any(row):
                r += 1
                continue

            cleaned_row = [cell.strip().strip('"\'') for cell in row]
            col_0 = cleaned_row[0] if len(cleaned_row) > 0 else ""

            # Check if row is a main arrival entry
            guest_name = cleaned_row[2] if len(cleaned_row) > 2 else ""
            booking_id = cleaned_row[5] if len(cleaned_row) > 5 else ""

            if not booking_id and len(cleaned_row) > 6:
                for c_val in cleaned_row[1:]:
                    if c_val.isdigit() and len(c_val) >= 4:
                        booking_id = c_val
                        break

            if guest_name and booking_id:
                room_no = col_0 if col_0.isdigit() else ""
                agency = cleaned_row[8] if len(cleaned_row) > 8 else ""
                arr_dt = cleaned_row[4] if len(cleaned_row) > 4 else ""
                adults = cleaned_row[9] if len(cleaned_row) > 9 else "1"
                children = cleaned_row[10] if len(cleaned_row) > 10 else "0"

                # Check following row for notes or room info (e.g. "was in room 1411")
                notes = ""
                if r + 1 < row_count:
                    next_row = [cell.strip().strip('"\'') for cell in rows[r + 1]]
                    if next_row and len(next_row) > 0 and not (len(next_row) > 5 and next_row[5].isdigit()):
                        notes = next_row[0]
                        if not room_no and "room" in notes.lower():
                            m = re.search(r"room\s*(\d{3,4})", notes, re.IGNORECASE)
                            if m:
                                room_no = m.group(1)
                        r += 1

                arrivals[booking_id] = {
                    "booking_id": booking_id,
                    "room": room_no,
                    "property": detected_prop,
                    "guests": [guest_name],
                    "agency": agency,
                    "arrival": arr_dt,
                    "departure": "",
                    "adults": adults,
                    "children": children,
                    "notes": notes
                }
            r += 1

        return detected_prop, arrivals

    def update_arrivals_state(self, property_name: str, arrivals_dict: Dict[str, Dict[str, Any]]):
        """Updates today_arrivals.json for Sandy Beach and caches Sandy Villas if needed."""
        norm_prop = property_name.upper().replace("_", " ")
        if "VILLAS" in norm_prop:
            self._villas_arrivals_cache = arrivals_dict
        else:
            self.save_arrivals_state({"SANDY BEACH": arrivals_dict})

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
        check_outs = []
        check_ins = []
        unchanged_count = 0

        # 1. Compare new bookings with current state
        for booking_id, new_data in new_bookings.items():
            new_room = str(new_data.get("Δωμάτιο", "")).strip()

            if booking_id in current_state:
                old_data = current_state[booking_id]
                old_room = str(old_data.get("Δωμάτιο", "")).strip()

                if old_room and new_room and old_room != new_room:
                    move_info = {
                        "booking_id": booking_id,
                        "guests": new_data.get("Πελάτες", []),
                        "old_room": old_room,
                        "new_room": new_room,
                        "arrival": new_data.get("Άφιξη", ""),
                        "departure": new_data.get("Αναχώρηση", ""),
                        "date": date_str,
                        "timestamp": datetime.now().isoformat()
                    }
                    candidate_moves.append(move_info)
                else:
                    unchanged_count += 1
            else:
                check_in_info = {
                    "booking_id": booking_id,
                    "guests": new_data.get("Πελάτες", []),
                    "room": new_room,
                    "arrival": new_data.get("Άφιξη", ""),
                    "departure": new_data.get("Αναχώρηση", ""),
                    "date": date_str
                }
                check_ins.append(check_in_info)

        # 2. Room Merge Detection & Exclusion Filter
        # A room merge occurs if:
        # a) Multiple candidate moves share the same new_room originating from different old_rooms.
        # b) Or multiple bookings are consolidated into one room today where bookings came from different rooms yesterday.
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
            rm = str(b_data.get("Δωμάτιο", "")).strip()
            if rm:
                new_room_to_all_bookings.setdefault(rm, []).append(b_id)

        for nr, b_ids in new_room_to_all_bookings.items():
            if len(b_ids) > 1:
                yesterday_rooms = set()
                moved_in = False
                for b_id in b_ids:
                    if b_id in current_state:
                        prev_rm = str(current_state[b_id].get("Δωμάτιο", "")).strip()
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
                check_out_info = {
                    "booking_id": booking_id,
                    "property": DEFAULT_PROPERTY,
                    "guests": old_data.get("Πελάτες", []),
                    "room": old_data.get("Δωμάτιο", ""),
                    "departure": old_data.get("Αναχώρηση", ""),
                    "checkout_date": date_str,
                    "archived_at": datetime.now().isoformat()
                }
                check_outs.append(check_out_info)

        # 4. Commit new state to master_state.json and update metadata
        self.save_master_state(new_bookings)
        self.set_last_sync_date(processing_date)

        # 4.1 Automated Room Block Exporter synchronization
        try:
            self.export_room_block_json_data()
        except Exception as exp_err:
            print(f"[InHouseDataManager] Warning during auto room block export: {exp_err}")

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

        # Deduplicate existing by (booking_id, checkout_date)
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
            print(f"[InHouseDataManager] Error archiving checkouts: {e}")

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
            print(f"[InHouseDataManager] Error writing room moves log: {e}")

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
            print(f"[InHouseDataManager] Error writing room moves history JSON: {e}")

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

    # -------------------------------------------------------------------------
    # Database Purge & Room Block JSON Exporter
    # -------------------------------------------------------------------------
    def purge_hotel_database(self) -> Dict[str, Any]:
        """
        Purges transient room and guest records from DATABASE/HOTEL STATE/,
        checkouts, room moves, booking calls, and all auxiliary system JSON files,
        stripping dynamic runtime fields from HotelDataSet.json and resetting
        room block JSON exports.
        """
        purged_count = 0

        # 1. Reset master_state.json
        save_and_archive_json({}, self.master_state_path)
        purged_count += 1

        # 2. Reset state_metadata.json
        reset_meta = {
            "last_sync_date": None,
            "last_updated_at": None,
            "total_bookings": 0,
            "last_processed_date": None
        }
        self.save_metadata(reset_meta)
        purged_count += 1

        # 3. Reset checkouts history
        try:
            save_and_archive_json({"records": []}, self.checkouts_path)
            purged_count += 1
        except Exception:
            pass

        # 4. Reset room moves history
        try:
            save_and_archive_json([], self.room_moves_path)
            purged_count += 1
        except Exception:
            pass

        # 5. Reset today's booking calls and arrivals
        try:
            if os.path.exists(BOOKING_CALLS_TODAY_JSON):
                save_and_archive_json([], BOOKING_CALLS_TODAY_JSON)
                purged_count += 1
        except Exception:
            pass

        try:
            if os.path.exists(self.arrivals_state_path):
                save_and_archive_json({}, self.arrivals_state_path)
                purged_count += 1
        except Exception:
            pass

        # 6. Target auxiliary JSON files across workspace
        aux_target_files = [
            "guest_manifest.json",
            "cake_memos.json",
            "offer_list.json",
            "reservations.json",
            "allocations.json",
            "stats_cache.json",
            "memos.json",
            "offers.json"
        ]
        search_dirs = [BASE_DIR, DATABASE_DIR, OUTPUT_DIR]
        for s_dir in search_dirs:
            if not os.path.exists(s_dir):
                continue
            for fname in aux_target_files:
                fpath = os.path.join(s_dir, fname)
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "w", encoding="utf-8") as f:
                            json.dump([], f, indent=2)
                        purged_count += 1
                    except Exception:
                        pass

        # 7. Flush dynamic runtime fields in HotelDataSet.json (occupancies and assignments)
        hotel_ds_path = Path(HOTEL_DATASET_PATH)
        if hotel_ds_path.exists():
            try:
                with open(hotel_ds_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                if isinstance(records, list):
                    for node in records:
                        if isinstance(node, dict):
                            node.pop("current_occupancy", None)
                            node.pop("assigned_guests", None)
                            node.pop("live_status", None)
                    with open(hotel_ds_path, "w", encoding="utf-8") as f:
                        json.dump(records, f, indent=2, ensure_ascii=False)
                    purged_count += 1
            except Exception as err:
                print(f"[purge_hotel_database] Warning resetting HotelDataSet.json: {err}")

        # 8. Synchronize / reset PLOT block files
        try:
            self.export_room_block_json_data()
        except Exception as e:
            print(f"[InHouseDataManager] Warning resetting block files on purge: {e}")

        return {"success": True, "purged_count": purged_count}

    def export_room_block_json_data(
        self,
        plot_dir: Optional[Union[str, Path]] = None,
        hotel_dataset_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Iterates over every room block defined in HotelDataSet.json (Block 1100 through Block 8000, plus Blocks 100-800).
        For each block:
          - Creates a subfolder named after the block (e.g., BLOCK_1100, BLOCK_7000).
          - Calculates live occupancy metrics against active In-House List (master_state.json):
              Occupancy Percentage = (Occupied Rooms in Block / Total Rooms in Block) * 100
          - Constructs payload with all original metadata fields + occupancy_metrics:
              total_rooms, occupied_rooms, vacant_rooms, occupancy_percentage, last_updated
          - Saves as <BLOCK_NAME>.json inside the subfolder with UTF-8 and indent=4.
        """
        plot_dir_p = Path(plot_dir or PLOT_DIR)
        dataset_path = Path(hotel_dataset_path or HOTEL_DATASET_PATH)

        if not dataset_path.exists():
            raise FileNotFoundError(f"Hotel dataset not found: {dataset_path}")

        with open(dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)

        master = self.load_master_state()
        occupied_rooms = set()
        for b_data in master.values():
            rm = str(b_data.get("Δωμάτιο") or b_data.get("room") or b_data.get("Room") or b_data.get("room_number") or "").strip()
            if rm:
                occupied_rooms.add(rm)

        def expand_range(rng_str: str) -> List[str]:
            m = re.match(r"^(\d+)-(\d+)$", rng_str.strip())
            if m:
                start, end = int(m.group(1)), int(m.group(2))
                return [str(r) for r in range(start, end + 1)]
            return [rng_str.strip()]

        exported_blocks = []
        os.makedirs(plot_dir_p, exist_ok=True)
        now_iso = datetime.now().isoformat()

        for item in dataset:
            cat = str(item.get("category", ""))
            name = str(item.get("name", ""))

            # Check if this entity is a room block
            if "Rooms" not in cat and not name.upper().startswith("BLOCK"):
                continue

            rooms = set()
            rd = item.get("room_details", {})
            floors = rd.get("floors", {})
            for floor_name, r_list in floors.items():
                for r_entry in r_list:
                    for r in expand_range(r_entry):
                        rooms.add(r)

            # Fallback to description for blocks without floors (e.g. Blocks 100-800)
            desc = str(item.get("description", ""))
            m_desc = re.search(r"ROOMS?\s+(\d+)-(\d+)", desc, re.IGNORECASE)
            if m_desc and not rooms:
                start, end = int(m_desc.group(1)), int(m_desc.group(2))
                for r in range(start, end + 1):
                    rooms.add(str(r))

            total_rooms = rd.get("total_rooms") or len(rooms)
            if total_rooms <= 0:
                total_rooms = len(rooms) if len(rooms) > 0 else 1

            occupied_count = len(rooms.intersection(occupied_rooms))
            vacant_count = max(0, total_rooms - occupied_count)
            occ_pct = round((occupied_count / total_rooms) * 100, 2) if total_rooms > 0 else 0.0

            # Create deepcopy payload
            payload = json.loads(json.dumps(item))
            payload["occupancy_metrics"] = {
                "total_rooms": int(total_rooms),
                "occupied_rooms": int(occupied_count),
                "vacant_rooms": int(vacant_count),
                "occupancy_percentage": occ_pct,
                "last_updated": now_iso
            }

            # Subfolder name (e.g. BLOCK_1100)
            block_slug = re.sub(r"[^\w\d]+", "_", name.strip()).strip("_")
            block_folder = plot_dir_p / block_slug
            os.makedirs(block_folder, exist_ok=True)

            json_path = block_folder / f"{block_slug}.json"
            with open(json_path, "w", encoding="utf-8") as out_f:
                json.dump(payload, out_f, indent=4, ensure_ascii=False)

            exported_blocks.append({
                "block": name,
                "slug": block_slug,
                "path": str(json_path),
                "metrics": payload["occupancy_metrics"]
            })

        return {
            "total_exported": len(exported_blocks),
            "blocks": exported_blocks,
            "timestamp": now_iso
        }


def purge_hotel_database() -> Dict[str, Any]:
    """Convenience top-level wrapper to purge transient hotel database records."""
    return InHouseDataManager().purge_hotel_database()


def export_room_block_json_data(
    plot_dir: Optional[Union[str, Path]] = None,
    hotel_dataset_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """Convenience top-level wrapper to export room block JSON payloads to PLOT/."""
    return InHouseDataManager().export_room_block_json_data(plot_dir, hotel_dataset_path)


# =============================================================================
# In-House Report Timestamp & Security Validation Helpers
# =============================================================================

def extract_inhouse_report_date(file_path: Union[str, Path]) -> Tuple[Optional[date], Optional[str]]:
    """
    Parses the internal header, metadata, or report timestamp cell of an In-House List file (.csv, .xlsx, .xls).
    Returns (operational_date, timestamp_str).
    """
    p = Path(file_path)
    if not p.exists():
        return None, None

    found_date: Optional[date] = None
    found_time_str: Optional[str] = None
    ext = p.suffix.lower()

    if ext == ".csv":
        enc, _ = InHouseDataManager._detect_encoding_and_delimiter(str(p))
        try:
            with open(p, "r", encoding=enc, errors="replace") as f:
                lines = [l.strip() for l in f if l.strip()]
        except Exception:
            lines = []

        candidates = lines[:50] + lines[-50:]
        for line in reversed(candidates):
            m_dt = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", line)
            if m_dt:
                is_meta = any(k in line.lower() for k in ["page", "σελίδα", "totals", "hotel", "print", "εκτύπωση", "report", "λίστα"])
                if is_meta or len(line.split(";")) <= 5 or len(line.split(",")) <= 5:
                    try:
                        d_val = int(m_dt.group(1))
                        m_val = int(m_dt.group(2))
                        y_val = int(m_dt.group(3))
                        found_date = date(y_val, m_val, d_val)
                        m_tm = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]\.?m\.?|μμ|πμ)?)", line, re.IGNORECASE)
                        if m_tm:
                            found_time_str = m_tm.group(1)
                        break
                    except Exception:
                        pass

    elif ext == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
            ws = wb.active
            rows_sample = []
            idx = 0
            for row in ws.iter_rows(values_only=True):
                if row:
                    rows_sample.append(row)
                idx += 1
                if idx > 100:
                    break
            wb.close()

            for row in rows_sample:
                for c in row:
                    if isinstance(c, datetime):
                        found_date = c.date()
                        found_time_str = c.strftime("%H:%M:%S")
                        break
                    elif isinstance(c, date):
                        found_date = c
                        break
                    elif isinstance(c, str):
                        m_dt = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", c)
                        if m_dt:
                            try:
                                found_date = date(int(m_dt.group(3)), int(m_dt.group(2)), int(m_dt.group(1)))
                                break
                            except Exception:
                                pass
                if found_date:
                    break
        except Exception as err:
            print(f"[extract_inhouse_report_date] Error reading xlsx: {err}")

    elif ext == ".xls":
        try:
            import xlrd
            wb = xlrd.open_workbook(str(p))
            ws = wb.sheet_by_index(0)
            for r in range(min(ws.nrows, 100)):
                for c in range(ws.ncols):
                    cell = ws.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        try:
                            dt = xlrd.xldate_as_datetime(cell.value, wb.datemode)
                            found_date = dt.date()
                            found_time_str = dt.strftime("%H:%M:%S")
                            break
                        except Exception:
                            pass
                    elif isinstance(cell.value, str):
                        m_dt = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", cell.value)
                        if m_dt:
                            try:
                                found_date = date(int(m_dt.group(3)), int(m_dt.group(2)), int(m_dt.group(1)))
                                break
                            except Exception:
                                pass
                if found_date:
                    break
        except Exception as err:
            print(f"[extract_inhouse_report_date] Error reading xls: {err}")

    # Fallback to filename
    if not found_date:
        fname = p.name
        m_fn = re.search(r"(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})", fname)
        if m_fn:
            try:
                found_date = date(int(m_fn.group(1)), int(m_fn.group(2)), int(m_fn.group(3)))
            except Exception:
                pass
        if not found_date:
            m_fn2 = re.search(r"(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})", fname)
            if m_fn2:
                try:
                    found_date = date(int(m_fn2.group(3)), int(m_fn2.group(2)), int(m_fn2.group(1)))
                except Exception:
                    pass

    ts_display = None
    if found_date:
        if found_time_str:
            ts_display = f"{found_date.strftime('%Y-%m-%d')} {found_time_str}"
        else:
            ts_display = found_date.strftime("%Y-%m-%d")

    return found_date, ts_display


def validate_inhouse_file_date(file_path: Union[str, Path], target_date: Optional[date] = None) -> Tuple[bool, Optional[date], str]:
    """
    Validates that the selected in-house list's operational date matches today's operational date.
    Returns (is_valid, extracted_date, message).
    """
    target = target_date or date.today()
    extracted_dt, ts_str = extract_inhouse_report_date(file_path)

    if not extracted_dt:
        return False, None, "Validation Error: Selected file lacks internal report timestamp or operational date metadata."

    if extracted_dt != target:
        msg = f"Validation Error: Selected report date [{extracted_dt.strftime('%Y-%m-%d')}] does not match current operational date [{target.strftime('%Y-%m-%d')}]."
        return False, extracted_dt, msg

    return True, extracted_dt, f"Validation successful: Report date [{extracted_dt.strftime('%Y-%m-%d')}] matches current operational date."


# =============================================================================
# PyQt6 Gatekeeper Modal Dialog (Strict In-House Sequential Synchronization)
# =============================================================================

class GatekeeperDialog(QDialog):
    """
    Blocking startup dialog that enforces sequential ingestion of all
    missing daily In-House CSV files for Sandy Beach up to today.
    Contains strictly In-House Synchronization (No arrivals tracker tab).
    """

    ingestion_completed = pyqtSignal()

    def __init__(self, data_manager: Optional[InHouseDataManager] = None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager or InHouseDataManager()
        self.missing_dates: List[date] = self.data_manager.get_missing_dates()
        self.current_step_idx: int = 0
        self.selected_inhouse_path: Optional[str] = None

        self.setWindowTitle("Gatekeeper : In-House Synchronization")
        self.setMinimumSize(780, 560)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        self._setup_styles()
        self._init_ui()
        self._update_step_ui()

    def _setup_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FA;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#header_card {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #800020, stop:1 #B03060);
                border-radius: 8px;
                padding: 18px;
            }
            QLabel#header_title {
                color: #FFFFFF;
                font-size: 19px;
                font-weight: bold;
            }
            QLabel#header_subtitle {
                color: #FFE4E1;
                font-size: 13px;
            }
            QFrame#step_card {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 18px;
            }
            QLabel#target_date_badge {
                background-color: #FFF0F5;
                color: #800020;
                border: 1px solid #B03060;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton.action-btn {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton.action-btn:hover {
                background-color: #357ABD;
            }
            QPushButton#btn_process_inhouse {
                background-color: #2ECC71;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 22px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btn_process_inhouse:hover {
                background-color: #27AE60;
            }
            QPushButton#btn_process_inhouse:disabled {
                background-color: #BDC3C7;
            }
            QPushButton#btn_quit {
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 18px;
                font-weight: bold;
            }
            QPushButton#btn_quit:hover {
                background-color: #C0392B;
            }
            QPushButton#btn_continue {
                background-color: #27AE60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 11px 26px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#btn_continue:hover {
                background-color: #219653;
            }
            QPushButton#btn_continue:disabled {
                background-color: #E0E0E0;
                color: #A0A0A0;
            }
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                gridline-color: #F0F0F0;
            }
            QHeaderView::section {
                background-color: #F4F6F7;
                font-weight: bold;
                color: #2C3E50;
                border: none;
                padding: 6px;
            }
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # 1. Header Banner
        header_card = QFrame()
        header_card.setObjectName("header_card")
        h_layout = QVBoxLayout(header_card)
        lbl_title = QLabel("GATEKEEPER : Sequential In-House Synchronization")
        lbl_title.setObjectName("header_title")
        lbl_sub = QLabel(
            "State integrity validation is mandatory before accessing the workspace.\n"
            "All daily In-House lists through today must be ingested sequentially for Sandy Beach."
        )
        lbl_sub.setObjectName("header_subtitle")
        h_layout.addWidget(lbl_title)
        h_layout.addWidget(lbl_sub)
        main_layout.addWidget(header_card)

        # 2. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        # 3. In-House Synchronization Card
        self.step_card = QFrame()
        self.step_card.setObjectName("step_card")
        s_layout = QVBoxLayout(self.step_card)
        s_layout.setSpacing(12)

        self.lbl_step_info = QLabel()
        self.lbl_step_info.setStyleSheet("font-size: 14px; font-weight: bold; color: #2C3E50;")
        s_layout.addWidget(self.lbl_step_info)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Target Date to Ingest (Sandy Beach):"))
        self.lbl_target_date = QLabel()
        self.lbl_target_date.setObjectName("target_date_badge")
        date_row.addWidget(self.lbl_target_date)
        date_row.addStretch()
        s_layout.addLayout(date_row)

        file_row = QHBoxLayout()
        self.lbl_inhouse_file = QLabel("No file selected")
        self.lbl_inhouse_file.setStyleSheet("color: #7F8C8D; font-style: italic;")
        self.btn_browse_inhouse = QPushButton("📁 Browse In-House CSV...")
        self.btn_browse_inhouse.setProperty("class", "action-btn")
        self.btn_browse_inhouse.clicked.connect(self._browse_inhouse_csv)

        file_row.addWidget(self.lbl_inhouse_file, stretch=1)
        file_row.addWidget(self.btn_browse_inhouse)
        s_layout.addLayout(file_row)

        btn_action_row = QHBoxLayout()
        self.btn_process_inhouse = QPushButton("⚡ Ingest In-House List")
        self.btn_process_inhouse.setObjectName("btn_process_inhouse")
        self.btn_process_inhouse.setEnabled(False)
        self.btn_process_inhouse.clicked.connect(self._process_inhouse_file)
        btn_action_row.addStretch()
        btn_action_row.addWidget(self.btn_process_inhouse)
        s_layout.addLayout(btn_action_row)

        main_layout.addWidget(self.step_card)

        # 4. Ingestion Results Table
        self.table_results = QTableWidget(0, 6)
        self.table_results.setHorizontalHeaderLabels([
            "Ingested Date", "Total In-House", "Room Moves", "Room Merges", "Check-Ins", "Check-Outs"
        ])
        self.table_results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        main_layout.addWidget(self.table_results, stretch=1)

        # 5. Bottom Controls
        bottom_row = QHBoxLayout()
        self.btn_quit = QPushButton("❌ Quit Application")
        self.btn_quit.setObjectName("btn_quit")
        self.btn_quit.clicked.connect(self._abort_and_quit)

        self.btn_continue = QPushButton("🚀 Access Guest Relations Workspace")
        self.btn_continue.setObjectName("btn_continue")
        self.btn_continue.setEnabled(False)
        self.btn_continue.clicked.connect(self.accept)

        bottom_row.addWidget(self.btn_quit)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_continue)
        main_layout.addLayout(bottom_row)

    def _update_step_ui(self):
        total_missing = len(self.missing_dates)
        if total_missing == 0 or self.current_step_idx >= total_missing:
            self.progress_bar.setValue(100)
            self.lbl_step_info.setText("✅ In-House state is fully up to date through today!")
            self.lbl_target_date.setText("All In-House Dates Synchronized")
            self.lbl_target_date.setStyleSheet("background-color: #D4EDDA; color: #155724; border: 1px solid #28A745; padding: 6px 14px;")
            self.btn_browse_inhouse.setEnabled(False)
            self.btn_process_inhouse.setEnabled(False)
            self.btn_continue.setEnabled(True)
            self.btn_continue.setStyleSheet("""
                background-color: #27AE60;
                color: white;
                font-weight: bold;
                padding: 11px 26px;
                border-radius: 4px;
                font-size: 14px;
            """)
            return

        progress_pct = int((self.current_step_idx / total_missing) * 100)
        self.progress_bar.setValue(progress_pct)

        target_date = self.missing_dates[self.current_step_idx]
        self.lbl_step_info.setText(f"Step {self.current_step_idx + 1} of {total_missing}: Mandatory In-House Ingestion")
        self.lbl_target_date.setText(target_date.strftime("%d/%m/%Y (%A)"))

        self.selected_inhouse_path = None
        self.lbl_inhouse_file.setText("No file selected — Click Browse to choose CSV")
        self.lbl_inhouse_file.setStyleSheet("color: #7F8C8D; font-style: italic;")
        self.btn_process_inhouse.setEnabled(False)
        has_state = bool(self.data_manager.load_master_state())
        if self.current_step_idx > 0 or has_state:
            self.btn_continue.setEnabled(True)
            self.btn_continue.setText("🚀 Access Guest Relations Workspace")
            self.btn_continue.setStyleSheet("""
                background-color: #27AE60;
                color: white;
                font-weight: bold;
                padding: 11px 26px;
                border-radius: 4px;
                font-size: 14px;
            """)
        else:
            self.btn_continue.setEnabled(False)
            self.btn_continue.setText("🚀 Access Guest Relations Workspace")
            self.btn_continue.setStyleSheet("")

    def _browse_inhouse_csv(self):
        target_date = self.missing_dates[self.current_step_idx]
        initial_dir = BASE_DIR
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select In-House List CSV for {target_date.strftime('%d/%m/%Y')}",
            initial_dir,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if file_path:
            self.selected_inhouse_path = file_path
            self.lbl_inhouse_file.setText(f"Selected: {os.path.basename(file_path)}")
            self.lbl_inhouse_file.setStyleSheet("color: #2C3E50; font-weight: bold;")
            self.btn_process_inhouse.setEnabled(True)

    def _process_inhouse_file(self):
        if not self.selected_inhouse_path or not os.path.exists(self.selected_inhouse_path):
            QMessageBox.warning(self, "Error", "Selected file does not exist.")
            return

        target_date = self.missing_dates[self.current_step_idx]
        try:
            parsed = self.data_manager.parse_in_house_csv(self.selected_inhouse_path)
            if not parsed:
                QMessageBox.warning(self, "Validation Error", "No valid bookings detected in the selected CSV file.")
                return

            summary = self.data_manager.compare_and_update(parsed, processing_date=target_date)
            self.data_manager.cleanup_file(self.selected_inhouse_path, mode="trash")

            # Update results table
            row = self.table_results.rowCount()
            self.table_results.insertRow(row)
            self.table_results.setItem(row, 0, QTableWidgetItem(target_date.strftime("%d/%m/%Y")))
            self.table_results.setItem(row, 1, QTableWidgetItem(str(summary["total_in_house"])))
            self.table_results.setItem(row, 2, QTableWidgetItem(str(len(summary["room_moves"]))))
            self.table_results.setItem(row, 3, QTableWidgetItem(str(len(summary.get("room_merges", [])))))
            self.table_results.setItem(row, 4, QTableWidgetItem(str(len(summary["check_ins"]))))
            self.table_results.setItem(row, 5, QTableWidgetItem(str(len(summary["check_outs"]))))

            self.current_step_idx += 1
            self._update_step_ui()

        except Exception as e:
            QMessageBox.critical(self, "Processing Error", f"Failed to ingest CSV:\n{str(e)}")

    def _abort_and_quit(self):
        reply = QMessageBox.question(
            self,
            "Quit Application?",
            "Closing the Gatekeeper without synchronizing missing In-House dates will terminate the application. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reject()


def run_gatekeeper_if_needed(parent=None) -> bool:
    """Checks if there are any missing dates and triggers Gatekeeper if needed."""
    dm = InHouseDataManager()
    missing = dm.get_missing_dates()

    if not missing:
        return True

    dialog = GatekeeperDialog(data_manager=dm, parent=parent)
    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted


if __name__ == "__main__":
    test_app = QApplication.instance() or QApplication(sys.argv)
    dm = InHouseDataManager()
    print(f"Master State Path: {dm.master_state_path}")
    print(f"Missing dates count: {len(dm.get_missing_dates())}")
    dlg = GatekeeperDialog(data_manager=dm)
    dlg.show()
    sys.exit(test_app.exec())
