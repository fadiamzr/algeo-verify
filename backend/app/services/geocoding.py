"""
Algeo Verify — Geocoding Service
==================================
Converts a normalised Algerian address string into GPS coordinates
via the OpenStreetMap Nominatim API (free, no API key required).

Usage::

    from app.services.geocoding import geocode_address

    geo = geocode_address("Rue Didouche Mourad, Constantine 25000",
                          wilaya="Constantine", commune="Constantine")
    print(geo["latitude"], geo["longitude"], geo["status"])
"""

from __future__ import annotations

from typing import Optional

import httpx


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_TIMEOUT_SECONDS = 10
_USER_AGENT = "AlgeoVerify/1.0 (university-project)"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_nominatim(query: str) -> Optional[dict]:
    """
    Make a single request to the Nominatim geocoding API.

    Returns the first result dict, or ``None`` if the request
    failed or returned no results.
    """
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "dz",
        "addressdetails": 1,
    }

    headers = {
        "User-Agent": _USER_AGENT,
    }

    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.get(_NOMINATIM_URL, params=params, headers=headers)
            response.raise_for_status()
            results = response.json()

        if results and len(results) > 0:
            return results[0]

        return None

    except httpx.HTTPStatusError as e:
        print(f"[GEO] HTTP error geocoding {query!r}: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        print(f"[GEO] Network error geocoding {query!r}: {e}")
        return None
    except Exception as e:
        print(f"[GEO] Unexpected error geocoding {query!r}: {type(e).__name__}: {e}")
        return None


def _classify_result(result: dict) -> str:
    """
    Map Nominatim result type/class to our internal status.

    - Building-level or specific address -> "success"
    - Town/city/village/suburb level -> "approximate"
    """
    osm_type = result.get("type", "")
    osm_class = result.get("class", "")

    if osm_type in ("house", "building", "residential", "apartments"):
        return "success"
    if osm_class == "building":
        return "success"
    if osm_type in ("street", "road", "path"):
        return "success"

    return "approximate"


def _extract_result(result: dict) -> dict:
    """Extract lat, lng, display_name from a Nominatim result."""
    try:
        lat = float(result.get("lat", 0))
        lng = float(result.get("lon", 0))
    except (ValueError, TypeError):
        lat = None
        lng = None

    display_name = result.get("display_name")
    status = _classify_result(result)
    location_type = result.get("type")

    return {
        "latitude": lat,
        "longitude": lng,
        "formatted_address": display_name,
        "location_type": location_type,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def geocode_address(
    address: str,
    wilaya: Optional[str] = None,
    commune: Optional[str] = None,
) -> dict:
    """
    Geocode *address* to GPS coordinates via the Nominatim API.

    If *wilaya* or *commune* are known they are appended to the query string
    for better accuracy.

    Fallback strategy:
        1. Try the full address (with wilaya/commune appended if provided).
        2. On failure, retry with just "{commune}, {wilaya}, Algeria".
        3. If both fail -> return status="failed" with null coordinates.

    Args:
        address:  The normalised address string to geocode.
        wilaya:   Optional French wilaya name to improve accuracy.
        commune:  Optional French commune name to improve accuracy.

    Returns:
        Dict with keys::

            {
                "latitude":          float | None,
                "longitude":         float | None,
                "formatted_address": str   | None,
                "location_type":     str   | None,
                "status":            "success" | "approximate" | "failed",
            }
    """
    _FAILED: dict = {
        "latitude": None,
        "longitude": None,
        "formatted_address": None,
        "location_type": None,
        "status": "failed",
    }

    # -- Build the query string ------------------------------------------------
    query_parts = [address]
    if wilaya and wilaya.lower() not in address.lower():
        query_parts.append(wilaya)
    if commune and commune.lower() not in address.lower():
        query_parts.insert(1, commune)

    full_query = ", ".join(query_parts)

    # -- Attempt 1: full query -------------------------------------------------
    result = _call_nominatim(full_query)
    if result:
        extracted = _extract_result(result)
        print(f"[GEO] Geocoded {address!r} -> "
              f"({extracted['latitude']}, {extracted['longitude']}) "
              f"[{extracted['status']}]")
        return extracted

    # -- Attempt 2: commune-level fallback -------------------------------------
    if commune or wilaya:
        fallback_parts = [p for p in [commune, wilaya, "Algeria"] if p]
        fallback_query = ", ".join(fallback_parts)
        print(f"[GEO] Full query failed; retrying with fallback: {fallback_query!r}")

        result = _call_nominatim(fallback_query)
        if result:
            extracted = _extract_result(result)
            extracted["status"] = "approximate"
            print(f"[GEO] Fallback geocoded -> "
                  f"({extracted['latitude']}, {extracted['longitude']}) [approximate]")
            return extracted

    print(f"[GEO] All geocoding attempts failed for: {address!r}")
    return _FAILED