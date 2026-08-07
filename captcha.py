#!/usr/bin/env python3
"""
CAPTCHA Solving Module
======================

Uses free vision-capable LLMs (Gemini, GPT-4V via OpenRouter) to solve
simple text CAPTCHAs. This is for legitimate use cases like:
  - Account registration on platforms the agent needs to use
  - Form submission for legitimate services
  - Directory submission for the agent's own website

⚠️  ETHICS & COMPLIANCE:
  - Only use for legitimate, ToS-compliant purposes
  - Do NOT use for mass account creation, spam, or scraping
  - Do NOT use to bypass rate limits on services
  - Many sites' ToS prohibit automated CAPTCHA solving
  - The agent must log every CAPTCHA solve in memory/captcha_log.md
  - If a site's ToS prohibits this, the agent should request human help instead

Supported CAPTCHA types:
  - Simple text CAPTCHAs (most common)
  - Math CAPTCHAs (e.g., "2 + 3 = ?")
  - Does NOT support: reCAPTCHA, hCaptcha, Cloudflare Turnstile, image grids

Free vision model options:
  - Gemini 2.0 Flash (GEMINI_API_KEY) — best free option
  - OpenRouter free vision models (limited)
"""

import os
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone

CAPTCHA_LOG_FILE = "memory/captcha_log.md"


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _log_captcha_solve(image_source, result, success, provider):
    """Log every CAPTCHA solve attempt for audit."""
    log_entry = (
        f"\n[{_timestamp()}] {provider}\n"
        f"  Source: {image_source[:100]}\n"
        f"  Result: {result if success else 'FAILED: ' + result}\n"
        f"  Success: {success}\n"
    )
    try:
        with open(CAPTCHA_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass


def _fetch_image_as_base64(image_source):
    """Fetch an image from URL or read from file, return base64."""
    if image_source.startswith("http://") or image_source.startswith("https://"):
        req = urllib.request.Request(image_source, headers={"User-Agent": "ZeroCostAIBot/4.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            image_data = resp.read()
    else:
        with open(image_source, "rb") as f:
            image_data = f.read()
    return base64.b64encode(image_data).decode("utf-8")


def _solve_with_gemini(image_b64, prompt):
    """Use Gemini's vision API to solve the CAPTCHA."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": image_b64}}
            ]
        }],
        "generationConfig": {"maxOutputTokens": 50, "temperature": 0.1}
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    return result["candidates"][0]["content"]["parts"][0]["text"].strip()


def solve_captcha(image_source, captcha_type="text"):
    """
    Solve a CAPTCHA image.

    Args:
        image_source: URL or local file path to the CAPTCHA image
        captcha_type: "text" (default), "math", or "alphanumeric"

    Returns:
        (success: bool, result: str) — the CAPTCHA text if successful

    Note: Every solve attempt is logged to memory/captcha_log.md for audit.
    """
    prompts = {
        "text": "This image contains a CAPTCHA. Read the text in the image and respond with ONLY the text, nothing else. No explanation, just the CAPTCHA text.",
        "math": "This image contains a math CAPTCHA. Solve the math problem shown and respond with ONLY the numeric answer, nothing else.",
        "alphanumeric": "This image contains an alphanumeric CAPTCHA (letters and numbers). Read the characters in the image and respond with ONLY those characters, nothing else.",
    }

    prompt = prompts.get(captcha_type, prompts["text"])

    try:
        image_b64 = _fetch_image_as_base64(image_source)
    except Exception as e:
        _log_captcha_solve(image_source, str(e), False, "fetch")
        return False, f"Failed to fetch image: {e}"

    # Try Gemini first (best free vision model)
    if os.environ.get("GEMINI_API_KEY"):
        try:
            result = _solve_with_gemini(image_b64, prompt)
            # Clean up the result
            result = result.strip().strip("`'\"")
            if result and len(result) < 50:  # Sanity check
                _log_captcha_solve(image_source, result, True, "gemini")
                return True, result
        except Exception as e:
            _log_captcha_solve(image_source, str(e), False, "gemini")

    # No other free vision providers configured reliably
    _log_captcha_solve(image_source, "No vision-capable LLM available", False, "none")
    return False, "No vision-capable LLM available (need GEMINI_API_KEY)"


def can_solve_captcha():
    """Check if CAPTCHA solving is available (requires a vision model)."""
    return bool(os.environ.get("GEMINI_API_KEY"))


if __name__ == "__main__":
    # Quick test
    print(f"CAPTCHA solving available: {can_solve_captcha()}")
    print(f"Requires GEMINI_API_KEY environment variable")
