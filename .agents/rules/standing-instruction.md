---
trigger: always_on
---

You will receive implementation specs produced by a separate planning AI that has already analyzed the relevant architecture and files.
Treat the spec as authoritative for scope and intent, but you are responsible
for correctness against the actual current codebase.

When you receive a spec:
1. Before writing code, verify the files and interfaces named in the spec
   still match the current state of the repo. If something has drifted
   (a file moved, a function signature changed, a dependency is missing),
   stop and report the discrepancy instead of improvising around it.
2. Implement only what's in the spec's scope. If you find you need to touch
   a file not listed, flag it and explain why before proceeding.
3. After implementing, summarize: files changed, anything that deviated from
   the spec and why, and anything you think should go back to planning
   (edge case not covered, ambiguity, etc.) — written so I can paste it
   directly back to the planning AI.