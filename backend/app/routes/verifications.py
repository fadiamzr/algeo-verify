import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from app.database import get_session
from app.models.user import User
from app.models.verification_record import VerificationRecord
from app.models.verification import AddressVerification
from app.routes.auth import get_current_user

router_verifications = APIRouter(prefix="/verifications", tags=["verifications"])

@router_verifications.get("/history")
def get_verification_history(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    try:
        # For now return the recent verifications, we will fetch AddressVerification for now
        # since it's simpler and contains all the data needed by the app
        verifications = session.exec(
            select(AddressVerification).order_by(AddressVerification.created_at.desc()).limit(50)
        ).all()
        
        return [
            {
                "id": str(v.id),
                "createdAt": v.created_at.isoformat(),
                "confidenceScore": v.confidence_score,
                "rawAddress": v.raw_address,
                "normalizedAddress": v.normalized_address
            }
            for v in verifications
        ]
    except Exception as e:
        logging.error(f"GET /verifications/history — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch verification history",
        )
