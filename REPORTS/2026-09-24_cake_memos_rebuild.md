# Rebuild CAKE MEMOS around a structured creation form — Task Report

**Branch:** `feature/offers-rebuild` (same PR #1, continuing directly on top of the OFFERS rebuild and the arrivals-panel/config-split task)
**Date:** 2026-09-24
**Plan:** `C:\Users\grigo\.claude\plans\moonlit-wishing-karp.md` (approved before implementation)

## Summary

Replaced CAKE MEMOS' hand-type-into-raw-Word-template flow (with a brittle regex/position-guessing
parser on save) with a structured Create/Update form, mirroring how the OFFERS rebuild replaced
ad-hoc arrivals-CSV parsing with header-driven, explicit data. New `MODULES/cake_memo/` and
`OPTIONS/cake_memo/` subpackages; `OPTIONS/cake_memo_option.py` is now a thin facade. Submenu
restructured to 6 buttons (Create/Update/Edit/Save/Close/Send Email), matching OFFERS' pattern.
7 commits. Test count grew from 245 (pre-task) to 260, all passing.

## Commits

| Commit | Description |
|---|---|
| `7412206` | Step 1 — package skeletons + deterministic compose/parse functions for the 3 composite docx columns |
| `5e96ac5` | Step 2 — header-driven document generator + parser |
| `9ddf91d` | Step 3 — the structured `CakeMemoForm` widget |
| `3b99f1f` | **Crash fix** — `CakeMemoForm()` was crashing the interpreter on construction; found and fixed during verification, not by the implementing agent |
| `f3625eb` | Step 4 — `CakeMemoOptionWidget` orchestration (modes, submenu, Save/Close) |
| `e7c7a16` | Step 5 — Send Email flow + widened 📨 task-state gating to include Cake Memo |
| `24a3057` | Step 6 — facade wiring, `app.py` submenu extraction, old parser/dead-import removal |

## Test output (final run)

```
py -m unittest discover -s TESTS -p "test_*.py"
...
Ran 260 tests in ~28s
OK (skipped=1)
```
Verified independently after every commit (not just trusted from agent reports), including repeated
standalone construction checks outside the test suite specifically to catch crashes the test runner
itself might mask.

## A real bug found and fixed during this task

`CakeMemoForm()` crashed the Python interpreter itself on construction — not a catchable exception,
a genuine native crash (exit code 127 on Windows, process death mid-construction). Root cause: the
Charge radio-button group connected its `toggled` signal to a handler referencing
`self.complimentary_by_frame`, then immediately called `.setChecked(True)` on the "Paid" button
*before* `self.complimentary_by_frame` had been created — `setChecked(True)` fires `toggled`
synchronously, so the handler ran against a not-yet-existing attribute. The implementing agent's own
test suite reported this as passing (its report characterized a related Windows exit code as an
"environment cleanup issue"); I did not accept that characterization and instead reproduced the crash
directly via bisection (`sys.settrace` line tracing, incremental construction in isolation) before
concluding it was a genuine bug, not a fluke — the crash was 100% reproducible until fixed, and stable
across repeated runs afterward. This also unmasked a second, unrelated latent bug: several new tests
asserted `widget.isVisible()`, which is always `False` for any `QWidget` that's never actually been
shown to screen (as in these headless offscreen-platform tests) regardless of `setVisible()` calls —
switched to `isHidden()`, matching the correct pattern already established by the OFFERS "no arrivals
panel" tests.

Every subsequent step's prompt was updated to explicitly warn about this exact failure class
(construction-order signal-handler crashes) and required independent standalone crash verification,
not just trusting the test suite's exit status — this caught nothing further, but the extra rigor held
through Steps 4-6.

## Design decisions worth your attention

1. **Update-mode Save overwrites the loaded file in place; Create-mode Save applies OFFERS'
   `" UPDATED"`/`" UPDATED (N)"` collision-suffix pattern.** Cake Memos are independent per-file
   records (unlike Offers' one-canonical-file-per-day model), so "Update" means "edit this specific
   file," not "version today's file."
2. **The 📨 "draft opened" task state, previously gated to exclude Cake Memo specifically** (a
   deliberate fix from the OFFERS rebuild, since Cake Memo's payload `category` is coincidentally also
   `"Offer"`), is now widened to an explicit allow-list (`subcategory in ("Offer List", "Cake Memo")`)
   per this task's explicit request that Cake Memo reuse this state too.
3. **Composite docx column formats** (SERVICE DESCRIPTION, PROVIDED AT, CHARGE) use deterministic,
   round-trip-tested compose/parse function pairs in `MODULES/cake_memo/field_format.py` — e.g.
   `compose_provided_at("il_gusto", 19, 30, True) == "IL GUSTO 19.30PM"`, matching the confirmed real
   example character-for-character.
4. **`storage.cake_memos_dir`** now actually drives the save destination — the old code hardcoded
   `OUTPUT_DIR/CAKE_MEMOS/...` directly, ignoring that setting entirely, despite it already existing
   in the Configuration UI.

## Not done as part of this task

- Not merged — pushed as 7 new commits to the same open PR #1 branch.
- No manual GUI smoke test (no display environment available) — worth checking on your machine:
  Create Cake Memo shows the new form (not the raw template), the Delivery/Flavor/Charge conditional
  sections show/hide correctly, Update pre-fills correctly from a real generated file, Edit still opens
  raw Word editing, and Send Email produces a correctly-attached Outlook draft without ever calling
  `mail.Send()`.
