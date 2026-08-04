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
