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

# Re-export CSV parsing functions from MODULES.offers.csv_parser
from MODULES.offers.csv_parser import (
    identify_digit_type,
    extract_excel_data,
)

# Re-export keyword classification from MODULES.offers.keyword_rules
from MODULES.offers.keyword_rules import (
    classify_order,
)

# Re-export record writing functions from MODULES.offers.records
from MODULES.offers.records import (
    write_arrival_record,
)

# Re-export pipeline functions from MODULES.offers.pipeline
from MODULES.offers.pipeline import (
    duplicate_for_update,
    get_todays_offer_list,
    execute_offers_pipeline,
    get_last_record_failures,
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
    "classify_order",
    "write_arrival_record",
    "duplicate_for_update",
    "get_todays_offer_list",
    "execute_offers_pipeline",
    "get_last_record_failures",
    "generate_word_document",
]
