"""
Data Manager Module: Ingestion, State Management, Room-Move Detection & Gatekeeper
===================================================================================
Façade module maintaining 100% backward-compatible API access for all callers.
Delegates to modular packages:
  - MODULES.common.paths_config (canonical paths, directories, and atomic JSON persistence)
  - MODULES.parsing.inhouse_parser (CSV/Excel ingestion, header mapping, loyalty tags, date validation)
  - MODULES.state.hotel_state_manager (master_state, checkouts, room moves, comparison engine)
  - MODULES.admin.database_admin (database purge, room block export)
  - MODULES.gui.gatekeeper_dialog (GatekeeperDialog modal UI)
"""

import os
import sys
from pathlib import Path
from datetime import date
from typing import Dict, List, Tuple, Optional, Any, Union

# -----------------------------------------------------------------------------
# Re-export Path Constants & Filesystem Utilities from MODULES.common
# -----------------------------------------------------------------------------
from MODULES.common.paths_config import (
    BASE_DIR,
    DATABASE_DIR,
    TEMPLATES_DIR,
    OUTPUT_DIR,
    TRASH_DIR,
    TODAYS_LIST_DIR,
    BOOKING_CALLS_DIR,
    PLOT_DIR,
    HOTEL_DATASET_PATH,
    ROOMS_DIR,
    HOTEL_STATE_DIR,
    BOOKING_CALLS_TODAY_DIR,
    CHECKOUT_HISTORY_DIR,
    ROOM_MOVES_DIR,
    SANDY_BEACH_DIR,
    SANDY_BEACH_ARRIVALS_DIR,
    SANDY_BEACH_DEPARTURE_DIR,
    MASTER_STATE_PATH,
    STATE_META_PATH,
    BOOKING_CALLS_TODAY_JSON,
    CHECKOUTS_JSON,
    ROOM_MOVES_JSON,
    ARRIVALS_BEACH_PATH,
    DEPARTURES_BEACH_PATH,
    MASTER_STATE_ROOT_PATH,
    STATE_META_ROOT_PATH,
    CHECKOUTS_TODAY_JSON,
    CHECKOUT_HISTORY_PATH,
    ROOM_MOVES_YESTERDAY_JSON,
    ROOM_MOVES_HISTORY_PATH,
    ROOM_MOVES_LOG_PATH,
    DEFAULT_PROPERTY,
    get_active_property,
    set_active_property,
    get_property_dir,
    get_property_arrivals_path,
    get_property_departures_path,
    resolve_template_path,
    safe_rmtree,
    save_and_archive_json,
    ensure_workspace_directories,
)

# -----------------------------------------------------------------------------
# Re-export Parsing & Date Validation Utilities from MODULES.parsing
# -----------------------------------------------------------------------------
from MODULES.parsing.inhouse_parser import (
    CANONICAL_HEADER_MAP,
    BOOKING_ID_KEYS,
    ROOM_KEYS,
    GUEST_NAME_KEYS,
    ARRIVAL_KEYS,
    DEPARTURE_KEYS,
    EXCLUDED_COLUMNS,
    normalize_booking_dict,
    detect_encoding_and_delimiter,
    process_in_house_rows,
    extract_loyalty_and_repeater_status,
    extract_special_event_matches,
    extract_guest_profile_tags,
    parse_in_house_csv as _parse_in_house_csv_fn,
    parse_in_house_excel as _parse_in_house_excel_fn,
    parse_in_house_file as _parse_in_house_file_fn,
    detect_property_from_file as _detect_property_from_file_fn,
    parse_arrivals_csv as _parse_arrivals_csv_fn,
    extract_inhouse_report_date,
    validate_inhouse_file_date,
)

# -----------------------------------------------------------------------------
# Re-export State Manager from MODULES.state & Room Type Ladder
# -----------------------------------------------------------------------------
from MODULES.state.hotel_state_manager import HotelStateManager
from MODULES.room_type_ladder import (
    ROOM_TYPE_LADDER,
    compare_room_types,
)

# -----------------------------------------------------------------------------
# Re-export Administration & Export Utilities from MODULES.admin
# -----------------------------------------------------------------------------
from MODULES.admin.database_admin import (
    purge_hotel_database as _purge_hotel_database_fn,
    export_room_block_json_data as _export_room_block_json_data_fn,
)

# -----------------------------------------------------------------------------
# Re-export GUI Dialogs from MODULES.gui
# -----------------------------------------------------------------------------
from MODULES.gui.gatekeeper_dialog import (
    GatekeeperDialog,
    run_gatekeeper_if_needed,
)


def __getattr__(name: str):
    if name == "active_property":
        return get_active_property()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value):
    if name == "active_property":
        set_active_property(value)
    else:
        globals()[name] = value


class InHouseDataManager(HotelStateManager):
    """
    Main Data Manager Engine (Façade):
      - Ingests In-House and Arrivals CSV exports for Sandy Beach.
      - Maintains master_state.json and state_metadata.json in DATABASE/HOTEL STATE/.
      - Detects room moves while strictly classifying and excluding room merges.
      - Detects check-outs and records them into checkouts.json.
      - Enforces Gatekeeper sequential in-house synchronization.
    """

    CANONICAL_HEADER_MAP = CANONICAL_HEADER_MAP
    BOOKING_ID_KEYS = BOOKING_ID_KEYS
    ROOM_KEYS = ROOM_KEYS
    GUEST_NAME_KEYS = GUEST_NAME_KEYS
    ARRIVAL_KEYS = ARRIVAL_KEYS
    DEPARTURE_KEYS = DEPARTURE_KEYS
    EXCLUDED_COLUMNS = EXCLUDED_COLUMNS

    _detect_encoding_and_delimiter = staticmethod(detect_encoding_and_delimiter)
    _process_in_house_rows = staticmethod(process_in_house_rows)
    extract_loyalty_and_repeater_status = staticmethod(extract_loyalty_and_repeater_status)
    extract_special_event_matches = staticmethod(extract_special_event_matches)
    extract_guest_profile_tags = staticmethod(extract_guest_profile_tags)

    def parse_in_house_csv(self, file_path: str, property_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Parses an in-house list CSV file."""
        return _parse_in_house_csv_fn(file_path, property_name)

    def parse_in_house_excel(self, file_path: str, property_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Parses an in-house list Excel file (.xlsx or .xls)."""
        return _parse_in_house_excel_fn(file_path, property_name)

    def parse_in_house_file(self, file_path: str, property_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Unified parser accepting .csv, .xlsx, and .xls in-house files."""
        return _parse_in_house_file_fn(file_path, property_name)

    parse_isws_csv = parse_in_house_csv

    def detect_property_from_file(self, file_path: str) -> str:
        """Auto-detects property. Standardized to SANDY BEACH."""
        return _detect_property_from_file_fn(file_path)

    def parse_arrivals_csv(self, file_path: str, property_name: Optional[str] = None) -> Tuple[str, Dict[str, Dict[str, Any]]]:
        """Parses hotel Arrivals CSV export."""
        return _parse_arrivals_csv_fn(file_path, property_name)

    def update_arrivals_state(self, property_name: str, arrivals_dict: Dict[str, Dict[str, Any]]):
        """Updates today_arrivals.json for Sandy Beach."""
        self.save_arrivals_state({"SANDY BEACH": arrivals_dict})

    def purge_hotel_database(self) -> Dict[str, Any]:
        """Purges transient room and guest records from DATABASE/."""
        return _purge_hotel_database_fn()

    def export_room_block_json_data(
        self,
        plot_dir: Optional[Union[str, Path]] = None,
        hotel_dataset_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Exports room block JSON payloads to PLOT/."""
        return _export_room_block_json_data_fn(
            plot_dir=plot_dir,
            hotel_dataset_path=hotel_dataset_path,
            master_state=self.load_master_state()
        )


def purge_hotel_database() -> Dict[str, Any]:
    """Convenience top-level wrapper to purge transient hotel database records."""
    return _purge_hotel_database_fn()


def export_room_block_json_data(
    plot_dir: Optional[Union[str, Path]] = None,
    hotel_dataset_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """Convenience top-level wrapper to export room block JSON payloads to PLOT/."""
    return _export_room_block_json_data_fn(plot_dir, hotel_dataset_path)


__all__ = [
    "BASE_DIR",
    "DATABASE_DIR",
    "TEMPLATES_DIR",
    "OUTPUT_DIR",
    "TRASH_DIR",
    "TODAYS_LIST_DIR",
    "BOOKING_CALLS_DIR",
    "PLOT_DIR",
    "HOTEL_DATASET_PATH",
    "ROOMS_DIR",
    "HOTEL_STATE_DIR",
    "BOOKING_CALLS_TODAY_DIR",
    "CHECKOUT_HISTORY_DIR",
    "ROOM_MOVES_DIR",
    "SANDY_BEACH_DIR",
    "SANDY_BEACH_ARRIVALS_DIR",
    "SANDY_BEACH_DEPARTURE_DIR",
    "MASTER_STATE_PATH",
    "STATE_META_PATH",
    "BOOKING_CALLS_TODAY_JSON",
    "CHECKOUTS_JSON",
    "ROOM_MOVES_JSON",
    "ARRIVALS_BEACH_PATH",
    "DEPARTURES_BEACH_PATH",
    "MASTER_STATE_ROOT_PATH",
    "STATE_META_ROOT_PATH",
    "CHECKOUTS_TODAY_JSON",
    "CHECKOUT_HISTORY_PATH",
    "ROOM_MOVES_YESTERDAY_JSON",
    "ROOM_MOVES_HISTORY_PATH",
    "ROOM_MOVES_LOG_PATH",
    "DEFAULT_PROPERTY",
    "get_active_property",
    "set_active_property",
    "get_property_dir",
    "get_property_arrivals_path",
    "get_property_departures_path",
    "resolve_template_path",
    "safe_rmtree",
    "save_and_archive_json",
    "ensure_workspace_directories",
    "CANONICAL_HEADER_MAP",
    "BOOKING_ID_KEYS",
    "ROOM_KEYS",
    "GUEST_NAME_KEYS",
    "ARRIVAL_KEYS",
    "DEPARTURE_KEYS",
    "EXCLUDED_COLUMNS",
    "normalize_booking_dict",
    "detect_encoding_and_delimiter",
    "process_in_house_rows",
    "extract_loyalty_and_repeater_status",
    "extract_special_event_matches",
    "extract_guest_profile_tags",
    "extract_inhouse_report_date",
    "validate_inhouse_file_date",
    "HotelStateManager",
    "InHouseDataManager",
    "GatekeeperDialog",
    "run_gatekeeper_if_needed",
    "purge_hotel_database",
    "export_room_block_json_data",
    "ROOM_TYPE_LADDER",
    "compare_room_types",
]
