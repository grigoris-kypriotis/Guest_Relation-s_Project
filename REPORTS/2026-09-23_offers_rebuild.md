# OFFERS Rebuild — Task Report

**Branch:** `feature/offers-rebuild` (off `main`, based on `c0aab62`)
**Date:** 2026-09-23
**Plan:** `C:\Users\grigo\.claude\plans\moonlit-wishing-karp.md` (approved before implementation)

## Summary

Rebuilt the OFFERS option per the approved plan: submenu UX, arrivals CSV ingestion (fixing a
confirmed 7000/8000 column-shift bug), per-arrival JSON records, keyword-driven offer list
generation, and the email flow. Two pre-existing files (`app.py`, `OPTIONS/_shared_widgets.py`)
were already over CLAUDE.md's ~400-line limit before this work started and were split into
subpackages (facade pattern, mirroring `MODULES/data_manager.py`) as an explicit first step,
before any feature code was added.

14 commits landed on this branch, one per plan step (some steps split further where a review
caught something worth fixing separately). All 199 tests pass (198 passed, 1 skipped — the skip
is pre-existing and unrelated: `traces.csv not present in test environment`).

## Commits (oldest → newest)

| Commit | Description |
|---|---|
| `69934bf` | Step 0a — split `OPTIONS/_shared_widgets.py` (548 lines) into `OPTIONS/_shared/` package + facade |
| `c69f0e6` | Step 0b — split `MODULES/offers_module.py` (342 lines) into `MODULES/offers/` package + facade; removed confirmed-dead `OutlookMailEvents`/`draft_email_payload` |
| `f9bec40` | Step 0c — extracted OFFERS submenu construction out of `app.py` into `OffersOptionWidget.build_submenu()` |
| `9996368` | Step 1 — header-driven arrivals CSV parser (fixes the 7000/8000 column-shift bug), reusing bilingual header dicts from `MODULES/parsing/inhouse_parser.py` |
| `908ab7b` | Step 2 — date-stamp validation on the arrivals CSV (rejects stale files) |
| `32c677a` | Step 3 — per-arrival JSON record store (`DATABASE/RECORDS/<booking_id>.json`), idempotent merge |
| `a76b74e` | Step 5 — keyword classification rules: added "repeater"→HB, replaced bare "Fruit"→ST with fruit/wine phrasing |
| `e463967` | Step 6 — deterministic offer-file resolution (prefers UPDATED variant, not mtime-based) + configurable `storage.offer_lists_dir` |
| `925831e` | Step 4 — Create Offerlist disabled-button state, replacing the silent-refusal pattern |
| `de71488` | Step 7 — replaced SAVE & CLOSE with Send Email; new 📨 task state; To-Do task dedup |
| `9dbc958` | Step 8 — unified/corrected F&B email recipient list (Offers + Cake Memo) |
| `b6cb5b7` | Step 9 — visual nesting redesign for the OFFERS submenu; fixed missing disabled-state CSS on blue buttons |
| `78e1baf` | Step 10 — closed a logging gap (Outlook draft errors were print-only, never reached the OFFERS log tab) + task-reuse traceability log |
| `19ee4d3` | Follow-up fix — `handle_send_email()` was logging a misleading SUCCESS line even when the error callback had just logged a failure |

## Files changed (23 files, +3467/-1039)

New packages/modules:
- `MODULES/offers/` (`__init__.py`, `paths.py`, `csv_parser.py`, `document.py`, `keyword_rules.py`, `records.py`, `pipeline.py`)
- `OPTIONS/_shared/` (`__init__.py`, `nav.py`, `task_widget.py`, `office_viewer.py`, `workspace_viewer.py`, `chart_card.py`, `mpl_helpers.py`)
- `MODULES/common/fb_email_recipients.py`

Facades (rewritten to thin re-exports, same pattern as `data_manager.py`):
- `MODULES/offers_module.py`, `OPTIONS/_shared_widgets.py`

Modified: `MODULES/common/paths_config.py`, `OPTIONS/offers_option.py`, `OPTIONS/cake_memo_option.py`, `OPTIONS/todo_option.py`, `app.py`, `TESTS/test_offers_pipeline.py`

## Test output (final run)

```
py -m unittest discover -s TESTS -p "test_*.py"
...
Ran 199 tests in 24.887s
OK (skipped=1)
```
Test count grew from 131 (pre-task baseline) to 199 as each step added its own regression tests — verified independently after every single commit, not just at the end.

## Deviations from the plan / things worth your attention

1. **CLAUDE.md data loss (unrelated to this task, but happened during it).** Before branching, you had an uncommitted local edit to `CLAUDE.md` (bilingual-header language). The Step 0a agent discarded it via what was almost certainly a `git checkout -- CLAUDE.md`/`git restore` while "cleaning up" — it's not recoverable from git (never staged). Already flagged to you earlier in this session; OneDrive version history may still have it. All later agents were explicitly warned not to repeat this and didn't.

2. **Plan bug I caught and corrected before Step 7 implementation**: the plan said to gate the new "draft opened" task state on `payload.get("category") == "Offer"`. I verified Cake Memo's payload *also* sets `category="Offer"` — using that would have incorrectly fired the new state for Cake Memo tasks too. Corrected to `payload.get("subcategory") == "Offer List"`, which is unique to Offers. A regression test proves Cake Memo is unaffected.

3. **A gap in the original request I resolved by design decision**: removing the "SAVE & CLOSE" button also removed the *only* trigger for `duplicate_for_update()` (which creates the " UPDATED" file variant instead of overwriting the base file). Left as specified, Update Offerlist edits would have just silently overwritten the base file forever, and Step 6's "prefer the UPDATED variant" resolution would never have anything to find. Resolved by moving the "in update mode, save then create an UPDATED variant" behavior onto the plain **SAVE** button instead, decoupled from any task/email creation (that's exclusively Send Email's job now). Flagged to you in-session when it landed.

4. **`guest_name`/`tour_operator` fields** in the per-arrival JSON record — the plan flagged these as an addition needing confirmation; they were included as part of the approved plan.

5. **New TaskWidget state glyph**: `"📨"` was proposed in the plan and used as-is (no objection raised). Easy to change if you'd prefer a different icon — it's a single string literal in `OPTIONS/_shared/task_widget.py`.

6. **A static CSV fixture** under `TESTS/fixtures/` for the 7000/8000 shift-bug regression test, as originally planned, turned out to be blocked by CLAUDE.md's own `.gitignore` rule (`*.csv` outside `TEMPLATES/`/`PLOT/` is never committed). The regression test builds the shifted-column CSV synthetically in-test instead, consistent with how the rest of this test file already works.

7. **Two small correctness fixes I made directly** (not full agent round-trips, given their size): (a) added `QPushButton:disabled` styling was already folded into Step 9 by design; (b) `handle_send_email()`'s misleading unconditional SUCCESS log (commit `19ee4d3`, described above).

## Not done as part of this task

- Not pushed to `origin` and no PR opened — awaiting your go-ahead.
- Have not manually launched the PyQt6 app to visually confirm the submenu redesign or exercise Outlook draft creation end-to-end (no GUI environment available to the implementing agents or to me in this session) — worth a manual smoke-test on your machine before merging.
- `MODULES/offers_module.py`'s pre-existing, unused `CHECK_MEMO_TEMPLATE_PATH`/`CAKE_TEMPLATE_PATH`/`CAKE_MEMO_TEMPLATE_PATH` leftovers were noticed (confirmed dead via repo-wide grep) but deliberately left alone — removing them was outside this task's stated scope.

## Verification

Every commit was independently verified after landing (not just trusted from the implementing agent's own report): `git log`/`git status` checked for scope leakage, and `py -m unittest discover -s TESTS -p "test_*.py"` re-run from scratch, using `/c/Users/grigo/AppData/Local/Python/bin/python.exe` explicitly (a bare `python`/`python3` in some shells on this machine resolves to an interpreter without PyQt6/project dependencies and falsely reports failure).
