"""
Algeo Verify — AI Address Preprocessor
========================================
Uses Google Gemini to parse messy Algerian addresses (Arabic, French, Darja,
mixed scripts) into structured fields before feeding into normalize().

Usage::

    from app.services.ai_preprocessor import preprocess_address, build_clean_address

    result = preprocess_address("حي الزهراء، بئر مراد رايس الجزائر")
    if result:
        clean = build_clean_address(result)
        # → "Bir Mourad Raïs, Alger 16000"  (example)
"""

from __future__ import annotations

import json
import re
from typing import Optional

import google.generativeai as genai

from app.config import get_settings

# ---------------------------------------------------------------------------
# Gemini system prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an Algerian address parser. Given a raw delivery address (which may be "
    "in Arabic, French, Darja/slang, or mixed), extract structured fields. The input "
    "may contain informal landmarks, neighborhood names, abbreviations, or "
    "transliterated Arabic.\n\n"
    "Return ONLY valid JSON with these fields:\n"
    "{\n"
    '  "wilaya": "French name of the wilaya, or null",\n'
    '  "commune": "French name of the commune, or null",\n'
    '  "street": "street/building/number info, or null",\n'
    '  "postal_code": "5-digit code if found, or null",\n'
    '  "landmark": "any landmark reference, or null",\n'
    '  "reconstructed_address": "your best reconstruction as a clean address string"\n'
    "}\n\n"
    "IMPORTANT: Always prefer French names for wilaya and commune. If the input is "
    "purely Arabic, translate the wilaya/commune names to French. Do not include any "
    "markdown, code fences, or explanation — only the JSON object."
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers that Gemini sometimes adds."""
    text = text.strip()
    # Remove opening fence (```json or ```)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _get_model() -> genai.GenerativeModel:
    """Return a configured Gemini GenerativeModel (cached per process)."""
    settings = get_settings()
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        system_instruction=_SYSTEM_PROMPT,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preprocess_address(raw_address: str) -> Optional[dict]:
    """
    Call Gemini to parse *raw_address* into structured address fields.

    Args:
        raw_address: Any messy address string (Arabic, French, mixed, etc.)

    Returns:
        A dict with keys: wilaya, commune, street, postal_code, landmark,
        reconstructed_address — or ``None`` on any failure.

    Notes:
        This is a **synchronous** function; it uses the Gemini SDK's blocking
        ``generate_content`` method, which is safe to call from sync FastAPI routes.
    """
    if not raw_address or not raw_address.strip():
        return None

    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        print("[AI] GEMINI_API_KEY is not set — skipping AI preprocessing")
        return None

    try:
        model = _get_model()
        response = model.generate_content(raw_address)
        raw_text: str = response.text

        cleaned = _strip_markdown_fences(raw_text)
        result: dict = json.loads(cleaned)

        # Validate expected keys are present (allow partial results)
        expected_keys = {
            "wilaya", "commune", "street",
            "postal_code", "landmark", "reconstructed_address",
        }
        if not isinstance(result, dict) or not expected_keys.intersection(result.keys()):
            print(f"[AI] Unexpected response structure: {raw_text[:200]}")
            return None

        print(f"[AI] Preprocessed address → wilaya={result.get('wilaya')!r}, "
              f"commune={result.get('commune')!r}")
        return result

    except json.JSONDecodeError as e:
        print(f"[AI] JSON parse error from Gemini response: {e}")
        return None

    except Exception as e:
        # Catch API errors, rate limits, network issues — never let this crash
        print(f"[AI] preprocess_address failed: {type(e).__name__}: {e}")
        return None


def build_clean_address(ai_result: dict) -> str:
    """
    Reconstruct a clean, normalisation-ready address string from AI output.

    Format (skipping null / missing fields)::

        "{street}, {commune}, {wilaya} {postal_code}"

    Args:
        ai_result: The dict returned by :func:`preprocess_address`.

    Returns:
        A clean address string suitable for passing to ``normalize()``.
        Falls back to ``reconstructed_address`` if individual fields are sparse.
    """
    if not ai_result:
        return ""

    street = ai_result.get("street")
    commune = ai_result.get("commune")
    wilaya = ai_result.get("wilaya")
    postal_code = ai_result.get("postal_code")
    reconstructed = ai_result.get("reconstructed_address", "")

    parts: list[str] = []

    if street:
        parts.append(street)
    if commune:
        parts.append(commune)

    # Combine wilaya + postal_code
    if wilaya and postal_code:
        parts.append(f"{wilaya} {postal_code}")
    elif wilaya:
        parts.append(wilaya)
    elif postal_code:
        parts.append(postal_code)

    if parts:
        return ", ".join(parts)

    # Fallback: use the model's own reconstruction
    return reconstructed or ""
