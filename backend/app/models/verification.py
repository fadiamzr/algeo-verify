"""
Algeo Verify — SQLModel: AddressVerification
Aligned with database/schema.sql + extended with detected_entities & risk_flags.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text, JSON


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AddressVerification(SQLModel, table=True):
    """Core verification result — one row per verify request."""

    __tablename__ = "address_verification"

    id: Optional[int] = Field(default=None, primary_key=True)
    raw_address: str = Field(sa_column=Column(Text))
    normalized_address: str = Field(sa_column=Column(Text))
    confidence_score: float = Field(default=0.0)
    match_details: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    detected_entities: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    risk_flags: Optional[list] = Field(default=None, sa_column=Column(JSON))
    commune_id: Optional[int] = Field(default=None, foreign_key="commune.id")
    created_at: datetime = Field(default_factory=_utcnow)
