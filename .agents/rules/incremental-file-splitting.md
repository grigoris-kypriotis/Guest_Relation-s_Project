---
trigger: always_on
---

Your task is to keep the codebase's .py files under roughly 300-400 lines by
splitting oversized files into smaller, logically organized ones. Do this
CAREFULLY and INCREMENTALLY — do not attempt the whole repo in one pass.

Process, per file over the limit:
1. Identify the file and report its current line count and what it contains
   (classes, function groups, responsibilities).
2. Propose a split: which functions/classes move to which new file, and why
   that grouping makes sense (by responsibility, not just line count).
   Name new files clearly (e.g. `user_auth.py`, `user_validation.py` rather
   than `user_part2.py`).
3. Wait for my confirmation on the proposed split before making changes.
4. After I confirm: create the new files, move the code, and update EVERY
   import/reference to that code across the entire codebase.
5. Run the test suite (or the app, if no tests exist) to confirm nothing broke.
6. Report: files created, files modified, import changes made, and test/run result.
7. Update ARCHITECTURE.md's module map to reflect the new structure.

Do not proceed to the next oversized file until the current split is confirmed
working. If you're unsure whether a function belongs in one new file or
another, ask rather than guessing. Never split a file in a way that creates
circular imports — flag it and propose an alternative if you hit that.