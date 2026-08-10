Action Log (Full Audit Trail)

Purpose: Uncapped log of every agent run. Auto-trimmed to last 100 runs when it exceeds 500KB.
Format: Each entry shows timestamp, model, budget, steps taken, and full reasoning.

NOTE (2026-08-10): This log was reset to break the list_dir docs/tools/ loop.
The previous log contained ~40 runs (Aug 4 – Aug 7) where the agent got stuck
repeating list_dir docs/tools/ and getting killed by the in-run loop detector.
Those entries were poisoning the LLM's context (the 6KB tail fed to it every run)
and biasing it to keep doing the same thing. They have been removed.
