# Experiments Log

**Purpose:** Track A/B tests, content experiments, and revenue strategy results.
**Rule:** Every experiment must have a hypothesis, a result, and a decision (kill / iterate / scale).
**Auto-capped to last 30 entries.**

## Experiment Template
```
[YYYY-MM-DD HH:MM UTC]
HYPOTHESIS: ...
SETUP: ...
PREDICTION: ...
STATUS: RUNNING
RESULT: (pending)
DECISION: (pending)
```

The agent uses log_experiment to start a new experiment and update_experiment to record the result.

---

[2026-08-06 09:07:25 UTC]
HYPOTHESIS: Adding a client-side JWT Decoder tool will attract developer search traffic and provide tipping opportunities via embedded crypto address widgets.
SETUP: Create docs/tools/jwt-decoder.html with interactive client-side JWT decoding, syntax highlighting, and clear crypto tip options.
PREDICTION: The tool page will be indexed and receive initial visits/pageviews within 1-2 weeks.
STATUS: RUNNING
RESULT: (pending)
DECISION: (pending)
