# Guest Relation Workspace

A comprehensive desktop management and CRM application designed for hospitality guest relation workflows. Built with Python, PyQt6, and Windows integration.

## Key Modules & Features

- **Autonomous Data Ingestion & State Management (`data_manager.py`)**:
  - Centralized database storage inside `DATABASE/` (`master_state.json`, `state_metadata.json`).
  - Consolidated history files saved directly in `DATABASE/` (`check_out_history.json`, `room_moves_history.json`).
  - Property arrivals segmentation for `SANDY BEACH` and `SANDY VILLAS`.
  - Daily scheduled booking calls folder: `DATABASE/booking calls for today/`.
  - Automated directory sorting and cleanup routine for temporary/obsolete Python files.

- **The Gatekeeper (Startup In-House Validation)**:
  - Validates that daily in-house data is up to date from the last processed date to today.
  - Blocking modal dialog (`GatekeeperDialog`) with manual CSV browse/upload capability that blocks access to the main interface until all dates are sequentially satisfied.
  - Automatic CSV archiving into `TRASH/` after ingestion.

- **Internal Memory & Comparison Engine**:
  - `master_state.json` serves as the single source of truth for in-house guests keyed by Booking ID (`"Αρ."`).
  - Excludes `"Τύπος Γεύματος"` (meal plan) column and groups multiple guests (`"Πελάτης"`) into a `"Πελάτες"` array.
  - Autonomous comparison engine detecting Room Moves, Check-outs, and Check-ins.

- **BOOKING CALLS CRM Module (`booking_calls.py`)**:
  - **Strict Agency Filtering**: Exclusively processes reservations where the travel agent is strictly `BOOKING.COM`.
  - **Target Follow-Up Sheet**: Reads and writes schedule data strictly to the `FOLLOW UP` / `FOLLOW UP 1` sheet in `BOOKING CALLS/BOOKING CALLS.xlsx` (never writes to Sheet 1).
  - **Calling Schedule Algorithm**:
    - Rule 1: Call 1 day after arrival ($A+1$).
    - Rule 2: Call 1 day prior to departure ($D-1$).
    - Rule 3: Call every other day in between.
    - Rule 4: Never schedule two consecutive days. If consecutive, strictly discard the earlier date and preserve the later date.
  - **Non-Sensitive Click-Only UI**: Status dropdowns disable mouse-wheel scrolling and trigger updates strictly on explicit user clicks (`activated` signal).
  - **Standardized Statuses**: 6 status options: `Green`, `Red`, `Yellow`, `N/A (NO ANSWER)`, `N/E (NO ENGLISH)`, `N/W (LINE NOT WORKING)`.
  - **Feedback Integration**: Typing feedback automatically captures and generates an item on the To Do List formatted exactly as:
    `Feedback on exclusivi: [comment text] - Room [room number]`.
  - **Task Completion & Logging**: Marking a task completed (`✅`) immediately removes it from the active To Do List UI and permanently preserves it in the system audit logs.

- **Offers Processing Pipeline (`1. OFFERS`)**:
  - Automatic parsing and processing of hotel arrivals CSV datasets (`SANDY BEACH` and `SANDY VILLAS`).
  - Native Word document generation (`python-docx` and COM automation) from custom templates.
  - In-app embedded document viewer (`OfficeViewer`) with automatic 70% zoom and edge-to-edge canvas.
  - Outlook payload creation and automated drafting with task lifecycle monitoring.

- **Centralized System Logs (`📋 LOGS`)**:
  - Filterable by subcategories: `All Activity`, `To Do List`, `1. OFFERS`, `2. ALLERGIES`, `3. CAKE MEMOS`, `BOOKING CALLS`, `5. ALL DATA`.
  - Audit logging to both UI and persistent disk log (`DATABASE/system.log`).

## Prerequisites

- Windows 10/11
- Python 3.10+
- Microsoft Office (optional for document generation via `python-docx`; required for embedded active COM viewing)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/grigoris-kypriotis/Guest_Relation-s_Project.git
   cd GuestRelation_Workspace_Files
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Launch the desktop interface using:
```bash
py app.py
```
or
```bash
python app.py
```

## Running Tests

Execute the comprehensive automated test suite:
```bash
py -m unittest test_data_manager.py test_booking_calls.py
```

## Directory Structure

```
├── app.py                      # Main PyQt6 desktop application & navigation
├── booking_calls.py            # Booking.com calls CRM module & scheduling logic
├── data_manager.py             # Data ingestion, master state, Gatekeeper & comparison engine
├── offers_module.py            # Arrivals pipeline, CSV parsing & Word generation engine
├── test_booking_calls.py       # Unit tests for booking calls module
├── test_data_manager.py        # Unit tests for data management & directory architecture
├── requirements.txt            # Python package dependencies
├── .gitignore                  # Git ignore rules (excludes sensitive JSONs & CSVs)
├── DATABASE/                   # Centralized local data store
│   ├── booking calls for today/# Today's scheduled calls (JSON)
│   ├── SANDY BEACH/            # Arrivals cache
│   ├── SANDY VILLAS/           # Arrivals cache
│   └── .gitkeep
├── BOOKING CALLS/              # Local booking calls work directory
│   └── .gitkeep
├── TEMPLATES/                  # Blank office document templates
│   ├── BOOKING CALLS TEMPLATE/ # Blank BOOKING CALLS.xlsx template
│   ├── CAKE MEMO TEMPLATE/     # Blank CAKE MEMO.docx template
│   └── OFFER LIST TEMPLATE/    # Blank OFFER LIST TEMPLATE.docx template
├── OUTPUT/                     # Pipeline output folders
│   ├── OFFERS/
│   └── TODAYS_LIST/
└── TRASH/                      # Processed and discarded CSV archive
```
