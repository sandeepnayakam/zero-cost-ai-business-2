# State — Most Recent Summaries

The agent appends a new summary to this file after each run. The last 2-3 summaries are preserved for continuity; older history lives in `action_log.md`.

## Summary
(initial run pending — agent will populate this on first execution)

This is v3 of the agent — the Agentic Loop edition. Key changes from v2:

1. **Multi-step agentic loop**: Each run, the agent can take 1-5 actions (chained together), not just one. This lets it do multi-step work like: read file → analyze → write improved version → log experiment.

2. **Daily budget management**: LLM usage is tracked per provider in `memory/budget.md`. Budget resets at UTC midnight. The agent scales its ambition based on remaining budget:
   - full (>80% remaining) → up to 5 steps per run
   - high (50-80%) → up to 4 steps
   - medium (20-50%) → up to 3 steps
   - low (5-20%) → up to 2 steps
   - critical (1-5%) → 1 step only
   - exhausted → skip run entirely

3. **Runs every 30 minutes** (48 runs/day) instead of every 2 hours (12 runs/day). With max 5 steps/run, that's up to 240 LLM calls/day — well within the ~18,550 daily budget across all providers.

4. **More tools**: read_file, list_dir, delete_file, log_experiment, update_experiment (in addition to write_file, append_doc, http_get).

5. **Non-prescriptive prompt**: The agent is NOT told what to build. It follows one method: "Run small experiments. Kill what doesn't work. Double down on what does. Log every experiment's result in experiments.md." Everything else is the agent's decision.

## Pre-Loaded Assets
The site ships with 8 useful tools already in `docs/tools/`:
- JSON Formatter & Validator
- QR Code Generator (with PNG download)
- Base64 Encoder/Decoder (Unicode-safe)
- Password Generator (cryptographically secure)
- Hash Generator (SHA-256, SHA-1, MD5)
- URL Encoder/Decoder
- UUID Generator (v4)
- Timestamp Converter (Unix epoch)

Plus a landing page, blog index, and a crypto tip guide page displaying all 5 wallet addresses.

The agent's job: experiment with new tools, content, and strategies to drive traffic and revenue. It decides what to try. It logs what works and what doesn't. It kills failures and scales successes.

See README.md for setup instructions.
