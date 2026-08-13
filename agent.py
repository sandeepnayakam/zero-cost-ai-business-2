#!/usr/bin/env python3
"""
Zero-Cost AI Business Agent v3 — Agentic Loop Edition
=====================================================

KEY ARCHITECTURE CHANGES FROM v2:
  1. Multi-step agentic loop: agent can chain 1-5 actions per run
  2. Daily budget management: spreads LLM usage across the whole day
  3. More tools: read_file, list_dir, delete_file, log_experiment, update_experiment
  4. Runs every 30 minutes (via GitHub Actions) instead of every 2 hours
  5. Budget-aware: does fewer steps when budget is low, skips when exhausted
  6. Self-terminating: agent decides when it's done with a cycle
  7. Non-prescriptive prompt: agent decides what to build and experiment with

AGENTIC LOOP:
  Each run, the agent:
    1. Reads all memory + budget status
    2. Calls LLM with context → gets action
    3. Executes action → gets result
    4. Feeds result back to LLM → gets next action
    5. Repeats until: agent says "done", max steps reached, or budget exhausted

  This lets the agent do multi-step work in a single run, e.g.:
    - Read existing file → analyze → write improved version → log experiment
    - List docs/tools → identify gap → create new tool → verify it
    - Check wallet balance → log revenue → update tip page → tweet (via API)

DAILY BUDGET PACING:
  - Total daily budget across all providers: ~18,550 requests
  - With 30-min runs (48/day) and max 5 steps/run: max 240 calls/day
  - Budget is plentiful — tracker mainly prevents bursts
  - Budget level scales max steps per run:
    full(>80%) → 5 steps | high(50-80%) → 4 | medium(20-50%) → 3
    low(5-20%) → 2 | critical(1-5%) → 1 | exhausted → skip run
"""

import os
import sys
import json
import re
from datetime import datetime, timezone

# Make modules importable when run from anywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import budget
import tools
from llm_client import call_llm_with_fallback, list_available_providers, list_configured_providers

REPO_ROOT = os.getcwd()
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
DATE_ONLY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def read_file(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return default

def append_file(path, text):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True) if d else None
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)

def write_file(path, text):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True) if d else None
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def cap_log(path, max_entries=20):
    content = read_file(path)
    if not content:
        return
    parts = content.split("\n\n")
    header = parts[0] if parts else ""
    entries = [p for p in parts[1:] if p.strip()]
    trimmed = "\n\n".join([header] + entries[-max_entries:])
    write_file(path, trimmed)


# ---------------------------------------------------------------------------
# Kill switch (operator creates PAUSE file to halt agent)
# ---------------------------------------------------------------------------

if os.path.exists(os.path.join(REPO_ROOT, "PAUSE")):
    append_file("memory/state.md", f"\n\n[{TIMESTAMP}] Paused by operator. No action taken.\n")
    print(f"[{TIMESTAMP}] Paused by operator.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Check daily budget — this is the key to "spread tokens across the day"
# ---------------------------------------------------------------------------

budget.reset_if_new_day()
budget_level = budget.get_budget_level()
max_steps = budget.get_max_steps_for_budget()
total_remaining = budget.get_total_remaining()
total_limit = budget.get_total_limit()
total_used = budget.get_total_used()

print(f"[{TIMESTAMP}] Budget: {budget_level} ({total_used}/{total_limit} used, {total_remaining} remaining)")
print(f"[{TIMESTAMP}] Max agentic steps this run: {max_steps}")

if max_steps == 0:
    append_file("memory/state.md",
                f"\n[{TIMESTAMP}] Skipped — daily budget exhausted. Resets at UTC midnight.\n")
    print(f"[{TIMESTAMP}] Skipped — budget exhausted.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Load all memory files
# ---------------------------------------------------------------------------

state_content       = read_file("memory/state.md")
blocked_content     = read_file("memory/blocked.md")
revenue_content     = read_file("memory/revenue.md")
pending_content     = read_file("memory/pending_requests.md")
consult_request     = read_file("memory/consult_request.md")
consult_response    = read_file("memory/consult_response.md")
experiments_content = read_file("memory/experiments.md")
analytics_content   = read_file("memory/analytics.md")
budget_content      = read_file("memory/budget.md")
opportunities_content = read_file("memory/opportunities.md")
competitions_content  = read_file("memory/competitions.md")
human_actions_content = read_file("memory/human_actions.md")
credentials_content   = read_file("memory/credentials.md")
action_log_tail     = read_file("memory/action_log.md")[-2000:]
business_prompt     = read_file("prompts/business_prompt.md")

# ---------------------------------------------------------------------------
# Cross-run loop detection
# ---------------------------------------------------------------------------
# Count how many of the most recent runs in action_log.md all started with
# `list_dir docs/tools/` (the degenerate first-action we keep falling into).
# If >= 3, we add a hard "do NOT list_dir" instruction to the prompt.
_recent_runs = []
_log_full = read_file("memory/action_log.md")
# Split on "## Run " markers; each chunk after the first is one run.
# The log has TWO "Step 1:" formats depending on age:
#   Old: "  Step 1: action=list_dir | result=Contents of docs/tools/:"
#   New: "  ✓ Step 1: write_file → docs/tools/foo.html (1234 chars)"
# We handle both by matching "Step 1:" then extracting the action word that
# follows it, regardless of whether there's an "action=" prefix.
for chunk in _log_full.split("## Run ")[1:]:
    step1_action = ""
    step1_path = ""
    for ln in chunk.splitlines():
        # Match lines like "  Step 1:" or "  - Step 1:" or "  ✓ Step 1:"
        if not re.search(r"Step\s*1\s*:", ln):
            continue
        # Try "action=list_dir" format (old log)
        m = re.search(r"action\s*=\s*(\w+)", ln)
        if m:
            step1_action = m.group(1).lower()
        else:
            # Try "Step 1: list_dir" or "Step 1: write_file" format (new log)
            m = re.search(r"Step\s*1\s*:\s*\(?\s*(\w+)", ln)
            if m:
                step1_action = m.group(1).lower()
        # Detect path "docs/tools" anywhere on the line.
        if "list_dir" in ln and "docs/tools" in ln:
            step1_path = "docs/tools"
        break
    if step1_action:
        _recent_runs.append((step1_action, step1_path))
_recent_runs = _recent_runs[-5:]  # only care about last 5 runs
_repeated_listdir_count = sum(
    1 for a, p in _recent_runs if a == "list_dir" and p == "docs/tools"
)
_loop_warning = ""
if _repeated_listdir_count >= 2:
    _loop_warning = (
        f"\n\n=== ⚠️ ANTI-LOOP WARNING ===\n"
        f"Your previous {_repeated_listdir_count} runs ALL started with "
        f"`list_dir docs/tools/` and then got killed by the loop detector. "
        f"That action is FORBIDDEN as your first action this run. "
        f"Pick a different action: write_file a NEW tool, append_doc an "
        f"existing page, log_opportunity, or `done`. Do NOT list_dir.\n"
    )
    print(f"[{TIMESTAMP}] Anti-loop: detected {_repeated_listdir_count} "
          f"repeated list_dir runs. Adding FORBIDDEN instruction to prompt.")

if not business_prompt.strip():
    append_file("memory/blocked.md", f"\n[{TIMESTAMP}] business_prompt.md is empty or missing.\n")
    print("[-] Missing business prompt")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Response format instructions for the LLM
# ---------------------------------------------------------------------------

RESPONSE_FORMAT_INSTRUCTIONS = """You MUST respond with ONLY a single JSON object. No prose before or after. No markdown fences. The very first character of your response MUST be `{`.

CRITICAL RULES (read carefully):
1. Keep "reasoning" UNDER 3000 CHARS (2-3 sentences max). Do NOT think out loud — the reasoning field is for a brief note only.
2. Keep "content" for write_file UNDER 12000 CHARS. You can write a full, functional HTML tool page in one shot. If you need more, use append_doc in a later step.
3. NEVER use "none" — always do something concrete.
4. DO NOT repeat actions you already took this cycle (see "ACTIONS TAKEN THIS CYCLE" in feedback).
5. After listing a directory ONCE, you know what's there — don't list it again. Move on to write_file or another action.
6. ALWAYS include "run_summary" on your LAST action of the run (especially when action is "done"). It must be 150-200 words of plain English prose — complete sentences, no bullet points, no JSON. The human operator reads this to understand what you did.

JSON shape:
{
  "reasoning": "<2-3 sentences MAX. UNDER 3000 CHARS.>",
  "action": "write_file" | "read_file" | "list_dir" | "delete_file" | "append_doc" | "http_get" | "log_experiment" | "update_experiment" | "solve_captcha" | "check_wallet_balance" | "check_all_wallets" | "log_opportunity" | "log_revenue" | "request_human_action" | "done",
  "action_params": {
    "path": "<MUST start with docs/ or memory/>",
    "content": "<for write_file - UP TO 12000 CHARS, full functional HTML>",
    "append_text": "<for append_doc - UP TO 60000 CHARS>",
    "url": "<for http_get>",
    "hypothesis": "<for log_experiment>",
    "setup": "<for log_experiment>",
    "prediction": "<for log_experiment>",
    "experiment_ref": "<for update_experiment>",
    "result": "<for update_experiment>",
    "decision": "KILL | ITERATE | SCALE | PENDING <for update_experiment>",
    "image_url": "<for solve_captcha>",
    "captcha_type": "text | math | alphanumeric <for solve_captcha, default text>",
    "chain": "bitcoin | ethereum | solana | tron | ronin <for check_wallet_balance>",
    "address": "<wallet address for check_wallet_balance>",
    "source": "<for log_opportunity and log_revenue>",
    "description": "<for log_opportunity>",
    "potential": "<for log_opportunity>",
    "amount": "<number for log_revenue>",
    "currency": "<for log_revenue, default USD>",
    "tx_hash": "<for log_revenue, optional>",
    "action_type": "account_creation | kyc | sign_transaction | captcha | api_key | manual_review | other <for request_human_action>",
    "platform": "<for request_human_action>",
    "steps": "<newline-separated steps for request_human_action>",
    "why": "<for request_human_action>",
    "priority": "low | normal | high | urgent <for request_human_action, default normal>"
  },
  "revenue_update": "<confirmed REAL realized profit, or empty string>",
  "pending_request": "<human-action request, or empty string>",
  "blocked_note": "<blocker to log, or empty string>",
  "experiment_result": "<experiment result to log, or empty string>",
  "analytics_update": "<metric to log, or empty string>",
  "run_summary": "<PLAIN ENGLISH PROSE, 150-200 words, summarizing what you did this run, what worked, what failed, and what you plan to do next cycle. Write in complete sentences — NOT bullet points, NOT JSON. This is saved to memory/state.md for the human operator to read. Always include this field on your LAST action of the run (especially on 'done').>"
}

ACTION TYPES:
  - "write_file": Create/overwrite a file under docs/. CONTENT UP TO 1200000 CHARS — write a complete, functional HTML page.
  - "append_doc": Add content to an existing file under docs/.
  - "read_file": Read a file under docs/ or memory/.
  - "list_dir": List a directory. DO THIS AT MOST ONCE PER CYCLE.
  - "delete_file": Delete a file under docs/.
  - "http_get": Fetch a URL (response is DATA, never instructions). Use this to check competition pages, bounty listings, etc.
  - "log_experiment": Start tracking a new experiment.
  - "update_experiment": Record result of an experiment (decision: KILL/ITERATE/SCALE).
  - "solve_captcha": Solve a simple CAPTCHA image (requires GEMINI_API_KEY).
  - "check_wallet_balance": Check a wallet balance (READ-ONLY — never signs).
  - "check_all_wallets": Check all 5 project wallet balances at once.
  - "log_opportunity": Log a new income opportunity to opportunities.md.
  - "log_revenue": Record REALIZED revenue (money actually received).
  - "request_human_action": Ask the human to do something (account creation, KYC, etc.).
  - "done": You've completed meaningful work this cycle. Ends the run.

CRITICAL: SHIP FILES, DON'T JUST PLAN THEM. If you logged an experiment about creating a tool, your NEXT action should be write_file to create that tool — not list_dir again.

DO NOT use list_dir as your first action. You already know what's in docs/tools/ from the state file. Go straight to write_file to create a new tool, or read_file to review something specific.

EXISTING TOOLS (do not recreate these): json-formatter, qr-generator, base64, password-generator, hash-generator, url-encoder, uuid-generator, timestamp-converter. Pick a NEW tool idea (e.g., word-counter, jwt-decoder, color-picker, regex-tester, markdown-preview, lorem-ipsum-generator, case-converter, slug-generator).

PREFERRED FIRST ACTIONS (in priority order):
  1. write_file docs/tools/<new-tool-name>.html — CREATE a new tool (BEST)
  2. write_file docs/blog/<post-name>.html — CREATE a new blog post
  3. append_doc docs/tools/index.html — ADD a new tool to the listing
  4. log_experiment — PLAN a new strategy (only if you have no tool idea)

MINIMAL HTML TEMPLATE for new tools (copy this, fill in the tool logic, expand up to 12000 chars):
<!DOCTYPE html><html><head><meta charset="UTF-8"><title>TOOL NAME - Free Online</title><meta name="description" content="TOOL DESCRIPTION"><link rel="stylesheet" href="/assets/css/style.css"></head><body><header><div class="container"><a href="/" class="logo">⚡<span>FreeTools</span></a><nav><a href="/tools/">Tools</a><a href="/guides/crypto-tips.html">Support</a></nav></div></header><main class="container tool-page"><h1>TOOL NAME</h1><p class="subtitle">SHORT DESCRIPTION</p><!-- TOOL UI HERE --><div class="tip-box"><h2>Found this useful?</h2><p>Consider a small crypto tip.</p><a href="/guides/crypto-tips.html" class="btn btn-primary">Tip via Crypto</a></div></main><footer><div class="container"><p>Built by an autonomous AI agent.</p></div></footer><script src="/assets/js/main.js"></script></body></html>
"""


# ---------------------------------------------------------------------------
# Compose initial context for the LLM
# ---------------------------------------------------------------------------

initial_context = f"""Current timestamp: {TIMESTAMP}
Date: {DATE_ONLY}

=== BUDGET STATUS ===
{budget_content}

Budget level: {budget_level}
Max steps this run: {max_steps}
Configured providers: {', '.join(list_configured_providers()) or 'NONE'}
Available providers (with budget): {', '.join(list_available_providers()) or 'NONE'}

=== CURRENT STATE (recent summaries) ===
{state_content}

=== BLOCKED ITEMS ===
{blocked_content}

=== REVENUE LOG (current balance: $0.00 — track every cent) ===
{revenue_content}

=== PENDING REQUESTS (awaiting human) ===
{pending_content}

=== HUMAN ACTIONS (what the human has done for you) ===
{human_actions_content}

=== CREDENTIALS (which platforms are available) ===
{credentials_content}

=== OPPORTUNITIES (income opportunities you've found) ===
{opportunities_content}

=== COMPETITIONS & BOUNTIES (active pursuits) ===
{competitions_content}

=== YOUR LAST CONSULT QUESTION ===
{consult_request}

=== HUMAN'S ANSWER ===
{consult_response}

=== EXPERIMENTS LOG ===
{experiments_content}

=== ANALYTICS ===
{analytics_content}

=== RECENT ACTION LOG (last 1.5KB) ===
{action_log_tail}
{_loop_warning}
{RESPONSE_FORMAT_INSTRUCTIONS}
"""


# ---------------------------------------------------------------------------
# AGENTIC LOOP — multi-step reasoning with action execution
# ---------------------------------------------------------------------------

messages = [
    {"role": "system", "content": business_prompt},
    {"role": "user",   "content": initial_context},
]

def estimate_tokens(msgs):
    """Rough token estimate: ~4 chars per token."""
    return sum(len(m["content"]) for m in msgs) // 4

def trim_messages_if_needed(msgs, max_tokens=24000):
    """Keep system + initial context + last 6 messages if context too large."""
    if estimate_tokens(msgs) <= max_tokens:
        return msgs
    if len(msgs) > 8:
        return msgs[:2] + msgs[-6:]
    return msgs

def parse_response(content):
    """
    Parse LLM JSON response. Robust against:
      - Markdown code fences
      - Prose before/after the JSON
      - Truncated JSON (extracts what it can)
      - Malformed JSON (falls back to default action, NOT 'none')
    """
    cleaned = content.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # If there's prose before the JSON, find the first { and last }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = cleaned[first_brace:last_brace + 1]
    else:
        json_candidate = cleaned

    # Try strict parse first
    try:
        parsed = json.loads(json_candidate)
        # "none" is no longer overridden to list_dir — that caused the loop.
        # Treat "none" as "done" (clean end-of-run) instead of falling back
        # to a useless directory listing.
        if parsed.get("action") == "none":
            parsed["action"] = "done"
        return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to extract fields individually from partial/truncated JSON
    # This handles the case where the LLM output got cut off mid-JSON.
    # SAFER DEFAULT: "done" instead of "list_dir docs/tools". The old default
    # caused the agent to keep re-listing the same directory every time the
    # LLM emitted bad JSON, which is what produced the loop. "done" ends the
    # run cleanly and waits for the next cycle.
    extracted = {
        "reasoning": "",
        "action": "done",
        "action_params": {},
        "revenue_update": "",
        "pending_request": "",
        "blocked_note": "",
        "experiment_result": "",
        "analytics_update": "",
    }

    # Extract reasoning
    m = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', json_candidate, re.DOTALL)
    if m:
        try:
            extracted["reasoning"] = json.loads('"' + m.group(1) + '"')
        except Exception:
            extracted["reasoning"] = m.group(1)[:1500]

    # Extract action
    m = re.search(r'"action"\s*:\s*"([^"]+)"', json_candidate)
    if m:
        action = m.group(1).strip().lower()
        if action in ("write_file", "read_file", "list_dir", "delete_file",
                      "append_doc", "http_get", "log_experiment",
                      "update_experiment", "done", "none"):
            extracted["action"] = action

    # Extract action_params if present (best effort)
    m = re.search(r'"action_params"\s*:\s*\{', json_candidate)
    if m:
        # Try to find path
        p = re.search(r'"path"\s*:\s*"([^"]+)"', json_candidate)
        if p:
            extracted["action_params"] = {"path": p.group(1)}
        # Try to find url
        u = re.search(r'"url"\s*:\s*"([^"]+)"', json_candidate)
        if u:
            extracted["action_params"] = {"url": u.group(1)}
        # Try to find hypothesis
        h = re.search(r'"hypothesis"\s*:\s*"([^"]+)"', json_candidate)
        if h:
            extracted["action_params"] = {"hypothesis": h.group(1)}

    # If action is write_file, try to extract content even from truncated JSON.
    # Save what we have with a completion marker — better than doing nothing.
    if extracted["action"] == "write_file":
        path_match = re.search(r'"path"\s*:\s*"([^"]+)"', json_candidate)
        if path_match:
            path = path_match.group(1)
            # Try to extract content — match from "content": " to the end of the string
            # (it's probably truncated, so take everything until end of input or next field)
            content_match = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|$)', json_candidate, re.DOTALL)
            if content_match:
                raw_content = content_match.group(1)
                # Unescape JSON string escapes
                try:
                    content = json.loads('"' + raw_content + '"')
                except Exception:
                    content = raw_content.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
                # If content is non-empty, save it with a completion marker
                if len(content) > 20:
                    # Add a completion note if it looks truncated (no closing </html>)
                    if "</html>" not in content.lower():
                        content = content + "\n\n<!-- FILE INCOMPLETE: agent will continue in next cycle. Use append_doc to add more. -->\n"
                    extracted["action_params"] = {"path": path, "content": content}
                else:
                    # Content too short — end the run cleanly.
                    extracted["action"] = "done"
                    extracted["action_params"] = {}
            else:
                # No content found — end the run cleanly.
                extracted["action"] = "done"
                extracted["action_params"] = {}
        else:
            # No path found — end the run cleanly.
            extracted["action"] = "done"
            extracted["action_params"] = {}

    # If action is none, treat as done (was: list_dir docs/tools — caused loop)
    if extracted["action"] == "none":
        extracted["action"] = "done"
        extracted["action_params"] = {}

    # Log the parse failure for debugging
    if not extracted["reasoning"]:
        # Diagnostic: figure out WHY parsing failed, so the log is useful.
        diag = "unknown reason"
        if not content or not content.strip():
            diag = "LLM returned an EMPTY response (possible safety filter or quota error)"
        elif not content.strip().startswith("{"):
            # LLM emitted prose before JSON (or no JSON at all)
            first_line = content.strip().split("\n", 1)[0][:120]
            diag = f"LLM started with prose instead of JSON. First line: {first_line!r}"
        elif "}" not in content:
            diag = "LLM output has `{` but no closing `}` (truncated mid-JSON)"
        else:
            diag = "JSON present but malformed (likely truncated or has unescaped chars)"
        extracted["reasoning"] = (
            f"[PARSE FALLBACK] {diag}. "
            f"Response length: {len(content)} chars. "
            f"Raw (first 1500 chars): {content[:1500]}"
        )

    return extracted

def apply_memory_updates(parsed):
    """Apply any memory updates from the parsed response.
    Returns the run_summary string (or empty string) if the LLM provided one."""
    if parsed.get("revenue_update"):
        append_file("memory/revenue.md",
                    f"\n[{TIMESTAMP}] {parsed['revenue_update']}\n")
    if parsed.get("pending_request"):
        append_file("memory/pending_requests.md",
                    f"\n[{TIMESTAMP}] {parsed['pending_request']}\n")
    if parsed.get("blocked_note"):
        append_file("memory/blocked.md",
                    f"\n[{TIMESTAMP}] {parsed['blocked_note']}\n")
        cap_log("memory/blocked.md", max_entries=20)
    if parsed.get("experiment_result"):
        append_file("memory/experiments.md",
                    f"\n[{TIMESTAMP}] RESULT: {parsed['experiment_result']}\n")
        cap_log("memory/experiments.md", max_entries=30)
    if parsed.get("analytics_update"):
        append_file("memory/analytics.md",
                    f"\n[{TIMESTAMP}] {parsed['analytics_update']}\n")
        cap_log("memory/analytics.md", max_entries=50)
    # Return the run_summary (or empty string) so the caller can track it.
    return str(parsed.get("run_summary", "") or "")


# Track all steps for this run
run_steps = []
run_summary_parts = []
first_action = "none"
first_model = "unknown"
used_model_for_log = "unknown"
# Track the LLM's prose summary of the run. Updated whenever the LLM provides
# a "run_summary" field — we keep the LAST non-empty one (the LLM is told to
# include it on its final action, so the final "done" response's summary wins).
run_summary_text = ""

for step_num in range(1, max_steps + 1):
    print(f"\n[{TIMESTAMP}] === Step {step_num}/{max_steps} ===")

    # Re-check budget before each LLM call
    if budget.get_total_remaining() <= 0:
        print("    Budget exhausted mid-run, stopping.")
        run_summary_parts.append("Stopped: budget exhausted mid-run.")
        break

    # Trim context if it's getting too large
    messages = trim_messages_if_needed(messages)

    # Call the LLM (with one retry on parse failure, using a stricter prompt)
    response_content = None
    used_provider = "unknown"
    attempts = []
    parsed = None
    for llm_attempt in (1, 2):
        try:
            response_content, used_provider, attempts = call_llm_with_fallback(
                messages, max_tokens=400000, temperature=0.7
            )
            used_model_for_log = used_provider
            if step_num == 1:
                first_model = used_provider
            for a in attempts:
                print(f"    {a}")
        except RuntimeError as e:
            err = str(e)[:500]
            append_file("memory/blocked.md",
                        f"\n[{TIMESTAMP}] LLM call failed at step {step_num}.\n{err}\n")
            cap_log("memory/blocked.md", max_entries=20)
            print(f"    [-] LLM failed: {err}")
            run_summary_parts.append(f"Stopped: LLM failed at step {step_num}.")
            response_content = None
            break

        # Parse the response
        parsed = parse_response(response_content)
        reasoning = str(parsed.get("reasoning", ""))[:1500]

        # Check if parsing fell back to defaults (reasoning starts with [PARSE FALLBACK])
        is_parse_failure = reasoning.startswith("[PARSE FALLBACK]")

        if not is_parse_failure or llm_attempt == 2:
            break  # either parsed OK, or this was our second try

        # Parse failed on first attempt — retry once with a stricter prompt.
        # Pop the bad assistant response so it doesn't pollute the next call,
        # and add a forceful reminder.
        print(f"    [!] Parse failed on attempt 1. Retrying with stricter JSON-only prompt.")
        print(f"        Diagnostic: {reasoning[:200]}")
        # Don't keep the bad assistant response in context — replace it with a
        # short note so the LLM knows what just happened.
        messages.append({"role": "assistant", "content": response_content[:500]})
        messages.append({
            "role": "user",
            "content": (
                "ERROR: Your previous response was NOT valid JSON. "
                "It either started with prose, was truncated, or had malformed syntax. "
                "Try AGAIN. Respond with ONLY a single JSON object. "
                "The very first character MUST be `{` and the very last MUST be `}`. "
                "No prose, no markdown fences, no thinking out loud. "
                "Pick a concrete action (write_file a new tool is best) and emit the JSON now."
            ),
        })

    if response_content is None:
        # LLM call itself failed on both attempts — already logged above
        break

    # Always append the final assistant response to the conversation.
    # (If we retried, we already appended the truncated bad response + the
    # error user-message above; now we append the final attempt's response.)
    messages.append({"role": "assistant", "content": response_content})

    # Use the parsed result from the final attempt
    reasoning = str(parsed.get("reasoning", ""))[:1500]
    action = parsed.get("action", "none")
    action_params = parsed.get("action_params", {}) or {}

    if step_num == 1:
        first_action = action

    print(f"    Action: {action}")
    print(f"    Reasoning: {reasoning[:200]}...")

    # Check for termination actions
    if action in ("none", "done"):
        run_steps.append({
            "step": step_num,
            "action": action,
            "reasoning": reasoning,
            "result": "Cycle ended by agent.",
        })
        run_summary_parts.append(f"Step {step_num}: {action} — {reasoning[:100]}")
        # Apply any final memory updates
        _summary_from_step = apply_memory_updates(parsed)
        if _summary_from_step:
            run_summary_text = _summary_from_step
        break

    # Pre-execution safety: if write_file has empty/too-short content, end
    # the run cleanly. (Was: fall back to list_dir docs/tools — that fallback
    # was a major contributor to the loop.)
    if action == "write_file":
        content_check = action_params.get("content", "")
        if not content_check or len(content_check) < 20:
            print(f"    write_file content too short ({len(content_check)} chars), ending run")
            action = "done"
            action_params = {}

    # Execute the action
    success, action_result = tools.execute_action(action, action_params)
    status = "OK" if success else "FAIL"
    print(f"    Result ({status}): {action_result[:200]}")

    # Apply memory updates from this step
    _summary_from_step = apply_memory_updates(parsed)
    if _summary_from_step:
        run_summary_text = _summary_from_step

    run_steps.append({
        "step": step_num,
        "action": action,
        "action_params": action_params,
        "reasoning": reasoning,
        "result": action_result[:500],
        "success": success,
    })
    run_summary_parts.append(f"Step {step_num}: {action} ({status})")

    # Build a summary of actions taken so far this cycle
    actions_taken_summary = ", ".join(
        f"step {s['step']}: {s['action']}({s.get('action_params', {}).get('path', s.get('action_params', {}).get('url', ''))})"
        for s in run_steps
    )

    # Feed the action result back to the LLM for the next step
    feedback = (
        f"Step {step_num} result ({'success' if success else 'failure'}):\n"
        f"{action_result[:1200]}\n\n"
        f"ACTIONS TAKEN THIS CYCLE: {actions_taken_summary}\n\n"
        f"You have {max_steps - step_num} step(s) remaining. "
        f"DO NOT repeat any action you already took. "
        f"If you logged an experiment about building something, your next step should be write_file to build it. "
        f"Continue with a NEW action, or use \"done\" if you've completed meaningful work."
    )
    messages.append({"role": "user", "content": feedback})

    # Detect repeated identical actions (infinite loop prevention)
    # Count how many times the most recent action has been taken this cycle.
    # LOWERED from 2 to 2 (kept), but also detect repeated actions even when
    # the path differs slightly — e.g. two list_dirs in a row on any path.
    current_action = run_steps[-1]["action"]
    current_path = run_steps[-1].get("action_params", {}).get("path", "")
    repeat_count = sum(1 for s in run_steps
                       if s["action"] == current_action
                       and s.get("action_params", {}).get("path", "") == current_path)
    # ALSO break if the same action type happened twice in a row, regardless
    # of params — e.g. two list_dirs, two read_files. This prevents the
    # agent from bouncing between slightly different list_dir calls.
    consecutive_same_type = 1
    if len(run_steps) >= 2 and run_steps[-2]["action"] == current_action:
        consecutive_same_type = 2
    if repeat_count >= 2 or consecutive_same_type >= 2:
        print(f"    Detected repeated action ({current_action} {current_path} "
              f"taken {repeat_count}x, consecutive same-type={consecutive_same_type}) "
              f"— stopping to prevent loop.")
        run_summary_parts.append(
            f"Stopped: repeated action ({current_action} {current_path})."
        )
        break

else:
    # Loop completed without break — max steps reached
    run_summary_parts.append(f"Completed all {max_steps} steps.")


# ---------------------------------------------------------------------------
# LOG FULL DETAIL (clean, readable format)
# ---------------------------------------------------------------------------

def short_action_desc(action, params):
    """Generate a short human-readable description of an action."""
    if action == "write_file":
        path = params.get("path", "?")
        size = len(params.get("content", ""))
        return f"write_file → {path} ({size} chars)"
    elif action == "append_doc":
        path = params.get("path", "?")
        size = len(params.get("append_text", ""))
        return f"append_doc → {path} (+{size} chars)"
    elif action == "read_file":
        return f"read_file → {params.get('path', '?')}"
    elif action == "list_dir":
        return f"list_dir → {params.get('path', '?')}"
    elif action == "delete_file":
        return f"delete_file → {params.get('path', '?')}"
    elif action == "http_get":
        return f"http_get → {params.get('url', '?')[:60]}"
    elif action == "log_experiment":
        hyp = params.get("hypothesis", "")[:60]
        return f"log_experiment: {hyp}"
    elif action == "update_experiment":
        return f"update_experiment → {params.get('decision', '?')}"
    elif action == "solve_captcha":
        return f"solve_captcha ({params.get('captcha_type', 'text')})"
    elif action == "check_wallet_balance":
        return f"check_wallet → {params.get('chain', '?')}"
    elif action == "check_all_wallets":
        return "check_all_wallets"
    elif action == "log_opportunity":
        src = params.get("source", "?")[:40]
        return f"log_opportunity: {src}"
    elif action == "log_revenue":
        amt = params.get("amount", "?")
        cur = params.get("currency", "USD")
        src = params.get("source", "?")[:30]
        return f"log_revenue: {amt} {cur} from {src}"
    elif action == "request_human_action":
        plat = params.get("platform", "?")[:30]
        act = params.get("action_type", "?")
        return f"request_human: {act} for {plat}"
    elif action in ("done", "none"):
        return action
    return action

def short_result(result, limit=280):
    """Truncate result to a readable length."""
    result = result or ""
    result = result.replace("\n", " ").strip()
    if len(result) > limit:
        return result[:limit] + "..."
    return result

# Build clean step-by-step log
steps_lines = []
for s in run_steps:
    step_num = s["step"]
    action_desc = short_action_desc(s["action"], s.get("action_params", {}))
    result_short = short_result(s.get("result", ""), 280)
    success = s.get("success", None)
    status_icon = "✓" if success else ("→" if success is None else "✗")
    steps_lines.append(f"  {status_icon} Step {step_num}: {action_desc}")
    steps_lines.append(f"      Result: {result_short}")

steps_detail = "\n".join(steps_lines)

log_entry = (
    f"\n## Run: {TIMESTAMP}\n"
    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    f"  Model:    {used_model_for_log}\n"
    f"  Budget:   {budget_level} ({total_used}/{total_limit} used)\n"
    f"  Steps:    {len(run_steps)} / {max_steps}\n"
    f"  Outcome:  {run_summary_parts[-1] if run_summary_parts else 'completed'}\n"
    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    f"\n{steps_detail}\n"
    f"\n---\n"
)
append_file("memory/action_log.md", log_entry)

# Cap action_log.md to last 100 runs (~500KB max)
_log = read_file("memory/action_log.md")
if len(_log) > 500_000:
    _parts = _log.split("---\n")
    _trimmed = "---\n".join(_parts[-100:])
    write_file("memory/action_log.md", _trimmed)


# ---------------------------------------------------------------------------
# COMPACT SUMMARY for state.md — now in plain English prose (200-300 words)
# ---------------------------------------------------------------------------

def generate_fallback_summary():
    """Generate a 200-300 word English prose summary of this run if the LLM
    didn't provide one. This is the fallback; the preferred source is the
    LLM's own 'run_summary' field, which is more insightful."""
    outcome = run_summary_parts[-1] if run_summary_parts else "completed"
    steps_count = len(run_steps)
    # Build a readable description of each step
    step_descriptions = []
    for s in run_steps:
        action_desc = short_action_desc(s["action"], s.get("action_params", {}))
        success = s.get("success", None)
        status_word = "succeeded" if success else ("ran" if success is None else "failed")
        step_descriptions.append(f"step {s['step']} ({action_desc}, which {status_word})")
    if step_descriptions:
        if len(step_descriptions) == 1:
            actions_clause = f"The agent took one action: {step_descriptions[0]}."
        else:
            actions_clause = (
                f"The agent took {steps_count} actions in sequence: "
                + "; ".join(step_descriptions[:-1])
                + f"; and finally {step_descriptions[-1]}."
            )
    else:
        actions_clause = "The agent did not complete any actions this run."

    # Compose a ~200-300 word prose summary
    parts = [
        f"This run began at {TIMESTAMP} using the {used_model_for_log} language model. "
        f"Daily LLM budget at the start of the run was {budget_level} "
        f"({total_used} of {total_limit} requests used across all providers, "
        f"with {total_remaining} remaining). The agent was allocated a maximum of "
        f"{max_steps} steps for this cycle and completed {steps_count} of them. "
        f"The run's outcome was: {outcome}.",
        actions_clause,
        f"Budget consumption was minimal this cycle, leaving ample capacity for "
        f"subsequent runs today. The agent's persistent memory files — including "
        f"action_log.md, blocked.md, experiments.md, and budget.md — were updated "
        f"to reflect this run's activity. The next scheduled run will occur in "
        f"approximately 30 minutes via GitHub Actions, at which point the agent "
        f"will re-read all memory files, check budget status, and decide its next "
        f"action based on what it finds.",
        f"If this run did not produce useful work (for example, if it ended in a "
        f"parse failure or a premature 'done'), the next run should recover "
        f"automatically thanks to the JSON-mode enforcement and retry-on-failure "
        f"mechanisms now in place. The human operator can review this state.md "
        f"file at any time to understand what the agent has been doing.",
    ]
    return " ".join(parts)

# Use the LLM's prose summary if provided; otherwise generate a fallback.
if run_summary_text and len(run_summary_text.strip()) > 50:
    prose_summary = run_summary_text.strip()
else:
    prose_summary = generate_fallback_summary()

# Extract last 2 prior summaries to keep in state.md (rolling window).
# Each summary is now ~200-300 words (~1500-2500 chars), so 2 prior + 1 new
# = ~7500 chars max — well within readable limits.
_prior_state = state_content
_prior_summaries = []
if _prior_state:
    chunks = _prior_state.split("## Summary — ")
    for chunk in chunks[1:]:
        prior_summary = ("## Summary — " + chunk).strip()
        if prior_summary and len(prior_summary) < 15000:
            _prior_summaries.append(prior_summary)
_prior_summaries = _prior_summaries[-2:]

# Build a short "Actions taken" list (kept as a compact reference under the prose)
steps_one_liners = []
for s in run_steps:
    action_desc = short_action_desc(s["action"], s.get("action_params", {}))
    success = s.get("success", None)
    status_icon = "✓" if success else ("→" if success is None else "✗")
    steps_one_liners.append(f"  {status_icon} {action_desc}")
actions_list = "\n".join(steps_one_liners) if steps_one_liners else "  (none)"

new_summary = (
    f"## Summary — {TIMESTAMP}\n"
    f"**Model:** {used_model_for_log} | **Budget:** {budget_level} ({total_used}/{total_limit}) | **Steps:** {len(run_steps)}/{max_steps}\n\n"
    f"{prose_summary}\n\n"
    f"**Actions taken this run:**\n{actions_list}\n"
)

state_content_out = "\n\n".join(_prior_summaries + [new_summary]) + "\n"
write_file("memory/state.md", state_content_out)

print(f"\n[+] Run complete at {TIMESTAMP}")
print(f"    Model: {used_model_for_log}")
print(f"    Steps: {len(run_steps)}")
print(f"    Budget: {budget.get_budget_summary()}")
print(f"    First action: {first_action}")
