---
trigger: always_on
---

FOLDER ORGANIZATION RULE (applies to all file-splitting work):

New files created from splitting an oversized file must not be placed flat
into the existing top-level folder (e.g. MODULES/). Instead:

1. Group new files into subfolders by responsibility (e.g. a folder for
   parsing logic, one for state/persistence, one for admin/maintenance
   operations, one for GUI/presentation code — decide actual names and
   groupings based on what fits this codebase, not a fixed template).
2. Create these subfolders as needed, with proper __init__.py files so
   they're valid Python packages.
3. Before creating anything, always propose the folder + file layout for
   my approval — do not create folders or move code until I confirm.
4. Keep the top-level facade file (e.g. data_manager.py) in its current
   location so existing imports elsewhere in the codebase keep working,
   even though its internals now live in subfolders.
5. Update all imports across the codebase to reflect new folder paths, not
   just new filenames.
6. Reflect the new folder structure in ARCHITECTURE.md's module map.

This rule applies to every file split going forward, not just the first one.