import traceback
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.models.verification import AddressVerification
from app.schemas.delivery import VerificationRead
from app.routes.auth import get_current_user
from app.models.user import User

router = APIRouter(
    tags=["verification"],
)

class VerifyRequest(BaseModel):
    raw_address: str

@router.post("/verify", response_model=VerificationRead)
def verify_address(
    body: VerifyRequest,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user), # Require auth
):
    """
    General address verification endpoint.
    Always returns a valid JSON response — never raises 500.
    """
    from app.services.verification import verifyAddress
    try:
        result = verifyAddress(body.raw_address, db)
        return result
    except Exception as e:
        # This should never happen since verifyAddress now has its own
        # fallback, but just in case — return a safe response instead
        # of a 500 error.
        print(f"[ERROR] POST /verify — unhandled exception: {e}")
        traceback.print_exc()

        now = datetime.now(timezone.utc)
        return {
            "id": None,
            "rawAddress": body.raw_address,
            "normalizedAddress": body.raw_address,
            "confidenceScore": 0.0,
            "matchDetails": f"Verification error: {type(e).__name__}",
            "detectedEntities": None,
            "riskFlags": None,
            "createdAt": now.isoformat(),
            "latitude": None,
            "longitude": None,
        }

@router.get("/verifications/history", response_model=List[VerificationRead])
def get_verification_history(
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Return the history of address verifications.
    For now, returns the most recent 100 verifications.
    """
    try:
        # In a real app, you might filter this by user/agent if they were linked.
        statement = select(AddressVerification).order_by(AddressVerification.created_at.desc()).limit(100)
        results = db.exec(statement).all()
        
        # Convert to VerificationRead schema (handling camelCase mapping)
        return [
            VerificationRead(
                id=v.id,
                rawAddress=v.raw_address,
                normalizedAddress=v.normalized_address,
                confidenceScore=v.confidence_score,
                matchDetails=v.match_details,
                detectedEntities=v.detected_entities,
                riskFlags=v.risk_flags,
                createdAt=v.created_at.isoformat(),
                latitude=v.latitude,
                longitude=v.longitude,
            )
            for v in results
        ]
    except Exception as e:
        print(f"[ERROR] GET /verifications/history — {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch verification history",
        )
