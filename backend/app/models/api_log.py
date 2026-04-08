"""
Algeo Verify — SQLModel: APILog
Tracks every API call for analytics and debugging.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class APILog(SQLModel, table=True):
    """One row per API request — used by the admin analytics dashboard."""

    __tablename__ = "api_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    endpoint: str = Field(max_length=100)
    method: str = Field(default="GET", max_length=10)
    request_time: datetime = Field(default_factory=_utcnow)
    status_code: int = Field(default=200)
