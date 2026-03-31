"""
Algeo Verify — Address Normalization Engine
============================================
Cleans and normalizes raw Algerian addresses into a consistent format
ready for entity detection. Handles bilingual (Arabic / French) input,
strips noise words, converts Arabic wilaya names to French equivalents,
and standardizes capitalization.

Usage:
    from app.services.normalization import normalize
    clean = normalize("  wilaya de   وهران ,  commune de   Bir El Djir  16000 ")
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List

# ---------------------------------------------------------------------------
# Paths — resolve by searching upward for the database/ folder
# ---------------------------------------------------------------------------
def _find_project_root() -> Path:
    """Walk up from this file until we find a directory containing 'database/'."""
    current = Path(__file__).resolve().parent
    for _ in range(10):  # safety limit
        if (current / "database").is_dir():
            return current
        current = current.parent
    raise RuntimeError(
        "Could not locate project root (expected a 'database/' folder "
        "in an ancestor directory)."
    )

_PROJECT_ROOT = _find_project_root()
_WILAYA_JSON = _PROJECT_ROOT / "database" / "wilaya.json"


# ---------------------------------------------------------------------------
# Lookup tables — built once at import time from the authoritative JSON data
# ---------------------------------------------------------------------------

def _load_wilaya_data() -> tuple[list[dict], Dict[str, str]]:
    """Load wilaya.json and build an Arabic-name → French-name mapping.

    Returns:
        wilayas: the raw list of wilaya dicts
        ar_to_fr: mapping of every Arabic wilaya name to its French equivalent
    """
    try:
        with open(_WILAYA_JSON, encoding="utf-8") as fh:
            wilayas: list[dict] = json.load(fh)
    except FileNotFoundError:
        raise RuntimeError(
            f"wilaya.json not found at {_WILAYA_JSON}. "
            "Check that the database/ directory exists."
        )

    ar_to_fr: Dict[str, str] = {}
    for w in wilayas:
        name_ar = w.get("name_ar", "").strip()
        name_fr = w.get("name_fr", "").strip()
        if name_ar and name_fr:
            ar_to_fr[name_ar] = name_fr

    return wilayas, ar_to_fr


_WILAYAS, _AR_TO_FR = _load_wilaya_data()


# ---------------------------------------------------------------------------
# Noise patterns — common French / Arabic filler phrases in Algerian addresses
# ---------------------------------------------------------------------------
_NOISE_PATTERNS_FR: List[str] = [
    r"\bcommune\s+d[e']\s*",
    r"\bwilaya\s+d[e']\s*",
    r"\bda[ïi]ra\s+d[e']\s*",
    r"\bcommune\s+de\b\s*",
    r"\bwilaya\s+de\b\s*",
    r"\bda[ïi]ra\s+de\b\s*",
    r"\bcommune\b\s*",
    r"\bwilaya\b\s*",
    r"\bda[ïi]ra\b\s*",
]

_NOISE_PATTERNS_AR: List[str] = [
    r"\bبلدية\b\s*",
    r"\bولاية\b\s*",
    r"\bدائرة\b\s*",
]

_ALL_NOISE_PATTERNS = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in
                       _NOISE_PATTERNS_FR + _NOISE_PATTERNS_AR]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_diacritics(text: str) -> str:
    """Remove combining diacritical marks (French accents are preserved at
    the character level; this only strips Arabic tashkeel / harakat)."""
    # Arabic tashkeel / harakat ranges:
    #   U+0610–U+061A  Arab. sign (e.g. alef above, hamza above/below)
    #   U+064B–U+065F  Fathatan through Waslah (fatha, damma, kasra, shadda, sukun …)
    result: list[str] = []
    for ch in text:
        if "\u0610" <= ch <= "\u061A":
            continue
        if "\u064B" <= ch <= "\u065F":
            continue
        result.append(ch)
    return "".join(result)


def _collapse_whitespace(text: str) -> str:
    """Replace runs of any whitespace (including newlines) with a single space."""
    return re.sub(r"\s+", " ", text).strip()


def _fix_punctuation(text: str) -> str:
    """Normalize common punctuation issues in Algerian addresses.

    - Normalize Arabic comma (،) to Latin comma
    - Remove duplicate commas / periods
    - Remove spaces before commas/semicolons ("Oran , Blida" → "Oran, Blida")
    - Ensure a space after commas and semicolons (if missing)
    """
    text = text.replace("،", ",")           # Arabic comma → Latin
    text = re.sub(r"[,]{2,}", ",", text)    # duplicate commas
    text = re.sub(r"[.]{2,}", ".", text)    # duplicate periods
    text = re.sub(r"\s+,", ",", text)       # remove space(s) before comma
    text = re.sub(r"\s+;", ";", text)       # remove space(s) before semicolon
    text = re.sub(r",(?=\S)", ", ", text)   # ensure space after comma
    text = re.sub(r";(?=\S)", "; ", text)   # ensure space after semicolon
    return text


def _replace_arabic_wilaya_names(text: str) -> str:
    """Replace Arabic wilaya names with their French equivalents.

    Searches longest-first to avoid partial matches (e.g. "سيدي بلعباس"
    before "بلعباس").
    """
    # Sort by length descending so longer Arabic names match first
    for ar_name in sorted(_AR_TO_FR, key=len, reverse=True):
        if ar_name in text:
            text = text.replace(ar_name, _AR_TO_FR[ar_name])
    return text


def _remove_noise(text: str) -> str:
    """Strip filler words such as 'commune de', 'wilaya de', 'daïra de' (FR)
    and their Arabic equivalents."""
    for pattern in _ALL_NOISE_PATTERNS:
        text = pattern.sub("", text)
    return text


def _title_case_french(text: str) -> str:
    """Apply title-case to Latin (French) words while leaving Arabic text
    and postal codes (digits) untouched.

    Handles French particles (de, d', el, le, la, les, du, des, ben, bou)
    correctly — they stay lowercase unless they start the string.
    """
    _PARTICLES = {
        "de", "d", "du", "des", "le", "la", "les",
        "el", "ben", "bou", "ibn",
    }

    words = text.split()
    result: list[str] = []

    for i, word in enumerate(words):
        # Skip purely numeric tokens (postal codes etc.)
        if word.isdigit():
            result.append(word)
            continue

        # Skip tokens that contain Arabic characters
        if any("\u0600" <= ch <= "\u06FF" for ch in word):
            result.append(word)
            continue

        lower = word.lower()

        # Handle apostrophe-containing words (e.g. "d'Oran", "M'Sila")
        if "'" in lower or "\u2019" in lower:
            parts = re.split(r"(['\u2019])", word)
            capitalized_parts: list[str] = []
            for part in parts:
                if part in ("'", "'"):
                    capitalized_parts.append("'")
                elif part.lower() in _PARTICLES:
                    capitalized_parts.append(part.lower() if i > 0 else part.capitalize())
                else:
                    capitalized_parts.append(part.capitalize())
            result.append("".join(capitalized_parts))
            continue

        # Particles stay lowercase except at start of string
        if lower in _PARTICLES and i > 0:
            result.append(lower)
            continue

        result.append(word.capitalize())

    return " ".join(result)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize(raw_address: str) -> str:
    """Normalize a raw Algerian address string.

    Pipeline:
        1. Strip Arabic tashkeel (diacritical marks)
        2. Fix punctuation
        3. Collapse whitespace
        4. Replace Arabic wilaya names with French equivalents
        5. Remove noise words (commune de, wilaya de, daïra de …)
        6. Collapse whitespace again (noise removal may leave gaps)
        7. Standardize capitalization (title-case for French words)

    Args:
        raw_address: The messy, user-entered address string.

    Returns:
        A cleaned, normalized address string ready for entity detection.
    """
    if not raw_address or not raw_address.strip():
        return ""

    text = raw_address

    # Step 1 — Strip Arabic diacritics
    text = _strip_diacritics(text)

    # Step 2 — Fix punctuation
    text = _fix_punctuation(text)

    # Step 3 — Collapse whitespace
    text = _collapse_whitespace(text)

    # Step 4 — Arabic → French wilaya names
    text = _replace_arabic_wilaya_names(text)

    # Step 5 — Remove noise words
    text = _remove_noise(text)

    # Step 6 — Collapse whitespace (again, after noise removal)
    text = _collapse_whitespace(text)

    # Step 7 — Title-case French words
    text = _title_case_french(text)

    return text


# ---------------------------------------------------------------------------
# Quick self-test — run: python -m app.services.normalization
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        "  wilaya de   وهران ,  commune de   Bir El Djir  31000 ",
        "الجزائر, باب الوادي, شارع حسيبة بن بوعلي 16001",
        "COMMUNE DE CONSTANTINE, WILAYA DE CONSTANTINE",
        "عنابة ,  23000",
        "  قسنطينة   ,  daïra de  EL KHROUB  ",
        "تلمسان ,  commune de MAGHNIA  ",
        "123  rue des frères bouadou ,, blida  09000",
        "  ",
        "",
    ]

    print("=" * 70)
    print("  Algeo Verify — Normalization Engine — Self-Test")
    print("=" * 70)
    for raw in test_cases:
        result = normalize(raw)
        print(f"\n  INPUT : {raw!r}")
        print(f"  OUTPUT: {result!r}")
    print("\n" + "=" * 70)
    print("  ✓ All test cases processed successfully")
    print("=" * 70)
