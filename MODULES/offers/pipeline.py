"""
Pipeline functions for offer list generation and management.
"""

import os
import glob
import re
import shutil
import traceback
from datetime import datetime

from MODULES.offers.document import generate_word_document
from MODULES.offers import paths as paths_module
from MODULES.offers.csv_parser import identify_digit_type, extract_excel_data


def _get_file_creation_date(file_path: str):
    """
    Get the creation date of a file.

    Returns a datetime.date object representing the file's creation time.
    This is extracted as a separate function to allow easy mocking in tests.
    """
    return datetime.fromtimestamp(os.path.getctime(file_path)).date()


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

        csv_ctime = _get_file_creation_date(csv_files[0])
        if csv_ctime != datetime.now().date():
            return False, f"Arrivals CSV is not today's file (created {csv_ctime.strftime('%Y-%m-%d')}).", None

        beach_csv = csv_files[0]
        beach_data, _, all_arrivals = extract_excel_data(beach_csv)
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
