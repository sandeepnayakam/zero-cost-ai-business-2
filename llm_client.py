#!/usr/bin/env python3
"""
Multi-provider LLM client with automatic fallback + budget tracking
+ DYNAMIC MODEL DISCOVERY.

This version auto-discovers available models from each provider's /models
endpoint, so you never have to update model names manually when providers
add or deprecate models.

Supports SEVEN free LLM providers (use any subset):
  1. Groq          - GROQ_API_KEY
  2. Google Gemini - GEMINI_API_KEY
  3. OpenRouter    - OPENROUTER_API_KEY  (supports openrouter/free alias)
  4. Cerebras      - CEREBRAS_API_KEY
  5. SambaNova     - SAMBANOVA_API_KEY
  6. Cloudflare    - CF_API_TOKEN + CF_ACCOUNT_ID
  7. HuggingFace   - HF_TOKEN

Budget integration:
  - Before calling, checks budget.get_remaining(provider)
  - After successful call, calls budget.record_usage(provider)
  - Skips providers with zero remaining budget
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple, List

import budget


# ---------------------------------------------------------------------------
# Fallback model lists (used if dynamic discovery fails)
# These are intentionally short — the dynamic fetch is the primary source.
# ---------------------------------------------------------------------------

FALLBACK_MODELS = {
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ],
    "gemini": [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
    ],
    "cerebras": [
        "llama-3.1-8b-instant",
        "llama3.1-70b",
    ],
    "sambanova": [
        "Meta-Llama-3.1-405B-Instruct",
        "Meta-Llama-3.1-70B-Instruct",
        "Meta-Llama-3.1-8B-Instruct",
    ],
    "cloudflare": [
        "@cf/meta/llama-3.1-8b-instruct",
        "@cf/meta/llama-3-8b-instruct",
    ],
    "huggingface": [
        "meta-llama/Meta-Llama-3-8B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "Qwen/Qwen2.5-7B-Instruct",
    ],
    "openrouter": [
        "openrouter/free",  # Special alias — uses any free model
    ],
}

# Known deprecated model prefixes (filtered out of dynamic discovery)
DEPRECATED_PATTERNS = [
    "gemini-1.5-",      # Deprecated Oct 2025
    "gemini-1.0-",      # Old
    "text-bison",       # Old PaLM
    "chat-bison",       # Old PaLM
    "gpt-3.5-turbo",    # OpenRouter legacy
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _post_json(url: str, headers: dict, payload: dict, timeout: int = 45) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, headers: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _is_deprecated(model_id: str) -> bool:
    """Check if a model matches any deprecated pattern."""
    model_lower = model_id.lower()
    for pattern in DEPRECATED_PATTERNS:
        if pattern in model_lower:
            return True
    return False


# ---------------------------------------------------------------------------
# Dynamic model discovery
# ---------------------------------------------------------------------------

def _cache_path(provider: str) -> str:
    return os.path.join("memory", "models_cache", f"{provider}.json")


def _read_cache(provider: str) -> Optional[List[str]]:
    """Read cached model list. Returns None if not cached or stale (>24h old)."""
    path = _cache_path(provider)
    try:
        with open(path, "r") as f:
            data = json.load(f)
        # Cache valid for 24 hours
        if time.time() - data.get("timestamp", 0) > 86400:
            return None
        return data.get("models", [])
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return None


def _write_cache(provider: str, models: List[str]):
    path = _cache_path(provider)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"timestamp": time.time(), "models": models}, f, indent=2)


def _discover_groq() -> List[str]:
    """Fetch available models from Groq."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return []
    try:
        data = _get_json(
            "https://api.groq.com/openai/v1/models",
            {"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        models = [m["id"] for m in data.get("data", [])]
        # Filter to instruction-tuned chat models (skip whisper, gemma, etc. for chat)
        chat_models = [m for m in models if any(k in m.lower() for k in
            ["llama", "mixtral", "gemma"])]
        return [m for m in chat_models if not _is_deprecated(m)]
    except Exception:
        return []


def _discover_gemini() -> List[str]:
    """Fetch available models from Google Gemini."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return []
    try:
        data = _get_json(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            {},
            timeout=15,
        )
        models = []
        for m in data.get("models", []):
            name = m.get("name", "").replace("models/", "")
            # Only include text-generation models (skip embedding, tts, etc.)
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods and not _is_deprecated(name):
                models.append(name)
        return models
    except Exception:
        return []


def _discover_openrouter() -> List[str]:
    """OpenRouter has a special alias 'openrouter/free' that auto-routes to free models.
    We use that as the primary, plus a few specific free models as fallback."""
    # The alias always works — no need to fetch the full model list
    return ["openrouter/free"]


def _discover_cerebras() -> List[str]:
    """Fetch available models from Cerebras."""
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        return []
    try:
        data = _get_json(
            "https://api.cerebras.ai/v1/models",
            {"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        models = [m["id"] for m in data.get("data", [])]
        return [m for m in models if not _is_deprecated(m)]
    except Exception:
        return []


def _discover_sambanova() -> List[str]:
    """Fetch available models from SambaNova."""
    api_key = os.environ.get("SAMBANOVA_API_KEY")
    if not api_key:
        return []
    try:
        data = _get_json(
            "https://api.sambanova.ai/v1/models",
            {"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        models = [m["id"] for m in data.get("data", [])]
        return [m for m in models if not _is_deprecated(m)]
    except Exception:
        return []


def _discover_cloudflare() -> List[str]:
    """Fetch available models from Cloudflare Workers AI."""
    api_token = os.environ.get("CF_API_TOKEN")
    account_id = os.environ.get("CF_ACCOUNT_ID")
    if not api_token or not account_id:
        return []
    try:
        data = _get_json(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search",
            {"Authorization": f"Bearer {api_token}"},
            timeout=15,
        )
        models = []
        for m in data.get("result", []):
            if m.get("type") == "text-generation":
                name = m.get("name", "")
                if name and not _is_deprecated(name):
                    models.append(name)
        return models
    except Exception:
        return []


def _discover_huggingface() -> List[str]:
    """HuggingFace has thousands of models — use the fallback list.
    Dynamic discovery would require polling the inference API per model."""
    return FALLBACK_MODELS.get("huggingface", [])


DISCOVERERS = {
    "groq":        _discover_groq,
    "gemini":      _discover_gemini,
    "openrouter":  _discover_openrouter,
    "cerebras":    _discover_cerebras,
    "sambanova":   _discover_sambanova,
    "cloudflare":  _discover_cloudflare,
    "huggingface": _discover_huggingface,
}


def get_models_for_provider(provider: str) -> List[str]:
    """Get available models for a provider. Uses cache, then dynamic discovery,
    then falls back to hardcoded list."""
    # Try cache first
    cached = _read_cache(provider)
    if cached:
        return cached

    # Try dynamic discovery
    discoverer = DISCOVERERS.get(provider)
    if discoverer:
        try:
            models = discoverer()
            if models:
                _write_cache(provider, models)
                return models
        except Exception:
            pass

    # Fall back to hardcoded list
    return FALLBACK_MODELS.get(provider, [])


# ---------------------------------------------------------------------------
# Provider call implementations
# ---------------------------------------------------------------------------

def _call_groq(messages, model, max_tokens, temperature, json_mode=False):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    # Force JSON-only output so the LLM can't waste tokens on prose preamble.
    # Groq (OpenAI-compatible) supports response_format=json_object.
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post_json(url, headers, payload, timeout=60)
    return data["choices"][0]["message"]["content"], "groq"


def _call_openrouter(messages, model, max_tokens, temperature, json_mode=False):
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
    # OpenRouter supports response_format=json_object for OpenAI-compatible models.
    # For the "openrouter/free" alias this may be ignored, but it's harmless.
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post_json(url, headers, payload, timeout=60)
    return data["choices"][0]["message"]["content"], "openrouter"


def _call_gemini(messages, model, max_tokens, temperature, json_mode=False):
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
    # Gemini supports responseMimeType="application/json" which FORCES the model
    # to output only valid JSON — no prose preamble, no markdown fences.
    # This is the single biggest fix for the "Raw: The user wants me to o" parse
    # failures, where Gemini was burning its output token budget on conversational
    # text before getting to the JSON.
    gen_config = {"maxOutputTokens": max_tokens, "temperature": temperature}
    if json_mode:
        gen_config["responseMimeType"] = "application/json"
    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]} if system_text else None,
        "contents": contents,
        "generationConfig": gen_config,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    data = _post_json(url, {"Content-Type": "application/json"}, payload, timeout=60)
    return data["candidates"][0]["content"]["parts"][0]["text"], "gemini"


def _call_cerebras(messages, model, max_tokens, temperature, json_mode=False):
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        raise RuntimeError("CEREBRAS_API_KEY not set")
    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post_json(url, headers, payload, timeout=60)
    return data["choices"][0]["message"]["content"], "cerebras"


def _call_sambanova(messages, model, max_tokens, temperature, json_mode=False):
    api_key = os.environ.get("SAMBANOVA_API_KEY")
    if not api_key:
        raise RuntimeError("SAMBANOVA_API_KEY not set")
    url = "https://api.sambanova.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post_json(url, headers, payload, timeout=90)
    return data["choices"][0]["message"]["content"], "sambanova"


def _call_cloudflare(messages, model, max_tokens, temperature, json_mode=False):
    api_token = os.environ.get("CF_API_TOKEN")
    account_id = os.environ.get("CF_ACCOUNT_ID")
    if not api_token or not account_id:
        raise RuntimeError("CF_API_TOKEN or CF_ACCOUNT_ID not set")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    # Cloudflare Workers AI does not support response_format natively.
    # json_mode is accepted but ignored — the prompt's "JSON only" instruction
    # is the only enforcement for this provider.
    data = _post_json(url, headers, payload, timeout=60)
    return data["result"]["response"], "cloudflare"


def _call_huggingface(messages, model, max_tokens, temperature, json_mode=False):
    api_key = os.environ.get("HF_TOKEN")
    if not api_key:
        raise RuntimeError("HF_TOKEN not set")
    url = f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    # HuggingFace's OpenAI-compatible endpoint supports response_format on some models.
    # If the model doesn't support it, the API will ignore it (harmless).
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post_json(url, headers, payload, timeout=60)
    return data["choices"][0]["message"]["content"], "huggingface"


# ---------------------------------------------------------------------------
# Provider registry — order matters, tried top-to-bottom
# ---------------------------------------------------------------------------

PROVIDERS = [
    # (name, env_var_to_check, call_fn)
    ("groq",        "GROQ_API_KEY",        _call_groq),
    ("gemini",      "GEMINI_API_KEY",      _call_gemini),
    ("cerebras",    "CEREBRAS_API_KEY",    _call_cerebras),
    ("sambanova",   "SAMBANOVA_API_KEY",   _call_sambanova),
    ("cloudflare",  "CF_API_TOKEN",        _call_cloudflare),
    ("huggingface", "HF_TOKEN",            _call_huggingface),
    ("openrouter",  "OPENROUTER_API_KEY",  _call_openrouter),
]

MAX_RETRIES_PER_MODEL = 1
RETRY_DELAY_SECONDS = 5


def list_available_providers() -> list:
    """Return list of providers that have API keys configured AND have budget remaining."""
    budget.reset_if_new_day()
    result = []
    for name, env, _ in PROVIDERS:
        if os.environ.get(env) and budget.get_remaining(name) > 0:
            result.append(name)
    return result


def list_configured_providers() -> list:
    """Return list of providers that have API keys configured (regardless of budget)."""
    return [name for name, env, _ in PROVIDERS if os.environ.get(env)]


def call_llm_with_fallback(messages, max_tokens=3000, temperature=0.7, json_mode=True):
    """
    Try every configured provider/model in order until one succeeds.
    Budget-aware: skips providers with zero remaining budget.

    Args:
        json_mode: If True (default), forces JSON-only output from the LLM.
                   This prevents the LLM from wasting output tokens on prose
                   preamble like "The user wants me to..." before the JSON.
                   Gemini uses responseMimeType, OpenAI-compatible APIs use
                   response_format=json_object.

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

    available = list_available_providers()
    if not available:
        raise RuntimeError(
            f"All configured providers exhausted daily budget. "
            f"Configured: {configured}. Budget resets at UTC midnight."
        )

    # Try each provider in priority order
    for provider_name, env_var, call_fn in PROVIDERS:
        if provider_name not in available:
            if provider_name in configured:
                attempts.append(f"SKIP {provider_name} - budget exhausted")
            continue

        # Dynamically discover models for this provider
        models = get_models_for_provider(provider_name)
        if not models:
            attempts.append(f"SKIP {provider_name} - no models available")
            continue

        for model in models:
            for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
                try:
                    content, used_provider = call_fn(
                        messages, model, max_tokens, temperature,
                        json_mode=json_mode,
                    )
                    budget.record_usage(used_provider)
                    attempts.append(f"OK {used_provider}/{model} (attempt {attempt})")
                    return content, used_provider, attempts
                except Exception as e:
                    err_msg = str(e)[:200]
                    attempts.append(f"FAIL {provider_name}/{model} attempt {attempt}: {err_msg}")
                    # If 404 (model not found), don't retry this model — move to next
                    if "404" in err_msg or "Not Found" in err_msg:
                        break
                    # If response_format is unsupported (400), retry without it
                    if "400" in err_msg and ("response_format" in err_msg or "response_mime" in err_msg or "responseMimeType" in err_msg):
                        try:
                            content, used_provider = call_fn(
                                messages, model, max_tokens, temperature,
                                json_mode=False,
                            )
                            budget.record_usage(used_provider)
                            attempts.append(f"OK {used_provider}/{model} (attempt {attempt}, json_mode=off fallback)")
                            return content, used_provider, attempts
                        except Exception as e2:
                            attempts.append(f"FAIL {provider_name}/{model} no-json-mode fallback: {str(e2)[:200]}")
                        break
                    if attempt < MAX_RETRIES_PER_MODEL:
                        time.sleep(RETRY_DELAY_SECONDS)

            # Check if this provider's budget got exhausted during retries
            if budget.get_remaining(provider_name) <= 0:
                attempts.append(f"BUDGET_EXHAUSTED {provider_name}")
                break

    raise RuntimeError("All LLM providers failed. Attempts:\n" + "\n".join(attempts))
