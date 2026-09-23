"""
Pipeline functions for offer list generation and management.
"""

import os
import glob
import csv
import re
import shutil
import traceback
from datetime import datetime

from MODULES.offers.document import generate_word_document
from MODULES.offers import paths as paths_module


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


def extract_excel_data(csv_path):
    """
    Extract offer-relevant data from a CSV arrivals file.

    Currently uses fixed-column indexing. Returns data for rows that match
    Booking.com or specific keywords in the remarks.

    Args:
        csv_path: Path to the CSV file

    Returns:
        Tuple of (extracted_data, minibar_data) where extracted_data is a list
        of dicts with keys: RoomNo, DepDate, Pax, Order
    """
    csv_path = os.path.abspath(csv_path)
    extracted_data = []

    with open(csv_path, mode='r', encoding='utf-8-sig', errors='ignore') as f:
        rows = list(csv.reader(f, delimiter=';'))

    row_count = len(rows)
    for r in range(row_count):
        row = rows[r]
        next_row = rows[r + 1] if (r + 1) < row_count else []

        col_a = row[0].strip() if len(row) > 0 else ""
        col_e_text = row[4].strip() if len(row) > 4 else ""
        col_i = row[8].strip() if len(row) > 8 else ""
        desc = next_row[0].strip() if len(next_row) > 0 else ""
        dep_date = ""

        if col_e_text:
            date_match = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})", col_e_text)
            if date_match:
                dep_date = f"{int(date_match.group(1)):02d}/{int(date_match.group(2)):02d}"
            else:
                dep_date = col_e_text.strip()

        is_booking = bool(re.search(r"(?i)BOOKING\.COM", col_i))
        is_room = bool(re.match(r"^\d{3,4}$", col_a))

        if is_booking:
            room_no = col_a.split()[0] if (not is_room and col_a) else col_a
            if not room_no: continue
            pax = sum(int(re.sub(r'\D', '', row[c])) for c in range(9, min(15, len(row))) if re.search(r'\d', row[c]))
            extracted_data.append({"RoomNo": room_no, "DepDate": dep_date, "Pax": pax, "Order": "ST"})

        elif is_room:
            if not col_a: continue
            order_str = None
            if re.search(r"(?i)Anniversary|Birthday|Honeymoon|Brthd|VIP", desc): order_str = "HB"
            elif re.search(r"(?i)Fruit", desc): order_str = "ST"

            if order_str:
                pax = sum(int(re.sub(r'\D', '', row[c])) for c in range(9, min(15, len(row))) if re.search(r'\d', row[c]))
                extracted_data.append({"RoomNo": col_a, "DepDate": dep_date, "Pax": pax, "Order": order_str})

    return extracted_data, []


def duplicate_for_update(file_path):
    """
    Create a copy of an offer file for updating, with " UPDATED" suffix.

    Handles multiple updates by appending (N) counter.

    Args:
        file_path: Path to the original file

    Returns:
        Path to the new " UPDATED" variant
    """
    file_path = os.path.abspath(file_path)
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path).replace(".docx", "")
    base_name = re.sub(r" UPDATED(?: \(\d+\))?", "", base_name)

    new_path = os.path.abspath(os.path.join(dir_name, base_name + " UPDATED.docx"))
    counter = 2
    while os.path.exists(new_path):
        new_path = os.path.abspath(os.path.join(dir_name, base_name + f" UPDATED ({counter}).docx"))
        counter += 1

    shutil.copy2(file_path, new_path)
    return new_path


def get_todays_offer_list():
    """
    Find today's base offer list file.

    Searches for files matching today's date pattern in FINAL_FOLDER.
    Returns the file with the most recent modification time.

    Returns:
        Path to today's offer file, or None if not found
    """
    from MODULES import offers_module as facade

    now = datetime.now()
    target_folder = os.path.abspath(os.path.join(facade.FINAL_FOLDER, f"GR OFFERS {now.month}.{now.year}"))
    base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
    search_pattern = os.path.abspath(os.path.join(target_folder, f"{base_name}*.docx"))
    files = glob.glob(search_pattern)
    if not files: return None
    return os.path.abspath(max(files, key=os.path.getmtime))


def execute_offers_pipeline(selected_csvs=None):
    """
    Execute the complete offer list generation pipeline.

    Args:
        selected_csvs: Optional list of CSV file paths to process.
                      If None, auto-discovers CSV files.

    Returns:
        Tuple of (success: bool, message: str, file_path: Optional[str])
    """
    from MODULES import offers_module as facade

    try:
        if not os.path.exists(facade.TEMPLATE_PATH):
            return False, f"Template missing at {facade.TEMPLATE_PATH}", None

        if selected_csvs is not None:
            csv_files = [os.path.abspath(f) for f in selected_csvs]
        else:
            csv_files = [os.path.abspath(f) for f in glob.glob(os.path.join(facade.ARRIVALS_FOLDER, "*.csv"))]
            if len(csv_files) != 1:
                beach_sub = glob.glob(os.path.join(facade.ARRIVALS_FOLDER, "SANDY BEACH", "*.csv"))
                if beach_sub:
                    latest_beach = max(beach_sub, key=os.path.getmtime)
                    csv_files = [os.path.abspath(latest_beach)]
                else:
                    sub_csvs = [os.path.abspath(f) for f in glob.glob(os.path.join(facade.ARRIVALS_FOLDER, "**", "*.csv"), recursive=True)]
                    if len(sub_csvs) == 1:
                        csv_files = sub_csvs

        if len(csv_files) != 1: return False, "MISSING_CSVS", None

        t = identify_digit_type(csv_files[0])
        if t != 4:
            return False, "CSV validation failed.", None

        beach_csv = csv_files[0]
        beach_data, _ = extract_excel_data(beach_csv)
        minibar_data = []

        beach_dir = os.path.abspath(os.path.join(facade.ARRIVALS_FOLDER, "SANDY BEACH"))
        os.makedirs(beach_dir, exist_ok=True)

        dest_beach = os.path.abspath(os.path.join(beach_dir, os.path.basename(beach_csv)))
        if os.path.abspath(beach_csv) != dest_beach:
            shutil.move(beach_csv, dest_beach)
            beach_csv = dest_beach

        all_data = sorted(beach_data, key=lambda x: (not str(x["RoomNo"]).isdigit(), int(x["RoomNo"]) if str(x["RoomNo"]).isdigit() else str(x["RoomNo"])))

        now = datetime.now()
        today_docx = now.strftime("%d/%m")
        year_str = now.strftime("%Y")
        target_folder = os.path.abspath(os.path.join(facade.FINAL_FOLDER, f"GR OFFERS {now.month}.{year_str}"))
        os.makedirs(target_folder, exist_ok=True)

        base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
        final_path = os.path.abspath(os.path.join(target_folder, base_name + ".docx"))

        if os.path.exists(final_path):
            final_path = os.path.abspath(os.path.join(target_folder, base_name + " UPDATED.docx"))
            counter = 2
            while os.path.exists(final_path):
                final_path = os.path.abspath(os.path.join(target_folder, base_name + f" UPDATED ({counter}).docx"))
                counter += 1

        generate_word_document(all_data, minibar_data, today_docx, final_path, year_str)
        return True, "Success: Pipeline complete.", final_path

    except Exception as e:
        error_msg = f"Pipeline Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return False, error_msg, None
