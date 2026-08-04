#!/usr/bin/env python3
"""
Daily LLM Budget Management
============================

Tracks LLM request usage per provider, resets at UTC midnight.
Ensures the agent spreads its daily token budget across the whole day
instead of exhausting it in the first few runs.

Usage:
    import budget
    budget.reset_if_new_day()           # Call at start of each run
    level = budget.get_budget_level()   # 'full' | 'high' | 'medium' | 'low' | 'critical' | 'exhausted'
    max_steps = budget.get_max_steps_for_budget()  # 0-5 based on budget level
    budget.record_usage("groq")         # Call after each successful LLM request

Budget file: memory/budget.md
"""

import os
import re
from datetime import datetime, timezone

BUDGET_FILE = os.path.join("memory", "budget.md")

# Conservative daily request limits per provider (free tiers, 2026 estimates)
# These are intentionally conservative — actual limits may be higher.
DAILY_LIMITS = {
    "groq":        14000,   # 30 RPM, generous daily cap on Llama 3.3 70B
    "gemini":       1500,   # 15 RPM, 1500/day on Gemini Flash
    "cerebras":     1000,   # Free tier, super-fast
    "sambanova":     500,   # Free tier, big models
    "cloudflare":   1000,   # 10K neurons/day ~ ~1000 requests
    "huggingface":   500,   # Rate-limited free tier
    "openrouter":     50,   # 50/day on free models
}

# Total daily capacity when all providers are configured: ~18,550 requests
# With 30-min runs (48/day) and up to 5 steps per run: max 240 calls/day
# So budget is plentiful — the tracker mainly prevents bursts.


def _today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _read_file(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return default


def _write_file(path, text):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True) if d else None
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _parse_budget(content):
    """Parse budget file. Returns (date_str, {provider: used_count})."""
    date_str = None
    usage = {p: 0 for p in DAILY_LIMITS}
    for line in content.split("\n"):
        m = re.match(r"^Date:\s*(\S+)", line)
        if m:
            date_str = m.group(1)
            continue
        # Format: "provider: used / limit  (remaining: N)"
        m = re.match(r"^(\w+):\s*(\d+)\s*/\s*(\d+)", line)
        if m:
            provider, used, _ = m.groups()
            if provider in usage:
                usage[provider] = int(used)
    return date_str, usage


def _write_budget(usage):
    """Write budget file with current usage."""
    today = _today_str()
    now = _now_str()
    lines = [
        "# Daily LLM Budget Tracker",
        "",
        f"Date: {today}",
        f"Last Updated: {now}",
        "",
        "## Provider Usage (resets at UTC midnight)",
        "",
    ]
    total_used = 0
    total_limit = 0
    for provider in DAILY_LIMITS:
        used = usage.get(provider, 0)
        limit = DAILY_LIMITS[provider]
        remaining = max(0, limit - used)
        status = "OK" if remaining > 0 else "EXHAUSTED"
        lines.append(f"{provider}: {used} / {limit}  (remaining: {remaining})  [{status}]")
        total_used += used
        total_limit += limit
    lines.append("")
    lines.append(f"TOTAL: {total_used} / {total_limit}  (remaining: {total_limit - total_used})")
    lines.append("")
    _write_file(BUDGET_FILE, "\n".join(lines))


def reset_if_new_day():
    """If the date in budget file differs from today, reset all counts to 0."""
    content = _read_file(BUDGET_FILE)
    date_str, _ = _parse_budget(content)
    today = _today_str()
    if date_str != today:
        _write_budget({p: 0 for p in DAILY_LIMITS})


def get_remaining(provider):
    """Get remaining requests for a provider today."""
    reset_if_new_day()
    content = _read_file(BUDGET_FILE)
    _, usage = _parse_budget(content)
    used = usage.get(provider, 0)
    return max(0, DAILY_LIMITS.get(provider, 0) - used)


def get_total_remaining():
    """Get total remaining requests across all providers."""
    reset_if_new_day()
    content = _read_file(BUDGET_FILE)
    _, usage = _parse_budget(content)
    total = 0
    for provider in DAILY_LIMITS:
        total += max(0, DAILY_LIMITS[provider] - usage.get(provider, 0))
    return total


def get_total_limit():
    """Get total daily limit across all providers."""
    return sum(DAILY_LIMITS.values())


def get_total_used():
    """Get total used requests today across all providers."""
    reset_if_new_day()
    content = _read_file(BUDGET_FILE)
    _, usage = _parse_budget(content)
    return sum(usage.values())


def record_usage(provider, count=1):
    """Record usage for a provider."""
    reset_if_new_day()
    content = _read_file(BUDGET_FILE)
    _, usage = _parse_budget(content)
    if provider in usage:
        usage[provider] += count
    _write_budget(usage)


def get_budget_level():
    """
    Return budget level string.
    'full'      — >80% remaining
    'high'      — 50-80% remaining
    'medium'    — 20-50% remaining
    'low'       — 5-20% remaining
    'critical'  — 1-5% remaining
    'exhausted' — 0% remaining
    """
    total = get_total_remaining()
    limit = get_total_limit()
    if limit == 0:
        return "exhausted"
    pct = total / limit
    if total == 0:
        return "exhausted"
    elif pct < 0.05:
        return "critical"
    elif pct < 0.20:
        return "low"
    elif pct < 0.50:
        return "medium"
    elif pct < 0.80:
        return "high"
    else:
        return "full"


def get_max_steps_for_budget():
    """
    Return max agentic steps based on budget level.
    This scales the agent's ambition based on remaining daily budget.
    """
    level = get_budget_level()
    return {
        "exhausted": 0,
        "critical":  1,
        "low":       2,
        "medium":    3,
        "high":      4,
        "full":      5,
    }.get(level, 3)


def get_budget_summary():
    """Return a human-readable summary for logging."""
    level = get_budget_level()
    remaining = get_total_remaining()
    limit = get_total_limit()
    used = get_total_used()
    return f"{level} ({used}/{limit} used, {remaining} remaining)"
