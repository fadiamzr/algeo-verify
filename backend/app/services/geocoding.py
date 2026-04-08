"""
Algeo Verify — Geocoding Service
==================================
Converts a normalised Algerian address string into GPS coordinates
via the Google Maps Geocoding API.

Usage::

    from app.services.geocoding import geocode_address

    geo = geocode_address("Rue Didouche Mourad, Constantine 25000",
                          wilaya="Constantine", commune="Constantine")
    print(geo["latitude"], geo["longitude"], geo["status"])
"""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import get_settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_TIMEOUT_SECONDS = 10

# Map Google's location_type to our internal status string
_LOCATION_TYPE_MAP: dict[str, str] = {
    "ROOFTOP":           "success",
    "RANGE_INTERPOLATED": "success",
    "GEOMETRIC_CENTER":  "approximate",
    "APPROXIMATE":       "approximate",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_geocoding_api(address: str, api_key: str) -> Optional[dict]:
    """
    Make a single request to the Google Maps Geocoding API.

    Returns the first result dict from the API, or ``None`` if the request
    failed or returned no results.
    """
    params = {
        "address": address,
        "key": api_key,
        "region": "dz",
        "components": "country:DZ",
    }

    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.get(_GEOCODING_URL, params=params)
            response.raise_for_status()
            data = response.json()

        api_status = data.get("status", "")
        results = data.get("results", [])

        if api_status == "OK" and results:
            return results[0]

        if api_status not in ("OK", "ZERO_RESULTS"):
            print(f"[GEO] Geocoding API returned status={api_status!r} for: {address!r}")

        return None

    except httpx.HTTPStatusError as e:
        print(f"[GEO] HTTP error geocoding {address!r}: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        print(f"[GEO] Network error geocoding {address!r}: {e}")
        return None
    except Exception as e:
        print(f"[GEO] Unexpected error geocoding {address!r}: {type(e).__name__}: {e}")
        return None


def _extract_result(api_result: dict) -> dict:
    """Extract lat, lng, formatted_address, location_type from an API result dict."""
    location = api_result.get("geometry", {}).get("location", {})
    location_type = api_result.get("geometry", {}).get("location_type", "")
    formatted_address = api_result.get("formatted_address")

    lat = location.get("lat")
    lng = location.get("lng")
    status = _LOCATION_TYPE_MAP.get(location_type, "approximate")

    return {
        "latitude": lat,
        "longitude": lng,
        "formatted_address": formatted_address,
        "location_type": location_type or None,
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
    Geocode *address* to GPS coordinates via the Google Maps Geocoding API.

    If *wilaya* or *commune* are known they are appended to the query string
    for better accuracy.

    Fallback strategy:
        1. Try the full address (with wilaya/commune appended if provided).
        2. On failure, retry with just "{commune}, {wilaya}, Algeria".
        3. If both fail → return status="failed" with null coordinates.

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

    settings = get_settings()
    if not settings.GOOGLE_MAPS_API_KEY:
        print("[GEO] GOOGLE_MAPS_API_KEY is not set — skipping geocoding")
        return _FAILED

    # ── Build the query string ────────────────────────────────────────────────
    query_parts = [address]
    if wilaya and wilaya.lower() not in address.lower():
        query_parts.append(wilaya)
    if commune and commune.lower() not in address.lower():
        # prepend commune before wilaya for better specificity
        query_parts.insert(1, commune)

    full_query = ", ".join(query_parts)

    # ── Attempt 1: full query ─────────────────────────────────────────────────
    result = _call_geocoding_api(full_query, settings.GOOGLE_MAPS_API_KEY)
    if result:
        extracted = _extract_result(result)
        print(f"[GEO] Geocoded {address!r} → "
              f"({extracted['latitude']}, {extracted['longitude']}) "
              f"[{extracted['status']}]")
        return extracted

    # ── Attempt 2: commune-level fallback ─────────────────────────────────────
    if commune or wilaya:
        fallback_parts = [p for p in [commune, wilaya, "Algeria"] if p]
        fallback_query = ", ".join(fallback_parts)
        print(f"[GEO] Full query failed; retrying with fallback: {fallback_query!r}")

        result = _call_geocoding_api(fallback_query, settings.GOOGLE_MAPS_API_KEY)
        if result:
            extracted = _extract_result(result)
            # Downgrade to approximate since we fell back to commune level
            extracted["status"] = "approximate"
            print(f"[GEO] Fallback geocoded → "
                  f"({extracted['latitude']}, {extracted['longitude']}) [approximate]")
            return extracted

    print(f"[GEO] All geocoding attempts failed for: {address!r}")
    return _FAILED
