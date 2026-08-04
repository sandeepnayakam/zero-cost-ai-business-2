#!/usr/bin/env python3
"""
Multi-provider LLM client with automatic fallback + budget tracking.

Supports SEVEN free LLM providers (use any subset, the agent will try them
in priority order until one succeeds):

  1. Groq          - GROQ_API_KEY          (RECOMMENDED - fast + generous free tier)
  2. Google Gemini - GEMINI_API_KEY        (RECOMMENDED - best free quality)
  3. OpenRouter    - OPENROUTER_API_KEY    (multiple free models as fallback)
  4. Cerebras      - CEREBRAS_API_KEY      (free, super-fast)
  5. SambaNova     - SAMBANOVA_API_KEY     (free, big models)
  6. Cloudflare    - CF_API_TOKEN + CF_ACCOUNT_ID (Workers AI free tier)
  7. HuggingFace   - HF_TOKEN              (free, open models)

Budget integration:
  - Before calling, checks budget.get_remaining(provider)
  - After successful call, calls budget.record_usage(provider)
  - Skips providers with zero remaining budget
  - If all providers exhausted, raises RuntimeError
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple

import budget


# ---------------------------------------------------------------------------
# Provider configurations
# ---------------------------------------------------------------------------

# OpenRouter free models — listed from most to least reliable
OPENROUTER_FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "deepseek/deepseek-r1:free",
    "meta-llama/llama-3.1-8b-instruct:free",
]

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

CEREBRAS_MODELS = [
    "llama-3.1-8b-instant",
    "llama3.1-70b",
]

SAMBANOVA_MODELS = [
    "Meta-Llama-3.1-405B-Instruct",
    "Meta-Llama-3.1-70B-Instruct",
    "Meta-Llama-3.1-8B-Instruct",
]

CLOUDFLARE_MODELS = [
    "@cf/meta/llama-3.1-8b-instruct",
    "@cf/meta/llama-3-8b-instruct",
    "@hf/thebloke/neural-chat-7b-v3-1-awq",
]

HUGGINGFACE_MODELS = [
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "Qwen/Qwen2.5-7B-Instruct",
]


# ---------------------------------------------------------------------------
# HTTP helpers (urllib, no external deps)
# ---------------------------------------------------------------------------

def _post_json(url: str, headers: dict, payload: dict, timeout: int = 45) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Provider implementations — each returns (content, model_used) or raises
# ---------------------------------------------------------------------------

def _call_groq(messages, model, max_tokens, temperature):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    data = _post_json(url, headers, payload, timeout=60)
    return data["choices"][0]["message"]["content"], "groq"


def _call_openrouter(messages, model, max_tokens, temperature):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/zero-cost-ai-business",
        "X-Title": "Zero-Cost AI Business Agent",
    }
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    data = _post_json(url, headers, payload, timeout=60)
    return data["choices"][0]["message"]["content"], "openrouter"


def _call_gemini(messages, model, max_tokens, temperature):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    system_text = ""
    contents = []
    for m in messages:
        if m["role"] == "system":
            system_text += m["content"] + "\n"
        elif m["role"] == "user":
            contents.append({"role": "user", "parts": [{"text": m["content"]}]})
        elif m["role"] == "assistant":
            contents.append({"role": "model", "parts": [{"text": m["content"]}]})
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]} if system_text else None,
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    data = _post_json(url, {"Content-Type": "application/json"}, payload, timeout=60)
    return data["candidates"][0]["content"]["parts"][0]["text"], "gemini"


def _call_cerebras(messages, model, max_tokens, temperature):
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        raise RuntimeError("CEREBRAS_API_KEY not set")
    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    data = _post_json(url, headers, payload, timeout=60)
    return data["choices"][0]["message"]["content"], "cerebras"


def _call_sambanova(messages, model, max_tokens, temperature):
    api_key = os.environ.get("SAMBANOVA_API_KEY")
    if not api_key:
        raise RuntimeError("SAMBANOVA_API_KEY not set")
    url = "https://api.sambanova.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    data = _post_json(url, headers, payload, timeout=90)
    return data["choices"][0]["message"]["content"], "sambanova"


def _call_cloudflare(messages, model, max_tokens, temperature):
    api_token = os.environ.get("CF_API_TOKEN")
    account_id = os.environ.get("CF_ACCOUNT_ID")
    if not api_token or not account_id:
        raise RuntimeError("CF_API_TOKEN or CF_ACCOUNT_ID not set")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    data = _post_json(url, headers, payload, timeout=60)
    return data["result"]["response"], "cloudflare"


def _call_huggingface(messages, model, max_tokens, temperature):
    api_key = os.environ.get("HF_TOKEN")
    if not api_key:
        raise RuntimeError("HF_TOKEN not set")
    url = f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    data = _post_json(url, headers, payload, timeout=60)
    return data["choices"][0]["message"]["content"], "huggingface"


# ---------------------------------------------------------------------------
# Provider registry — order matters, tried top-to-bottom
# ---------------------------------------------------------------------------

PROVIDERS = [
    # (name, env_var_to_check, models_list, call_fn)
    ("groq",        "GROQ_API_KEY",        GROQ_MODELS,        _call_groq),
    ("gemini",      "GEMINI_API_KEY",      GEMINI_MODELS,      _call_gemini),
    ("cerebras",    "CEREBRAS_API_KEY",    CEREBRAS_MODELS,    _call_cerebras),
    ("sambanova",   "SAMBANOVA_API_KEY",   SAMBANOVA_MODELS,   _call_sambanova),
    ("cloudflare",  "CF_API_TOKEN",        CLOUDFLARE_MODELS,  _call_cloudflare),
    ("huggingface", "HF_TOKEN",            HUGGINGFACE_MODELS, _call_huggingface),
    ("openrouter",  "OPENROUTER_API_KEY",  OPENROUTER_FREE_MODELS, _call_openrouter),
]

MAX_RETRIES_PER_MODEL = 1
RETRY_DELAY_SECONDS = 5


def list_available_providers() -> list:
    """Return list of providers that have API keys configured AND have budget remaining."""
    budget.reset_if_new_day()
    result = []
    for name, env, _, _ in PROVIDERS:
        if os.environ.get(env) and budget.get_remaining(name) > 0:
            result.append(name)
    return result


def list_configured_providers() -> list:
    """Return list of providers that have API keys configured (regardless of budget)."""
    return [name for name, env, _, _ in PROVIDERS if os.environ.get(env)]


def call_llm_with_fallback(messages, max_tokens=3000, temperature=0.7):
    """
    Try every configured provider/model in order until one succeeds.
    Budget-aware: skips providers with zero remaining budget.

    Returns: (content, provider_name, attempts_log)
    Raises:  RuntimeError if ALL providers fail or budget exhausted.
    """
    attempts = []
    budget.reset_if_new_day()

    configured = list_configured_providers()
    if not configured:
        raise RuntimeError(
            "No LLM provider API keys found. Set at least one of: "
            "GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, CEREBRAS_API_KEY, "
            "SAMBANOVA_API_KEY, CF_API_TOKEN+CF_ACCOUNT_ID, HF_TOKEN"
        )

    # Check if any provider has budget
    available = list_available_providers()
    if not available:
        raise RuntimeError(
            f"All configured providers exhausted daily budget. "
            f"Configured: {configured}. Budget resets at UTC midnight."
        )

    # Try each provider in priority order
    for provider_name, env_var, models, call_fn in PROVIDERS:
        if provider_name not in available:
            if provider_name in configured:
                attempts.append(f"SKIP {provider_name} - budget exhausted")
            continue

        for model in models:
            for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
                try:
                    content, used_provider = call_fn(messages, model, max_tokens, temperature)
                    # Record budget usage
                    budget.record_usage(used_provider)
                    attempts.append(f"OK {used_provider}/{model} (attempt {attempt})")
                    return content, used_provider, attempts
                except Exception as e:
                    err_msg = str(e)[:200]
                    attempts.append(f"FAIL {provider_name}/{model} attempt {attempt}: {err_msg}")
                    if attempt < MAX_RETRIES_PER_MODEL:
                        time.sleep(RETRY_DELAY_SECONDS)

            # Check if this provider's budget got exhausted during retries
            if budget.get_remaining(provider_name) <= 0:
                attempts.append(f"BUDGET_EXHAUSTED {provider_name}")
                break

    raise RuntimeError("All LLM providers failed. Attempts:\n" + "\n".join(attempts))
