from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .delivery_agent import DeliveryAgent
    from .feedback import Feedback

class Delivery(SQLModel, table=True):
    __tablename__ = "delivery"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: str
    scheduled_date: datetime

    customer_name: Optional[str] = Field(default=None)
    customer_phone: Optional[str] = Field(default=None)

    # ── Address & geocoding fields ────────────────────────────────────
    address: Optional[str] = Field(default=None)
    normalized_address: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    confidence_score: Optional[float] = Field(default=None)
    ai_preprocessed: bool = Field(default=False)
    geocoding_status: Optional[str] = Field(default=None)  # "success" | "approximate" | "failed" | None

    delivery_agent_id: int = Field(foreign_key="delivery_agent.id", index=True)

    # Relationships
    delivery_agent: Optional["DeliveryAgent"] = Relationship(back_populates="deliveries")
    feedback: Optional["Feedback"] = Relationship(
        back_populates="delivery",
        sa_relationship_kwargs={"uselist": False}
    )