"""
Algeo Verify — SQLModel: Wilaya & Commune
Aligned with database/schema.sql.
"""

from typing import Optional

from sqlmodel import SQLModel, Field


class Wilaya(SQLModel, table=True):
    """Wilaya (province) reference table."""

    __tablename__ = "wilaya"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: Optional[str] = Field(default=None, max_length=10)
    name_fr: Optional[str] = Field(default=None, max_length=100)
    name_ar: Optional[str] = Field(default=None, max_length=100)
    name_en: Optional[str] = Field(default=None, max_length=100)


class Commune(SQLModel, table=True):
    """Commune reference table — belongs to a Wilaya."""

    __tablename__ = "commune"

    id: Optional[int] = Field(default=None, primary_key=True)
    name_fr: Optional[str] = Field(default=None, max_length=100)
    name_ar: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[int] = Field(default=None)
    wilaya_id: Optional[int] = Field(default=None, foreign_key="wilaya.id")
