"""
MODULES Package: Core business logic, data models, and backend components
for the Guest Relation Workspace application.
"""

import sys
import os

# Ensure the workspace root is always in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from MODULES.data_manager import (
    InHouseDataManager,
    HotelStateManager,
    GatekeeperDialog,
    purge_hotel_database,
    export_room_block_json_data,
    ensure_workspace_directories,
    resolve_template_path,
    save_and_archive_json,
    BASE_DIR as WORKSPACE_DIR,
    DATABASE_DIR,
    TEMPLATES_DIR,
    OUTPUT_DIR,
    TRASH_DIR,
    BOOKING_CALLS_DIR,
    PLOT_DIR,
    HOTEL_DATASET_PATH,
    MASTER_STATE_PATH,
    STATE_META_PATH,
    BOOKING_CALLS_TODAY_JSON,
    CHECKOUTS_JSON,
    ROOM_MOVES_JSON,
)
from MODULES.booking_calls import (
    BookingCallsManager,
    BookingCallsWidget,
    CALL_STATUSES,
)
from MODULES.offers_module import (
    log_task,
)
from MODULES.plot_viewer import (
    PlotGraphWindow,
)

__all__ = [
    "InHouseDataManager",
    "HotelStateManager",
    "GatekeeperDialog",
    "purge_hotel_database",
    "export_room_block_json_data",
    "ensure_workspace_directories",
    "resolve_template_path",
    "save_and_archive_json",
    "WORKSPACE_DIR",
    "DATABASE_DIR",
    "TEMPLATES_DIR",
    "OUTPUT_DIR",
    "TRASH_DIR",
    "BOOKING_CALLS_DIR",
    "PLOT_DIR",
    "HOTEL_DATASET_PATH",
    "MASTER_STATE_PATH",
    "STATE_META_PATH",
    "BOOKING_CALLS_TODAY_JSON",
    "CHECKOUTS_JSON",
    "ROOM_MOVES_JSON",
    "BookingCallsManager",
    "BookingCallsWidget",
    "CALL_STATUSES",
    "log_task",
    "PlotGraphWindow",
]

