from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from app.database import get_session
from app.models.user import User
from app.models.delivery import Delivery
from app.models.delivery_agent import DeliveryAgent
from app.models.verification import AddressVerification
from app.routes.auth import get_current_user
from app.schemas.delivery import DeliveryRead, VerificationRead
from app.routes.deliveries import _get_or_create_agent

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
)

@router.post("/", response_model=dict)
def sync_data(
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Consolidated endpoint to sync app state in one request.
    Returns deliveries, verification history, and user profile.
    """
    try:
        agent = _get_or_create_agent(user, db)
        
        # 1. Fetch Deliveries
        deliveries_stmt = select(Delivery).where(Delivery.delivery_agent_id == agent.id)
        deliveries = db.exec(deliveries_stmt).all()
        
        # 2. Fetch Verification History (most recent 50 for sync)
        verifications_stmt = select(AddressVerification).order_by(AddressVerification.created_at.desc()).limit(50)
        verifications = db.exec(verifications_stmt).all()
        
        # 3. Build response
        return {
            "deliveries": [DeliveryRead.model_validate(d).model_dump() for d in deliveries],
            "verifications": [
                {
                    "id": v.id,
                    "rawAddress": v.raw_address,
                    "normalizedAddress": v.normalized_address,
                    "confidenceScore": v.confidence_score,
                    "matchDetails": v.match_details,
                    "detectedEntities": v.detected_entities,
                    "riskFlags": v.risk_flags,
                    "createdAt": v.created_at.isoformat(),
                    "latitude": v.latitude,
                    "longitude": v.longitude,
                }
                for v in verifications
            ],
            "profile": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "agentId": agent.id,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "totalItems": len(deliveries)
        }
    except Exception as e:
        print(f"[ERROR] POST /sync — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sync failed",
        )
