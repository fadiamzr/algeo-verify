from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .delivery import Delivery

class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    outcome: str
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # 1-to-1 relationship with deliveries logic
    delivery_id: int = Field(foreign_key="delivery.id", unique=True, index=True)

    # Relationships
    delivery: Optional["Delivery"] = Relationship(back_populates="feedback")