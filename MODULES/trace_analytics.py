"""
Trace Analytics & Room-Matching Engine
=======================================
Provides data extraction, normalization, deterministic keyword tagging,
room-matching JSON generation (ROOMS/<room_number>.json), and operational
aggregations for the 10 Visual Analytics charts.
"""

import os
import re
import csv
import json
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from collections import Counter, defaultdict

from MODULES.room_type_ladder import compare_room_types
from MODULES.parsing.inhouse_csv_reader import parse_inhouse_csv, group_guest_rows_to_reservations
from MODULES.room_type_upgrade_downgrade import compute_room_type_upgrade_downgrade
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(BASE_DIR, "DATABASE")
ROOMS_DIR = os.path.join(BASE_DIR, "ROOMS")
PLOT_DIR = os.path.join(BASE_DIR, "PLOT")
HOTEL_DATASET_PATH = os.path.join(PLOT_DIR, "HotelDataSet.json")
HOTEL_STATE_DIR = os.path.join(DATABASE_DIR, "HOTEL STATE")
MASTER_STATE_PATH = os.path.join(HOTEL_STATE_DIR, "master_state.json")
from MODULES.common.paths_config import DATA_BACKUP_DIR
ROOM_MOVES_PATH = os.path.join(DATABASE_DIR, "ROOM MOVES", "room_moves.json")

# =============================================================================
# Deterministic Classification Taxonomies & Tagging Dictionaries (Re-exported)
# =============================================================================

from MODULES.trace_keywords import (
    PHYSICAL_DEFECT_TAGS,
    CLEAR_SERVICE_CATEGORIES,
    EXCLUDED_TERMS,
    TAG_DICTIONARY,
    SPECIFIC_TAG_PATTERNS,
    ALLERGY_TOKENS,
    PRIMARY_TRACE_CATEGORIES,
    TRACE_SUBCATEGORIES,
    TRACE_SUBCATEGORY_KEYWORDS,
    ROOM_ISSUE_CATEGORIES,
    EXCLUDED_ROOM_ISSUE_CATEGORIES,
    LENS_ROOM_STAY,
    LENS_GR_TRACES,
    LENS_DIETARY,
    LENS_ALL,
    LENS_CATEGORIES,
    classify_trace_subcategory,
    is_room_issue_trace,
)

from MODULES.room_change_detector import (
    compute_repeat_issue_rooms,
    compute_rcr_analytics,
    compute_trace_room_change_correlation,
)

# RCR Resolution Status Tracking (Item 2e)
RCR_RESOLUTION_PATTERNS: Dict[str, List[str]] = {
    "Resolved / Moved": ["they changed", "ok change", "moved to", "can move", "is ready for", "moved"],
    "Attempted / No Answer": ["rec call n/a", "no answer", "call n/a"],
    "Decided to Stay": ["they decide to not change", "not change", "decided to stay", "decide to stay"],
}

# Feedback Sentiment Taxonomy (Item 5b)
FEEDBACK_SENTIMENT_KEYWORDS: Dict[str, List[str]] = {
    "Positive": ["happy", "great", "excellent", "love", "wonderful", "satisfied", "everything", "perfect", "good", "amazing"],
    "Negative": ["complain", "not happy", "unhappy", "upset", "bad", "problem", "issue", "disappointed", "dirty", "poor"]
}



def compute_rcr_resolution_status(notes: str) -> str:
    """
    Computes resolution status for Room Change Request traces:
    - 'Resolved / Moved': 'they changed', 'ok change', 'moved to', 'can move', 'is ready for', 'moved'
    - 'Attempted / No Answer': 'rec call n/a', 'n/a', 'no answer'
    - 'Decided to Stay': 'they decide to not change', 'not change', 'decided to stay'
    - 'Pending / Unresolved': otherwise
    """
    if not notes:
        return "Pending / Unresolved"
    notes_low = str(notes).lower()

    # 'Decided to Stay' checked first
    for phrase in RCR_RESOLUTION_PATTERNS["Decided to Stay"]:
        if phrase in notes_low:
            return "Decided to Stay"

    # 'Resolved / Moved'
    for phrase in RCR_RESOLUTION_PATTERNS["Resolved / Moved"]:
        if phrase in notes_low:
            return "Resolved / Moved"

    # 'Attempted / No Answer'
    for phrase in RCR_RESOLUTION_PATTERNS["Attempted / No Answer"]:
        if phrase in notes_low:
            return "Attempted / No Answer"
    if re.search(r"\bn/?a\b", notes_low):
        return "Attempted / No Answer"

    return "Pending / Unresolved"


def classify_feedback_sentiment(notes: str) -> str:
    """Classifies category == 'Feedback' notes into Positive, Negative, or Neutral."""
    if not notes:
        return "Neutral"
    notes_low = str(notes).lower()

    negated_pos = ["not happy", "not satisfied", "not wonderful", "not great", "not good", "unhappy", "never happy"]
    has_negated_pos = any(np in notes_low for np in negated_pos)
    has_neg = has_negated_pos or any(kw in notes_low for kw in FEEDBACK_SENTIMENT_KEYWORDS["Negative"])

    clean_pos_text = notes_low
    for np in negated_pos:
        clean_pos_text = clean_pos_text.replace(np, "")

    has_pos = any(kw in clean_pos_text for kw in FEEDBACK_SENTIMENT_KEYWORDS["Positive"])

    if has_neg and not has_pos:
        return "Negative"
    elif has_pos and not has_neg:
        return "Positive"
    elif has_neg and has_pos:
        return "Negative"
    return "Neutral"




def normalize_trace_category(cat: str) -> str:
    """Normalizes raw PMS trace category strings to standardized primary categories."""
    cat_str = str(cat or "").strip()
    cat_low = cat_str.lower()
    if "room change" in cat_low or cat_low in ["rcr", "room change request"]:
        return "Room Change Request"
    elif "allerg" in cat_low:
        return "Allergies"
    elif "late check" in cat_low or "late c/o" in cat_low or cat_low in ["lco", "late checkout", "late check out"]:
        return "Late Check Out"
    elif "trace" in cat_low:
        return "Trace"
    elif "feedback" in cat_low:
        return "Feedback"
    elif "offer" in cat_low:
        return "Offer"
    elif "allocation" in cat_low:
        return "Allocation Comments"
    elif "booking" in cat_low:
        return "Booking"
    elif "decoration" in cat_low:
        return "Decoration"
    elif "birthday" in cat_low:
        return "Birthday"
    elif "special request" in cat_low:
        return "Special Requests"
    elif "restaurant" in cat_low:
        return "Restaurants"
    elif "flower" in cat_low:
        return "Flowers"
    return cat_str or "Trace"


def classify_trace(trace: Dict[str, Any]) -> Tuple[bool, bool]:
    """
    Two-tier deterministic classification taxonomy separating Physical Room Defects
    from Clear Operational Service Traces.
    Returns: (is_room_defect: bool, is_service_trace: bool)
    """
    cat = str(trace.get("category", "")).strip()
    cat_lower = cat.lower()
    notes = str(trace.get("notes", "")).strip()
    notes_lower = notes.lower()

    # Check for explicit service/dietary tokens that preclude physical defect classification
    is_non_asset = (
        any(k in cat_lower for k in ["allerg", "late check", "birthday", "cake", "flower", "offer", "decoration", "booking"])
        or any(k in notes_lower for k in ["gluten", "lactose", "celiac", "coeliac", "peanuts", "nuts", "vegan"])
    )

    # Physical defect tag search across regex dictionary
    has_defect_tag = any(
        re.search(pat, notes_lower)
        for patterns in PHYSICAL_DEFECT_TAGS.values()
        for pat in patterns
    )

    is_explicit_rcr = ("room change" in cat_lower) or (cat == "Room Change Request")

    if is_explicit_rcr:
        is_room_defect = True
    elif (cat in ["Trace", "Feedback"] or not is_non_asset) and has_defect_tag and not is_non_asset:
        is_room_defect = True
    else:
        is_room_defect = False

    is_clear_cat = any(sc.lower() in cat_lower for sc in CLEAR_SERVICE_CATEGORIES) or is_non_asset
    is_service_trace = bool(is_clear_cat and not is_room_defect)

    return is_room_defect, is_service_trace


# =============================================================================
# Helper & Normalization Functions
# =============================================================================

def normalize_date_to_iso(date_str: Any) -> str:
    """Normalizes various date string representations to 'YYYY-MM-DD'."""
    if not date_str:
        return ""
    if isinstance(date_str, (date, datetime)):
        return date_str.strftime("%Y-%m-%d")
    
    clean_str = str(date_str).strip()
    if not clean_str:
        return ""

    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", clean_str):
        return clean_str

    # DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", clean_str)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except Exception:
            pass

    # YYYY/MM/DD
    m = re.match(r"^(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$", clean_str)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except Exception:
            pass

    return clean_str

def parse_room_block_floor(room_number: str) -> Tuple[str, str]:
    """
    Parses room number to identify Block and Floor using verified resort deterministic rules.
    Any room that is not a valid 4-digit resort room returns ("Unknown", "Unknown").

    Main hotel (4-digit room):
      - Below 2000: first two digits + "00" (e.g. "1101" -> "1100")
      - 2000 and above: first digit + "000" (e.g. "2114" -> "2000", "7041" -> "7000")

    Floor:
      - 1100, 1200, 1400-1900: 3rd digit (0->Ground, 1->1st, 2->2nd)
      - 1300: Explicit range table (Ground, 1st, 2nd)
      - 2000: D2 // 2 (0->Ground, 1->1st, 2->2nd)
      - 4000, 5000: D2 % 2 (0->Ground, 1->1st)
      - 6000, 7000, 8000: D2 direct (0->Ground, 1->1st, 2->2nd)
      - 3000: Single level ("Level")
    """
    clean_room = str(room_number).strip()
    if not clean_room or not clean_room.isdigit() or len(clean_room) != 4:
        return ("Unknown", "Unknown")

    val = int(clean_room)
    if val < 2000:
        block = clean_room[:2] + "00"
    else:
        block = clean_room[0] + "000"

    d2 = int(clean_room[1])
    d3 = clean_room[2]
    digit_floor_map = {"0": "Ground", "1": "1st", "2": "2nd"}

    if block in ("1100", "1200", "1400", "1500", "1600", "1700", "1800", "1900"):
        floor = digit_floor_map.get(d3, "Unknown")
    elif block == "1300":
        if (1301 <= val <= 1310) or (1321 <= val <= 1324):
            floor = "Ground"
        elif (1311 <= val <= 1314) or (1325 <= val <= 1334):
            floor = "1st"
        elif 1341 <= val <= 1354:
            floor = "2nd"
        else:
            floor = "Unknown"
    elif block == "2000":
        floor = {0: "Ground", 1: "1st", 2: "2nd"}.get(d2 // 2, "Unknown")
    elif block in ("4000", "5000"):
        floor = {0: "Ground", 1: "1st"}.get(d2 % 2, "Unknown")
    elif block in ("6000", "7000", "8000"):
        floor = digit_floor_map.get(str(d2), "Unknown")
    elif block == "3000":
        floor = "Level"
    else:
        floor = "Unknown"

    if floor == "Unknown":
        return ("Unknown", "Unknown")

    return (block, floor)


def extract_rcr_tags(notes: str) -> List[str]:
    """Extracts keyword tags from Room Change Request free-text notes."""
    if not notes:
        return ["unclassified"]

    lower_notes = notes.lower()
    matched_tags: List[str] = []

    # Specific fine-grained tag matching first
    for pattern, tag_name in SPECIFIC_TAG_PATTERNS:
        if re.search(pattern, lower_notes):
            if tag_name not in matched_tags:
                matched_tags.append(tag_name)

    # High-level category dictionary matching
    for cat_name, keywords in TAG_DICTIONARY.items():
        if any(kw in lower_notes for kw in keywords):
            tag_slug = cat_name.lower().replace(" ", "_").replace("/", "_")
            if tag_slug not in matched_tags:
                matched_tags.append(tag_slug)

    if not matched_tags:
        matched_tags.append("unclassified")

    return matched_tags


def extract_allergy_tokens(notes: str) -> List[str]:
    """Parses free-text allergy notes for standardized dietary tokens."""
    if not notes:
        return ["Other / Unspecified"]

    lower_notes = notes.lower()
    matched: List[str] = []

    for allergen, tokens in ALLERGY_TOKENS.items():
        if any(tok in lower_notes for tok in tokens):
            matched.append(allergen)

    if not matched:
        matched.append("Other / Unspecified")

    return matched


def generate_trace_id(room: str, guest: str, category: str, arrival: str, notes: str) -> str:
    """Generates a deterministic unique trace ID for idempotent syncing."""
    seed = f"{room}_{guest.strip().lower()}_{category.strip().lower()}_{arrival}_{notes.strip().lower()}"
    return "trc_" + hashlib.md5(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]


# =============================================================================
# In-House Context Loader (for Operator and Room Type Enrichment)
# =============================================================================

def load_in_house_context() -> Dict[str, Dict[str, str]]:
    """
    Builds a fast lookup dictionary from master_state.json and backup In-House lists
    to enrich trace records with Tour Operator, Booked Room Type, and Assigned Room Type.
    Indexed by:
      - booking_id
      - room_number
      - guest_name (lowercase)
    """
    context: Dict[str, Dict[str, str]] = {}

    def index_entry(b_id: str, rm: str, guest: str, tour_op: str, booked_t: str, assigned_t: str):
        val = {
            "tour_operator": tour_op or "Direct / Other",
            "room_booked": (booked_t or "").strip(),
            "room_assigned": (assigned_t or "").strip()
        }
        if b_id:
            context[f"id:{b_id.strip()}"] = val
        if rm:
            context[f"room:{rm.strip()}"] = val
        if guest:
            context[f"guest:{guest.strip().lower()}"] = val

    # 1. Master state
    if os.path.exists(MASTER_STATE_PATH):
        try:
            with open(MASTER_STATE_PATH, "r", encoding="utf-8", errors="replace") as f:
                ms = json.load(f)
                if isinstance(ms, dict):
                    for b_id, b_data in ms.items():
                        rm = b_data.get("Room") or b_data.get("Δωμάτιο") or ""
                        tour_op = b_data.get("Agency") or b_data.get("Χρεώστης") or b_data.get("Market") or ""
                        assigned_t = b_data.get("Room Type") or b_data.get("Τύπος Δωμ") or ""
                        booked_t = b_data.get("Booked Room Type") or b_data.get("Κρατηθείς Τύπος") or ""
                        guests = b_data.get("Guests") or b_data.get("Πελάτες") or []
                        guest_name = guests[0] if (isinstance(guests, list) and guests) else (b_data.get("Guest") or "")
                        index_entry(str(b_id), str(rm), str(guest_name), str(tour_op), str(booked_t), str(assigned_t))
        except Exception:
            pass

    # 2. Backup In-House CSVs (scan DATA_BACKUP/)
    if os.path.exists(DATA_BACKUP_DIR):
        try:
            for f_name in os.listdir(DATA_BACKUP_DIR):
                if f_name.endswith(".csv") and "in_house" in f_name.lower():
                    p = os.path.join(DATA_BACKUP_DIR, f_name)
                    try:
                        with open(p, "r", encoding="cp1253", errors="replace") as fh:
                            reader = csv.reader(fh, delimiter=";")
                            for row in reader:
                                if len(row) >= 8 and row[0].strip().isdigit():
                                    rm = row[0].strip()
                                    gst = row[1].strip()
                                    assigned_t = row[4].strip()
                                    booked_t = row[5].strip()
                                    op = row[6].strip()
                                    b_id = row[7].strip()
                                    index_entry(b_id, rm, gst, op, booked_t, assigned_t)
                    except Exception:
                        pass
        except Exception:
            pass

    return context


def lookup_enrichment(context: Dict[str, Dict[str, str]], booking_id: str, room: str, guest: str) -> Dict[str, str]:
    """Looks up operator and room types from the pre-indexed context."""
    if booking_id and f"id:{booking_id.strip()}" in context:
        return context[f"id:{booking_id.strip()}"]
    if guest and f"guest:{guest.strip().lower()}" in context:
        return context[f"guest:{guest.strip().lower()}"]
    if room and f"room:{room.strip()}" in context:
        return context[f"room:{room.strip()}"]
    return {
        "tour_operator": "Standard Agency",
        "room_booked": "",
        "room_assigned": ""
    }


# =============================================================================
# Trace List File Ingestion Engine
# =============================================================================

def scan_for_trace_files(search_dir: Optional[str] = None) -> List[str]:
    """
    Scans the database directory (or specified folder) to find potential trace files.
    Recognizes .csv, .xlsx, and .xls exports matching trace keywords.
    """
    root_dir = search_dir or DATABASE_DIR
    found_files: List[str] = []

    if not os.path.exists(root_dir):
        return found_files

    for root, _, files in os.walk(root_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in [".csv", ".xlsx", ".xls"]:
                full_path = os.path.join(root, file)
                name_low = file.lower()
                # Prioritize explicit trace folders or filenames
                if "trace" in name_low or "traces" in name_low or "trace list" in root.lower():
                    found_files.insert(0, full_path)
                elif any(k in name_low for k in ["request", "notes", "dietary"]):
                    found_files.append(full_path)

    # Guarantee unique list preserving priority
    seen: Set[str] = set()
    deduped: List[str] = []
    for f in found_files:
        if f not in seen:
            seen.add(f)
            deduped.append(f)

    return deduped


def parse_trace_file(file_path: str, in_house_context: Optional[Dict[str, Dict[str, str]]] = None) -> List[Dict[str, Any]]:
    """
    Parses a trace list file (.csv, .xlsx, .xls) and outputs normalized trace items.
    Normalizes columns:
      - room_number
      - guest_name
      - arrival
      - departure
      - tour_operator
      - room_booked
      - room_assigned
      - category
      - notes
      - status
      - tags
      - trace_id
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Trace file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    raw_rows: List[List[str]] = []

    if ext == ".csv":
        # Detect encoding and delimiter
        encodings = ["cp1253", "utf-8-sig", "utf-8", "windows-1253", "latin1"]
        detected_enc = "cp1253"
        with open(file_path, "rb") as f:
            sample_bytes = f.read(4096)
        for enc in encodings:
            try:
                sample_bytes.decode(enc)
                detected_enc = enc
                break
            except Exception:
                continue

        with open(file_path, "r", encoding=detected_enc, errors="replace") as f:
            sample_text = f.read(2048)
            delim = ";" if sample_text.count(";") >= sample_text.count(",") else ","

        with open(file_path, "r", encoding=detected_enc, errors="replace") as f:
            reader = csv.reader(f, delimiter=delim)
            for row in reader:
                raw_rows.append([str(c).strip().strip('"\'') for c in row])

    elif ext in [".xlsx", ".xls"]:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                raw_rows.append([str(c).strip() if c is not None else "" for c in row])
            wb.close()
        except Exception as ex:
            # Fallback to xlrd if xls
            if ext == ".xls":
                import xlrd
                wb = xlrd.open_workbook(file_path)
                ws = wb.sheet_by_index(0)
                for r_idx in range(ws.nrows):
                    raw_rows.append([str(ws.cell_value(r_idx, c_idx)).strip() for c_idx in range(ws.ncols)])
            else:
                raise ex

    if in_house_context is None:
        in_house_context = load_in_house_context()

    normalized_traces: List[Dict[str, Any]] = []

    # Check if this is a standard flat table with column headers
    header_idx = -1
    col_map: Dict[str, int] = {}
    for idx, row in enumerate(raw_rows[:15]):
        row_low = [c.lower() for c in row if c]
        if any("room" in c or "δωμάτιο" in c for c in row_low) and any("trace" in c or "category" in c or "υπενθύμιση" in c for c in row_low):
            header_idx = idx
            for c_idx, cell in enumerate(row):
                cell_clean = cell.lower().strip()
                col_map[cell_clean] = c_idx
            break

    # If flat table format detected
    if header_idx != -1 and len(col_map) >= 3:
        for row in raw_rows[header_idx + 1:]:
            if not any(row):
                continue
            def get_val(keys: List[str]) -> str:
                for k in keys:
                    for h_name, pos in col_map.items():
                        if k in h_name and pos < len(row):
                            return row[pos]
                return ""

            room = get_val(["room", "δωμάτιο", "room number"])
            if not room:
                continue

            guest = get_val(["guest", "πελάτης", "name"])
            arr = normalize_date_to_iso(get_val(["arrival", "άφιξη"]))
            dep = normalize_date_to_iso(get_val(["departure", "αναχώρηση"]))
            cat = get_val(["category", "υπενθύμιση", "trace category", "type"]) or "Trace"
            notes = get_val(["notes", "σημειώσεις", "comment", "details"])
            status = get_val(["status", "κατάσταση"]) or "Checked In"
            b_id = get_val(["booking", "αρ.", "id", "reservation"])
            tour_op = get_val(["operator", "agency", "πρακτορείο", "χρεώστης"])
            b_room = get_val(["booked room", "κρατηθείς"])
            a_room = get_val(["assigned room", "τύπος δωμ", "room type"])

            enrich = lookup_enrichment(in_house_context, b_id, room, guest)
            tour_op = tour_op or enrich["tour_operator"]
            b_room = b_room or enrich["room_booked"]
            a_room = a_room or enrich["room_assigned"]

            cat_norm = normalize_trace_category(cat)
            tags: List[str] = []
            if cat_norm == "Room Change Request":
                tags = extract_rcr_tags(notes)
            elif cat_norm == "Allergies":
                tags = [t.lower().replace(" ", "_") for t in extract_allergy_tokens(notes)]
            elif cat_norm == "Trace":
                extracted = extract_rcr_tags(notes)
                tags = [t for t in extracted if t != "unclassified"]
                if not tags:
                    tags = ["trace"]
            else:
                tags = [cat_norm.lower().replace(" ", "_")]

            res_status = compute_rcr_resolution_status(notes) if ("room change" in cat_norm.lower() or cat_norm == "Room Change Request") else ""
            trace_subcat = classify_trace_subcategory(notes) if cat_norm == "Trace" else ""
            feedback_sent = classify_feedback_sentiment(notes) if cat_norm == "Feedback" else ""

            t_id = generate_trace_id(room, guest, cat_norm, arr, notes)
            t_item = {
                "trace_id": t_id,
                "room_number": room,
                "guest_name": guest,
                "arrival": arr,
                "departure": dep,
                "tour_operator": tour_op,
                "room_booked": b_room,
                "room_assigned": a_room,
                "category": cat_norm,
                "notes": notes,
                "status": status,
                "booking_id": b_id,
                "tags": tags,
                "resolution_status": res_status,
                "trace_subcategory": trace_subcat,
                "feedback_sentiment": feedback_sent
            }
            is_defect, is_service = classify_trace(t_item)
            t_item["is_room_defect"] = is_defect
            t_item["is_service_trace"] = is_service
            normalized_traces.append(t_item)
        return normalized_traces

    # Hierarchical PMS format (as seen in traces.csv)
    # Row 1: Room, Arrival, Departure, Guest Name, Status, Booking ID
    # Sub-Row: Category, Notes
    current_guest: Optional[Dict[str, Any]] = None

    for row in raw_rows:
        non_empty = [c for c in row if c]
        if not non_empty:
            continue

        first = row[0].strip()
        # Skip report headers & pagination
        if any(h in first for h in ["SANDY", "Trace's List", "Date Due", "Ημέρα Ενέργειας", "Page"]):
            continue
        if any("Page" in c for c in non_empty) or "Εκτύπωση" in " ".join(non_empty):
            continue
        if len(row) >= 5 and any(h in first for h in ["Δωμάτιο", "Room"]) and any("Άφιξη" in c or "Arrival" in c for c in non_empty):
            continue

        # Check for guest summary line:
        # Col 0: Room (digit)
        # Col 2: Arrival Date
        # Col 4: Departure Date
        # Col 5: Guest Name
        # Col 7: Status
        # Col 10: Booking ID
        is_guest_row = (
            re.match(r"^\d{3,4}$", first) is not None
            and len(row) >= 6
            and any(re.search(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", c) for c in row[1:5] if c)
        )

        if is_guest_row:
            room = first
            arr = ""
            dep = ""
            for c in row[1:6]:
                if re.search(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", c):
                    if not arr:
                        arr = normalize_date_to_iso(c)
                    elif not dep:
                        dep = normalize_date_to_iso(c)
                        break

            guest_name = row[5].strip() if len(row) > 5 else (row[1].strip() if len(row) > 1 else "")
            status = row[7].strip() if len(row) > 7 and row[7].strip() else "Checked In"
            b_id = row[10].strip() if len(row) > 10 and row[10].strip().isdigit() else ""

            enrich = lookup_enrichment(in_house_context, b_id, room, guest_name)

            current_guest = {
                "room_number": room,
                "guest_name": guest_name,
                "arrival": arr,
                "departure": dep,
                "status": status,
                "booking_id": b_id,
                "tour_operator": enrich["tour_operator"],
                "room_booked": enrich["room_booked"],
                "room_assigned": enrich["room_assigned"],
            }
            continue

        # Check for trace line associated with current guest
        if current_guest:
            # Skip sub-headers: e.g. "Υπενθύμιση: Room Change Request" or "Υπενθύμιση; Σημειώσεις"
            if "Υπενθύμιση" in first or "Σημειώσεις" in " ".join(non_empty):
                continue
            if "Trace:" in first or "Notes" in " ".join(non_empty):
                continue

            # Candidate trace line: Category in col 0, Notes in col 1 or 2
            cat = first
            notes = ""
            if len(row) > 2 and row[2].strip():
                notes = row[2].strip()
            elif len(row) > 1 and row[1].strip():
                notes = row[1].strip()
            elif len(non_empty) >= 2:
                notes = non_empty[1]

            # Normalize primary categories
            cat_norm = normalize_trace_category(cat)

            tags: List[str] = []
            if cat_norm == "Room Change Request":
                tags = extract_rcr_tags(notes)
            elif cat_norm == "Allergies":
                tags = [t.lower().replace(" ", "_") for t in extract_allergy_tokens(notes)]
            elif cat_norm == "Trace":
                extracted = extract_rcr_tags(notes)
                tags = [t for t in extracted if t != "unclassified"]
                if not tags:
                    tags = ["trace"]
            else:
                tags = [cat_norm.lower().replace(" ", "_")]

            res_status = compute_rcr_resolution_status(notes) if ("room change" in cat_norm.lower() or cat_norm == "Room Change Request") else ""
            trace_subcat = classify_trace_subcategory(notes) if cat_norm == "Trace" else ""
            feedback_sent = classify_feedback_sentiment(notes) if cat_norm == "Feedback" else ""

            t_id = generate_trace_id(
                current_guest["room_number"],
                current_guest["guest_name"],
                cat_norm,
                current_guest["arrival"],
                notes
            )

            t_item = {
                "trace_id": t_id,
                "room_number": current_guest["room_number"],
                "guest_name": current_guest["guest_name"],
                "arrival": current_guest["arrival"],
                "departure": current_guest["departure"],
                "tour_operator": current_guest["tour_operator"],
                "room_booked": current_guest["room_booked"],
                "room_assigned": current_guest["room_assigned"],
                "category": cat_norm,
                "notes": notes,
                "status": current_guest["status"],
                "booking_id": current_guest["booking_id"],
                "tags": tags,
                "resolution_status": res_status,
                "trace_subcategory": trace_subcat,
                "feedback_sentiment": feedback_sent
            }
            is_defect, is_service = classify_trace(t_item)
            t_item["is_room_defect"] = is_defect
            t_item["is_service_trace"] = is_service
            normalized_traces.append(t_item)

    return normalized_traces


# =============================================================================
# ROOMS/ JSON Generation Engine (Idempotent Mapping)
# =============================================================================

def get_hotel_room_schema(hotel_dataset_path: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """
    Discovers all physical rooms in the resort schema and associates Block & Floor.
    Uses 4-digit block format matching resort layout rules (e.g. "1100".."8000").
    Returns: { "7030": {"block": "7000", "floor": "0"}, ... }
    """
    schema_rooms: Dict[str, Dict[str, str]] = {}
    ds_path = hotel_dataset_path or HOTEL_DATASET_PATH

    if os.path.exists(ds_path):
        try:
            with open(ds_path, "r", encoding="utf-8", errors="replace") as f:
                items = json.load(f)
                if isinstance(items, list):
                    floor_norm_map = {"Ground": "0", "Level": "0", "1st": "1", "2nd": "2"}
                    for item in items:
                        floors = item.get("room_details", {}).get("floors", {})
                        for fl_name, fl_ranges in floors.items():
                            for rng in fl_ranges:
                                m = re.search(r"(\d+)-(\d+)", rng)
                                if m:
                                    start, end = int(m.group(1)), int(m.group(2))
                                    for r in range(start, end + 1):
                                        rm_str = str(r)
                                        # Derive block and floor matching real resort schema
                                        blk, fl = parse_room_block_floor(rm_str)
                                        fl_digit = floor_norm_map.get(fl)
                                        if fl_digit is None:
                                            # Fallback: safe word-boundary / exact check on floor label
                                            fl_lower = fl_name.lower().strip()
                                            if re.search(r"\b(1st|first)\b", fl_lower):
                                                fl_digit = "1"
                                            elif re.search(r"\b(2nd|second)\b", fl_lower):
                                                fl_digit = "2"
                                            elif re.search(r"\b(ground|level)\b", fl_lower):
                                                fl_digit = "0"
                                            else:
                                                fl_digit = "0"
                                        schema_rooms[rm_str] = {
                                            "block": blk,
                                            "floor": fl_digit
                                        }
        except Exception:
            pass

    return schema_rooms


def normalize_guest_surname(guest_name: str) -> str:
    """Extracts and normalizes guest surname from various formatting conventions."""
    if not guest_name:
        return ""
    cleaned = str(guest_name).strip()
    parts = re.split(r"[,/\s]+", cleaned)
    return parts[0].lower() if parts else ""


def fuse_inhouse_and_traces(
    in_house_dict: Dict[str, Any],
    trace_list: List[Dict[str, Any]],
    hotel_dataset_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dual-Source Integration Engine (In-House List + Traces Fusion).
    Synchronizes in-house manifest and trace records:
      - Indexes in-house manifest by Room, Booking ID, and normalized surname.
      - Enriches trace records with missing room numbers, operators, booking IDs, room types.
      - Attaches all active and historical traces to each in-house room.
      - Classifies each room into one of four states:
          * 'Occupied with Active Physical Complaints'
          * 'Occupied with Clear Service Traces'
          * 'Occupied with Clean Record (No Traces)'
          * 'Vacant'
      - Calculates the Resort Incident Ratio:
          Incident Ratio = (Occupied Rooms with Defect Traces / Total Occupied Rooms) * 100
    """
    in_house_manifest = dict(in_house_dict) if isinstance(in_house_dict, dict) else {}

    # Multi-attribute lookup indices for in-house manifest
    by_booking_id: Dict[str, Dict[str, Any]] = {}
    by_room: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_surname: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for b_id, b_data in in_house_manifest.items():
        if not isinstance(b_data, dict):
            continue
        clean_bid = str(b_id).strip()
        by_booking_id[clean_bid] = b_data
        alt_bid = str(b_data.get("Booking ID") or b_data.get("Αρ.") or b_data.get("booking_id") or "").strip()
        if alt_bid:
            by_booking_id[alt_bid] = b_data

        rm = str(b_data.get("Room") or b_data.get("Δωμάτιο") or b_data.get("room") or "").strip()
        if rm:
            by_room[rm].append(b_data)

        # Index guest surname(s)
        guests = b_data.get("Guests") or b_data.get("Πελάτες") or []
        if isinstance(guests, list) and guests:
            for g in guests:
                sn = normalize_guest_surname(str(g))
                if sn:
                    by_surname[sn].append(b_data)
        else:
            g_single = str(b_data.get("Guest") or b_data.get("Πελάτης") or b_data.get("guest_name") or "")
            sn = normalize_guest_surname(g_single)
            if sn:
                by_surname[sn].append(b_data)

    # Resolve and enrich all trace records
    enriched_traces: List[Dict[str, Any]] = []
    for tr in (trace_list or []):
        t = dict(tr)
        t_rm = str(t.get("room_number", "")).strip()
        t_bid = str(t.get("booking_id", "")).strip()
        t_guest = str(t.get("guest_name", "")).strip()
        t_sname = normalize_guest_surname(t_guest)

        matched_ih: Optional[Dict[str, Any]] = None
        if t_bid and t_bid in by_booking_id:
            matched_ih = by_booking_id[t_bid]
        elif t_rm and t_rm in by_room:
            matched_ih = by_room[t_rm][0]
        elif t_sname and t_sname in by_surname:
            matched_ih = by_surname[t_sname][0]

        if matched_ih:
            if not t_rm or not t_rm.isdigit():
                resolved_rm = str(matched_ih.get("room") or matched_ih.get("Room") or matched_ih.get("Δωμάτιο") or matched_ih.get("room_number") or "").strip()
                if resolved_rm:
                    t["room_number"] = resolved_rm
            if not t_bid:
                t["booking_id"] = str(matched_ih.get("booking_id") or matched_ih.get("Booking ID") or matched_ih.get("Αρ.") or "").strip()
            if not t.get("tour_operator") or t.get("tour_operator") in ["Direct / Other", "Standard Agency", ""]:
                op = str(matched_ih.get("tour_operator") or matched_ih.get("Tour Operator") or matched_ih.get("Agency") or matched_ih.get("Agency Name") or matched_ih.get("Χρεώστης") or matched_ih.get("Market") or "").strip()
                if op:
                    t["tour_operator"] = op
            if not t.get("room_booked") or t.get("room_booked") == "Standard Room":
                bk = str(matched_ih.get("room_booked") or matched_ih.get("room_category") or matched_ih.get("Booked Room Type") or matched_ih.get("Κρατηθείς Τύπος") or "").strip()
                if bk:
                    t["room_booked"] = bk
            if not t.get("room_assigned") or t.get("room_assigned") == "Standard Room":
                asn = str(matched_ih.get("room_assigned") or matched_ih.get("room_category") or matched_ih.get("Room Type") or matched_ih.get("Τύπος Δωματίου") or matched_ih.get("Τύπος Δωμ") or "").strip()
                if asn:
                    t["room_assigned"] = asn

        if not t.get("resolution_status") and ("room change" in str(t.get("category", "")).lower() or t.get("category") == "Room Change Request"):
            t["resolution_status"] = compute_rcr_resolution_status(t.get("notes", ""))
        if not t.get("trace_subcategory") and str(t.get("category", "")).lower() == "trace":
            t["trace_subcategory"] = classify_trace_subcategory(t.get("notes", ""))
        if not t.get("feedback_sentiment") and str(t.get("category", "")).lower() == "feedback":
            t["feedback_sentiment"] = classify_feedback_sentiment(t.get("notes", ""))

        is_defect, is_service = classify_trace(t)
        t["is_room_defect"] = is_defect
        t["is_service_trace"] = is_service
        enriched_traces.append(t)

    # Attach trace records to in-house bookings & rooms
    traces_by_room: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in enriched_traces:
        rm = str(t.get("room_number", "")).strip()
        if rm:
            traces_by_room[rm].append(t)

    for b_id, b_data in in_house_manifest.items():
        if isinstance(b_data, dict):
            rm = str(b_data.get("Room") or b_data.get("Δωμάτιο") or "").strip()
            b_data["attached_traces"] = list(traces_by_room.get(rm, []))

    # Unified Occupancy & Complaint Linkage (4 discrete room states)
    schema_rooms = get_hotel_room_schema(hotel_dataset_path)
    all_rooms_set = set(schema_rooms.keys())
    for rm in by_room.keys():
        if rm and rm.isdigit():
            all_rooms_set.add(rm)
    for rm in traces_by_room.keys():
        if rm and rm.isdigit():
            all_rooms_set.add(rm)

    occupied_rooms = {rm for rm in by_room.keys() if rm and rm.isdigit()}

    room_states: Dict[str, str] = {}
    occupied_with_defects = set()
    occupied_with_service = set()
    occupied_clean = set()
    vacant_rooms = set()

    for rm in all_rooms_set:
        if rm in occupied_rooms:
            r_traces = traces_by_room.get(rm, [])
            has_defect = any(is_room_issue_trace(t) for t in r_traces)
            has_service = any(t.get("is_service_trace") for t in r_traces)
            if has_defect:
                st = "Occupied with Active Physical Complaints"
                occupied_with_defects.add(rm)
            elif has_service:
                st = "Occupied with Clear Service Traces"
                occupied_with_service.add(rm)
            else:
                st = "Occupied with Clean Record (No Traces)"
                occupied_clean.add(rm)
        else:
            st = "Vacant"
            vacant_rooms.add(rm)
        room_states[rm] = st

    tot_occ = len(occupied_rooms)
    incident_ratio = (len(occupied_with_defects) / tot_occ * 100.0) if tot_occ > 0 else 0.0

    return {
        "in_house": in_house_manifest,
        "traces": enriched_traces,
        "enriched_traces": enriched_traces,
        "room_states": room_states,
        "room_state_counts": {
            "Occupied with Active Physical Complaints": len(occupied_with_defects),
            "Occupied with Clear Service Traces": len(occupied_with_service),
            "Occupied with Clean Record (No Traces)": len(occupied_clean),
            "Vacant": len(vacant_rooms)
        },
        "total_occupied_rooms": tot_occ,
        "occupied_with_defects": len(occupied_with_defects),
        "occupied_rooms_with_defects": len(occupied_with_defects),
        "incident_ratio": round(incident_ratio, 2)
    }


def generate_room_json_mappings(
    trace_items: List[Dict[str, Any]],
    rooms_dir: Optional[str] = None,
    hotel_dataset_path: Optional[str] = None,
    include_all_schema_rooms: bool = False
) -> Dict[str, Any]:
    """
    Generates or updates ROOMS/<room_number>.json idempotently.
    
    Schema for ROOMS/<room_number>.json:
    {
      "room_number": "7030",
      "block": "7000",
      "floor": "0",
      "total_traces": 2,
      "traces": [
        {
          "trace_id": "...",
          "category": "Room Change Request",
          "status": "Checked In",
          "guest_name": "...",
          "arrival": "YYYY-MM-DD",
          "departure": "YYYY-MM-DD",
          "tour_operator": "TUI Germany",
          "room_booked": "Standard Sea View",
          "room_assigned": "Standard Sea View",
          "notes": "no hot water in shower",
          "tags": ["no_hot_water"]
        }
      ]
    }
    """
    target_dir = rooms_dir or ROOMS_DIR
    os.makedirs(target_dir, exist_ok=True)

    schema_rooms = get_hotel_room_schema(hotel_dataset_path)

    # Group traces by room number
    traces_by_room: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in trace_items:
        rm = str(t.get("room_number", "")).strip()
        if rm:
            traces_by_room[rm].append(t)

    target_room_numbers = set(traces_by_room.keys())
    if include_all_schema_rooms:
        target_room_numbers.update(schema_rooms.keys())

    updated_count = 0
    created_count = 0
    total_traces_synced = 0

    for rm in target_room_numbers:
        file_path = os.path.join(target_dir, f"{rm}.json")
        existing_doc: Dict[str, Any] = {}

        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    existing_doc = json.load(f)
            except Exception:
                existing_doc = {}

        # Determine block and floor
        if rm in schema_rooms:
            block = schema_rooms[rm]["block"]
            floor = schema_rooms[rm]["floor"]
        else:
            block, floor = parse_room_block_floor(rm)

        # Merge traces idempotently
        existing_traces: List[Dict[str, Any]] = existing_doc.get("traces", [])
        trace_map: Dict[str, Dict[str, Any]] = {}
        
        for tr in existing_traces:
            t_id = tr.get("trace_id")
            if t_id:
                trace_map[t_id] = tr
            else:
                # Assign deterministic ID if missing
                t_id = generate_trace_id(rm, tr.get("guest_name", ""), tr.get("category", ""), tr.get("arrival", ""), tr.get("notes", ""))
                tr["trace_id"] = t_id
                trace_map[t_id] = tr

        # Insert/Update new traces
        for new_tr in traces_by_room.get(rm, []):
            t_id = new_tr["trace_id"]
            if t_id in trace_map:
                # Merge fields while preserving any manual edits/notes
                merged = dict(trace_map[t_id])
                for k, v in new_tr.items():
                    if k not in merged or not merged[k]:
                        merged[k] = v
                trace_map[t_id] = merged
            else:
                trace_map[t_id] = new_tr

        combined_traces = list(trace_map.values())
        total_traces = len(combined_traces)
        total_traces_synced += total_traces

        room_data = {
            "room_number": rm,
            "block": block,
            "floor": floor,
            "total_traces": total_traces,
            "traces": combined_traces
        }
        # Preserve any extra custom top-level keys manually set by staff
        for k, v in existing_doc.items():
            if k not in room_data:
                room_data[k] = v

        is_new = not os.path.exists(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(room_data, f, indent=2, ensure_ascii=False)

        if is_new:
            created_count += 1
        else:
            updated_count += 1

    return {
        "rooms_directory": target_dir,
        "total_rooms_processed": len(target_room_numbers),
        "created": created_count,
        "updated": updated_count,
        "total_traces_synced": total_traces_synced
    }


# =============================================================================
# Segregated Analytical Calculation Engines & Extended KPIs
# =============================================================================



def compute_clear_trace_analytics(traces: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes analytics for Clear Operational Service Traces (Allergies, VIP, Late Check Out, Amenities).
    """
    service_traces = [
        t for t in traces
        if t.get("is_service_trace")
        or (str(t.get("category", "")) in CLEAR_SERVICE_CATEGORIES and not t.get("is_room_defect"))
    ]

    total_courtesy = len(service_traces)
    dietary_profiles: Counter = Counter()
    late_checkout_cnt = 0
    late_checkout_rev = 0.0
    vip_amenities = 0

    vip_keywords = ["vip", "birthday", "cake", "offer", "flowers", "flower", "decoration", "champagne", "wine", "fruit"]

    for t in service_traces:
        cat_low = str(t.get("category", "")).lower()
        notes_low = str(t.get("notes", "")).lower()

        if "allerg" in cat_low or any(tok in notes_low for tokens in ALLERGY_TOKENS.values() for tok in tokens):
            tokens = extract_allergy_tokens(t.get("notes", ""))
            for tok in tokens:
                dietary_profiles[tok] += 1

        if "late check" in cat_low or "late check" in notes_low:
            late_checkout_cnt += 1
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:€|euro|eur)", notes_low)
            if m:
                try:
                    late_checkout_rev += float(m.group(1))
                except Exception:
                    late_checkout_rev += 35.0
            elif "free" not in notes_low and "complimentary" not in notes_low:
                late_checkout_rev += 35.0

        if any(k in cat_low or k in notes_low for k in vip_keywords):
            vip_amenities += 1

    return {
        "total_courtesy_actions": total_courtesy,
        "dietary_profiles": dict(dietary_profiles.most_common()),
        "late_checkout_count": late_checkout_cnt,
        "late_checkout_revenue": round(late_checkout_rev, 2),
        "vip_amenity_deliveries": vip_amenities
    }


def compute_normalized_block_defect_rate(
    traces: List[Dict[str, Any]],
    hotel_dataset_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculates defect density scaled to physical block capacity rather than absolute counts:
      Defect Rate_B = (Total Verified Defects in Block B / Total Physical Room Capacity of Block B) * 100
    """
    schema = get_hotel_room_schema(hotel_dataset_path)
    block_capacities: Counter = Counter()
    for rm, info in schema.items():
        blk = info.get("block", "")
        if blk:
            block_capacities[blk] += 1

    block_defects: Counter = Counter()
    for t in traces:
        if t.get("is_room_defect") or t.get("category") == "Room Change Request":
            rm = str(t.get("room_number", "")).strip()
            blk, _ = parse_room_block_floor(rm)
            if blk != "Unknown":
                block_defects[blk] += 1

    all_blocks = sorted(list(set(block_capacities.keys()) | set(block_defects.keys())))
    rate_table = []
    for blk in all_blocks:
        cap = block_capacities.get(blk, 0)
        defects = block_defects.get(blk, 0)
        if cap > 0:
            rate_pct = defects / cap * 100.0
            rate_table.append({
                "block": blk,
                "defects": defects,
                "capacity": cap,
                "defect_rate_pct": round(rate_pct, 2),
                "capacity_known": True
            })
        else:
            rate_table.append({
                "block": blk,
                "defects": defects,
                "capacity": None,
                "defect_rate_pct": None,
                "capacity_known": False
            })

    valid_rates = [r for r in rate_table if r.get("defect_rate_pct") is not None]
    highest_block = max(valid_rates, key=lambda x: x["defect_rate_pct"])["block"] if valid_rates else "N/A"

    return {
        "block_defect_rates": rate_table,
        "rates": rate_table,
        "highest_risk_block": highest_block
    }


def compute_departmental_attribution(traces: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Maps each physical complaint to responsible operational departments:
      - Technical Maintenance: Plumbing, Water Pressure, HVAC, Electrical, Hardware
      - Housekeeping: Odor, Humidity, Mold, Cleanliness, Towel/Linen Service
      - Front Office / Reception: View Mismatch, Floor Allocation, Merged Room Proximity
    """
    dept_counts = {
        "Technical Maintenance": 0,
        "Housekeeping": 0,
        "Front Office / Reception": 0
    }

    tech_patterns = [
        r"\bwater\b", r"\bleak\b", r"\bpressure\b", r"\btoilet\b", r"\bshower\b",
        r"\bdrain\b", r"\ba/?c\b", r"\bcold\b", r"\bheating\b", r"\bfan\b",
        r"\belectric\b", r"\blight\b", r"\bpower\b", r"\btv\b", r"\bdoor\b", r"\block\b"
    ]
    hk_patterns = [
        r"\bsmell\b", r"\bodor\b", r"\bstink\b", r"\bhumidity\b", r"\bdamp\b",
        r"\bmold\b", r"\bsewer\b", r"\bdirty\b", r"\bclean\b", r"\btowel\b",
        r"\blinen\b", r"\bsheet\b", r"\bpillow\b"
    ]
    fo_patterns = [
        r"\bview\b", r"\bsea\s+view\b", r"\bgarden\b", r"\bfloor\b", r"\bstairs\b",
        r"\belevator\b", r"\blift\b", r"\bmerge\b", r"\badjoining\b", r"\bconnecting\b",
        r"\bnoise\b", r"\bnoisy\b", r"\bloud\b", r"\bmusic\b", r"\bbar\b"
    ]

    for t in traces:
        if not (t.get("is_room_defect") or t.get("category") == "Room Change Request"):
            continue
        notes_low = str(t.get("notes", "")).lower()
        tags = [str(tg).lower() for tg in t.get("tags", [])]

        assigned = False
        if any(re.search(p, notes_low) for p in tech_patterns) or any(t_g in ["no_hot_water", "water_plumbing", "hvac", "climate"] for t_g in tags):
            dept_counts["Technical Maintenance"] += 1
            assigned = True
        if any(re.search(p, notes_low) for p in hk_patterns) or any(t_g in ["smell", "hygiene", "odor"] for t_g in tags):
            dept_counts["Housekeeping"] += 1
            assigned = True
        if any(re.search(p, notes_low) for p in fo_patterns) or any(t_g in ["view_mismatch", "room_merge", "accessibility", "noise"] for t_g in tags):
            dept_counts["Front Office / Reception"] += 1
            assigned = True

        if not assigned:
            dept_counts["Technical Maintenance"] += 1

    total_dept = sum(dept_counts.values())
    percentages = {
        k: round((v / total_dept * 100.0), 1) if total_dept > 0 else 0.0
        for k, v in dept_counts.items()
    }

    res = dict(dept_counts)
    res.update({
        "counts": dept_counts,
        "percentages": percentages,
        "total_complaints": total_dept
    })
    return res


def compute_dietary_risk_index(
    traces: List[Dict[str, Any]],
    in_house_manifest: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Extracts guest allergy counts categorized by allergen severity and cross-references
    against active in-house reservations for F&B briefing.
    """
    severity_map = {
        "Gluten": "High (Celiac)",
        "Nuts/Peanuts": "High (Anaphylaxis)",
        "Shellfish/Seafood": "High (Anaphylaxis)",
        "Lactose/Dairy": "Moderate",
        "Egg": "Moderate",
        "Mushrooms": "Moderate",
        "Vegan": "Lifestyle",
        "Other / Unspecified": "Low / General"
    }

    allergen_counts: Counter = Counter()
    allergy_traces = [
        t for t in traces
        if "allerg" in str(t.get("category", "")).lower()
        or any(tok in str(t.get("notes", "")).lower() for tokens in ALLERGY_TOKENS.values() for tok in tokens)
    ]

    for t in allergy_traces:
        tokens = extract_allergy_tokens(t.get("notes", ""))
        for tok in tokens:
            allergen_counts[tok] += 1

    in_house_briefing = []
    seen_rooms = set()

    for t in allergy_traces:
        rm = str(t.get("room_number", "")).strip()
        gst = str(t.get("guest_name", "")).strip()
        dep = str(t.get("departure", "")).strip()
        tokens = extract_allergy_tokens(t.get("notes", ""))

        if rm and in_house_manifest:
            matching_ih = any(
                str(b.get("room") or b.get("Room") or b.get("Δωμάτιο") or b.get("room_number") or "").strip() == rm
                for b in in_house_manifest.values() if isinstance(b, dict)
            )
            if not matching_ih:
                continue

        entry_key = f"{rm}_{gst}"
        if entry_key not in seen_rooms and rm:
            seen_rooms.add(entry_key)
            severities = [severity_map.get(tok, "Moderate") for tok in tokens]
            top_severity = "High" if any("High" in s for s in severities) else ("Moderate" if any("Moderate" in s for s in severities) else "Low")
            in_house_briefing.append({
                "room_number": rm,
                "guest_name": gst,
                "allergens": tokens,
                "severity": top_severity,
                "departure": dep,
                "notes": str(t.get("notes", "")).strip()
            })

    high_risk_count = sum(allergen_counts[k] for k in ["Gluten", "Nuts/Peanuts", "Shellfish/Seafood"])
    moderate_risk_count = sum(allergen_counts[k] for k in ["Lactose/Dairy", "Egg", "Mushrooms"])

    counts = dict(allergen_counts)
    counts["Celiac / Gluten"] = counts.get("Gluten", 0)
    counts["Severe Nut / Peanut"] = counts.get("Nuts/Peanuts", 0)
    counts["Dairy / Lactose"] = counts.get("Lactose/Dairy", 0)
    counts["Shellfish"] = counts.get("Shellfish/Seafood", 0)

    return {
        "allergen_counts": dict(allergen_counts),
        "counts": counts,
        "high_risk_count": high_risk_count,
        "moderate_risk_count": moderate_risk_count,
        "total_affected_guests": sum(allergen_counts.values()),
        "active_inhouse_alerts": len(in_house_briefing),
        "in_house_briefing": in_house_briefing,
        "briefing_list": in_house_briefing
    }




def compute_occupancy_normalized_issue_density(
    traces: List[Dict[str, Any]],
    in_house_manifest: Optional[Dict[str, Any]] = None,
    hotel_dataset_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Normalizes incident volume: Total Traces in Block / Occupied Rooms in Block.
    Prevents large accommodation blocks from displaying artificially inflated incident ratings.
    """
    schema = get_hotel_room_schema(hotel_dataset_path)
    block_capacities: Counter = Counter()
    for rm, info in schema.items():
        blk = info.get("block", "")
        if blk:
            block_capacities[blk] += 1

    block_traces: Counter = Counter()
    for t in traces:
        if is_room_issue_trace(t):
            rm = str(t.get("room_number", "")).strip()
            blk, _ = parse_room_block_floor(rm)
            if blk != "Unknown":
                block_traces[blk] += 1

    occupied_by_block: Counter = Counter()
    if in_house_manifest:
        seen_occupied = set()
        for b_data in in_house_manifest.values():
            if isinstance(b_data, dict):
                rm = str(b_data.get("room") or b_data.get("Room") or b_data.get("Δωμάτιο") or b_data.get("room_number") or "").strip()
                if rm and rm not in seen_occupied:
                    seen_occupied.add(rm)
                    blk, _ = parse_room_block_floor(rm)
                    if blk != "Unknown":
                        occupied_by_block[blk] += 1

    all_blocks = sorted(list(set(block_traces.keys()) | set(occupied_by_block.keys()) | set(block_capacities.keys())))

    density_rows = []
    for blk in all_blocks:
        t_cnt = block_traces.get(blk, 0)
        cap = block_capacities.get(blk, 0)
        if cap > 0:
            if in_house_manifest is not None:
                occ = occupied_by_block.get(blk, 0)
                if occ == 0:
                    density_rows.append({
                        "block": blk,
                        "total_traces": t_cnt,
                        "occupied_rooms": 0,
                        "capacity": cap,
                        "density_ratio": None,
                        "capacity_known": True,
                        "occupancy_status": "vacant"
                    })
                else:
                    ratio = round(t_cnt / occ, 3)
                    density_rows.append({
                        "block": blk,
                        "total_traces": t_cnt,
                        "occupied_rooms": occ,
                        "capacity": cap,
                        "density_ratio": ratio,
                        "capacity_known": True,
                        "occupancy_status": "known"
                    })
            else:
                density_rows.append({
                    "block": blk,
                    "total_traces": t_cnt,
                    "occupied_rooms": None,
                    "capacity": cap,
                    "density_ratio": None,
                    "capacity_known": True,
                    "occupancy_status": "unknown"
                })
        else:
            density_rows.append({
                "block": blk,
                "total_traces": t_cnt,
                "occupied_rooms": None,
                "capacity": None,
                "density_ratio": None,
                "capacity_known": False,
                "occupancy_status": "unknown"
            })

    return {
        "block_densities": density_rows,
        "densities": density_rows
    }


def compute_profile_friction_index(
    traces: List[Dict[str, Any]],
    in_house_manifest: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Ratio of trace generation rates segmented by guest classification:
    First-time guests vs. Repeaters vs. VIP tier levels.
    """
    repeater_guests: Set[str] = set()
    vip_guests: Set[str] = set()
    all_guests: Set[str] = set()

    if in_house_manifest:
        for b in in_house_manifest.values():
            if isinstance(b, dict):
                g_name = str(b.get("guest_name") or b.get("Guest") or b.get("Πελάτης") or "").strip().lower()
                if g_name:
                    all_guests.add(g_name)
                    notes_str = str(b.get("notes") or b.get("Remarks") or "").lower()
                    if b.get("is_repeater") or "repeater" in notes_str or "repeat" in notes_str:
                        repeater_guests.add(g_name)
                    if b.get("is_vip") or "vip" in notes_str or "suite" in str(b.get("room_type", "")).lower():
                        vip_guests.add(g_name)

    repeater_traces = 0
    vip_traces = 0
    first_time_traces = 0

    for t in traces:
        g_name = str(t.get("guest_name", "")).strip().lower()
        if g_name:
            all_guests.add(g_name)
        notes_low = str(t.get("notes", "")).lower()

        is_rep = g_name in repeater_guests or "repeater" in notes_low or "repeat" in notes_low
        is_vip = g_name in vip_guests or "vip" in notes_low or "suite" in str(t.get("room_assigned", "")).lower()

        if is_rep:
            repeater_guests.add(g_name)
            repeater_traces += 1
        elif is_vip:
            vip_guests.add(g_name)
            vip_traces += 1
        else:
            first_time_traces += 1

    first_time_guests = all_guests - repeater_guests - vip_guests
    n_first = max(1, len(first_time_guests))
    n_rep = max(1, len(repeater_guests))
    n_vip = max(1, len(vip_guests))

    rate_first = round(first_time_traces / n_first, 2)
    rate_rep = round(repeater_traces / n_rep, 2)
    rate_vip = round(vip_traces / n_vip, 2)

    return {
        "first_time": {"guests": len(first_time_guests), "traces": first_time_traces, "friction_index": rate_first},
        "repeaters": {"guests": len(repeater_guests), "traces": repeater_traces, "friction_index": rate_rep},
        "vips": {"guests": len(vip_guests), "traces": vip_traces, "friction_index": rate_vip}
    }


# =============================================================================
# 15 Visual Analytics Data Aggregation Routines
# =============================================================================

def compute_visual_analytics_data(
    trace_items: List[Dict[str, Any]],
    in_house_manifest: Optional[Dict[str, Any]] = None,
    hotel_dataset_path: Optional[str] = None,
    room_moves_path: Optional[str] = None,
    in_house_csv_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes deterministic statistical aggregations for all required visual analytics charts
    and returns segregated KPI streams for RCR, clear operational traces,
    normalized defect rates, departmental attribution, and dietary briefings.
    """
    # -------------------------------------------------------------------------
    # 1. Tour Operator / Market Mix
    # -------------------------------------------------------------------------
    op_counts: Counter = Counter()
    for t in trace_items:
        op = t.get("tour_operator") or "Direct / Other"
        op_counts[op.strip()] += 1

    # Augment from in-house manifest if trace list has limited operator variance
    if in_house_manifest and sum(op_counts.values()) < 10:
        for b_data in in_house_manifest.values():
            if isinstance(b_data, dict):
                op = b_data.get("Agency") or b_data.get("Χρεώστης") or b_data.get("Market")
                if op:
                    op_counts[op.strip()] += 1

    total_op = sum(op_counts.values())
    tour_operator_mix = []
    other_op_count = 0
    if total_op > 0:
        for op, cnt in op_counts.most_common():
            pct = (cnt / total_op) * 100.0
            if pct < 2.0:
                other_op_count += cnt
            else:
                tour_operator_mix.append({"operator": op, "count": cnt, "percentage": pct})
        if other_op_count > 0:
            pct_other = (other_op_count / total_op) * 100.0
            tour_operator_mix.append({"operator": "Other (<2%)", "count": other_op_count, "percentage": pct_other})

    # -------------------------------------------------------------------------
    # 2. Length of Stay Distribution (1-3, 4-6, 7-13, 14+ nights)
    # -------------------------------------------------------------------------
    stay_bins = {
        "1-3 nights": 0,
        "4-6 nights": 0,
        "7-13 nights": 0,
        "14+ nights": 0
    }
    seen_reservations: Set[str] = set()

    for t in trace_items:
        res_key = f"{t.get('room_number')}_{t.get('guest_name')}_{t.get('arrival')}_{t.get('departure')}"
        if res_key in seen_reservations:
            continue
        seen_reservations.add(res_key)

        arr = t.get("arrival")
        dep = t.get("departure")
        if arr and dep:
            try:
                d_arr = datetime.strptime(arr[:10], "%Y-%m-%d").date()
                d_dep = datetime.strptime(dep[:10], "%Y-%m-%d").date()
                nights = (d_dep - d_arr).days
                if nights <= 0:
                    continue
                if 1 <= nights <= 3:
                    stay_bins["1-3 nights"] += 1
                elif 4 <= nights <= 6:
                    stay_bins["4-6 nights"] += 1
                elif 7 <= nights <= 13:
                    stay_bins["7-13 nights"] += 1
                else:
                    stay_bins["14+ nights"] += 1
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # 3. Room Type Booked vs. Assigned (Upgrade/Downgrade Tracker)
    # -------------------------------------------------------------------------
    if in_house_csv_path and os.path.exists(in_house_csv_path):
        guest_rows = parse_inhouse_csv(in_house_csv_path)
        reservations = group_guest_rows_to_reservations(guest_rows)
    else:
        reservations = []
    room_type_result = compute_room_type_upgrade_downgrade(reservations)

    # -------------------------------------------------------------------------
    # 4. Trace Category Breakdown
    # -------------------------------------------------------------------------
    cat_counts: Counter = Counter()
    for t in trace_items:
        c = t.get("category", "Trace")
        cat_counts[c] += 1

    trace_category_breakdown = [
        {"category": cat, "count": cat_counts[cat]}
        for cat in PRIMARY_TRACE_CATEGORIES if cat_counts[cat] > 0
    ]
    for cat, cnt in cat_counts.most_common():
        if cat not in PRIMARY_TRACE_CATEGORIES:
            trace_category_breakdown.append({"category": cat, "count": cnt})

    # -------------------------------------------------------------------------
    # 5. Room Change Request Reason Tagging
    # -------------------------------------------------------------------------
    rcr_tag_counts: Counter = Counter()
    for t in trace_items:
        if "room change" in t.get("category", "").lower():
            tags = t.get("tags", [])
            if not tags:
                tags = extract_rcr_tags(t.get("notes", ""))
            for tag in tags:
                label = tag.replace("_", " ").title()
                rcr_tag_counts[label] += 1

    rcr_reason_tagging = [
        {"reason": tag, "count": count}
        for tag, count in rcr_tag_counts.most_common()
    ]

    # -------------------------------------------------------------------------
    # 6. Allergy & Dietary Requirement Frequency
    # -------------------------------------------------------------------------
    allergy_counts: Counter = Counter()
    for t in trace_items:
        if "allerg" in t.get("category", "").lower():
            tokens = extract_allergy_tokens(t.get("notes", ""))
            for tok in tokens:
                allergy_counts[tok] += 1

    allergy_frequency = [
        {"allergen": tok, "count": allergy_counts[tok]}
        for tok in ALLERGY_TOKENS.keys() if allergy_counts[tok] > 0
    ]
    if allergy_counts["Other / Unspecified"] > 0:
        allergy_frequency.append({"allergen": "Other / Unspecified", "count": allergy_counts["Other / Unspecified"]})

    # -------------------------------------------------------------------------
    # 7. Strict Repeat-Issue Rooms (Physical Room Defects Exclusively)
    # -------------------------------------------------------------------------
    repeat_issue_rooms = compute_repeat_issue_rooms(trace_items)

    # -------------------------------------------------------------------------
    # 9. Block / Floor Incident Heatmap (Strict Traces & Room Changes Only)
    # -------------------------------------------------------------------------
    density_matrix: Dict[str, Counter] = defaultdict(Counter)
    blocks_set: Set[str] = set()
    floors_set: Set[str] = set(["0", "1", "2"])

    for t in trace_items:
        if not is_room_issue_trace(t):
            continue
        rm = t.get("room_number", "")
        blk, fl = parse_room_block_floor(rm)
        if blk != "Unknown":
            # "Level" (Block 3000) is intentionally counted as Ground.
            fl_norm = "0" if fl in ("0", "Ground", "Level") else ("1" if fl in ("1", "1st") else ("2" if fl in ("2", "2nd") else fl))
            density_matrix[blk][fl_norm] += 1
            blocks_set.add(blk)

    sorted_blocks = sorted(list(blocks_set)) if blocks_set else [
        "1100", "1200", "1300", "1400", "1500", "1600", "1700", "1800", "1900",
        "2000", "3000", "4000", "5000", "6000", "7000", "8000"
    ]
    sorted_floors = ["0", "1", "2"]

    matrix_rows = []
    for blk in sorted_blocks:
        row_counts = [density_matrix[blk][fl] for fl in sorted_floors]
        matrix_rows.append({
            "block": blk,
            "floor_0": row_counts[0],
            "floor_1": row_counts[1],
            "floor_2": row_counts[2],
            "total": sum(row_counts)
        })

    # -------------------------------------------------------------------------
    # 10. Trace Sub-Category Breakdown (Informational vs. Operational Work)
    # -------------------------------------------------------------------------
    trace_subcat_counts: Counter = Counter()
    for t in trace_items:
        if str(t.get("category", "")).strip().lower() == "trace":
            sc = t.get("trace_subcategory") or classify_trace_subcategory(t.get("notes", ""))
            trace_subcat_counts[sc] += 1

    trace_subcategory_breakdown = [
        {"subcategory": sc, "count": trace_subcat_counts[sc]}
        for sc in TRACE_SUBCATEGORIES if trace_subcat_counts[sc] > 0
    ]
    for sc, cnt in trace_subcat_counts.most_common():
        if sc not in TRACE_SUBCATEGORIES:
            trace_subcategory_breakdown.append({"subcategory": sc, "count": cnt})

    # -------------------------------------------------------------------------
    # 11-15. Five New Diagnostic & Risk Metrics
    # -------------------------------------------------------------------------
    trace_room_change_correlation = compute_trace_room_change_correlation(
        trace_items, room_moves_path=room_moves_path, in_house_manifest=in_house_manifest
    )
    occupancy_normalized_issue_density = compute_occupancy_normalized_issue_density(
        trace_items, in_house_manifest=in_house_manifest, hotel_dataset_path=hotel_dataset_path
    )
    profile_friction_index = compute_profile_friction_index(
        trace_items, in_house_manifest=in_house_manifest
    )

    # -------------------------------------------------------------------------
    # Extended Analytical Calculations & Segregated KPI Streams
    # -------------------------------------------------------------------------
    rcr_analytics = compute_rcr_analytics(trace_items, room_moves_path=room_moves_path)
    clear_trace_analytics = compute_clear_trace_analytics(trace_items)
    normalized_block_defect_rate = compute_normalized_block_defect_rate(trace_items, hotel_dataset_path=hotel_dataset_path)
    departmental_attribution = compute_departmental_attribution(trace_items)
    dietary_risk_index = compute_dietary_risk_index(trace_items, in_house_manifest=in_house_manifest)

    return {
        "total_traces": len(trace_items),
        "tour_operator_mix": tour_operator_mix,
        "length_of_stay_dist": stay_bins,
        "room_type_upgrade_downgrade": room_type_result,
        "trace_category_breakdown": trace_category_breakdown,
        "rcr_reason_tagging": rcr_reason_tagging,
        "allergy_dietary_frequency": allergy_frequency,
        "repeat_issue_rooms": repeat_issue_rooms,
        "block_floor_complaint_density": {
            "blocks": sorted_blocks,
            "floors": sorted_floors,
            "matrix": matrix_rows
        },
        "trace_subcategory_breakdown": trace_subcategory_breakdown,
        "trace_room_change_correlation": trace_room_change_correlation,
        "occupancy_normalized_issue_density": occupancy_normalized_issue_density,
        "profile_friction_index": profile_friction_index,
        "rcr_analytics": rcr_analytics,
        "rcr_conversion": rcr_analytics,
        "clear_trace_analytics": clear_trace_analytics,
        "normalized_block_defect_rate": normalized_block_defect_rate,
        "departmental_attribution": departmental_attribution,
        "dietary_risk_index": dietary_risk_index
    }

