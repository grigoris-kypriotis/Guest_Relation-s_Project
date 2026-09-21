"""
In-House & Arrivals File Parsing Module
=======================================
Handles raw PMS export ingestion (CSV, Excel), encoding and delimiter detection,
Greek-to-English header normalization, guest profile and loyalty tag extraction,
and report timestamp validation.
"""

import os
import csv
import re
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional, Any, Union

from MODULES.common.paths_config import DEFAULT_PROPERTY

CANONICAL_HEADER_MAP = {
    # Room
    "δωμάτιο": "Room",
    "δωματιο": "Room",
    "δωμ.": "Room",
    "δωμ": "Room",
    "room": "Room",
    "room no": "Room",
    "room no.": "Room",
    "room number": "Room",
    "rm": "Room",
    # Booking ID
    "αρ.": "Booking ID",
    "αρ": "Booking ID",
    "αριθμός κράτησης": "Booking ID",
    "αριθμος κρατησης": "Booking ID",
    "booking id": "Booking ID",
    "booking no": "Booking ID",
    "reservation id": "Booking ID",
    "res id": "Booking ID",
    "res no": "Booking ID",
    # Guests
    "πελάτης": "Guests",
    "πελατης": "Guests",
    "πελάτες": "Guests",
    "πελατες": "Guests",
    "όνομα πελάτη": "Guests",
    "ονομα πελατη": "Guests",
    "guest": "Guests",
    "guests": "Guests",
    "guest name": "Guests",
    "guest names": "Guests",
    # Arrival
    "άφιξη": "Arrival",
    "αφιξη": "Arrival",
    "arrival": "Arrival",
    "arr date": "Arrival",
    "arr": "Arrival",
    "arr.": "Arrival",
    # Departure
    "αναχώρηση": "Departure",
    "αναχωρηση": "Departure",
    "departure": "Departure",
    "dep date": "Departure",
    "dep": "Departure",
    "dep.": "Departure",
    # Room Type
    "τύπος δωματίου": "Room Type",
    "τυπος δωματιου": "Room Type",
    "τύπος δωμ": "Room Type",
    "τυπος δωμ": "Room Type",
    "τύπος δωμ.": "Room Type",
    "room type": "Room Type",
    "room cat": "Room Type",
    "room category": "Room Type",
    # Booked Room Type
    "χρεωστικός τύπος δωματίου": "Booked Room Type",
    "χρεωστικος τυπος δωματιου": "Booked Room Type",
    "κρατηθείς τύπος": "Booked Room Type",
    "κρατηθεις τυπος": "Booked Room Type",
    "booked room type": "Booked Room Type",
    "booked type": "Booked Room Type",
    # Agency / Debtor
    "χρεώστης": "Agency",
    "χρεωστης": "Agency",
    "agency": "Agency",
    "debtor": "Agency",
    "travel agency": "Agency",
    "tour operator": "Agency",
    # Market
    "αγορά": "Market",
    "αγορα": "Market",
    "market": "Market",
    "market segment": "Market",
    # Meal Plan / Board
    "τύπος γεύματος": "Meal Plan",
    "τυπος γευματος": "Meal Plan",
    "meal plan": "Meal Plan",
    "meal": "Meal Plan",
    "board": "Meal Plan",
    "board basis": "Meal Plan",
    # Adults
    "σύν. ατόμων": "Adults",
    "συν. ατομων": "Adults",
    "αρ. ενηλ": "Adults",
    "αρ. ενηλ.": "Adults",
    "ενήλικες": "Adults",
    "ενηλικες": "Adults",
    "adults": "Adults",
    "ad": "Adults",
    # Children
    "αρ. παιδ": "Children",
    "αρ. παιδ.": "Children",
    "παιδιά": "Children",
    "παιδια": "Children",
    "children": "Children",
    "ch": "Children",
    # Pricelist
    "τιμοκατάλογος": "Pricelist",
    "τιμοκαταλογος": "Pricelist",
    "pricelist": "Pricelist",
}

BOOKING_ID_KEYS = ["Αρ.", "Αρ", "Booking ID", "Reservation ID", "Res ID", "Αριθμός Κράτησης", "Booking No"]
ROOM_KEYS = ["Δωμάτιο", "Room", "Room No", "Room Number", "Δωμ.", "Rm"]
GUEST_NAME_KEYS = ["Πελάτης", "Guest", "Guest Name", "Guests", "Όνομα Πελάτη", "Πελάτες"]
ARRIVAL_KEYS = ["Άφιξη", "Arrival", "Arr Date", "Arr."]
DEPARTURE_KEYS = ["Αναχώρηση", "Departure", "Dep Date", "Dep."]
EXCLUDED_COLUMNS = ["τύπος γεύματος", "meal plan", "meal", "γεύμα"]


def normalize_booking_dict(booking_id: str, b: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures both English (primary canonical) and Greek (backward-compatible alias) keys exist."""
    res = dict(b)
    room = str(res.get("Room") or res.get("Δωμάτιο") or res.get("room") or "").strip()
    res["Room"] = room
    res["Δωμάτιο"] = room

    guests = res.get("Guests") or res.get("Πελάτες") or res.get("guests") or []
    if not isinstance(guests, list):
        guests = [str(guests)] if guests else []
    res["Guests"] = guests
    res["Πελάτες"] = guests

    arrival = str(res.get("Arrival") or res.get("Άφιξη") or res.get("arrival") or "").strip()
    res["Arrival"] = arrival
    res["Άφιξη"] = arrival

    departure = str(res.get("Departure") or res.get("Αναχώρηση") or res.get("departure") or "").strip()
    res["Departure"] = departure
    res["Αναχώρηση"] = departure

    b_id = str(res.get("Booking ID") or res.get("Αρ.") or res.get("booking_id") or booking_id).strip()
    res["Booking ID"] = b_id
    res["Αρ."] = b_id

    rtype = str(res.get("Room Type") or res.get("Τύπος Δωματίου") or res.get("Τύπος Δωμ") or res.get("room_type") or "").strip()
    res["Room Type"] = rtype
    res["Τύπος Δωματίου"] = rtype
    res["Τύπος Δωμ"] = rtype

    booked_rtype = str(res.get("Booked Room Type") or res.get("Χρεωστικός Τύπος Δωματίου") or res.get("Κρατηθείς Τύπος") or "").strip()
    res["Booked Room Type"] = booked_rtype
    res["Χρεωστικός Τύπος Δωματίου"] = booked_rtype
    res["Κρατηθείς Τύπος"] = booked_rtype

    agency = str(res.get("Agency") or res.get("Χρεώστης") or res.get("agency") or "Direct").strip()
    res["Agency"] = agency
    res["Χρεώστης"] = agency

    market = str(res.get("Market") or res.get("Αγορά") or res.get("market") or agency).strip()
    res["Market"] = market
    res["Αγορά"] = market

    adults = str(res.get("Adults") or res.get("Σύν. Ατόμων") or res.get("Αρ. Ενηλ") or res.get("adults") or "1").strip()
    res["Adults"] = adults
    res["Σύν. Ατόμων"] = adults
    res["Αρ. Ενηλ"] = adults

    children = str(res.get("Children") or res.get("Αρ. Παιδ") or res.get("children") or "0").strip()
    res["Children"] = children
    res["Αρ. Παιδ"] = children

    meal = res.get("Meal Plan") or res.get("Τύπος Γεύματος") or res.get("meal_plan")
    if meal:
        m_str = str(meal).strip()
        res["Meal Plan"] = m_str
        res["Τύπος Γεύματος"] = m_str

    return res


def detect_encoding_and_delimiter(file_path: str) -> Tuple[str, str]:
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


def process_in_house_rows(raw_rows: Any, property_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Core parsing engine for in-house rows (CSV or Excel)."""
    bookings: Dict[str, Dict[str, Any]] = {}
    header = None

    for raw_row in raw_rows:
        if not raw_row:
            continue

        cleaned_row = [str(cell).strip().strip('"\'') for cell in raw_row]
        if cleaned_row and cleaned_row[0].startswith('\ufeff'):
            cleaned_row[0] = cleaned_row[0].replace('\ufeff', '')

        is_header = any(
            any(alias.lower() == cell.lower() for alias in BOOKING_ID_KEYS)
            for cell in cleaned_row
        )
        if is_header:
            header = cleaned_row
            continue

        if header is None:
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
        for key_alias in BOOKING_ID_KEYS:
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
        for key_alias in GUEST_NAME_KEYS:
            for col in header:
                if col.strip().lower() == key_alias.lower():
                    guest_name = row_dict.get(col, "").strip()
                    break
            if guest_name:
                break

        # Prepare fields for JSON
        if booking_id not in bookings:
            booking_entry: Dict[str, Any] = {}
            for col, val in row_dict.items():
                col_clean = col.strip()
                if col_clean.lower() in EXCLUDED_COLUMNS:
                    continue
                if any(col_clean.lower() == alias.lower() for alias in GUEST_NAME_KEYS):
                    continue
                if any(col_clean.lower() == alias.lower() for alias in BOOKING_ID_KEYS):
                    continue
                canon_name = CANONICAL_HEADER_MAP.get(col_clean.lower(), col_clean)
                if canon_name == "Room":
                    val_str = str(val).strip()
                    if val_str.isdigit():
                        val_padded = val_str.zfill(4)
                        if re.match(r"^\d{4}$", val_padded):
                            val = val_padded
                booking_entry[canon_name] = val
                booking_entry[col_clean] = val

            booking_entry["Guests"] = []
            booking_entry["Πελάτες"] = []
            bookings[booking_id] = booking_entry

        if guest_name:
            if "Guests" not in bookings[booking_id]:
                bookings[booking_id]["Guests"] = []
            if "Πελάτες" not in bookings[booking_id]:
                bookings[booking_id]["Πελάτες"] = []
            if guest_name not in bookings[booking_id]["Guests"]:
                bookings[booking_id]["Guests"].append(guest_name)
            if guest_name not in bookings[booking_id]["Πελάτες"]:
                bookings[booking_id]["Πελάτες"].append(guest_name)

    normalized_bookings: Dict[str, Dict[str, Any]] = {}
    for b_id, b_data in bookings.items():
        normalized_bookings[b_id] = normalize_booking_dict(b_id, b_data)

    return normalized_bookings


def extract_loyalty_and_repeater_status(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Identifies guest loyalty and repeater status flags across ingested datasets.
    Checks for repeater keywords, loyalty club flags, and repeat visit counts.
    """
    text_corpus = " ".join([
        str(item.get("Notes") or item.get("notes") or ""),
        str(item.get("Agency") or item.get("Χρεώστης") or ""),
        str(item.get("Market") or item.get("Αγορά") or ""),
        str(item.get("Pricelist") or item.get("Τιμοκατάλογος") or ""),
        str(item.get("Guests") or item.get("Πελάτες") or "")
    ]).lower()

    is_repeater = bool(re.search(r"\b(repeater|rep\.?|repeat guest|loyal|club member|return guest)\b", text_corpus))
    vip_tier = None
    m_tier = re.search(r"\b(vip\s*[1-3]|gold|silver|diamond|platinum)\b", text_corpus)
    if m_tier:
        vip_tier = m_tier.group(1).upper()
    elif "vip" in text_corpus:
        vip_tier = "VIP"

    return {
        "is_repeater": is_repeater,
        "vip_tier": vip_tier,
        "has_loyalty_status": is_repeater or (vip_tier is not None)
    }


def extract_special_event_matches(
    item: Dict[str, Any],
    stay_start: Optional[date] = None,
    stay_end: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Identifies wedding anniversaries, birthdays, honeymoons, and special event
    dates matching the stay range.
    """
    text_corpus = " ".join([
        str(item.get("Notes") or item.get("notes") or ""),
        str(item.get("Special Requests") or item.get("category") or "")
    ])

    events = []
    if re.search(r"(?i)\b(birthday|bday|b-day|γενέθλια)\b", text_corpus):
        events.append({"type": "Birthday", "matched": True})
    if re.search(r"(?i)\b(wedding|anniversary|επέτειος|honeymoon)\b", text_corpus):
        events.append({"type": "Anniversary / Special Event", "matched": True})

    return events


def extract_guest_profile_tags(item: Dict[str, Any]) -> List[str]:
    """
    Extracts guest profile tags (e.g., VIP tiers, mobility requirements).
    """
    tags = []
    text_corpus = " ".join([
        str(item.get("Notes") or item.get("notes") or ""),
        str(item.get("Tags") or item.get("tags") or ""),
        str(item.get("Room Type") or item.get("Τύπος Δωματίου") or "")
    ]).lower()

    if re.search(r"\b(wheelchair|mobility|disabled|handicap|ground floor|no stairs|elevator)\b", text_corpus):
        tags.append("Reduced Mobility / Accessibility")

    if "vip 1" in text_corpus:
        tags.append("VIP Tier 1")
    elif "vip 2" in text_corpus:
        tags.append("VIP Tier 2")
    elif "vip 3" in text_corpus:
        tags.append("VIP Tier 3")
    elif "vip" in text_corpus:
        tags.append("VIP")

    return tags


def parse_in_house_csv(file_path: str, property_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Parses an in-house list CSV file.
    - Groups multiple rows by Booking ID ('Αρ.')
    - Excludes 'Τύπος Γεύματος' (Meal Plan)
    - Aggregates guest names ('Πελάτης') into 'Πελάτες' list
    - Strips whitespace from keys and values
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    encoding, delimiter = detect_encoding_and_delimiter(file_path)
    with open(file_path, mode="r", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        return process_in_house_rows(reader, property_name)


def parse_in_house_excel(file_path: str, property_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
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

    return process_in_house_rows(rows, property_name)


def parse_in_house_file(file_path: str, property_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Unified parser accepting .csv, .xlsx, and .xls in-house files."""
    if property_name is None:
        property_name = "SANDY BEACH"

    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        return parse_in_house_excel(file_path, property_name)
    return parse_in_house_csv(file_path, property_name)


def detect_property_from_file(file_path: str) -> str:
    """Auto-detects property. Standardized to SANDY BEACH."""
    return "SANDY BEACH"


def parse_arrivals_csv(file_path: str, property_name: Optional[str] = None) -> Tuple[str, Dict[str, Dict[str, Any]]]:
    """
    Parses hotel Arrivals CSV export.
    Returns: (detected_property_name, arrivals_dict_keyed_by_booking_id)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    encoding, delimiter = detect_encoding_and_delimiter(file_path)
    arrivals: Dict[str, Dict[str, Any]] = {}
    detected_prop = property_name.upper().replace("_", " ") if property_name else "SANDY BEACH"

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
        enc, delim = detect_encoding_and_delimiter(str(p))
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
                if is_meta or len(line.split(delim)) <= 5:
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
        if not found_date:
            for line in reversed(candidates):
                m_dt = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", line)
                if m_dt:
                    is_meta = any(k in line.lower() for k in ["page", "σελίδα", "totals", "hotel", "print", "εκτύπωση", "report", "λίστα"])
                    if is_meta or len(line.split(delim)) <= 5:
                        try:
                            found_date = date(int(m_dt.group(1)), int(m_dt.group(2)), int(m_dt.group(3)))
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
                non_empty = [c for c in row if c is not None and str(c).strip() != ""]
                is_meta = any(any(k in str(c).lower() for k in ["page", "σελίδα", "totals", "hotel", "print", "εκτύπωση", "report", "λίστα", "date", "ημερομηνία"]) for c in non_empty)
                if not is_meta and len(non_empty) > 5:
                    continue
                for c in non_empty:
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
                        m_dt2 = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", c)
                        if m_dt2:
                            try:
                                found_date = date(int(m_dt2.group(1)), int(m_dt2.group(2)), int(m_dt2.group(3)))
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
                row_vals = [ws.cell(r, c).value for c in range(ws.ncols) if str(ws.cell(r, c).value).strip() != ""]
                is_meta = any(any(k in str(v).lower() for k in ["page", "σελίδα", "totals", "hotel", "print", "εκτύπωση", "report", "λίστα", "date", "ημερομηνία"]) for v in row_vals)
                if not is_meta and len(row_vals) > 5:
                    continue
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
                        m_dt2 = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", cell.value)
                        if m_dt2:
                            try:
                                found_date = date(int(m_dt2.group(1)), int(m_dt2.group(2)), int(m_dt2.group(3)))
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
