from sqlmodel import Session, select, func
from datetime import datetime, timezone
from collections import defaultdict

from app.models import (
    Delivery,
    AddressVerification,
    VerificationRecord,
    DeliveryAgent,
    User,
    APILog,
)


# ─────────────────────────────────────────
# General statistics
# ─────────────────────────────────────────

def get_statistics(session: Session) -> dict:
    total_deliveries = session.exec(select(func.count(Delivery.id))).one()
    total_verifications = session.exec(select(func.count(AddressVerification.id))).one()

    avg_score = session.exec(
        select(func.avg(AddressVerification.confidence_score))
    ).one() or 0.0

    high_risk = session.exec(
        select(func.count(AddressVerification.id)).where(
            AddressVerification.confidence_score < 0.5
        )
    ).one()

    # ── Use correct status strings matching the DB ──
    status_counts = {}
    for status in ["pending", "in_progress", "delivered", "cancelled"]:
        count = session.exec(
            select(func.count(Delivery.id)).where(Delivery.status == status)
        ).one()
        status_counts[status] = count

    total_agents = session.exec(select(func.count(DeliveryAgent.id))).one()
    total_api_calls = session.exec(select(func.count(APILog.id))).one()

    # Delivery success rate
    delivered = status_counts.get("delivered", 0)
    success_rate = round(delivered / total_deliveries, 3) if total_deliveries > 0 else 0.0

    return {
        "totalDeliveries": total_deliveries,
        "totalVerifications": total_verifications,
        "avgConfidenceScore": round(avg_score, 3),
        "riskyAddresses": high_risk,
        "deliveryStatusCounts": status_counts,
        "totalAgents": total_agents,
        "totalApiCalls": total_api_calls,
        "deliverySuccessRate": success_rate,
        "activeAgents": total_agents,
    }


# ─────────────────────────────────────────
# Monthly trends
# ─────────────────────────────────────────

def get_monthly_trends(session: Session) -> list[dict]:
    # Use AddressVerification (which is actually populated) instead of VerificationRecord
    verifications = session.exec(select(AddressVerification)).all()
    deliveries = session.exec(select(Delivery)).all()

    monthly_verif: dict[str, int] = defaultdict(int)
    monthly_deliv: dict[str, int] = defaultdict(int)

    for v in verifications:
        if v.created_at:
            key = v.created_at.strftime("%Y-%m")
            monthly_verif[key] += 1

    for d in deliveries:
        if d.scheduled_date:
            key = d.scheduled_date.strftime("%Y-%m")
            monthly_deliv[key] += 1

    all_months = sorted(set(list(monthly_verif.keys()) + list(monthly_deliv.keys())))

    return [
        {
            "month": month,
            "verifications": monthly_verif.get(month, 0),
            "deliveries": monthly_deliv.get(month, 0),
        }
        for month in all_months
    ]


# ─────────────────────────────────────────
# Delivery status distribution
# ─────────────────────────────────────────

def get_delivery_status_distribution(session: Session) -> list[dict]:
    # ── Use correct status strings matching the DB ──
    statuses = ["pending", "in_progress", "delivered", "cancelled"]
    colors = {
        "pending": "#EAB308",
        "in_progress": "#3B82F6",
        "delivered": "#22C55E",
        "cancelled": "#EF4444",
    }
    labels = {
        "pending": "Pending",
        "in_progress": "In Progress",
        "delivered": "Delivered",
        "cancelled": "Cancelled",
    }
    total = session.exec(select(func.count(Delivery.id))).one() or 1

    distribution = []
    for status in statuses:
        count = session.exec(
            select(func.count(Delivery.id)).where(Delivery.status == status)
        ).one()
        distribution.append({
            "name": labels[status],
            "value": count,
            "color": colors[status],
            "status": status,
            "percentage": round((count / total) * 100, 1),
        })

    return distribution


# ─────────────────────────────────────────
# Verifications by wilaya
# ─────────────────────────────────────────

def get_verifications_by_wilaya(session: Session) -> list[dict]:
    """
    Extract wilaya info from Delivery addresses using the detection engine.
    Uses deliveries with normalized_address rather than the non-existent
    DetectedEntities table.
    """
    from app.services.detection import detectEntities

    deliveries = session.exec(select(Delivery)).all()

    wilaya_counts: dict[str, int] = defaultdict(int)
    for d in deliveries:
        addr = d.normalized_address or d.address
        if addr:
            entities = detectEntities(addr)
            if entities.wilaya:
                wilaya_counts[entities.wilaya] += 1

    return [
        {"wilaya": wilaya, "count": count}
        for wilaya, count in sorted(wilaya_counts.items(), key=lambda x: -x[1])
    ]


# ─────────────────────────────────────────
# Score distribution
# ─────────────────────────────────────────

def get_score_distribution(session: Session) -> list[dict]:
    buckets = [
        ("0.0 – 0.2", 0.0, 0.2),
        ("0.2 – 0.4", 0.2, 0.4),
        ("0.4 – 0.6", 0.4, 0.6),
        ("0.6 – 0.8", 0.6, 0.8),
        ("0.8 – 1.0", 0.8, 1.01),
    ]

    distribution = []
    for label, low, high in buckets:
        count = session.exec(
            select(func.count(AddressVerification.id)).where(
                AddressVerification.confidence_score >= low,
                AddressVerification.confidence_score < high,
            )
        ).one()
        distribution.append({"range": label, "count": count})

    return distribution


# ─────────────────────────────────────────
# API Logs
# ─────────────────────────────────────────

def get_logs(session: Session, limit: int = 100) -> list[dict]:
    logs = session.exec(
        select(APILog).order_by(APILog.request_time.desc()).limit(limit)
    ).all()

    return [
        {
            "id": log.id,
            "endpoint": log.endpoint,
            "method": log.method,
            "requestTime": log.request_time.isoformat(),
            "statusCode": log.status_code,
        }
        for log in logs
    ]


def get_requests_per_endpoint(session: Session) -> list[dict]:
    logs = session.exec(select(APILog)).all()

    endpoint_counts: dict[str, int] = defaultdict(int)
    for log in logs:
        endpoint_counts[log.endpoint] += 1

    return [
        {"endpoint": ep, "requests": count}
        for ep, count in sorted(endpoint_counts.items(), key=lambda x: -x[1])
    ]


def get_error_rate(session: Session) -> dict:
    total = session.exec(select(func.count(APILog.id))).one() or 1
    errors = session.exec(
        select(func.count(APILog.id)).where(APILog.status_code >= 400)
    ).one()

    return {
        "total": total,
        "errors": errors,
        "errorRate": round((errors / total) * 100, 2),
    }