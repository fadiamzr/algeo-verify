import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, DeliveryAgent
from app.routes.auth import get_current_user
from app.models.user import UserRole

router_import_agents = APIRouter(prefix="/api/admin", tags=["admin-import"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router_import_agents.post("/agents/import")
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

            # Check user exists
            user = session.get(User, user_id)
            if not user:
                errors.append(f"Row {i}: user_id {user_id} does not exist")
                continue

            # Check agent not already created for this user
            existing = session.exec(
                select(DeliveryAgent).where(DeliveryAgent.user_id == user_id)
            ).first()
            if existing:
                errors.append(f"Row {i}: agent already exists for user_id {user_id}")
                continue

            company_id = int(company_id_str) if company_id_str else None

            agent = DeliveryAgent(
                user_id=user_id,
                company_id=company_id,
            )
            session.add(agent)
            created += 1

        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")

    session.commit()

    return {
        "message": "Import complete",
        "created": created,
        "errors": errors,
    }