# Guest Relation Workspace — Rules for Claude Code

Full architecture: see ARCHITECTURE.md. This file is the short, load-every-session version. If a rule here conflicts with something you infer from code, this file wins.

## Never violate these

- **Booking.com filter**: `booking_calls.py` must only process reservations where the agent is `BOOKING.COM` (case-insensitive). Never widen this filter.
- **FOLLOW UP sheet only**: All reads/writes to `BOOKING CALLS.xlsx` go to the `FOLLOW UP` sheet. Never touch Sheet 1.
- **Call schedule rule 4**: If two calculated call dates land on consecutive days, discard the earlier one, keep the later one.
- **Room moves vs. merges**: A room move is one booking ID changing rooms. A room merge is multiple records combined under one room. Merges must never be logged as moves. This logic lives in `hotel_state_manager.py` (`compare_and_update`).
- **Room numbers are 4 digits.** Anything else is "Unknown" and excluded from analytics. Do not "fix" a 3-digit or 5-digit room number by guessing — exclude it per the existing rule.
- **Greek PMS headers** (`"Αρ."`, `"Πελάτης"`, `"Τύπος Γεύματος"`, `"Δωμάτιο"`) must map through the existing normalization dictionaries in `data_manager.py` / `trace_analytics.py`. Don't hardcode new header strings elsewhere.

## File size

- No file over ~400 lines. If a task would push a file over this, split it first, as its own step, before adding the feature.
- New code for a widget/feature goes in a folder named for that feature (e.g. `OPTIONS/stats/`), not appended to an existing large file.

## Data safety

- Never read, print, or reason about contents of `DATABASE/`, `ROOMS/`, `DATA_BACKUP/`, `TRASH/`, `OUTPUT/`, `BOOKING CALLS/*.xlsx`. These contain real guest data and are access-denied by settings — if a task seems to need them, use `TESTS/fixtures/` synthetic data instead and say so.
- Never commit anything matching `*.json`, `*.csv`, `*.xlsx`, `*.docx`, `.env` outside `TEMPLATES/` or `PLOT/HotelDataSet.json` — `.gitignore` already blocks this, don't override it.

## Workflow

- One task = one small, scoped change. Do not touch files outside the task's stated scope.
- After implementing: run the relevant tests for real (`python -m unittest discover -s TESTS -p "test_*.py"` or the specific test file) and capture actual output — never assert tests pass without running them.
- One git commit per task, on a feature branch, never directly to `main`.
- Write a report file for the task with: files changed, summary of changes, full `git diff`, full test output, deviations from the plan, anything uncertain.

## Testing

- Run via: `py -m unittest discover -s TESTS -p "test_*.py"` (or `python -m unittest ...` on non-Windows).
- Tests must not depend on real data in `DATABASE/`/`ROOMS/`. Use `TESTS/fixtures/`.
