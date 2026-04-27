"""
Algeo Verify — Verification Pipeline
======================================
Main orchestrator that chains normalization → entity detection → scoring
and persists the result to the database.

Usage (within a FastAPI route)::

    from sqlmodel import Session
    from app.database import get_session
    from app.services.verification import verifyAddress

    @app.post("/verify")
    def verify(raw: str, db: Session = Depends(get_session)):
        return verifyAddress(raw, db)
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from sqlmodel import Session

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.models import AddressVerification, APILog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_match_details(
    wilaya: str | None,
    commune: str | None,
    postal_code: str | None,
    street: str | None,
) -> str:
    """Build a human-readable description of which fields were matched."""
    matched: list[str] = []
    if wilaya:
        matched.append("Wilaya")
    if commune:
        matched.append("Commune")
    if postal_code:
        matched.append("Postal code")
    if street:
        matched.append("Street")

    if not matched:
        return "No fields matched"
    if len(matched) == 4:
        return "Full address matched (Wilaya, Commune, Postal code, and Street)"

    return " and ".join(
        [", ".join(matched[:-1]), matched[-1]] if len(matched) > 1 else matched
    ) + " matched"


def _risk_flags_to_dicts(flags: list) -> List[Dict[str, str]]:
    """Serialize RiskFlag dataclass instances to plain dicts."""
    return [
        {
            "label": f.label,
            "severity": f.severity,
            "description": f.description,
        }
        for f in flags
    ]


def _build_fallback_response(
    raw_address: str,
    error_msg: str,
    now: datetime,
) -> Dict[str, Any]:
    """Return a valid verification response when the pipeline fails.

    This ensures the API **never** returns a 500 — callers always get
    structured JSON they can display to the user.
    """
    return {
        "id": None,
        "rawAddress": raw_address,
        "normalizedAddress": raw_address,
        "confidenceScore": 0.0,
        "matchDetails": f"Verification could not be completed: {error_msg}",
        "detectedEntities": {
            "wilaya": None,
            "commune": None,
            "postalCode": None,
            "street": None,
        },
        "riskFlags": [
            {
                "label": "Verification Error",
                "severity": "high",
                "description": error_msg,
            }
        ],
        "aiPreprocessed": False,
        "createdAt": now.isoformat(),
        "latitude": None,
        "longitude": None,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def verifyAddress(raw_address: str, db: Session) -> Dict[str, Any]:
    """Run the full address-verification pipeline.

    Pipeline steps:
        0. (Optional) AI preprocess the raw address via Gemini if AI_ENABLED.
        1. Normalize the (optionally pre-processed) address string.
        2. Detect entities (wilaya, commune, postal code, street).
        3. Compute a confidence score and generate risk flags.
        4. Persist an :class:`AddressVerification` record.
        5. Log the API call in :class:`APILog`.
        6. Return a structured response dict.

    **Resilience guarantees:**
    - Each step is wrapped in its own try/except so a failure in one step
      does not prevent later steps from running.
    - If the entire pipeline fails, a fallback response with
      ``confidenceScore=0`` is returned instead of raising.
    - Every exception is logged with a full traceback.

    Args:
        raw_address: The unprocessed address entered by the user.
        db: An active SQLModel/SQLAlchemy session.

    Returns:
        A dict matching the Algeo Verify response schema::

            {
                "id": int,
                "rawAddress": str,
                "normalizedAddress": str,
                "confidenceScore": float,
                "matchDetails": str,
                "detectedEntities": {
                    "wilaya": str | None,
                    "commune": str | None,
                    "postalCode": str | None,
                    "street": str | None,
                },
                "riskFlags": [{"label": str, "severity": str, "description": str}],
                "aiPreprocessed": bool,
                "createdAt": str (ISO 8601),
            }
    """
    now = datetime.now(timezone.utc)

    # -- Guard: empty / blank input ----------------------------------------
    if not raw_address or not raw_address.strip():
        logger.warning("[VERIFY] Empty raw_address received — returning fallback")
        return _build_fallback_response(
            raw_address or "",
            "Empty address provided",
            now,
        )

    try:
        settings = get_settings()
    except Exception as exc:
        logger.error(f"[VERIFY][CRITICAL] Failed to load settings: {exc}", exc_info=True)
        return _build_fallback_response(raw_address, "Internal configuration error", now)

    # ── Step 0: AI preprocess (optional) ──────────────────────────────
    ai_was_used: bool = False
    address_for_normalization = raw_address

    if settings.AI_ENABLED:
        try:
            from app.services import ai_preprocessor

            ai_result = ai_preprocessor.preprocess_address(raw_address)
            if ai_result:
                clean = ai_preprocessor.build_clean_address(ai_result)
                if clean:
                    address_for_normalization = clean
                    ai_was_used = True
                    logger.info(f"[AI] Using AI-cleaned address: {clean!r}")
        except Exception as exc:
            logger.warning(f"[AI] Preprocessor error (continuing without AI): {exc}", exc_info=True)

    # ── Step 1: Normalize ─────────────────────────────────────────────
    normalized_address = raw_address  # safe default
    try:
        from app.services.normalization import normalize

        normalized_address = normalize(address_for_normalization)
        if not normalized_address:
            normalized_address = raw_address
    except Exception as exc:
        logger.error(f"[VERIFY] Normalization failed (using raw address): {exc}", exc_info=True)

    # ── Step 2: Detect entities ───────────────────────────────────────
    detected = None
    try:
        from app.services.detection import detectEntities

        detected = detectEntities(normalized_address)
    except Exception as exc:
        logger.error(f"[VERIFY] Entity detection failed: {exc}", exc_info=True)

    # Build a safe entities dict regardless of whether detection succeeded
    entities_dict: Dict[str, Any] = {
        "wilaya": getattr(detected, "wilaya", None) if detected else None,
        "commune": getattr(detected, "commune", None) if detected else None,
        "postalCode": getattr(detected, "postalCode", None) if detected else None,
        "street": getattr(detected, "street", None) if detected else None,
    }

    # ── Step 3: Score ─────────────────────────────────────────────────
    confidence_score: float = 0.0
    risk_flags: list = []
    risk_flags_dicts: List[Dict[str, str]] = []

    if detected is not None:
        try:
            from app.services.scoring import ScoringEngine

            engine = ScoringEngine()
            confidence_score, risk_flags = engine.computeScore(detected)
            risk_flags_dicts = _risk_flags_to_dicts(risk_flags)
        except Exception as exc:
            logger.error(f"[VERIFY] Scoring failed: {exc}", exc_info=True)
    else:
        risk_flags_dicts = [
            {
                "label": "Detection Failed",
                "severity": "high",
                "description": "Entity detection could not run on this address.",
            }
        ]

    # ── Step 4: Build match description ───────────────────────────────
    match_details = _build_match_details(
        entities_dict["wilaya"],
        entities_dict["commune"],
        entities_dict["postalCode"],
        entities_dict["street"],
    )

    # ── Step 5: Geocode (best-effort) ─────────────────────────────────
    lat, lng = None, None
    if settings.GEOCODING_ENABLED:
        try:
            from app.services.geocoding import geocode_address

            geo = geocode_address(
                normalized_address,
                wilaya=entities_dict["wilaya"],
                commune=entities_dict["commune"],
            )
            lat = geo.get("latitude")
            lng = geo.get("longitude")
        except Exception as exc:
            logger.warning(f"[WARN] Geocoding service failed: {exc}", exc_info=True)

    # ── Step 6: Persist AddressVerification ───────────────────────────
    verification_id: int | None = None
    try:
        verification = AddressVerification(
            raw_address=raw_address,
            normalized_address=normalized_address,
            confidence_score=confidence_score,
            match_details=match_details,
            risk_flags=risk_flags_dicts,
            detected_entities=entities_dict,
            latitude=lat,
            longitude=lng,
            created_at=now,
        )
        db.add(verification)
        db.commit()
        db.refresh(verification)
        verification_id = verification.id
    except Exception as exc:
        logger.error(f"[VERIFY] DB persist (AddressVerification) failed: {exc}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        # Do not return fallback response, instead keep going and return the computed data with id=None
        verification_id = None

    # ── Step 7: Log API call ──────────────────────────────────────────
    try:
        api_log = APILog(
            endpoint="/verify",
            method="POST",
            request_time=now,
            status_code=200,
        )
        db.add(api_log)
        db.commit()
    except Exception as exc:
        logger.error(f"[VERIFY] DB persist (APILog) failed: {exc}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    # ── Step 8: Return structured response ────────────────────────────
    return {
        "id": verification_id,
        "rawAddress": raw_address,
        "normalizedAddress": normalized_address,
        "confidenceScore": confidence_score,
        "matchDetails": match_details,
        "detectedEntities": entities_dict,
        "riskFlags": risk_flags_dicts,
        "aiPreprocessed": ai_was_used,
        "createdAt": now.isoformat(),
        "latitude": lat,
        "longitude": lng,
    }


# ---------------------------------------------------------------------------
# Quick self-test — run from backend/ folder:
#   py -m app.services.verification
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    import json
    from sqlmodel import SQLModel, create_engine, Session as TestSession

    # In-memory SQLite for self-test (no .env needed)
    test_engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(test_engine)

    test_cases = [
        "123 rue Didouche Mourad, Constantine 25000",
        "Oran, Bir El Djir 31003",
        "16000",
        "  ",
    ]

    print("=" * 72)
    print("  Algeo Verify — Verification Pipeline — Self-Test")
    print("=" * 72)

    with TestSession(test_engine) as session:
        for raw in test_cases:
            result = verifyAddress(raw, session)
            print(f"\n  RAW: {raw!r}")
            print(json.dumps(result, indent=4, ensure_ascii=False, default=str))

    print("\n" + "=" * 72)
    print("  \u2713 All test cases processed successfully")
    print("=" * 72)
