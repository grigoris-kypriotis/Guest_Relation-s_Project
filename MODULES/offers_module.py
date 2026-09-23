"""
Offers Module: Re-export Facade
================================
Maintains 100% backward-compatible API access for all callers.
Delegates to modular subpackage MODULES.offers:
  - MODULES.offers.paths (constants, env loading, task logging)
  - MODULES.offers.document (Word document generation)
  - MODULES.offers.pipeline (CSV parsing, offer list generation, file management)
"""

# Re-export path constants, environment loading, and logging from MODULES.offers.paths
from MODULES.offers.paths import (
    BASE_DIR,
    ARRIVALS_FOLDER,
    FINAL_FOLDER,
    TODAY_LIST_FOLDER,
    TEMPLATE_PATH,
    CHECK_MEMO_TEMPLATE_PATH,
    CAKE_TEMPLATE_PATH,
    CAKE_MEMO_TEMPLATE_PATH,
    log_task,
)

# Re-export document generation from MODULES.offers.document
from MODULES.offers.document import (
    generate_word_document,
)

# Re-export pipeline functions from MODULES.offers.pipeline
from MODULES.offers.pipeline import (
    identify_digit_type,
    extract_excel_data,
    duplicate_for_update,
    get_todays_offer_list,
    execute_offers_pipeline,
)


__all__ = [
    "BASE_DIR",
    "ARRIVALS_FOLDER",
    "FINAL_FOLDER",
    "TODAY_LIST_FOLDER",
    "TEMPLATE_PATH",
    "CHECK_MEMO_TEMPLATE_PATH",
    "CAKE_TEMPLATE_PATH",
    "CAKE_MEMO_TEMPLATE_PATH",
    "log_task",
    "identify_digit_type",
    "extract_excel_data",
    "duplicate_for_update",
    "get_todays_offer_list",
    "execute_offers_pipeline",
    "generate_word_document",
]
