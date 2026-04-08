"""
Algeo Verify — SQLModel: VerificationRecord
Links to an AddressVerification and stores per-run scoring snapshots.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VerificationRecord(SQLModel, table=True):
    """Historical record tied to a single verification run."""

    __tablename__ = "verification_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    address_verification_id: Optional[int] = Field(
        default=None, foreign_key="address_verification.id"
    )
    verification_date: datetime = Field(default_factory=_utcnow)
    result_score: float = Field(default=0.0)
