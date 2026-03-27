from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .user import User
    from .delivery import Delivery

class DeliveryAgent(SQLModel, table=True):
    __tablename__ = "delivery_agent"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 1-to-1 extension of User requires unique=True
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    company_id: Optional[int] = None
    
    # Relationships
    user: Optional["User"] = Relationship(back_populates="delivery_agent_profile")
    deliveries: List["Delivery"] = Relationship(back_populates="delivery_agent")