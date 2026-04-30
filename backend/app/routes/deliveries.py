"""
Algeo Verify — Delivery Routes
================================
All endpoints are scoped to the authenticated delivery agent.

Prefix  : /deliveries
Auth    : Bearer JWT  →  Depends(get_current_user)

Endpoints
---------
GET    /deliveries/                   list (paginated + filtered)
POST   /deliveries/                   create
GET    /deliveries/{id}               single delivery
PATCH  /deliveries/{id}/status        update status
POST   /deliveries/{id}/verify        address verification
POST   /deliveries/{id}/feedback      submit feedback
GET    /deliveries/{id}/history       verification history
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models.delivery import Delivery
from app.models.delivery_agent import DeliveryAgent
from app.models.feedback import Feedback
from app.models.user import User
from app.models.verification import AddressVerification
from app.routes.auth import get_current_user
from app.schemas.delivery import (
    ALLOWED_STATUSES,
    DeliveryCreate,
    DeliveryRead,
    DeliveryUpdateStatus,
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/deliveries",
    tags=["deliveries"],
)


# ---------------------------------------------------------------------------
# Internal schemas (feedback only — delivery schemas live in app/schemas/)
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    outcome: str
    notes: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    outcome: str
    notes: Optional[str]
    delivery_id: int


class VerifyResponse(BaseModel):
    confidenceScore: float
    risk: str
    normalizedAddress: str


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_or_create_agent(user: User, session: Session) -> DeliveryAgent:
    """
    Return the DeliveryAgent linked to *user*, creating one on the fly
    if it does not exist yet.

    This prevents the "No delivery agent profile linked to this account"
    error for users who authenticated before their agent row was seeded.
    """
    agent = session.exec(
        select(DeliveryAgent).where(DeliveryAgent.user_id == user.id)
    ).first()

    if not agent:
        logging.info(f"Auto-creating DeliveryAgent for user {user.id} ({user.email})")
        agent = DeliveryAgent(user_id=user.id)
        session.add(agent)
        session.commit()
        session.refresh(agent)

    return agent


def _get_delivery_or_404(
    delivery_id: int,
    agent: DeliveryAgent,
    session: Session,
) -> Delivery:
    """Fetch a delivery owned by *this* agent, or raise 404."""
    delivery = session.exec(
        select(Delivery).where(
            Delivery.id == delivery_id,
            Delivery.delivery_agent_id == agent.id,
        )
    ).first()

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delivery {delivery_id} not found",
        )
    return delivery


def _score_to_risk(score: float) -> str:
    """Map a 0–1 confidence score to a risk label."""
    if score >= 0.75:
        return "low"
    if score >= 0.45:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# A)  GET /deliveries/  — paginated + filtered list
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[DeliveryRead])
def get_deliveries(
    # pagination
    limit: int = Query(default=10, ge=1, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    # filters
    status: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    # deps
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Return deliveries assigned to the authenticated agent.
    """
    try:
        agent = _get_or_create_agent(user, session)

        query = select(Delivery).where(Delivery.delivery_agent_id == agent.id).order_by(Delivery.id.desc())

        # Optional filters
        if status:
             query = query.where(Delivery.status == status)

        if date_from:
            query = query.where(Delivery.scheduled_date >= date_from)

        if date_to:
            query = query.where(Delivery.scheduled_date <= date_to)

        # Pagination
        query = query.offset(offset).limit(limit)

        deliveries = session.exec(query).all()
        return deliveries

    except HTTPException:
        raise

    except Exception as e:
        logging.error(f"GET /deliveries/ — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch deliveries",
        )


# ---------------------------------------------------------------------------
# B)  POST /deliveries/  — create a new delivery
# ---------------------------------------------------------------------------

@router.post("/", response_model=DeliveryRead, status_code=status.HTTP_201_CREATED)
def create_delivery(
    body: DeliveryCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Create a new delivery linked to the authenticated agent.

    The delivery_agent_id is resolved automatically from the current user —
    the caller never supplies it directly.

    After persisting the record, the address verification + geocoding pipeline
    runs in a best-effort try/except; failures never block delivery creation.
    """
    try:
        agent = _get_or_create_agent(user, session)

        delivery = Delivery(
            address=body.address,
            status=body.status,
            scheduled_date=body.scheduled_date,
            delivery_agent_id=agent.id,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
        )
        session.add(delivery)
        session.commit()
        session.refresh(delivery)

    except HTTPException:
        raise

    except Exception as e:
        logging.error(f"POST /deliveries/ — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create delivery",
        )

    # ── Address verification + geocoding (best-effort) ────────────────────────
    try:
        from app.services.verification import verifyAddress
        from app.services.geocoding import geocode_address
        from app.config import get_settings
        settings = get_settings()

        result = verifyAddress(delivery.address, session)
        delivery.normalized_address = result.get("normalizedAddress")
        delivery.confidence_score = result.get("confidenceScore")
        delivery.ai_preprocessed = result.get("aiPreprocessed", False)

        # Geocode if enabled and we have a normalised address to work with
        if settings.GEOCODING_ENABLED and delivery.normalized_address:
            entities = result.get("detectedEntities", {})
            geo = geocode_address(
                delivery.normalized_address,
                wilaya=entities.get("wilaya"),
                commune=entities.get("commune"),
            )
            delivery.latitude = geo.get("latitude")
            delivery.longitude = geo.get("longitude")
            delivery.geocoding_status = geo.get("status")

        session.add(delivery)
        session.commit()
        session.refresh(delivery)

    except Exception as e:
        logging.warning(f"Address processing failed for delivery {delivery.id}: {e}")
        # Don't fail the delivery creation — address processing is best-effort

    return delivery


# ---------------------------------------------------------------------------
# C)  GET /deliveries/{id}  — single delivery
# ---------------------------------------------------------------------------

@router.get("/{delivery_id}", response_model=DeliveryRead)
def get_delivery(
    delivery_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Return a single delivery owned by the authenticated agent."""
    try:
        agent = _get_or_create_agent(user, session)
        return _get_delivery_or_404(delivery_id, agent, session)

    except HTTPException:
        raise

    except Exception as e:
        logging.error(f"GET /deliveries/{delivery_id} — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch delivery",
        )


# ---------------------------------------------------------------------------
# D)  PATCH /deliveries/{id}/status  — update delivery status
# ---------------------------------------------------------------------------

@router.patch("/{delivery_id}/status", response_model=DeliveryRead)
def update_delivery_status(
    delivery_id: int,
    body: DeliveryUpdateStatus,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Update the status of a delivery owned by the authenticated agent.

    Allowed statuses: pending | in_progress | delivered | cancelled
    """
    try:
        agent = _get_or_create_agent(user, session)
        delivery = _get_delivery_or_404(delivery_id, agent, session)

        delivery.status = body.status
        session.add(delivery)
        session.commit()
        session.refresh(delivery)

        return delivery

    except HTTPException:
        raise

    except Exception as e:
        logging.error(f"PATCH /deliveries/{delivery_id}/status — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update delivery status",
        )


# ---------------------------------------------------------------------------
# E)  POST /deliveries/{id}/verify  — address verification
# ---------------------------------------------------------------------------

@router.post("/{delivery_id}/verify", response_model=VerifyResponse)
def verify_delivery(
    delivery_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Run the address-verification pipeline on an owned delivery.
    The real verifyAddress() service is called; Delivery.address/raw_address
    is used when available, otherwise a placeholder is passed.
    """
    try:
        agent = _get_or_create_agent(user, session)
        delivery = _get_delivery_or_404(delivery_id, agent, session)

        raw_address: str = (
            getattr(delivery, "address", None)
            or getattr(delivery, "raw_address", None)
            or f"Delivery #{delivery.id} — address pending"
        )

        from app.services.verification import verifyAddress

        result = verifyAddress(raw_address, session)
        confidence: float = result.get("confidenceScore", 0.0)

        return VerifyResponse(
            confidenceScore=confidence,
            risk=_score_to_risk(confidence),
            normalizedAddress=result.get("normalizedAddress", raw_address),
        )

    except HTTPException:
        raise

    except Exception as e:
        logging.error(f"POST /deliveries/{delivery_id}/verify — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Address verification failed",
        )


# ---------------------------------------------------------------------------
# F)  POST /deliveries/{id}/feedback  — submit / update feedback
# ---------------------------------------------------------------------------

@router.post(
    "/{delivery_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    delivery_id: int,
    body: FeedbackRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Save (or overwrite) feedback for an owned delivery.
    Feedback has a UNIQUE constraint on delivery_id (1-to-1 with Delivery).
    """
    try:
        agent = _get_or_create_agent(user, session)
        delivery = _get_delivery_or_404(delivery_id, agent, session)

        existing: Optional[Feedback] = session.exec(
            select(Feedback).where(Feedback.delivery_id == delivery.id)
        ).first()

        if existing:
            existing.outcome = body.outcome
            existing.notes = body.notes
            session.add(existing)
            session.commit()
            session.refresh(existing)
            feedback = existing
        else:
            feedback = Feedback(
                outcome=body.outcome,
                notes=body.notes,
                delivery_id=delivery.id,
            )
            session.add(feedback)
            session.commit()
            session.refresh(feedback)

        return FeedbackResponse(
            id=feedback.id,
            outcome=feedback.outcome,
            notes=feedback.notes,
            delivery_id=feedback.delivery_id,
        )

    except HTTPException:
        raise

    except Exception as e:
        logging.error(f"POST /deliveries/{delivery_id}/feedback — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback",
        )


# ---------------------------------------------------------------------------
# G)  GET /deliveries/{id}/history  — past verification records
# ---------------------------------------------------------------------------

@router.get("/{delivery_id}/history")
def get_delivery_history(
    delivery_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Return basic delivery history (current logic: single event).
    """
    try:
        agent = _get_or_create_agent(user, session)
        delivery = _get_delivery_or_404(delivery_id, agent, session)

        # Keep it simple: return the current state as the basic history.
        return {
            "deliveryId": delivery_id,
            "history": [
                {
                    "status": delivery.status,
                    "date": delivery.scheduled_date.isoformat(),
                    "note": "Delivery created/updated"
                }
            ]
        }

    except HTTPException:
        raise

    except Exception as e:
        logging.error(f"GET /deliveries/{delivery_id}/history — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch history",
        )

# ---------------------------------------------------------------------------
# H)  PATCH /deliveries/{id}/verification  — save verification
# ---------------------------------------------------------------------------
class VerificationSaveRequest(BaseModel):
    confidence_score: float
    normalized_address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

@router.patch("/{delivery_id}/verification")
def save_verification(
    delivery_id: int,
    body: VerificationSaveRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        agent = _get_or_create_agent(user, session)
        delivery = _get_delivery_or_404(delivery_id, agent, session)

        delivery.confidence_score = body.confidence_score
        delivery.normalized_address = body.normalized_address
        if body.latitude is not None:
            delivery.latitude = body.latitude
        if body.longitude is not None:
            delivery.longitude = body.longitude

        session.add(delivery)
        session.commit()
        session.refresh(delivery)

        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PATCH /deliveries/{delivery_id}/verification — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save verification",
        )