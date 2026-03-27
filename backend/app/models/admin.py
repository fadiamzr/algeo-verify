from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .user import User

class Admin(SQLModel, table=True):
    __tablename__ = "admin"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 1-to-1 extension of User requires unique=True
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="admin_profile")
