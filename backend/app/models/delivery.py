from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import Text, JSON

if TYPE_CHECKING:
    from .delivery_agent import DeliveryAgent
    from .feedback import Feedback

class Delivery(SQLModel, table=True):
    __tablename__ = "delivery"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: str
    scheduled_date: datetime

    # ── Customer info ─────────────────────────────────────────────────
    customer_name: Optional[str] = Field(default=None)
    customer_phone: Optional[str] = Field(default=None)

    # ── Address & geocoding fields ────────────────────────────────────
    delivery_code: Optional[str] = Field(default=None)
    address: Optional[str] = Field(default=None, sa_column=Column(Text))
    normalized_address: Optional[str] = Field(default=None, sa_column=Column(Text))
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    confidence_score: Optional[float] = Field(default=None)
    match_details: Optional[str] = Field(default=None, sa_column=Column(Text))
    detected_entities: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    risk_flags: Optional[list] = Field(default=None, sa_column=Column(JSON))
    ai_preprocessed: bool = Field(default=False)
    geocoding_status: Optional[str] = Field(default=None)  # "success" | "approximate" | "failed" | None

    delivery_agent_id: int = Field(foreign_key="delivery_agent.id", index=True)

    # Relationships
    delivery_agent: Optional["DeliveryAgent"] = Relationship(back_populates="deliveries")
    feedback: Optional["Feedback"] = Relationship(
        back_populates="delivery",
        sa_relationship_kwargs={"uselist": False}
    )