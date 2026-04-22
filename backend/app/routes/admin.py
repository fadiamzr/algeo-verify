import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.database import get_session
from app.models import (
    User, UserRole, DeliveryAgent, Admin,
    Delivery, AddressVerification, VerificationRecord, APILog
)
from app.models.commune import Wilaya, Commune
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
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


# -----------------------------------------
# JWT Protection — admin only
# -----------------------------------------

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# -----------------------------------------
# Statistics
# -----------------------------------------

@router.get("/statistics")
def statistics(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return get_statistics(session)


@router.get("/monthly-trends")
def monthly_trends(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return get_monthly_trends(session)


@router.get("/delivery-status-distribution")
def delivery_status_distribution(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return get_delivery_status_distribution(session)


@router.get("/verifications-by-wilaya")
def verifications_by_wilaya(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return get_verifications_by_wilaya(session)


# -----------------------------------------
# Verifications
# -----------------------------------------

@router.get("/verifications")
def list_verifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    filter: Optional[str] = Query("all"),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
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

    return {"total": total, "page": page, "pageSize": page_size, "items": items}


@router.get("/verifications/{verification_id}")
def get_verification(
    verification_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    v = session.get(AddressVerification, verification_id)
    if not v:
        raise HTTPException(status_code=404, detail="Verification not found")
    return v


# -----------------------------------------
# Deliveries
# -----------------------------------------

@router.get("/deliveries")
def list_deliveries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    query = select(Delivery)
    total = len(session.exec(query).all())
    offset = (page - 1) * page_size
    items = session.exec(query.offset(offset).limit(page_size)).all()
    return {"total": total, "page": page, "pageSize": page_size, "items": items}


@router.post("/deliveries/import")
async def import_deliveries_csv(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    text = content.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))

    created = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        try:
            status = row.get("status", "pending").strip()
            scheduled_date_str = row.get("scheduled_date", "").strip()
            delivery_agent_id = row.get("delivery_agent_id", "").strip()

            if not delivery_agent_id:
                errors.append(f"Row {i}: missing delivery_agent_id")
                continue

            from datetime import datetime
            if scheduled_date_str:
                try:
                    scheduled_date = datetime.fromisoformat(scheduled_date_str)
                except ValueError:
                    scheduled_date = datetime.now()
            else:
                scheduled_date = datetime.now()

            delivery = Delivery(
                status=status,
                scheduled_date=scheduled_date,
                delivery_agent_id=int(delivery_agent_id),
                address=row.get("address", "").strip() or None,
            )
            session.add(delivery)
            session.commit()
            session.refresh(delivery)

            if delivery.address:
                try:
                    from app.services.verification import verifyAddress
                    from app.services.geocoding import geocode_address
                    result = verifyAddress(delivery.address, session)
                    delivery.normalized_address = result.get("normalizedAddress")
                    delivery.confidence_score = result.get("confidenceScore")
                    delivery.ai_preprocessed = result.get("aiPreprocessed", False)
                    entities = result.get("detectedEntities", {})
                    geo = geocode_address(
                        delivery.normalized_address or delivery.address,
                        wilaya=entities.get("wilaya"),
                        commune=entities.get("commune"),
                    )
                    delivery.latitude = geo.get("latitude")
                    delivery.longitude = geo.get("longitude")
                    delivery.geocoding_status = geo.get("status")
                    session.add(delivery)
                    session.commit()
                except Exception as e:
                    print(f"[WARN] Pipeline failed for row {i}: {e}")

            created += 1

        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")

    return {"message": "Import complete", "created": created, "errors": errors}


@router.get("/deliveries/map")
def deliveries_map(
    status: Optional[str] = Query(default=None, description="Filter by delivery status"),
    limit: int = Query(default=200, ge=1, le=1000, description="Max results"),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    query = select(Delivery).where(
        Delivery.latitude != None,  # noqa: E711
        Delivery.longitude != None,  # noqa: E711
    )
    if status:
        query = query.where(Delivery.status == status)
    query = query.limit(limit)
    items = session.exec(query).all()
    return [
        {
            "id": d.id,
            "address": d.address,
            "normalized_address": d.normalized_address,
            "latitude": d.latitude,
            "longitude": d.longitude,
            "status": d.status,
            "confidence_score": d.confidence_score,
            "geocoding_status": d.geocoding_status,
            "scheduled_date": d.scheduled_date.isoformat() if d.scheduled_date else None,
            "agent_id": d.delivery_agent_id,
        }
        for d in items
    ]


@router.get("/deliveries/{delivery_id}/geocode")
def re_geocode_delivery(
    delivery_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    d = session.get(Delivery, delivery_id)
    if not d:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if not d.address:
        raise HTTPException(status_code=400, detail="Delivery has no address to process")
    try:
        from app.services.verification import verifyAddress
        from app.services.geocoding import geocode_address
        result = verifyAddress(d.address, session)
        d.normalized_address = result.get("normalizedAddress")
        d.confidence_score = result.get("confidenceScore")
        d.ai_preprocessed = result.get("aiPreprocessed", False)
        if d.normalized_address:
            entities = result.get("detectedEntities", {})
            geo = geocode_address(
                d.normalized_address,
                wilaya=entities.get("wilaya"),
                commune=entities.get("commune"),
            )
            d.latitude = geo.get("latitude")
            d.longitude = geo.get("longitude")
            d.geocoding_status = geo.get("status")
        else:
            d.geocoding_status = "failed"
        session.add(d)
        session.commit()
        session.refresh(d)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-geocoding pipeline failed: {e}")
    return {
        "id": d.id, "address": d.address, "normalized_address": d.normalized_address,
        "latitude": d.latitude, "longitude": d.longitude, "status": d.status,
        "confidence_score": d.confidence_score, "geocoding_status": d.geocoding_status,
        "ai_preprocessed": d.ai_preprocessed,
        "scheduled_date": d.scheduled_date.isoformat() if d.scheduled_date else None,
        "agent_id": d.delivery_agent_id,
    }


@router.get("/deliveries/{delivery_id}")
def get_delivery(
    delivery_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    d = session.get(Delivery, delivery_id)
    if not d:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return d


# -----------------------------------------
# Agents CRUD + Import
# -----------------------------------------

@router.get("/agents")
def list_agents(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    agents = session.exec(select(DeliveryAgent)).all()
    result = []
    for agent in agents:
        user = session.get(User, agent.user_id)
        result.append({
            "id": agent.id,
            "user_id": agent.user_id,
            "company_id": agent.company_id,
            "name": user.name if user else "—",
            "email": user.email if user else "—",
        })
    return result

@router.post("/agents/import")
async def import_agents_csv(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    text = content.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))

    created = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        try:
            user_id_str = row.get("user_id", "").strip()
            company_id_str = row.get("company_id", "").strip()

            if not user_id_str:
                errors.append(f"Row {i}: missing user_id")
                continue

            user_id = int(user_id_str)
            company_id = int(company_id_str) if company_id_str else None

            user = session.get(User, user_id)
            if not user:
                errors.append(f"Row {i}: user_id {user_id} not found")
                continue

            existing = session.exec(
                select(DeliveryAgent).where(DeliveryAgent.user_id == user_id)
            ).first()
            if existing:
                errors.append(f"Row {i}: agent already exists for user_id {user_id}")
                continue

            agent = DeliveryAgent(user_id=user_id, company_id=company_id)
            session.add(agent)
            session.commit()
            session.refresh(agent)
            created += 1

        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")

    return {"message": "Import complete", "created": created, "errors": errors}

import secrets
import string

class AgentRegisterRequest(BaseModel):
    name: str
    email: str

@router.post("/agents/register")
def register_agent(
    body: AgentRegisterRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    from app.core.security import hash_password
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    generated_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(generated_password),
        role=UserRole.delivery_agent,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    agent = DeliveryAgent(user_id=user.id)
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return {
        "id": agent.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "company_id": agent.company_id,
        "generated_password": generated_password,
    }

@router.post("/agents")
def create_agent(
    user_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
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

from pydantic import BaseModel

class AgentRegisterRequest(BaseModel):
    name: str
    email: str
    password: str

@router.post("/agents/register")
def register_agent(
    body: AgentRegisterRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    from app.core.security import hash_password
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=UserRole.delivery_agent,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    agent = DeliveryAgent(user_id=user.id)
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return {"id": agent.id, "user_id": user.id, "name": user.name, "email": user.email, "company_id": agent.company_id}
@router.get("/agents/{agent_id}")
def get_agent(
    agent_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    agent = session.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}")
def update_agent(
    agent_id: int,
    company_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
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
def delete_agent(
    agent_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    agent = session.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Delete associated deliveries first
    deliveries = session.exec(
        select(Delivery).where(Delivery.delivery_agent_id == agent_id)
    ).all()
    for delivery in deliveries:
        session.delete(delivery)
    
    session.delete(agent)
    session.commit()
    return {"message": "Agent deleted"}

# -----------------------------------------
# Users
# -----------------------------------------

@router.get("/users")
def list_users(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    users = session.exec(select(User)).all()
    return [{"id": u.id, "email": u.email, "full_name": getattr(u, "full_name", None)} for u in users]

# -----------------------------------------
# Analytics
# -----------------------------------------

@router.get("/analytics/score-distribution")
def score_distribution(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return get_score_distribution(session)


@router.get("/logs")
def logs(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return get_logs(session, limit=limit)


@router.get("/logs/requests-per-endpoint")
def requests_per_endpoint(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return get_requests_per_endpoint(session)


@router.get("/logs/error-rate")
def error_rate(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return get_error_rate(session)


# -----------------------------------------
# Geographic Data — Wilayas & Communes
# -----------------------------------------

@router.get("/wilayas")
def list_wilayas(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return session.exec(select(Wilaya)).all()


@router.get("/communes")
def list_communes(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    return session.exec(select(Commune)).all()