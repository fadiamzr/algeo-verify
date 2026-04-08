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

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlmodel import Session

from app.config import get_settings
from app.models import AddressVerification, APILog
from app.services import ai_preprocessor
from app.services.normalization import normalize
from app.services.detection import detectEntities
from app.services.scoring import ScoringEngine, RiskFlag


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


def _risk_flags_to_dicts(flags: List[RiskFlag]) -> List[Dict[str, str]]:
    """Serialize RiskFlag dataclass instances to plain dicts."""
    return [
        {
            "label": f.label,
            "severity": f.severity,
            "description": f.description,
        }
        for f in flags
    ]


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
    settings = get_settings()

    # ── Step 0: AI preprocess (optional) ──────────────────────────────
    ai_was_used: bool = False
    address_for_normalization = raw_address

    if settings.AI_ENABLED:
        try:
            ai_result = ai_preprocessor.preprocess_address(raw_address)
            if ai_result:
                clean = ai_preprocessor.build_clean_address(ai_result)
                if clean:
                    address_for_normalization = clean
                    ai_was_used = True
                    print(f"[AI] Using AI-cleaned address: {clean!r}")
        except Exception as e:
            print(f"[AI] Preprocessor error (continuing without AI): {e}")

    # ── Step 1: Normalize ─────────────────────────────────────────────
    normalized_address = normalize(address_for_normalization)

    # ── Step 2: Detect entities ───────────────────────────────────────
    detected = detectEntities(normalized_address)

    # ── Step 3: Score ─────────────────────────────────────────────────
    engine = ScoringEngine()
    confidence_score, risk_flags = engine.computeScore(detected)

    # ── Step 4: Build match description ───────────────────────────────
    match_details = _build_match_details(
        detected.wilaya, detected.commune, detected.postalCode, detected.street
    )

    # ── Step 5: Persist AddressVerification ───────────────────────────
    verification = AddressVerification(
        raw_address=raw_address,
        normalized_address=normalized_address,
        confidence_score=confidence_score,
        match_details=match_details,
        created_at=now,
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)

    # ── Step 6: Log API call ──────────────────────────────────────────
    api_log = APILog(
        endpoint="/verify",
        method="POST",
        request_time=now,
        status_code=200,
    )
    db.add(api_log)
    db.commit()

    # ── Step 7: Return structured response ────────────────────────────
    return {
        "id": verification.id,
        "rawAddress": raw_address,
        "normalizedAddress": normalized_address,
        "confidenceScore": confidence_score,
        "matchDetails": match_details,
        "detectedEntities": {
            "wilaya": detected.wilaya,
            "commune": detected.commune,
            "postalCode": detected.postalCode,
            "street": detected.street,
        },
        "riskFlags": _risk_flags_to_dicts(risk_flags),
        "aiPreprocessed": ai_was_used,
        "createdAt": now.isoformat(),
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
