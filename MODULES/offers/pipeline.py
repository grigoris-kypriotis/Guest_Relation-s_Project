"""
Pipeline functions for offer list generation and management.
"""

import os
import glob
import re
import shutil
import traceback
from datetime import datetime
from typing import Optional

from MODULES.offers.document import generate_word_document
from MODULES.offers import paths as paths_module
from MODULES.offers.csv_parser import identify_digit_type, extract_excel_data
from MODULES.offers.records import write_arrival_record
from MODULES.state.hotel_state_manager import HotelStateManager

# Module-level storage for last pipeline record write failures
# Format: list of (booking_id, error_message) tuples
_last_record_failures = []


def get_last_record_failures():
    """Return the list of record write failures from the last pipeline run."""
    global _last_record_failures
    return _last_record_failures.copy()


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


def resolve_todays_offer_file(offer_lists_dir: Optional[str] = None) -> Optional[str]:
    """
    Deterministically resolves today's offer list file, preferring the highest-numbered
    ' UPDATED' variant over the base file when one exists — never by mtime (duplicate_for_update
    uses shutil.copy2 which preserves source mtime, making mtime-based selection unreliable).

    Args:
        offer_lists_dir: Optional directory to search in. If None, falls back to today's
                        FINAL_FOLDER-based logic (FINAL_FOLDER/GR OFFERS {month}.{year}).

    Returns:
        Path to today's offer file (preferring highest UPDATED variant), or None if not found.
    """
    from MODULES import offers_module as facade

    now = datetime.now()

    # Determine target folder
    if offer_lists_dir is None:
        # Fall back to original get_todays_offer_list logic
        target_folder = os.path.abspath(os.path.join(facade.FINAL_FOLDER, f"GR OFFERS {now.month}.{now.year}"))
    else:
        target_folder = os.path.abspath(offer_lists_dir)

    # Glob for today's files
    base_name = f"OFFER LIST ({now.strftime('%Y-%m-%d')})"
    search_pattern = os.path.abspath(os.path.join(target_folder, f"{base_name}*.docx"))
    files = glob.glob(search_pattern)

    if not files:
        return None

    # Partition into base vs UPDATED variants
    base_file = None
    updated_files = {}  # counter -> filepath mapping

    for filepath in files:
        filename = os.path.basename(filepath)

        # Check if it's the exact base file
        if filename == f"{base_name}.docx":
            base_file = filepath
        else:
            # Check if it's an UPDATED variant
            # Pattern: "OFFER LIST (YYYY-MM-DD) UPDATED.docx" or "OFFER LIST (YYYY-MM-DD) UPDATED (N).docx"
            match = re.search(r' UPDATED(?: \((\d+)\))?\.docx$', filename)
            if match:
                counter_str = match.group(1)
                counter = int(counter_str) if counter_str else 1
                updated_files[counter] = filepath

    # Prefer UPDATED variants by highest counter
    if updated_files:
        highest_counter = max(updated_files.keys())
        return updated_files[highest_counter]

    # Fall back to base file
    if base_file:
        return base_file

    # Shouldn't normally reach here (since files list is not empty), but be defensive
    if files:
        return files[0]

    return None


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

        # Write arrival records for each entry in all_arrivals (idempotent, non-blocking)
        global _last_record_failures
        _last_record_failures = []
        hsm = HotelStateManager()
        for arrival in all_arrivals:
            try:
                write_arrival_record(arrival, hsm)
            except Exception as e:
                booking_id = arrival.get("booking_id", "?")
                _last_record_failures.append((booking_id, str(e)))

        # Build success message, appending note if there were record failures
        success_msg = "Success: Pipeline complete."
        if _last_record_failures:
            failure_count = len(_last_record_failures)
            success_msg += f" ({failure_count} record write failures — see log)"

        return True, success_msg, final_path

    except Exception as e:
        error_msg = f"Pipeline Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return False, error_msg, None
