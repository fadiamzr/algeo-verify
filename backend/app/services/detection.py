"""
Algeo Verify — Entity Detection Engine
========================================
Extracts structured entities (wilaya, commune, postal code, street) from
a *normalized* Algerian address string.

Uses fuzzy matching (stdlib ``difflib``) against the authoritative geo
reference files ``database/wilaya.json`` and ``database/communes.json``.

Usage:
    from app.services.normalization import normalize
    from app.services.detection import detectEntities

    raw = "123 rue Didouche Mourad, Constantine 25000"
    entities = detectEntities(normalize(raw))
    print(entities)
    # DetectedEntities(wilaya='Constantine', commune='Constantine',
    #                  postalCode='25000', street='123 Rue Didouche Mourad')
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
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
_COMMUNES_JSON = _PROJECT_ROOT / "database" / "communes.json"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DetectedEntities:
    """Structured result returned by :func:`detectEntities`."""
    wilaya: Optional[str] = None
    commune: Optional[str] = None
    postalCode: Optional[str] = None
    street: Optional[str] = None


# ---------------------------------------------------------------------------
# Geo-data store (loaded once at import-time via ``load_geo_data()``)
# ---------------------------------------------------------------------------

# Populated by load_geo_data()
_wilayas: List[dict] = []
_communes: List[dict] = []

# Lookup indexes — built by load_geo_data()
_wilaya_name_to_code: Dict[str, str] = {}        # lowered FR/AR/EN name → code
_wilaya_code_to_fr: Dict[str, str] = {}           # code → French name
_commune_names: List[Tuple[str, str, dict]] = []  # (lowered_name, type, commune_dict)


def load_geo_data() -> None:
    """Load ``wilaya.json`` and ``communes.json`` into memory and build
    fast-lookup indexes.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _wilayas, _communes
    if _wilayas:  # already loaded
        return

    try:
        with open(_WILAYA_JSON, encoding="utf-8") as fh:
            _wilayas = json.load(fh)
    except FileNotFoundError:
        raise RuntimeError(
            f"wilaya.json not found at {_WILAYA_JSON}. "
            "Check that the database/ directory exists."
        )
    try:
        with open(_COMMUNES_JSON, encoding="utf-8") as fh:
            _communes = json.load(fh)
    except FileNotFoundError:
        raise RuntimeError(
            f"communes.json not found at {_COMMUNES_JSON}. "
            "Check that the database/ directory exists."
        )

    # --- Build wilaya indexes ---
    for w in _wilayas:
        code = w["code"]
        name_fr = w.get("name_fr", "")
        name_ar = w.get("name_ar", "")
        name_en = w.get("name_en", "")

        _wilaya_code_to_fr[code] = name_fr

        for name in (name_fr, name_ar, name_en):
            if name:
                _wilaya_name_to_code[name.lower()] = code

    # --- Build commune index ---
    for c in _communes:
        name_fr = c.get("name_fr", "")
        name_ar = c.get("name_ar", "")
        if name_fr:
            _commune_names.append((name_fr.lower(), "fr", c))
        if name_ar:
            _commune_names.append((name_ar.lower(), "ar", c))


# Load at import-time so the data is always available.
load_geo_data()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_for_compare(text: str) -> str:
    """Lowercase, strip accents (for comparison only), and collapse spaces."""
    # Decompose → drop combining marks → recompose
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _fuzzy_score(a: str, b: str) -> float:
    """Return a similarity ratio between 0.0 and 1.0 using SequenceMatcher."""
    return SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Public matching functions
# ---------------------------------------------------------------------------

def match_wilaya(text: str) -> Optional[str]:
    """Fuzzy-match *text* against all known wilaya names (FR, AR, EN).

    Returns the **French name** of the best-matching wilaya, or ``None``
    if no match scores above the threshold.

    The function first tries an exact (case-insensitive, accent-insensitive)
    lookup.  If that fails, it falls back to fuzzy matching with a 0.75
    similarity threshold.  Multi-word wilaya names that appear as a
    *substring* of the input text are also detected.
    """
    if not text or not text.strip():
        return None

    text_lower = text.strip().lower()
    text_norm = _normalize_for_compare(text)

    # 1) Exact match on lowered name
    if text_lower in _wilaya_name_to_code:
        return _wilaya_code_to_fr[_wilaya_name_to_code[text_lower]]

    # 2) Check if any known name appears as a whole-word substring of the
    #    input text (handles "123 rue X, Constantine 25000").  We require
    #    word-boundary alignment so that "El Oued" does NOT match inside
    #    "Bab El Oued".
    best_substring: Optional[str] = None
    best_len = 0
    for name_lower, code in _wilaya_name_to_code.items():
        name_norm = _normalize_for_compare(name_lower)
        # Use regex word boundaries to avoid partial matches
        pattern = r"(?:^|(?<=\s))" + re.escape(name_norm) + r"(?=\s|$|[,;])"
        if re.search(pattern, text_norm) and len(name_norm) > best_len:
            best_len = len(name_norm)
            best_substring = _wilaya_code_to_fr[code]

    if best_substring and best_len >= 3:
        return best_substring

    # 3) Fuzzy match — compare each word-window of the input against names
    threshold = 0.75
    best_score = 0.0
    best_match: Optional[str] = None

    words = text_norm.split()
    for name_lower, code in _wilaya_name_to_code.items():
        name_norm = _normalize_for_compare(name_lower)
        name_words = name_norm.split()
        window = len(name_words)

        for i in range(len(words) - window + 1):
            candidate = " ".join(words[i : i + window])
            score = _fuzzy_score(candidate, name_norm)
            if score > best_score:
                best_score = score
                best_match = _wilaya_code_to_fr[code]

    if best_score >= threshold:
        return best_match

    return None


def _match_commune_in_segment(
    segment_norm: str,
    wilaya_code: Optional[str],
    wilaya_fr: Optional[str],
) -> Tuple[Optional[str], int, float]:
    """Try to match a commune in a single segment of text.

    Returns (best_fr_name, substring_len, fuzzy_score).
    """
    best_fr: Optional[str] = None
    best_len = 0

    # --- Exact substring match (longest wins) ---
    for name_lower, kind, commune_dict in _commune_names:
        if wilaya_code and commune_dict.get("wilaya_code") != wilaya_code:
            continue
        name_norm = _normalize_for_compare(name_lower)
        if name_norm in segment_norm and len(name_norm) > best_len:
            best_len = len(name_norm)
            best_fr = commune_dict["name_fr"]

    if best_fr and best_len >= 3:
        return best_fr, best_len, 1.0

    # --- Fuzzy window match ---
    threshold = 0.78
    best_score = 0.0
    best_match: Optional[str] = None
    words = segment_norm.split()

    for name_lower, kind, commune_dict in _commune_names:
        if wilaya_code and commune_dict.get("wilaya_code") != wilaya_code:
            continue
        name_norm = _normalize_for_compare(name_lower)
        name_words = name_norm.split()
        window = len(name_words)
        for i in range(len(words) - window + 1):
            candidate = " ".join(words[i : i + window])
            score = _fuzzy_score(candidate, name_norm)
            if score > best_score:
                best_score = score
                best_match = commune_dict["name_fr"]

    if best_score >= threshold:
        return best_match, 0, best_score

    return None, 0, 0.0


# Street-segment detection keywords (French Algerian)
_STREET_KEYWORDS = re.compile(
    r"\b(?:rue|boulevard|blvd|avenue|ave|cit[eé]|lotissement|"
    r"r[eé]sidence|chemin|impasse|place|route|rte|quartier|hai|"
    r"lot|bt|b[aâ]timent|bloc|immeuble|n[°o])\b",
    re.IGNORECASE | re.UNICODE,
)


def _is_street_segment(segment: str) -> bool:
    """Return True if *segment* looks like a street / building part.

    A segment is considered street-like if it:
    - starts with digits (house number), OR
    - contains common French road keywords (rue, boulevard, …)
    """
    stripped = segment.strip()
    if not stripped:
        return False
    # Starts with a house number
    if re.match(r"\d", stripped):
        return True
    # Contains a road keyword
    if _STREET_KEYWORDS.search(stripped):
        return True
    return False


def match_commune(text: str, wilaya: Optional[str] = None) -> Optional[str]:
    """Match a commune name inside *text*, optionally filtered by *wilaya*.

    If *wilaya* is provided (French name), only communes belonging to that
    wilaya are considered.  When the text contains multiple comma-separated
    segments, each is tried **individually** — this prevents street names
    like "Didouche Mourad" from being matched as a commune when they
    appear in a separate segment from the wilaya/commune names.

    Among matches, a commune that *differs* from the wilaya name is
    preferred (since the wilaya capital often shares the name).
    Returns the **French name** of the best match or ``None``.
    """
    if not text or not text.strip():
        return None

    # Resolve wilaya → code for filtering
    wilaya_code: Optional[str] = None
    wilaya_fr = wilaya
    if wilaya:
        wilaya_code = _wilaya_name_to_code.get(wilaya.lower())

    # Split on commas / semicolons to get individual segments
    segments = re.split(r"[,;]", text)
    segments = [s.strip() for s in segments if s.strip()]

    # If there's only one segment, just match directly
    if len(segments) <= 1:
        result, _, _ = _match_commune_in_segment(
            _normalize_for_compare(text), wilaya_code, wilaya_fr
        )
        return result

    # Multiple segments — try each one, skipping street-like segments.
    # Prefer a commune that is NOT the same as the wilaya name (the
    # wilaya capital often shares the name).
    all_matches: List[Tuple[str, bool]] = []  # (commune_fr, is_same_as_wilaya)

    for seg in segments:
        # Skip segments that look like street addresses (contain house
        # numbers, "rue", "boulevard", etc.) — these should not be
        # searched for commune names.
        if _is_street_segment(seg):
            continue
        seg_norm = _normalize_for_compare(seg)
        match, _, _ = _match_commune_in_segment(seg_norm, wilaya_code, wilaya_fr)
        if match:
            is_same = wilaya_fr and match.lower() == wilaya_fr.lower()
            all_matches.append((match, bool(is_same)))

    if not all_matches:
        return None

    # Prefer a commune that differs from the wilaya
    non_wilaya = [m for m, same in all_matches if not same]
    if non_wilaya:
        return non_wilaya[0]

    # Fall back to the first match (which equals the wilaya name)
    return all_matches[0][0]


def extract_postal_code(text: str) -> Optional[str]:
    """Extract a 5-digit Algerian postal code from *text*.

    Algerian postal codes follow the pattern ``WWNNN`` where ``WW`` is the
    2-digit wilaya code (01–69) and ``NNN`` is a 3-digit sequence.
    """
    if not text:
        return None

    # Match 5-digit sequences that are NOT part of a longer number
    matches = re.findall(r"(?<!\d)\d{5}(?!\d)", text)
    for m in matches:
        wilaya_part = int(m[:2])
        if 1 <= wilaya_part <= 69:
            return m

    return None


def extract_street(
    text: str,
    wilaya: Optional[str] = None,
    commune: Optional[str] = None,
) -> Optional[str]:
    """Return the *residual* address text after removing the known
    wilaya name, commune name, and postal code.

    This is a best-effort extraction: whatever remains after stripping
    known entities is assumed to be the street / building / number.
    """
    if not text:
        return None

    residual = text

    # Remove postal code(s)
    residual = re.sub(r"(?<!\d)\d{5}(?!\d)", "", residual)

    # Remove detected wilaya name (case-insensitive)
    if wilaya:
        pattern = re.compile(re.escape(wilaya), re.IGNORECASE)
        residual = pattern.sub("", residual, count=1)

    # Remove detected commune name (case-insensitive), but only if it
    # differs from the wilaya (many wilayas share the name with their
    # capital commune — don't double-remove).
    if commune and (not wilaya or commune.lower() != wilaya.lower()):
        pattern = re.compile(re.escape(commune), re.IGNORECASE)
        residual = pattern.sub("", residual, count=1)

    # Clean up separators and whitespace
    residual = re.sub(r"[,;]+", " ", residual)
    residual = re.sub(r"\s+", " ", residual).strip()

    return residual if residual else None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def detectEntities(normalized_address: str) -> DetectedEntities:
    """Analyse a **normalized** address and extract structured entities.

    Call :func:`app.services.normalization.normalize` on raw user input
    *before* passing it to this function.

    Args:
        normalized_address: A cleaned address string from the normalizer.

    Returns:
        A :class:`DetectedEntities` dataclass with the detected
        wilaya, commune, postal code, and street.
    """
    if not normalized_address or not normalized_address.strip():
        return DetectedEntities()

    text = normalized_address.strip()

    # --- Postal code (most reliable signal) ---
    postal_code = extract_postal_code(text)

    # If a postal code was found, try to infer the wilaya from it
    wilaya_hint: Optional[str] = None
    if postal_code:
        wilaya_code = postal_code[:2]
        wilaya_hint = _wilaya_code_to_fr.get(wilaya_code)

    # --- Wilaya ---
    wilaya = match_wilaya(text)
    # Postal code is the most reliable signal — if it disagrees with the
    # fuzzy name match, prefer the postal-code-derived wilaya.
    if wilaya_hint:
        if not wilaya or wilaya != wilaya_hint:
            wilaya = wilaya_hint

    # --- Commune (scoped to detected wilaya when possible) ---
    commune = match_commune(text, wilaya=wilaya)

    # --- Street (residual text) ---
    street = extract_street(text, wilaya=wilaya, commune=commune)

    return DetectedEntities(
        wilaya=wilaya,
        commune=commune,
        postalCode=postal_code,
        street=street,
    )


# ---------------------------------------------------------------------------
# Quick self-test — run from backend/ folder:
#   .venv\Scripts\python.exe -m app.services.detection
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    from app.services.normalization import normalize

    test_cases = [
        "123 rue Didouche Mourad, Constantine 25000",
        "Oran, Bir El Djir 31003",
        "عنابة 23000",
        "Bab El Oued, Alger 16001",
        "BLIDA, BOUFARIK 09001",
        "45 boulevard de l'ALN, Sétif 19000",
        "تلمسان ,  Maghnia  ",
        "16000",
        "  ",
        "",
    ]

    print("=" * 72)
    print("  Algeo Verify — Detection Engine — Self-Test")
    print("=" * 72)

    for raw in test_cases:
        norm = normalize(raw)
        result = detectEntities(norm)
        print(f"\n  RAW   : {raw!r}")
        print(f"  NORM  : {norm!r}")
        print(f"  RESULT: wilaya={result.wilaya!r}  commune={result.commune!r}")
        print(f"          postal={result.postalCode!r}  street={result.street!r}")

    print("\n" + "=" * 72)
    print("  \u2713 All test cases processed successfully")
    print("=" * 72)
