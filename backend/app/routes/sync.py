import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from app.database import get_session
from app.models.user import User
from app.models.delivery import Delivery
from app.routes.auth import get_current_user
from app.routes.deliveries import _get_or_create_agent
from datetime import datetime, timezone

router_sync = APIRouter(prefix="/sync", tags=["sync"])

@router_sync.post("/")
def sync_deliveries(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    try:
        agent = _get_or_create_agent(user, session)
        
        # Get deliveries
        deliveries = session.exec(
            select(Delivery).where(Delivery.delivery_agent_id == agent.id)
        ).all()
        
        # Prepare response that matches what Flutter SyncService expects
        return {
            "lastSync": datetime.now(timezone.utc).isoformat(),
            "deliveries": [
                {
                    "id": str(d.id),
                    "status": d.status,
                    "scheduled_date": d.scheduled_date.isoformat() if d.scheduled_date else None,
                    "address": d.address,
                    "normalized_address": d.normalized_address,
                    "latitude": d.latitude,
                    "longitude": d.longitude,
                    "confidence_score": d.confidence_score,
                    "customer_name": getattr(d, "customer_name", ""),
                    "customer_phone": getattr(d, "customer_phone", "")
                }
                for d in deliveries
            ],
            "history": [], # We don't have a good way to fetch just the history right now
            "totalItems": len(deliveries) + 1 # +1 for the profile
        }
    except Exception as e:
        logging.error(f"POST /sync/ — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync",
        )
