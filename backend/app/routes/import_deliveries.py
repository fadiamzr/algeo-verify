import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session

from app.database import get_session
from app.models import Delivery, User
from app.routes.auth import get_current_user
from app.models.user import UserRole

router_import = APIRouter(prefix="/api/admin", tags=["admin-import"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router_import.post("/deliveries/import")
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
                normalized_address=row.get("normalized_address", "").strip() or None,
                confidence_score=float(row["confidence_score"]) if row.get("confidence_score") else None,
                latitude=float(row["latitude"]) if row.get("latitude") else None,
                longitude=float(row["longitude"]) if row.get("longitude") else None,
                ai_preprocessed=row.get("ai_preprocessed", "").lower() == "true",
                geocoding_status=row.get("geocoding_status", "").strip() or None,
            )
            session.add(delivery)
            created += 1

        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")

    session.commit()

    return {
        "message": f"Import complete",
        "created": created,
        "errors": errors,
    }
