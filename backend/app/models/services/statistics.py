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

    status_counts = {}
    for status in ["pending", "inProgress", "completed", "failed"]:
        count = session.exec(
            select(func.count(Delivery.id)).where(Delivery.status == status)
        ).one()
        status_counts[status] = count

    total_agents = session.exec(select(func.count(DeliveryAgent.id))).one()

    return {
        "totalDeliveries": total_deliveries,
        "totalVerifications": total_verifications,
        "averageConfidenceScore": round(avg_score, 3),
        "highRiskAddresses": high_risk,
        "deliveryStatusCounts": status_counts,
        "totalAgents": total_agents,
    }


# ─────────────────────────────────────────
# Monthly trends
# ─────────────────────────────────────────

def get_monthly_trends(session: Session) -> list[dict]:
    records = session.exec(select(VerificationRecord)).all()

    monthly: dict[str, dict] = defaultdict(lambda: {"verifications": 0, "totalScore": 0.0})

    for record in records:
        key = record.verification_date.strftime("%Y-%m")
        monthly[key]["verifications"] += 1
        monthly[key]["totalScore"] += record.result_score

    trends = []
    for month, data in sorted(monthly.items()):
        count = data["verifications"]
        avg = round(data["totalScore"] / count, 3) if count else 0.0
        trends.append({
            "month": month,
            "verifications": count,
            "averageScore": avg,
        })

    return trends


# ─────────────────────────────────────────
# Delivery status distribution
# ─────────────────────────────────────────

def get_delivery_status_distribution(session: Session) -> list[dict]:
    statuses = ["pending", "inProgress", "completed", "failed"]
    total = session.exec(select(func.count(Delivery.id))).one() or 1

    distribution = []
    for status in statuses:
        count = session.exec(
            select(func.count(Delivery.id)).where(Delivery.status == status)
        ).one()
        distribution.append({
            "status": status,
            "count": count,
            "percentage": round((count / total) * 100, 1),
        })

    return distribution


# ─────────────────────────────────────────
# Verifications by wilaya
# ─────────────────────────────────────────

def get_verifications_by_wilaya(session: Session) -> list[dict]:
    from app.models import DetectedEntities

    results = session.exec(select(DetectedEntities)).all()

    wilaya_counts: dict[str, int] = defaultdict(int)
    for entity in results:
        if entity.wilaya:
            wilaya_counts[entity.wilaya] += 1

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
        {"endpoint": ep, "count": count}
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