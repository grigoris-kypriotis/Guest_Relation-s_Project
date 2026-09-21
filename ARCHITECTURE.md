# ARCHITECTURE.md

## 1. PROJECT OVERVIEW
Guest Relation Workspace is a Windows desktop management and CRM application tailored for hospitality guest relations workflows at Sandy Beach resort. It ingests daily Property Management System (PMS) exports (In-House lists, Arrivals, Traces) to maintain live hotel state, track room moves and departures, and compute guest satisfaction and physical defect analytics. The system also automates operational workflows including stay-based Booking.com follow-up scheduling, Word offer list/cake memo generation, and Outlook email drafting.

---

## 2. TECH STACK
- **Language**: Python 3.10+
- **GUI Framework**: PyQt6 (QMainWindow, QStackedWidget, QGraphicsScene/View, custom QWidget panels)
- **Data & File Processing**: JSON (flat-file database), CSV (`csv`), Excel (`openpyxl`, `xlrd`)
- **Document & Office Automation**: `python-docx` (Word generation), `pywin32` / `pythoncom` (COM/ActiveX embedding and Outlook integration)
- **Visualization**: `matplotlib` (embedded FigureCanvas in PyQt6 for visual analytics and resort graphs)
- **Database**: Flat-file JSON store under `DATABASE/` and `ROOMS/` (no SQL/relational database)

---

## 3. FOLDER STRUCTURE
```
.
├── app.py                      # Main desktop application shell, navigation, and signal routing
├── requirements.txt            # Python dependencies (PyQt6, python-docx, pywin32, openpyxl, matplotlib, xlrd)
├── MODULES/                    # Core business logic, PMS ingestion, trace analytics, and scheduling engines
│   ├── common/                 # Canonical paths, directory management, and atomic JSON persistence (paths_config.py)
│   ├── parsing/                # In-house CSV/Excel parsing, Greek header normalization, and independent CSV reader
│   │   ├── inhouse_parser.py   # Primary PMS parser, Greek header canonicalization, and date validation
│   │   └── inhouse_csv_reader.py # Independent safety-net CSV reader with per-page header re-derivation
│   ├── state/                  # Master state persistence, checkouts history, and room move tracking (hotel_state_manager.py)
│   ├── admin/                  # Database purge operations and room block JSON dataset exports (database_admin.py)
│   ├── gui/                    # PyQt6 Gatekeeper modal dialog for sequential startup ingestion (gatekeeper_dialog.py)
│   ├── data_manager.py         # Top-level façade re-exporting modules and hosting InHouseDataManager
│   ├── analytics_registry.py   # Keyed ChartSpec registry and lens metadata for the Visual Analytics Suite
│   ├── room_type_ladder.py     # Official room type ladder and upgrade/downgrade comparison engine
│   ├── room_type_upgrade_downgrade.py # Room type upgrade/downgrade aggregation, agency & block breakdown
│   ├── booking_calls.py        # Booking.com CRM business logic, schedule algorithm, and Excel I/O
│   ├── trace_analytics.py      # Trace note parsing, taxonomy classification, and KPI aggregation
│   ├── plot_viewer.py          # Interactive resort node graph visualizer and Matplotlib chart engine
│   └── offers_module.py        # Arrivals CSV parsing, Word offer list generation, and Outlook automation
├── OPTIONS/                    # PyQt6 UI view widgets registered in the menu dispatch system
├── DATABASE/                   # Centralized flat-file JSON storage for hotel state, history, and calls
│   ├── HOTEL STATE/            # Single source of truth: master_state.json and state_metadata.json
│   ├── BOOKING CALLS FOR TODAY/# Daily scheduled calls payload (booking_calls_for_today.json)
│   ├── CHECK OUT HISTORY/      # Historical check-out records (checkouts.json)
│   ├── ROOM MOVES/             # Historical room move records (room_moves.json)
│   └── SANDY BEACH/            # Arrivals and departures cache for Sandy Beach
├── BOOKING CALLS/              # Working directory containing active BOOKING CALLS.xlsx
├── ROOMS/                      # 680+ room-specific JSON files tracking physical room state and historical traces
├── PLOT/                       # Resort map block data, room coordinates, and HotelDataSet.json
├── TEMPLATES/                  # Master blank templates (.docx, .xlsx) for memos, offer lists, and calls
├── OUTPUT/                     # Generated documents (CAKE_MEMOS/, OFFERS/, TODAYS_LIST/)
├── DATA_BACKUP/                # Backup archive of processed raw In-House CSV files
├── TRASH/                      # Processed and timestamp-archived CSV files
└── TESTS/                      # Automated unittest test suite covering ingestion, scheduling, and UI
```

---

## 4. MODULE MAP

### Application Core & Shell
- **[app.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/app.py)**
  - *Responsibility*: Thin orchestration shell; hosts sidebar navigation, stacked widget dispatch, COM message pump, and cross-module signal routing.
  - `GuestRelationApp`: Main QMainWindow wiring navigation buttons, submenus, COM pump, and global signals.
  - `select_category`: Dispatches category activation to registered QWidget panels.

### Backend & Engines (`MODULES/`)
- **[MODULES/data_manager.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/data_manager.py)**
  - *Responsibility*: Top-level façade maintaining 100% backward compatibility; re-exports all constants, classes, and utilities; hosts `InHouseDataManager` which delegates to specialized subpackages.
  - `InHouseDataManager`: Unified interface orchestrating parsing, state management, and database administration.
- **[MODULES/common/paths_config.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/common/paths_config.py)**
  - *Responsibility*: Centralized filesystem topology, directory creation, path resolution, and atomic JSON persistence.
  - `ensure_workspace_directories`: Initializes canonical directory structure and cleans up legacy mirrors.
  - `resolve_template_path`: Locates document templates within `TEMPLATES/` with fallback logic.
  - `save_and_archive_json`: Synchronous and atomic JSON persistence via temporary file replacement.
  - `get_active_property` / `set_active_property`: Single source of truth for runtime active property state.
- **[MODULES/parsing/inhouse_parser.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/parsing/inhouse_parser.py)**
  - *Responsibility*: Raw PMS CSV/Excel parsing, Greek header canonicalization, guest profile and loyalty tag extraction, and report date validation.
  - `parse_in_house_file` / `parse_in_house_csv` / `parse_in_house_excel`: In-house list parsing with multi-guest aggregation per booking ID.
  - `parse_arrivals_csv`: Parses daily arrivals CSV exports and extracts notes/room information.
  - `extract_inhouse_report_date` / `validate_inhouse_file_date`: Validates report operational dates from internal headers and timestamps.
- **[MODULES/parsing/inhouse_csv_reader.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/parsing/inhouse_csv_reader.py)**
  - *Responsibility*: Independent cp1253 semicolon-delimited CSV parser with per-page header re-derivation, room number validation (dropping empty, non-numeric, and 3-digit room values), and reservation-level guest row grouping.
  - `parse_inhouse_csv`: Reads multi-page CSV, dynamically mapping columns on every "Δωμάτιο" header row.
  - `group_guest_rows_to_reservations`: Groups guest rows by booking ID, preserving first-row metadata and pax.
- **[MODULES/state/hotel_state_manager.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/state/hotel_state_manager.py)**
  - *Responsibility*: Master state persistence, checkouts history, room move detection excluding merges, and missing sync date computation.
  - `HotelStateManager`: Core state persistence and comparison engine.
  - `compare_and_update`: Compares new in-house data against previous state, detects checkouts, checkins, and standard room moves while strictly excluding room merges.
  - `get_missing_dates`: Computes missing dates requiring sequential synchronization.
- **[MODULES/admin/database_admin.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/admin/database_admin.py)**
  - *Responsibility*: Database maintenance, transient state reset, and room block JSON dataset exports for the plot viewer.
  - `purge_hotel_database`: Clears transient guest and room data from `DATABASE/` and `ROOMS/` while preserving schema.
  - `export_room_block_json_data`: Generates block and floor occupancy metrics for `PLOT/`.
- **[MODULES/gui/gatekeeper_dialog.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/gui/gatekeeper_dialog.py)**
  - *Responsibility*: Presentation layer for startup synchronization; enforces sequential ingestion of missing daily in-house files.
  - `GatekeeperDialog`: Blocking modal PyQt6 dialog guiding users through missing date CSV loading.
  - `run_gatekeeper_if_needed`: Checks for missing sync dates and invokes `GatekeeperDialog` before workspace access.
- **[MODULES/booking_calls.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/booking_calls.py)**
  - *Responsibility*: Booking.com CRM business logic, stay-based calling schedule algorithm, and direct Excel read/write operations.
  - `BookingCallsManager`: Schedules calls, updates `BOOKING CALLS.xlsx`, and generates today's calls JSON.
  - `BookingCallsWidget`: Interactive CRM widget displaying room call cards with click-only status dropdowns.
  - `calculate_call_schedule`: Pure algorithm implementing the 4 calling rules ($A+1$, $D-1$, every other day, discard consecutive).
  - `is_booking_com`: Predicate strictly filtering for reservations where the agent is `BOOKING.COM`.
- **[MODULES/analytics_registry.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/analytics_registry.py)**
  - *Responsibility*: Keyed operational chart specifications and lens filter metadata for the Visual Analytics Suite.
  - `ChartSpec`: Frozen metadata dataclass (`key`, `title`, `subtitle`, `icon`, `lenses`, `render_attr`).
  - `CHART_REGISTRY`: Ordered sequence of the 12 canonical operational chart specifications.
  - `get_spec`: O(1) spec resolver raising `KeyError` on unrecognized chart keys.
- **[MODULES/room_type_ladder.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/room_type_ladder.py)**
  - *Responsibility*: Official resort room category hierarchy (`ROOM_TYPE_LADDER`) and deterministic upgrade/downgrade evaluation (`compare_room_types`).
- **[MODULES/room_type_upgrade_downgrade.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/room_type_upgrade_downgrade.py)**
  - *Responsibility*: In-house reservation room category discrepancy analysis, exact-match/upgrade/downgrade counting, all-8 ladder code distributions, per-agency breakdowns, per-block breakdowns, and unrecognized room code data issue tracking.
  - `compute_room_type_upgrade_downgrade`: Computes upgrade/downgrade metrics, enforcing invariant identity and omitting 'unknown' bucket.
- **[MODULES/trace_keywords.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/trace_keywords.py)**
  - *Responsibility*: Deterministic keyword taxonomies, regex defect tag patterns, allergy tokens, 3-lens filter definitions, and room issue filtration (`is_room_issue_trace`).
- **[MODULES/room_change_detector.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/room_change_detector.py)**
  - *Responsibility*: Room change request resolution cross-referencing against PMS moves (`compute_rcr_analytics`), repeat-issue room computation with guest pattern identification (`compute_repeat_issue_rooms`), and trace precedence correlation (`compute_trace_room_change_correlation`).
- **[MODULES/trace_analytics.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/trace_analytics.py)**
  - *Responsibility*: Trace note parsing, deterministic taxonomy classification, in-house data fusion, and resort KPI computation.
  - `fuse_inhouse_and_traces`: Integrates in-house guest data with raw PMS traces and updates `ROOMS/*.json`.
  - `classify_trace`: Deterministically classifies notes into Physical Room Defects vs. Operational Service Traces.
  - `compute_visual_analytics_data`: Aggregates all KPI metrics (RCR rates, defect densities, friction indices, risk queues).
  - `generate_room_json_mappings`: Idempotently updates individual room records in `ROOMS/`.
- **[MODULES/plot_viewer.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/plot_viewer.py)**
  - *Responsibility*: Interactive resort node graph visualizer and Matplotlib visual analytics chart engine.
  - `PlotViewerWidget`: Embeddable QGraphicsView displaying connected resort block/room nodes with hover/click inspection.
  - `TraceAnalyticsPlotEngine`: Implements 13 modular Matplotlib chart rendering methods (heatmaps, defect densities, friction indices).
  - `ResortNodeItem`: Interactive graph node with hover glow and room metadata inspection.
- **[MODULES/offers_module.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/MODULES/offers_module.py)**
  - *Responsibility*: Single beach arrivals CSV parsing, Word offer list document generation, and Outlook email draft automation.
  - `execute_offers_pipeline`: Orchestrates single beach arrivals CSV data extraction, VIP/order parsing, and `.docx` creation.
  - `generate_word_document`: Populates Word template tables using `python-docx`.
  - `draft_email_payload`: Generates an Outlook draft email with the generated document attached via COM.

### UI Panels (`OPTIONS/`)
- **[OPTIONS/_shared_widgets.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/_shared_widgets.py)**: Shared UI infrastructure (`Sidebar`, `OfficeViewer` for ActiveX document embedding, `TaskWidget` for todo items, `ChartCardWidget` for Matplotlib cards).
- **[OPTIONS/configuration_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/configuration_option.py)**: System configuration UI (`ConfigurationWidget`) managing `app_settings.json`, manual in-house loading, and database purging.
- **[OPTIONS/stats_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/stats_option.py)**: Operational dashboard (`StatsWidget`, `ResortStatsDialog`) displaying live metrics and embedding `TraceAnalyticsPlotEngine` charts.
- **[OPTIONS/manifest_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/manifest_option.py)**: Guest manifest data table (`ManifestWidget`) decoupled from analytics.
- **[OPTIONS/moves_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/moves_option.py)**: Room move inspection view (`MovesWidget`) reading from `room_moves.json`.
- **[OPTIONS/todo_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/todo_option.py)**: Task management view (`TodoWidget`) supporting status cycling and automated task ingestion.
- **[OPTIONS/offers_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/offers_option.py)**: Document viewer container (`OffersOptionWidget`) hosting `OfficeViewer` for offer lists.
- **[OPTIONS/cake_memo_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/cake_memo_option.py)**: Cake memo document editor and Outlook draft dispatcher (`CakeMemoOptionWidget`).
- **[OPTIONS/booking_calls_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/booking_calls_option.py)**: Navigation wrapper (`BookingCallsOptionWidget`) hosting `BookingCallsWidget`.
- **[OPTIONS/system_data_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/system_data_option.py)**: Raw JSON database inspector (`SystemDataOptionWidget`) for viewing state files.
- **[OPTIONS/logs_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/logs_option.py)**: Centralized tabbed audit logging panel (`LogsWidget`).
- **[OPTIONS/allergies_option.py](file:///c:/Users/grigo/OneDrive/Υπολογιστής/underconstruction/GuestRelation_Workspace_Files/OPTIONS/allergies_option.py)**: Placeholder view (`AllergiesWidget`) for future dietary/allergy processing.

---

## 5. DATA FLOW

1. **Daily In-House Ingestion & State Update**:
   - **Entry**: `GatekeeperDialog` (startup) or `ConfigurationWidget.load_inhouse_list()`.
   - **Processing**: `InHouseDataManager.parse_in_house_file()` parses CSV/Excel -> groups multiple guests by booking ID -> compares against `DATABASE/HOTEL STATE/master_state.json`.
   - **Storage/Output**: Detects room moves -> writes to `DATABASE/ROOM MOVES/room_moves.json`; detects checkouts -> writes to `DATABASE/CHECK OUT HISTORY/checkouts.json`; overwrites `master_state.json` & `state_metadata.json`; moves raw file to `TRASH/` and copies to `DATA_BACKUP/`.

2. **Trace Analytics & Room Data Fusion**:
   - **Entry**: Trace files scanned in `DATABASE/` -> `parse_trace_file()`.
   - **Processing**: `classify_trace()` categorizes into Physical Defects vs. Operational Services -> `fuse_inhouse_and_traces()` joins traces with active guest state.
   - **Storage/Output**: Writes/updates individual `ROOMS/<room_number>.json` records -> `compute_visual_analytics_data()` calculates KPIs -> `TraceAnalyticsPlotEngine` renders charts into `StatsWidget`.

3. **Booking Calls CRM & Follow-Up**:
   - **Entry**: `BookingCallsWidget.sync_and_refresh()`.
   - **Processing**: `BookingCallsManager` filters `master_state.json` strictly for `BOOKING.COM` -> `calculate_call_schedule()` computes call dates.
   - **Storage/Output**: Writes schedule to `BOOKING CALLS/BOOKING CALLS.xlsx` (`FOLLOW UP` sheet) -> saves today's calls to `DATABASE/BOOKING CALLS FOR TODAY/booking_calls_for_today.json` -> user logs status/notes -> emits `feedback_submitted` signal -> creates task in `TodoWidget` and updates cell in `BOOKING CALLS.xlsx`.

4. **Document Generation & Dispatch (Offers / Cake Memos)**:
   - **Entry**: User clicks Create/Update in `OffersOptionWidget` or `CakeMemoOptionWidget`.
   - **Processing**: Ingests arrivals CSV or reads Word template -> populates tables using `python-docx` -> saves `.docx` to `OUTPUT/`.
   - **Storage/Output**: Loads document into embedded `OfficeViewer` -> on "SAVE & CLOSE", triggers COM automation to create an Outlook email draft and logs completion to `TodoWidget`.

---

## 6. KEY CONVENTIONS
- **Option Panel Interface**: Every option widget in `OPTIONS/` inherits from `QWidget`, is registered in `OPTION_REGISTRY` (`OPTIONS/__init__.py`), and must expose an `activate()` method called upon selection.
- **Naming Patterns**:
  - Files: `snake_case.py` (e.g., `data_manager.py`, `moves_option.py`).
  - Classes: `PascalCase` (e.g., `InHouseDataManager`, `BookingCallsWidget`).
  - Constants & Paths: `UPPER_CASE` (e.g., `DATABASE_DIR`, `MASTER_STATE_PATH`).
  - Signal handlers: `handle_<event>` or `on_<event>` (e.g., `handle_booking_feedback_to_todo`).
- **Data Persistence**: Exclusively flat-file JSON. No relational DB or ORM. JSON updates use atomic writes or standard `json.dump(..., indent=2)`.
- **Error Handling**: Defensive, non-crashing GUI approach. File I/O, parsing, and COM automation are wrapped in `try...except` blocks with errors routed to `LogsWidget` / `DATABASE/system.log` or displayed via `QMessageBox`.
- **Testing Approach**: Python `unittest` suite located in `TESTS/` (`test_*.py`). Tests execute against temporary directories or mock state without requiring a live GUI or PMS.

---

## 7. KNOWN COMPLEXITY / GOTCHAS
- **Monolithic Oversized Modules**: Several core files are large and mix UI with business logic (`data_manager.py` 280 lines [modularized facade], `trace_analytics.py` ~1796 lines, `plot_viewer.py` ~1920 lines, `stats_option.py` ~1642 lines, `configuration_option.py` ~1164 lines). *Any modifications must respect the incremental file splitting rule (<300-400 lines).*
- **COM & Windows Dependency**: `OfficeViewer` and Outlook email drafting rely heavily on `pywin32` (`win32com.client`, `pythoncom`). A 500ms COM message pump (`pythoncom.PumpWaitingMessages()` in `app.py`) is required to prevent UI lockups; embedded viewing requires Microsoft Office on Windows.
- **Greek vs. English PMS Headers**: PMS CSV exports use Greek headers (`"Αρ."`, `"Πελάτης"`, `"Τύπος Γεύματος"`, `"Δωμάτιο"`) that must be mapped to normalized English fields. Any variation in PMS column names breaks parsing unless updated in header normalization dictionaries in `data_manager.py` and `trace_analytics.py`.
- **Strict Booking.com Rule Constraints**: `booking_calls.py` must strictly process reservations where the travel agent is `BOOKING.COM` (case-insensitive string match) and must only write to the `FOLLOW UP` sheet in `BOOKING CALLS.xlsx` (never Sheet 1). The 4-rule scheduling algorithm must discard the earlier date when two call dates are consecutive.
- **Room Moves vs. Merges**: `data_manager.py` implements complex comparison logic to avoid false positives: room moves track individual booking IDs moving between rooms, while room merges (multiple records merged under one room) are explicitly excluded from move logs.
- **680+ Room JSON Files**: `ROOMS/<room_number>.json` are updated individually during trace fusion. High file I/O overhead exists if bulk updates are performed without idempotency checks.

---

## 8. RESORT LAYOUT RULES
Source of truth: PLOT/HotelDataSet.json, 16 main-hotel blocks, 711 rooms; every block's total_rooms equals its expanded ranges.
Room numbers are 4 digits. Block = first two digits + 00 below 2000, first digit + 000 from 2000. Any non-4-digit number parses as Unknown and is excluded from all analytics.
Floor: blocks 1100, 1200, 1400-1900 use the 3rd digit (0 Ground, 1 1st, 2 2nd); Block 1300 uses an explicit range table; Block 2000 uses D2 // 2; Blocks 4000 and 5000 use D2 % 2 (Ground/1st only); Blocks 6000, 7000, 8000 use D2 directly; Block 3000 is a single "Level".
The complaint heatmap intentionally folds "Level" into Ground.
Known data note: room-type counts (types) for Blocks 1300, 7000, 8000 do not sum to total_rooms; trace_analytics.py does not use them.
