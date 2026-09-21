"""
Paths and Directory Configuration Module
=======================================
Defines canonical paths, target directories, standardized JSON artifact locations,
and atomic filesystem helpers for the Guest Relation Workspace.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
ROOMS_DIR = os.path.join(BASE_DIR, "ROOMS")
DATA_BACKUP_DIR = os.path.join(BASE_DIR, "DATA_BACKUP")

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
_property_state = {"active_property": DEFAULT_PROPERTY}


def get_active_property() -> str:
    """Returns the current active property from the centralized state."""
    return _property_state["active_property"]


def set_active_property(property_name: str) -> None:
    """Updates the active property in the centralized single source of truth."""
    _property_state["active_property"] = property_name


def __getattr__(name: str):
    if name == "active_property":
        return get_active_property()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value):
    if name == "active_property":
        set_active_property(value)
    else:
        globals()[name] = value


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
        DATA_BACKUP_DIR,
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
