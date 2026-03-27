from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .delivery_agent import DeliveryAgent
    from .admin import Admin

class UserRole(str, Enum):
    admin = "admin"
    delivery_agent = "delivery_agent"

class User(SQLModel, table=True):
    __tablename__ = "user"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: UserRole = Field(default=UserRole.delivery_agent)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships (One-to-One Extensions)
    delivery_agent_profile: Optional["DeliveryAgent"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False}
    )
    admin_profile: Optional["Admin"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False}
    )
