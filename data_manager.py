"""
Data Manager Module: Ingestion, State Management, Room-Move Detection & Gatekeeper
===================================================================================
Handles daily 'In-House List' and 'Arrivals' CSV exports, maintains master_state.json
and state_metadata.json in the root directory, autonomously sorts and routes all JSON
files into designated property directories, detects room-moves / check-ins / check-outs,
cleans up processed CSV files, and enforces Gatekeeper startup validation.
"""

import os
import sys
import csv
import json
import shutil
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QProgressBar, QFrame, QScrollArea, QWidget,
    QApplication, QTextEdit, QTabWidget, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "DATABASE")
SANDY_BEACH_DIR = os.path.join(DATABASE_DIR, "SANDY BEACH")
SANDY_VILLAS_DIR = os.path.join(DATABASE_DIR, "SANDY VILLAS")
OUTPUT_DIR = os.path.join(BASE_DIR, "OUTPUT")
TRASH_DIR = os.path.join(BASE_DIR, "TRASH")
TODAYS_LIST_DIR = os.path.join(OUTPUT_DIR, "TODAYS_LIST")
BOOKING_CALLS_DIR = os.path.join(BASE_DIR, "BOOKING CALLS")
BOOKING_CALLS_TODAY_DIR = os.path.join(DATABASE_DIR, "booking calls for today")
BOOKING_CALLS_TODAY_JSON = os.path.join(BOOKING_CALLS_TODAY_DIR, "booking_calls_today.json")

# Explicit State Files inside DATABASE/ (not in root directory)
MASTER_STATE_PATH = os.path.join(DATABASE_DIR, "master_state.json")
STATE_META_PATH = os.path.join(DATABASE_DIR, "state_metadata.json")

# History & Audit Logs directly inside DATABASE/ (no separate subdirectories)
CHECKOUT_HISTORY_PATH = os.path.join(DATABASE_DIR, "check_out_history.json")
ROOM_MOVES_LOG_PATH = os.path.join(TODAYS_LIST_DIR, "room_moves.log")
ROOM_MOVES_HISTORY_PATH = os.path.join(DATABASE_DIR, "room_moves_history.json")

# Designated Property Arrivals State JSON Files
ARRIVALS_STATE_PATH = os.path.join(DATABASE_DIR, "arrivals_state.json")
ARRIVALS_BEACH_PATH = os.path.join(SANDY_BEACH_DIR, "arrivals_sandy_beach.json")
ARRIVALS_VILLAS_PATH = os.path.join(SANDY_VILLAS_DIR, "arrivals_sandy_villas.json")

# Active Python Whitelist for Autonomous Cleanup
ACTIVE_PYTHON_WHITELIST = {
    "app.py",
    "data_manager.py",
    "booking_calls.py",
    "offers_module.py",
    "test_data_manager.py",
    "test_booking_calls.py"
}


def ensure_workspace_directories():
    """
    Autonomously verifies, creates, and corrects all workspace folder structures.
    Enforces:
      - master_state.json and state_metadata.json strictly inside DATABASE/
      - check_out_history.json and room_moves_history.json directly inside DATABASE/
        (strictly dismantling any separate 'check out history' or 'room moves history' subdirectories)
      - today's booking calls JSON strictly inside database/booking calls for today/
      - automated routing of all other JSON files into designated directories
    """
    dirs_to_create = [
        DATABASE_DIR,
        SANDY_BEACH_DIR,
        SANDY_VILLAS_DIR,
        OUTPUT_DIR,
        TRASH_DIR,
        TODAYS_LIST_DIR,
        BOOKING_CALLS_DIR,
        BOOKING_CALLS_TODAY_DIR
    ]
    for d in dirs_to_create:
        os.makedirs(d, exist_ok=True)

    # 1. State files strictly inside DATABASE/ (migrate from root if present)
    root_master = os.path.join(BASE_DIR, "master_state.json")
    if os.path.exists(root_master):
        try:
            if not os.path.exists(MASTER_STATE_PATH):
                shutil.move(root_master, MASTER_STATE_PATH)
            else:
                if os.path.getsize(root_master) > os.path.getsize(MASTER_STATE_PATH):
                    shutil.move(root_master, MASTER_STATE_PATH)
                else:
                    os.remove(root_master)
        except Exception as e:
            print(f"[FileManager] Error migrating master_state.json: {e}")

    root_meta = os.path.join(BASE_DIR, "state_metadata.json")
    if os.path.exists(root_meta):
        try:
            if not os.path.exists(STATE_META_PATH):
                shutil.move(root_meta, STATE_META_PATH)
            else:
                os.remove(root_meta)
        except Exception as e:
            print(f"[FileManager] Error migrating state_metadata.json: {e}")

    # 2. check_out_history.json directly inside DATABASE/ (no subdirectories)
    # Check for legacy checkout_history.json without underscore
    legacy_checkout = os.path.join(DATABASE_DIR, "checkout_history.json")
    if os.path.exists(legacy_checkout):
        try:
            if not os.path.exists(CHECKOUT_HISTORY_PATH):
                shutil.move(legacy_checkout, CHECKOUT_HISTORY_PATH)
            else:
                try:
                    with open(CHECKOUT_HISTORY_PATH, "r", encoding="utf-8") as f:
                        cur_data = json.load(f)
                    with open(legacy_checkout, "r", encoding="utf-8") as f:
                        leg_data = json.load(f)
                    if isinstance(cur_data, list) and isinstance(leg_data, list):
                        cur_data.extend(leg_data)
                        with open(CHECKOUT_HISTORY_PATH, "w", encoding="utf-8") as f:
                            json.dump(cur_data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                os.remove(legacy_checkout)
        except Exception as e:
            print(f"[FileManager] Error consolidating checkout_history: {e}")

    # Dismantle any separate 'CHECKOUT HISTORY' subdirectory in DATABASE/
    checkout_subdirs = [
        os.path.join(DATABASE_DIR, "CHECKOUT HISTORY"),
        os.path.join(DATABASE_DIR, "checkout history"),
        os.path.join(DATABASE_DIR, "check out history")
    ]
    for sub in checkout_subdirs:
        if os.path.exists(sub) and os.path.isdir(sub):
            try:
                for fname in os.listdir(sub):
                    fpath = os.path.join(sub, fname)
                    if fname.endswith(".json") and os.path.isfile(fpath):
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                sub_data = json.load(f)
                            if os.path.exists(CHECKOUT_HISTORY_PATH):
                                with open(CHECKOUT_HISTORY_PATH, "r", encoding="utf-8") as f:
                                    cur_data = json.load(f)
                                if isinstance(cur_data, list) and isinstance(sub_data, list):
                                    cur_data.extend(sub_data)
                                    with open(CHECKOUT_HISTORY_PATH, "w", encoding="utf-8") as f:
                                        json.dump(cur_data, f, ensure_ascii=False, indent=2)
                            else:
                                shutil.move(fpath, CHECKOUT_HISTORY_PATH)
                        except Exception:
                            pass
                shutil.rmtree(sub, ignore_errors=True)
            except Exception as e:
                print(f"[FileManager] Error removing checkout subdirectory {sub}: {e}")

    # 3. room_moves_history.json directly inside DATABASE/ (no subdirectories)
    room_moves_subdirs = [
        os.path.join(DATABASE_DIR, "ROOM MOVES HISTORY"),
        os.path.join(DATABASE_DIR, "room moves history"),
        os.path.join(DATABASE_DIR, "room_moves_history")
    ]
    for sub in room_moves_subdirs:
        if os.path.exists(sub) and os.path.isdir(sub):
            try:
                for fname in os.listdir(sub):
                    fpath = os.path.join(sub, fname)
                    if fname.endswith(".json") and os.path.isfile(fpath):
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                sub_data = json.load(f)
                            if os.path.exists(ROOM_MOVES_HISTORY_PATH):
                                with open(ROOM_MOVES_HISTORY_PATH, "r", encoding="utf-8") as f:
                                    cur_data = json.load(f)
                                if isinstance(cur_data, list) and isinstance(sub_data, list):
                                    cur_data.extend(sub_data)
                                    with open(ROOM_MOVES_HISTORY_PATH, "w", encoding="utf-8") as f:
                                        json.dump(cur_data, f, ensure_ascii=False, indent=2)
                            else:
                                shutil.move(fpath, ROOM_MOVES_HISTORY_PATH)
                        except Exception:
                            pass
                shutil.rmtree(sub, ignore_errors=True)
            except Exception as e:
                print(f"[FileManager] Error removing room moves subdirectory {sub}: {e}")

    # 4. Route today's booking calls JSON to database/booking calls for today/
    legacy_today_locations = [
        os.path.join(BASE_DIR, "booking calls for today", "booking_calls_today.json"),
        os.path.join(BASE_DIR, "booking_calls_today.json"),
        os.path.join(BOOKING_CALLS_DIR, "booking_calls_today.json"),
        os.path.join(DATABASE_DIR, "booking_calls_today.json"),
        os.path.join(DATABASE_DIR, "BOOKING CALLS FOR TODAY", "booking_calls_today.json")
    ]
    for loc in legacy_today_locations:
        if os.path.exists(loc) and os.path.abspath(loc) != os.path.abspath(BOOKING_CALLS_TODAY_JSON):
            try:
                if not os.path.exists(BOOKING_CALLS_TODAY_JSON):
                    shutil.move(loc, BOOKING_CALLS_TODAY_JSON)
                else:
                    os.remove(loc)
            except Exception:
                pass

    # Clean up empty legacy folder in root if present
    root_legacy_fold = os.path.join(BASE_DIR, "booking calls for today")
    if os.path.exists(root_legacy_fold) and os.path.abspath(root_legacy_fold).lower() != os.path.abspath(BOOKING_CALLS_TODAY_DIR).lower():
        try:
            if os.path.isdir(root_legacy_fold) and not os.listdir(root_legacy_fold):
                os.rmdir(root_legacy_fold)
        except Exception:
            pass

    # Ensure BOOKING_CALLS_TODAY_DIR exists inside database directory
    os.makedirs(BOOKING_CALLS_TODAY_DIR, exist_ok=True)

    # 5. Route Sandy Beach arrivals JSON to DATABASE/SANDY BEACH/
    misplaced_beach = [
        os.path.join(BASE_DIR, "arrivals_sandy_beach.json"),
        os.path.join(DATABASE_DIR, "arrivals_sandy_beach.json")
    ]
    for p in misplaced_beach:
        if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(ARRIVALS_BEACH_PATH):
            try:
                if not os.path.exists(ARRIVALS_BEACH_PATH):
                    shutil.move(p, ARRIVALS_BEACH_PATH)
                else:
                    os.remove(p)
            except Exception:
                pass

    # 6. Route Sandy Villas arrivals JSON to DATABASE/SANDY VILLAS/
    misplaced_villas = [
        os.path.join(BASE_DIR, "arrivals_sandy_villas.json"),
        os.path.join(DATABASE_DIR, "arrivals_sandy_villas.json")
    ]
    for p in misplaced_villas:
        if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(ARRIVALS_VILLAS_PATH):
            try:
                if not os.path.exists(ARRIVALS_VILLAS_PATH):
                    shutil.move(p, ARRIVALS_VILLAS_PATH)
                else:
                    os.remove(p)
            except Exception:
                pass

    # 7. Route Booking.com calls state JSON to BOOKING CALLS/
    misplaced_bcom = [
        os.path.join(BASE_DIR, "booking_calls_state.json"),
        os.path.join(DATABASE_DIR, "booking_calls_state.json")
    ]
    booking_calls_state_target = os.path.join(BOOKING_CALLS_DIR, "booking_calls_state.json")
    for p in misplaced_bcom:
        if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(booking_calls_state_target):
            try:
                if not os.path.exists(booking_calls_state_target):
                    shutil.move(p, booking_calls_state_target)
                else:
                    os.remove(p)
            except Exception:
                pass


def cleanup_obsolete_python_files(workspace_dir: str = BASE_DIR) -> List[str]:
    """
    Autonomous cleanup routine:
    Scans the workspace and safely removes unused, obsolete, or temporary Python (.py)
    files that are not part of the active application manifest.
    """
    deleted_files = []
    ignore_dirs = {".git", ".venv", "venv", "env", "__pycache__"}

    for root, dirs, files in os.walk(workspace_dir):
        # Skip version control and virtual envs
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if f.endswith(".py"):
                if f not in ACTIVE_PYTHON_WHITELIST:
                    full_path = os.path.join(root, f)
                    try:
                        os.remove(full_path)
                        deleted_files.append(full_path)
                    except Exception as e:
                        print(f"[Cleanup] Could not remove {full_path}: {e}")
    return deleted_files


# Run autonomous directory verification and cleanup on module import
ensure_workspace_directories()
cleanup_obsolete_python_files()


class InHouseDataManager:
    """
    Core data engine for In-House and Arrivals list ingestion, state management,
    room-move detection, and file cleanup.
    """

    EXCLUDED_COLUMNS = {"τύπος γεύματος", "τυποσ γευματοσ", "meal plan", "mealplan"}
    BOOKING_ID_KEYS = ["Αρ.", "Αρ", "Booking ID", "BookingID", "Reservation No"]
    GUEST_NAME_KEYS = ["Πελάτης", "Πελατης", "Guest Name", "Guest", "Name"]
    ROOM_KEYS = ["Δωμάτιο", "Δωματιο", "Room", "Room No", "RoomNo"]

    def __init__(self, master_state_path: str = MASTER_STATE_PATH,
                 state_meta_path: str = STATE_META_PATH,
                 arrivals_state_path: str = ARRIVALS_STATE_PATH,
                 trash_dir: str = TRASH_DIR):
        ensure_workspace_directories()
        self.master_state_path = os.path.abspath(master_state_path)
        self.state_meta_path = os.path.abspath(state_meta_path)
        self.arrivals_state_path = os.path.abspath(arrivals_state_path)
        self.trash_dir = os.path.abspath(trash_dir)

    # -------------------------------------------------------------------------
    # In-House State Persistence (master_state.json inside DATABASE/ directory)
    # -------------------------------------------------------------------------
    def load_master_state(self) -> Dict[str, Dict[str, Any]]:
        """Loads master_state.json from DATABASE/ directory."""
        if not os.path.exists(self.master_state_path):
            # Check root location as fallback migration
            legacy = os.path.join(BASE_DIR, "master_state.json")
            if os.path.exists(legacy):
                shutil.move(legacy, self.master_state_path)
            else:
                return {}

        try:
            with open(self.master_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                return {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception as e:
            print(f"[InHouseDataManager] Error loading master state: {e}")
            return {}

    def save_master_state(self, state: Dict[str, Dict[str, Any]]):
        """Atomically saves the active in-house guests to master_state.json inside DATABASE/."""
        temp_path = self.master_state_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            if os.path.exists(self.master_state_path):
                os.replace(temp_path, self.master_state_path)
            else:
                os.rename(temp_path, self.master_state_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise e

    def load_metadata(self) -> Dict[str, Any]:
        """Loads state metadata (last_processed_date, timestamps, etc.) from DATABASE/."""
        if not os.path.exists(self.state_meta_path):
            legacy = os.path.join(BASE_DIR, "state_metadata.json")
            if os.path.exists(legacy):
                shutil.move(legacy, self.state_meta_path)

        if os.path.exists(self.state_meta_path):
            try:
                with open(self.state_meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_metadata(self, meta: Dict[str, Any]):
        """Persists state metadata to DATABASE/."""
        try:
            with open(self.state_meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[InHouseDataManager] Error saving metadata: {e}")

    def get_last_processed_date(self) -> Optional[date]:
        """Returns the date of the last ingested in-house CSV, or None if brand new."""
        meta = self.load_metadata()
        last_str = meta.get("last_processed_date")
        if last_str:
            try:
                return datetime.strptime(last_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        return None

    def set_last_processed_date(self, target_date: date):
        """Updates last_processed_date in metadata."""
        meta = self.load_metadata()
        meta["last_processed_date"] = target_date.strftime("%Y-%m-%d")
        meta["last_updated_at"] = datetime.now().isoformat()
        self.save_metadata(meta)

    # -------------------------------------------------------------------------
    # Arrivals State Persistence (Automated Routing to Designated Folders)
    # -------------------------------------------------------------------------
    def load_arrivals_state(self) -> Dict[str, Any]:
        """Loads arrivals_state.json and property-specific arrivals."""
        if not os.path.exists(self.arrivals_state_path):
            # Check property folders
            data: Dict[str, Any] = {"_metadata": {}, "SANDY BEACH": {}, "SANDY VILLAS": {}}
            if os.path.exists(ARRIVALS_BEACH_PATH):
                try:
                    with open(ARRIVALS_BEACH_PATH, "r", encoding="utf-8") as f:
                        data["SANDY BEACH"] = json.load(f)
                except Exception:
                    pass
            if os.path.exists(ARRIVALS_VILLAS_PATH):
                try:
                    with open(ARRIVALS_VILLAS_PATH, "r", encoding="utf-8") as f:
                        data["SANDY VILLAS"] = json.load(f)
                except Exception:
                    pass
            return data

        try:
            with open(self.arrivals_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {"_metadata": {}, "SANDY BEACH": {}, "SANDY VILLAS": {}}
                if "SANDY BEACH" not in data:
                    data["SANDY BEACH"] = {}
                if "SANDY VILLAS" not in data:
                    data["SANDY VILLAS"] = {}
                return data
        except Exception as e:
            print(f"[InHouseDataManager] Error loading arrivals state: {e}")
            return {"_metadata": {}, "SANDY BEACH": {}, "SANDY VILLAS": {}}

    def save_arrivals_state(self, arrivals_data: Dict[str, Any]):
        """
        Autonomously routes arrivals into designated folders:
          - Sandy Beach arrivals -> DATABASE/SANDY BEACH/arrivals_sandy_beach.json
          - Sandy Villas arrivals -> DATABASE/SANDY VILLAS/arrivals_sandy_villas.json
          - Unified arrivals state -> DATABASE/arrivals_state.json
        """
        ensure_workspace_directories()

        # Save unified state
        temp_path = self.arrivals_state_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(arrivals_data, f, ensure_ascii=False, indent=2)
            if os.path.exists(self.arrivals_state_path):
                os.replace(temp_path, self.arrivals_state_path)
            else:
                os.rename(temp_path, self.arrivals_state_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise e

        # Route Sandy Beach arrivals to DATABASE/SANDY BEACH/
        try:
            with open(ARRIVALS_BEACH_PATH, "w", encoding="utf-8") as f:
                json.dump(arrivals_data.get("SANDY BEACH", {}), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[InHouseDataManager] Error saving Sandy Beach arrivals: {e}")

        # Route Sandy Villas arrivals to DATABASE/SANDY VILLAS/
        try:
            with open(ARRIVALS_VILLAS_PATH, "w", encoding="utf-8") as f:
                json.dump(arrivals_data.get("SANDY VILLAS", {}), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[InHouseDataManager] Error saving Sandy Villas arrivals: {e}")

    # -------------------------------------------------------------------------
    # Gatekeeper Missing Dates Calculation
    # -------------------------------------------------------------------------
    def get_missing_dates(self, reference_date: Optional[date] = None) -> List[date]:
        """
        Determines sequential calendar dates from the day after last_processed_date
        up to reference_date (defaults to today).
        """
        if reference_date is None:
            reference_date = date.today()

        last_date = self.get_last_processed_date()
        master_state = self.load_master_state()

        if last_date is None or not master_state:
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

    # -------------------------------------------------------------------------
    # In-House CSV Parsing Engine
    # -------------------------------------------------------------------------
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
        bookings: Dict[str, Dict[str, Any]] = {}

        with open(file_path, mode="r", encoding=encoding, errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)
            header = None

            for raw_row in reader:
                if not raw_row:
                    continue

                cleaned_row = [cell.strip().strip('"\'') for cell in raw_row]

                if header is None:
                    is_header = any(
                        any(alias.lower() == cell.lower() for alias in self.BOOKING_ID_KEYS)
                        for cell in cleaned_row
                    )
                    if is_header:
                        header = cleaned_row
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

    # Alias for backward compatibility
    parse_isws_csv = parse_in_house_csv

    # -------------------------------------------------------------------------
    # Arrivals CSV Parsing Engine (Beach & Villas)
    # -------------------------------------------------------------------------
    def detect_property_from_file(self, file_path: str) -> str:
        """
        Auto-detects whether the arrivals CSV belongs to SANDY VILLAS or SANDY BEACH.
        """
        filename_upper = os.path.basename(file_path).upper()
        if "VILLA" in filename_upper:
            return "SANDY VILLAS"
        if "BEACH" in filename_upper:
            return "SANDY BEACH"

        try:
            encoding, delimiter = self._detect_encoding_and_delimiter(file_path)
            with open(file_path, mode="r", encoding=encoding, errors="ignore") as f:
                reader = csv.reader(f, delimiter=delimiter)
                for i, row in enumerate(reader):
                    if i > 40:
                        break
                    if not row:
                        continue
                    col_0 = row[0].strip().strip('"\'')
                    if col_0.isdigit():
                        if len(col_0) == 3:
                            return "SANDY VILLAS"
                        if len(col_0) == 4:
                            return "SANDY BEACH"
        except Exception:
            pass

        return "SANDY BEACH"

    def parse_arrivals_csv(self, file_path: str, property_name: Optional[str] = None) -> Tuple[str, Dict[str, Dict[str, Any]]]:
        """
        Parses a hotel Arrivals CSV export.
        Returns: (detected_property, arrivals_dict_keyed_by_booking_id)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not property_name:
            property_name = self.detect_property_from_file(file_path)

        encoding, delimiter = self._detect_encoding_and_delimiter(file_path)
        arrivals: Dict[str, Dict[str, Any]] = {}

        with open(file_path, mode="r", encoding=encoding, errors="replace") as f:
            rows = list(csv.reader(f, delimiter=delimiter))

        row_count = len(rows)
        r = 0
        while r < row_count:
            row = [c.strip().strip('"\'') for c in rows[r]]
            next_row = [c.strip().strip('"\'') for c in rows[r + 1]] if (r + 1) < row_count else []

            if not any(row):
                r += 1
                continue

            is_header = any(c.lower() in ["room", "δωμάτιο", "booking id", "αρ.", "guest", "πελάτης"] for c in row)
            if is_header:
                r += 1
                continue

            col_room = row[0] if len(row) > 0 else ""
            col_guest = row[2] if len(row) > 2 else ""
            col_dep = row[4] if len(row) > 4 else ""
            col_booking_id = row[5] if len(row) > 5 else ""
            col_room_type = row[6] if len(row) > 6 else ""
            col_bill_type = row[7] if len(row) > 7 else ""
            col_agency = row[8] if len(row) > 8 else ""
            col_pax = row[9] if len(row) > 9 else "1"
            col_meal = row[15] if len(row) > 15 else ""

            booking_id = col_booking_id if (col_booking_id and col_booking_id.isdigit()) else ""
            if not booking_id:
                for idx in [5, 0, 9, 1, 3]:
                    if idx < len(row) and row[idx].isdigit() and len(row[idx]) >= 4:
                        booking_id = row[idx]
                        break

            if not booking_id and not col_guest:
                r += 1
                continue

            if not booking_id:
                booking_id = f"ARR_{r}"

            dep_date = col_dep
            date_match = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.]?(\d{2,4})?", col_dep)
            if date_match:
                d = int(date_match.group(1))
                m = int(date_match.group(2))
                y = date_match.group(3) or str(date.today().year)
                if len(y) == 2:
                    y = "20" + y
                dep_date = f"{d:02d}/{m:02d}/{y}"

            notes = next_row[0] if next_row else ""

            room_assigned = col_room
            if not room_assigned:
                room_in_notes = re.search(r"room\s*(\d{3,4})", notes, re.IGNORECASE)
                if room_in_notes:
                    room_assigned = room_in_notes.group(1)

            arrival_entry = {
                "booking_id": booking_id,
                "property": property_name,
                "room": room_assigned or "Unassigned",
                "guest_name": col_guest,
                "departure_date": dep_date,
                "room_type": col_room_type,
                "billing_room_type": col_bill_type,
                "agency": col_agency,
                "pax": int(re.sub(r"\D", "", col_pax)) if re.search(r"\d", col_pax) else 1,
                "meal_plan": col_meal,
                "notes": notes,
                "imported_at": datetime.now().isoformat()
            }

            arrivals[booking_id] = arrival_entry
            r += 2 if (next_row and not any(next_row[1:])) else 1

        return property_name, arrivals

    def update_arrivals_state(self, property_name: str,
                              arrivals: Dict[str, Dict[str, Any]],
                              target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Updates arrivals state and routes property files into designated folders.
        """
        if target_date is None:
            target_date = date.today()

        current_arrivals = self.load_arrivals_state()
        prop_key = property_name.upper()
        if "VILLA" in prop_key:
            prop_key = "SANDY VILLAS"
        else:
            prop_key = "SANDY BEACH"

        current_arrivals[prop_key] = arrivals
        current_arrivals["_metadata"] = {
            "date": target_date.strftime("%Y-%m-%d"),
            "last_updated": datetime.now().isoformat(),
            "total_beach": len(current_arrivals.get("SANDY BEACH", {})),
            "total_villas": len(current_arrivals.get("SANDY VILLAS", {}))
        }

        self.save_arrivals_state(current_arrivals)
        return current_arrivals

    # -------------------------------------------------------------------------
    # Comparison Engine & In-House State Synchronizer
    # -------------------------------------------------------------------------
    def compare_and_update(self, new_bookings: Dict[str, Dict[str, Any]],
                           processing_date: date) -> Dict[str, Any]:
        """
        Compares new_bookings against master_state.json.
        Detects:
          - Room Move (Booking ID exists, but 'Δωμάτιο' changed)
          - Check-out (Booking ID in master_state, missing from new_bookings)
          - Check-in (Booking ID not in master_state, present in new_bookings)
        Updates master_state.json and logs events.
        """
        current_state = self.load_master_state()

        room_moves = []
        check_outs = []
        check_ins = []
        unchanged_count = 0

        date_str = processing_date.strftime("%d/%m/%Y")

        # 1. Compare new bookings with current state (detect Room Moves & Check-ins)
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
                    room_moves.append(move_info)
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

        # 2. Compare current state with new bookings (detect Check-outs)
        for booking_id, old_data in current_state.items():
            if booking_id not in new_bookings:
                check_out_info = {
                    "booking_id": booking_id,
                    "guests": old_data.get("Πελάτες", []),
                    "room": old_data.get("Δωμάτιο", ""),
                    "departure": old_data.get("Αναχώρηση", ""),
                    "checkout_date": date_str,
                    "archived_at": datetime.now().isoformat()
                }
                check_outs.append(check_out_info)

        # 3. Commit new state to master_state.json in root
        self.save_master_state(new_bookings)
        self.set_last_processed_date(processing_date)

        # 4. Record Check-outs to History
        if check_outs:
            self._archive_checkouts(check_outs)

        # 5. Record Room Moves to Log & History
        if room_moves:
            self._record_room_moves(room_moves)

        summary = {
            "date": date_str,
            "total_in_house": len(new_bookings),
            "room_moves": room_moves,
            "check_ins": check_ins,
            "check_outs": check_outs,
            "unchanged": unchanged_count
        }
        return summary

    # -------------------------------------------------------------------------
    # Audit & History Logging
    # -------------------------------------------------------------------------
    def _archive_checkouts(self, checkouts: List[Dict[str, Any]]):
        history = []
        if os.path.exists(CHECKOUT_HISTORY_PATH):
            try:
                with open(CHECKOUT_HISTORY_PATH, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    if not isinstance(history, list):
                        history = []
            except Exception:
                history = []
        history.extend(checkouts)
        try:
            with open(CHECKOUT_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[InHouseDataManager] Error archiving checkouts: {e}")

    def _record_room_moves(self, room_moves: List[Dict[str, Any]]):
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

        history = []
        if os.path.exists(ROOM_MOVES_HISTORY_PATH):
            try:
                with open(ROOM_MOVES_HISTORY_PATH, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    if not isinstance(history, list):
                        history = []
            except Exception:
                history = []
        history.extend(room_moves)
        try:
            with open(ROOM_MOVES_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[InHouseDataManager] Error writing room moves history JSON: {e}")

    # -------------------------------------------------------------------------
    # Cleanup Manager
    # -------------------------------------------------------------------------
    def cleanup_file(self, file_path: str, mode: str = "trash") -> str:
        """
        Cleans up the ingested CSV file (In-House or Arrivals).
        - mode='trash': Moves file to TRASH/ with timestamped suffix.
        - mode='remove': Deletes file using os.remove.
        """
        if not os.path.exists(file_path):
            return "File already gone"

        if mode == "remove":
            os.remove(file_path)
            return "File permanently deleted"

        base_name = os.path.basename(file_path)
        name, ext = os.path.splitext(base_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(self.trash_dir, exist_ok=True)
        dest_filename = f"{name}_{timestamp}{ext}"
        dest_path = os.path.join(self.trash_dir, dest_filename)

        shutil.move(file_path, dest_path)
        return dest_path


# =============================================================================
# PyQt6 Gatekeeper Modal Dialog
# =============================================================================

class GatekeeperDialog(QDialog):
    """
    Blocking startup dialog that enforces sequential ingestion of all
    missing daily In-House CSV files up to today and provides an Arrivals Tracker
    for Sandy Beach and Sandy Villas before granting access to main app.
    """

    ingestion_completed = pyqtSignal()

    def __init__(self, data_manager: Optional[InHouseDataManager] = None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager or InHouseDataManager()
        self.missing_dates: List[date] = self.data_manager.get_missing_dates()
        self.current_step_idx: int = 0
        self.all_detected_room_moves: List[Dict[str, Any]] = []

        self.setWindowTitle("Gatekeeper : In-House & Arrivals Synchronization")
        self.setMinimumSize(840, 680)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        self._setup_styles()
        self._init_ui()
        self._update_inhouse_step_ui()

    def _setup_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FA;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#header_card {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #800020, stop:1 #B03060);
                border-radius: 8px;
                padding: 16px;
            }
            QLabel#header_title {
                color: #FFFFFF;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#header_subtitle {
                color: #FFE4E1;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #E0E0E0;
                background-color: #FFFFFF;
                border-radius: 6px;
                padding: 12px;
            }
            QTabBar::tab {
                background-color: #ECEFF1;
                color: #37474F;
                padding: 8px 20px;
                margin-right: 4px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                color: #800020;
                border-top: 3px solid #800020;
            }
            QFrame#step_card {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 14px;
            }
            QLabel#target_date_badge {
                background-color: #FFF0F5;
                color: #B03060;
                border: 1px solid #FF69B4;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 15px;
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
                padding: 10px 20px;
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
                padding: 8px 16px;
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
                padding: 10px 24px;
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
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # 1. Header Banner
        header_card = QFrame()
        header_card.setObjectName("header_card")
        h_layout = QVBoxLayout(header_card)
        lbl_title = QLabel("GATEKEEPER : Daily In-House & Arrivals Synchronization")
        lbl_title.setObjectName("header_title")
        lbl_sub = QLabel(
            "State integrity validation is mandatory before accessing the workspace.\n"
            "All daily In-House lists through today must be ingested sequentially, and today's arrivals "
            "can be updated for Sandy Beach and Sandy Villas."
        )
        lbl_sub.setObjectName("header_subtitle")
        h_layout.addWidget(lbl_title)
        h_layout.addWidget(lbl_sub)
        main_layout.addWidget(header_card)

        # 2. Main Tabs
        self.tabs = QTabWidget()

        # Tab 1: In-House Sequential Ingestion
        tab_inhouse = QWidget()
        inhouse_layout = QVBoxLayout(tab_inhouse)
        inhouse_layout.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        inhouse_layout.addWidget(self.progress_bar)

        self.step_card = QFrame()
        self.step_card.setObjectName("step_card")
        s_layout = QVBoxLayout(self.step_card)

        self.lbl_step_info = QLabel()
        self.lbl_step_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #2C3E50;")
        s_layout.addWidget(self.lbl_step_info)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Target Date to Ingest:"))
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

        inhouse_layout.addWidget(self.step_card)

        lbl_table_header = QLabel("Detected Room Moves & Activity Audit:")
        lbl_table_header.setStyleSheet("font-weight: bold; color: #333333; margin-top: 2px;")
        inhouse_layout.addWidget(lbl_table_header)

        self.table_moves = QTableWidget(0, 5)
        self.table_moves.setHorizontalHeaderLabels([
            "Date", "Booking ID", "Guest(s)", "Previous Room", "New Room"
        ])
        self.table_moves.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_moves.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_moves.setAlternatingRowColors(True)
        inhouse_layout.addWidget(self.table_moves)

        self.tabs.addTab(tab_inhouse, "1. In-House Synchronization")

        # Tab 2: Arrivals Tracker (Sandy Beach & Sandy Villas)
        tab_arrivals = QWidget()
        arrivals_layout = QVBoxLayout(tab_arrivals)
        arrivals_layout.setSpacing(12)

        lbl_arr_desc = QLabel(
            "Upload today's Arrivals CSV files to update the arrivals state for Sandy Beach and Sandy Villas."
        )
        lbl_arr_desc.setStyleSheet("color: #555555; font-size: 12px;")
        arrivals_layout.addWidget(lbl_arr_desc)

        group_beach = QGroupBox("🏖️ Sandy Beach Arrivals")
        group_beach.setStyleSheet("QGroupBox { font-weight: bold; color: #1E3A8A; }")
        beach_layout = QHBoxLayout(group_beach)
        self.lbl_beach_file = QLabel("No file selected")
        self.lbl_beach_file.setStyleSheet("color: #7F8C8D; font-style: italic;")
        self.btn_browse_beach = QPushButton("📁 Browse Beach CSV...")
        self.btn_browse_beach.setProperty("class", "action-btn")
        self.btn_browse_beach.clicked.connect(lambda: self._browse_arrivals_csv("SANDY BEACH"))
        self.btn_ingest_beach = QPushButton("⚡ Ingest Beach")
        self.btn_ingest_beach.setEnabled(False)
        self.btn_ingest_beach.clicked.connect(lambda: self._process_arrivals_file("SANDY BEACH"))

        beach_layout.addWidget(self.lbl_beach_file, stretch=1)
        beach_layout.addWidget(self.btn_browse_beach)
        beach_layout.addWidget(self.btn_ingest_beach)
        arrivals_layout.addWidget(group_beach)

        group_villas = QGroupBox("🏡 Sandy Villas Arrivals")
        group_villas.setStyleSheet("QGroupBox { font-weight: bold; color: #065F46; }")
        villas_layout = QHBoxLayout(group_villas)
        self.lbl_villas_file = QLabel("No file selected")
        self.lbl_villas_file.setStyleSheet("color: #7F8C8D; font-style: italic;")
        self.btn_browse_villas = QPushButton("📁 Browse Villas CSV...")
        self.btn_browse_villas.setProperty("class", "action-btn")
        self.btn_browse_villas.clicked.connect(lambda: self._browse_arrivals_csv("SANDY VILLAS"))
        self.btn_ingest_villas = QPushButton("⚡ Ingest Villas")
        self.btn_ingest_villas.setEnabled(False)
        self.btn_ingest_villas.clicked.connect(lambda: self._process_arrivals_file("SANDY VILLAS"))

        villas_layout.addWidget(self.lbl_villas_file, stretch=1)
        villas_layout.addWidget(self.btn_browse_villas)
        villas_layout.addWidget(self.btn_ingest_villas)
        arrivals_layout.addWidget(group_villas)

        self.lbl_arrivals_status = QLabel()
        self._refresh_arrivals_summary_label()
        arrivals_layout.addWidget(self.lbl_arrivals_status)
        arrivals_layout.addStretch()

        self.tabs.addTab(tab_arrivals, "2. Arrivals Tracker (Beach & Villas)")

        main_layout.addWidget(self.tabs)

        # 3. Bottom Controls
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

        self.selected_inhouse_path: Optional[str] = None
        self.selected_beach_path: Optional[str] = None
        self.selected_villas_path: Optional[str] = None

    def _refresh_arrivals_summary_label(self):
        state = self.data_manager.load_arrivals_state()
        beach_cnt = len(state.get("SANDY BEACH", {}))
        villas_cnt = len(state.get("SANDY VILLAS", {}))
        meta = state.get("_metadata", {})
        dt = meta.get("date", "Not updated today")
        self.lbl_arrivals_status.setText(
            f"<b>Current Active State:</b> Date: <code>{dt}</code> | "
            f"🏖️ Sandy Beach: <b>{beach_cnt} arrivals</b> | "
            f"🏡 Sandy Villas: <b>{villas_cnt} arrivals</b>"
        )
        self.lbl_arrivals_status.setStyleSheet(
            "background-color: #E8F5E9; color: #1B5E20; padding: 10px; border-radius: 4px; border: 1px solid #C8E6C9;"
        )

    def _update_inhouse_step_ui(self):
        total_steps = len(self.missing_dates)

        if self.current_step_idx >= total_steps:
            self.progress_bar.setValue(100)
            self.step_card.setEnabled(False)
            self.lbl_step_info.setText("✅ In-House synchronization complete through today.")
            self.lbl_target_date.setText("All Up-to-Date")
            self.lbl_inhouse_file.setText("State is fully synchronized.")
            self.btn_browse_inhouse.setEnabled(False)
            self.btn_process_inhouse.setEnabled(False)
            self.btn_continue.setEnabled(True)
            self.btn_continue.setStyleSheet("""
                QPushButton#btn_continue {
                    background-color: #27AE60;
                    color: white;
                    padding: 12px 28px;
                    font-size: 15px;
                }
            """)
            return

        target_date = self.missing_dates[self.current_step_idx]
        is_today = (target_date == date.today())
        date_label = target_date.strftime("%d/%m/%Y") + (" (TODAY)" if is_today else "")

        pct = int((self.current_step_idx / total_steps) * 100) if total_steps > 0 else 0
        self.progress_bar.setValue(pct)

        self.lbl_step_info.setText(f"Step {self.current_step_idx + 1} of {total_steps}: Ingest daily In-House export")
        self.lbl_target_date.setText(date_label)
        self.lbl_inhouse_file.setText(f"Please select the In-House CSV for {target_date.strftime('%d/%m/%Y')}")
        self.selected_inhouse_path = None
        self.btn_process_inhouse.setEnabled(False)

    def _browse_inhouse_csv(self):
        target_date = self.missing_dates[self.current_step_idx]
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select In-House CSV for {target_date.strftime('%d/%m/%Y')}",
            BASE_DIR,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if file_path:
            self.selected_inhouse_path = file_path
            self.lbl_inhouse_file.setText(os.path.basename(file_path))
            self.lbl_inhouse_file.setStyleSheet("color: #2C3E50; font-weight: bold;")
            self.btn_process_inhouse.setEnabled(True)

    def _process_inhouse_file(self):
        if not self.selected_inhouse_path or not os.path.exists(self.selected_inhouse_path):
            QMessageBox.warning(self, "Invalid File", "Selected file does not exist.")
            return

        target_date = self.missing_dates[self.current_step_idx]

        try:
            new_bookings = self.data_manager.parse_in_house_csv(self.selected_inhouse_path)
            if not new_bookings:
                QMessageBox.critical(
                    self,
                    "Parsing Error",
                    "No valid booking records found in the selected CSV. "
                    "Ensure the file contains the booking ID column ('Αρ.')."
                )
                return

            summary = self.data_manager.compare_and_update(new_bookings, target_date)
            trash_dest = self.data_manager.cleanup_file(self.selected_inhouse_path, mode="trash")

            for rm in summary["room_moves"]:
                self.all_detected_room_moves.append(rm)
                row_pos = self.table_moves.rowCount()
                self.table_moves.insertRow(row_pos)

                date_item = QTableWidgetItem(rm["date"])
                date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_moves.setItem(row_pos, 0, date_item)

                bk_item = QTableWidgetItem(str(rm["booking_id"]))
                bk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_moves.setItem(row_pos, 1, bk_item)

                guests_text = ", ".join(rm.get("guests", []))
                self.table_moves.setItem(row_pos, 2, QTableWidgetItem(guests_text))

                old_room_item = QTableWidgetItem(rm["old_room"])
                old_room_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                old_room_item.setForeground(QColor("#C0392B"))
                self.table_moves.setItem(row_pos, 3, old_room_item)

                new_room_item = QTableWidgetItem(rm["new_room"])
                new_room_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                new_room_item.setForeground(QColor("#27AE60"))
                new_room_item.setFont(QFont("Segoe UI", weight=QFont.Weight.Bold))
                self.table_moves.setItem(row_pos, 4, new_room_item)

            moves_count = len(summary["room_moves"])
            in_count = len(summary["check_ins"])
            out_count = len(summary["check_outs"])
            total = summary["total_in_house"]

            msg = (
                f"Successfully ingested {target_date.strftime('%d/%m/%Y')}!\n\n"
                f"• In-House Guests: {total} bookings\n"
                f"• Room Moves Detected: {moves_count}\n"
                f"• New Check-Ins: {in_count}\n"
                f"• Check-Outs: {out_count}\n\n"
                f"File moved to TRASH archive: {os.path.basename(trash_dest)}"
            )
            QMessageBox.information(self, "Step Complete", msg)

            self.current_step_idx += 1
            self._update_inhouse_step_ui()

        except Exception as e:
            QMessageBox.critical(self, "Processing Failure", f"Failed to process In-House CSV:\n{str(e)}")

    def _browse_arrivals_csv(self, property_name: str):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Arrivals CSV for {property_name}",
            BASE_DIR,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if file_path:
            if property_name == "SANDY BEACH":
                self.selected_beach_path = file_path
                self.lbl_beach_file.setText(os.path.basename(file_path))
                self.lbl_beach_file.setStyleSheet("color: #1E3A8A; font-weight: bold;")
                self.btn_ingest_beach.setEnabled(True)
            else:
                self.selected_villas_path = file_path
                self.lbl_villas_file.setText(os.path.basename(file_path))
                self.lbl_villas_file.setStyleSheet("color: #065F46; font-weight: bold;")
                self.btn_ingest_villas.setEnabled(True)

    def _process_arrivals_file(self, property_name: str):
        target_path = self.selected_beach_path if property_name == "SANDY BEACH" else self.selected_villas_path
        if not target_path or not os.path.exists(target_path):
            QMessageBox.warning(self, "Invalid File", "Selected file does not exist.")
            return

        try:
            detected_prop, arrivals = self.data_manager.parse_arrivals_csv(target_path, property_name=property_name)
            self.data_manager.update_arrivals_state(detected_prop, arrivals)
            trash_dest = self.data_manager.cleanup_file(target_path, mode="trash")

            self._refresh_arrivals_summary_label()
            QMessageBox.information(
                self,
                "Arrivals Ingested",
                f"Successfully processed {len(arrivals)} arrivals for {detected_prop}!\n\n"
                f"File moved to TRASH archive: {os.path.basename(trash_dest)}"
            )

            if property_name == "SANDY BEACH":
                self.btn_ingest_beach.setEnabled(False)
                self.lbl_beach_file.setText(f"Ingested ({len(arrivals)} records)")
            else:
                self.btn_ingest_villas.setEnabled(False)
                self.lbl_villas_file.setText(f"Ingested ({len(arrivals)} records)")

        except Exception as e:
            QMessageBox.critical(self, "Processing Failure", f"Failed to parse Arrivals CSV:\n{str(e)}")

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
