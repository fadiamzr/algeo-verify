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
            )
            session.add(delivery)
            session.commit()
            session.refresh(delivery)

            # Run the full pipeline
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

    return {
        "message": "Import complete",
        "created": created,
        "errors": errors,
    }