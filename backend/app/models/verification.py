from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship

class AddressVerification(SQLModel, table=True):
    __tablename__ = "address_verification"

    id: Optional[int] = Field(default=None, primary_key=True)
    raw_address: str
    normalized_address: Optional[str] = None
    confidence_score: float
    match_details: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    verification_records: List["VerificationRecord"] = Relationship(back_populates="address_verification")


class DetectedEntities(SQLModel, table=True):
    __tablename__ = "detected_entities"

    id: Optional[int] = Field(default=None, primary_key=True)
    wilaya: Optional[str] = None
    commune: Optional[str] = None
    postal_code: Optional[str] = None
    street: Optional[str] = None


class VerificationRecord(SQLModel, table=True):
    __tablename__ = "verification_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    verification_date: datetime
    result_score: float
    
    address_verification_id: int = Field(foreign_key="address_verification.id", index=True)

    # Relationships
    address_verification: Optional["AddressVerification"] = Relationship(back_populates="verification_records")


class APILog(SQLModel, table=True):
    __tablename__ = "api_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    endpoint: str
    method: str
    request_time: datetime
    status_code: int  