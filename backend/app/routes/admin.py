from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional

from app.database import get_session
from app.models import (
    User, UserRole, DeliveryAgent, Admin,
    Delivery, AddressVerification, VerificationRecord, APILog
)
from app.services.statistics import (
    get_statistics,
    get_monthly_trends,
    get_delivery_status_distribution,
    get_verifications_by_wilaya,
    get_score_distribution,
    get_logs,
    get_requests_per_endpoint,
    get_error_rate,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─────────────────────────────────────────
# Statistics
# ─────────────────────────────────────────

@router.get("/statistics")
def statistics(session: Session = Depends(get_session)):
    return get_statistics(session)


@router.get("/monthly-trends")
def monthly_trends(session: Session = Depends(get_session)):
    return get_monthly_trends(session)


@router.get("/delivery-status-distribution")
def delivery_status_distribution(session: Session = Depends(get_session)):
    return get_delivery_status_distribution(session)


@router.get("/verifications-by-wilaya")
def verifications_by_wilaya(session: Session = Depends(get_session)):
    return get_verifications_by_wilaya(session)


# ─────────────────────────────────────────
# Verifications
# ─────────────────────────────────────────

@router.get("/verifications")
def list_verifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    filter: Optional[str] = Query("all"),
    session: Session = Depends(get_session),
):
    query = select(AddressVerification)

    if filter == "high":
        query = query.where(AddressVerification.confidence_score >= 0.8)
    elif filter == "medium":
        query = query.where(
            AddressVerification.confidence_score >= 0.5,
            AddressVerification.confidence_score < 0.8,
        )
    elif filter == "low":
        query = query.where(AddressVerification.confidence_score < 0.5)
    elif filter == "risky":
        query = query.where(AddressVerification.confidence_score < 0.4)

    total = len(session.exec(query).all())
    offset = (page - 1) * page_size
    items = session.exec(query.offset(offset).limit(page_size)).all()

    return {
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": items,
    }


@router.get("/verifications/{verification_id}")
def get_verification(verification_id: int, session: Session = Depends(get_session)):
    v = session.get(AddressVerification, verification_id)
    if not v:
        raise HTTPException(status_code=404, detail="Verification not found")
    return v


# ─────────────────────────────────────────
# Deliveries
# ─────────────────────────────────────────

@router.get("/deliveries")
def list_deliveries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = select(Delivery)
    total = len(session.exec(query).all())
    offset = (page - 1) * page_size
    items = session.exec(query.offset(offset).limit(page_size)).all()

    return {
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": items,
    }


@router.get("/deliveries/{delivery_id}")
def get_delivery(delivery_id: int, session: Session = Depends(get_session)):
    d = session.get(Delivery, delivery_id)
    if not d:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return d


# ─────────────────────────────────────────
# Agents CRUD
# ─────────────────────────────────────────

@router.get("/agents")
def list_agents(session: Session = Depends(get_session)):
    agents = session.exec(select(DeliveryAgent)).all()
    return agents


@router.get("/agents/{agent_id}")
def get_agent(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/agents")
def create_agent(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = session.exec(
        select(DeliveryAgent).where(DeliveryAgent.user_id == user_id)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agent already exists for this user")
    agent = DeliveryAgent(user_id=user_id)
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@router.put("/agents/{agent_id}")
def update_agent(
    agent_id: int,
    company_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    agent = session.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if company_id is not None:
        agent.company_id = company_id
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    session.delete(agent)
    session.commit()
    return {"message": "Agent deleted"}


# ─────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────

@router.get("/analytics/score-distribution")
def score_distribution(session: Session = Depends(get_session)):
    return get_score_distribution(session)


@router.get("/logs")
def logs(limit: int = Query(100, ge=1, le=500), session: Session = Depends(get_session)):
    return get_logs(session, limit=limit)


@router.get("/logs/requests-per-endpoint")
def requests_per_endpoint(session: Session = Depends(get_session)):
    return get_requests_per_endpoint(session)


@router.get("/logs/error-rate")
def error_rate(session: Session = Depends(get_session)):
    return get_error_rate(session)