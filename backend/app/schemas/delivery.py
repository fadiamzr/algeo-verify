"""
Algeo Verify — Delivery Schemas
================================
Pydantic models for request validation and response serialization.
Kept separate from the SQLModel ORM model to respect the separation
between API contract and DB layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Allowed statuses (single source of truth)
# ---------------------------------------------------------------------------

ALLOWED_STATUSES = {"pending", "in_progress", "delivered", "cancelled"}
AllowedStatus = Literal["pending", "in_progress", "delivered", "cancelled"]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class DeliveryCreate(BaseModel):
    """Payload for POST /deliveries/"""

    address: str
    status: AllowedStatus
    scheduled_date: datetime
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {sorted(ALLOWED_STATUSES)}"
            )
        return v


class DeliveryUpdateStatus(BaseModel):
    """Payload for PATCH /deliveries/{id}/status"""

    status: AllowedStatus

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {sorted(ALLOWED_STATUSES)}"
            )
        return v


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class DeliveryRead(BaseModel):
    """Returned for every delivery endpoint — never exposes raw ORM model."""

    id: int
    status: str
    scheduled_date: datetime
    delivery_agent_id: int

    # ── Customer info ─────────────────────────────────────────────────
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    # ── Address & geocoding fields ────────────────────────────────────
    delivery_code: Optional[str] = None
    address: Optional[str] = None
    normalized_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence_score: Optional[float] = None
    ai_preprocessed: bool = False
    geocoding_status: Optional[str] = None
    match_details: Optional[str] = None
    detected_entities: Optional[Dict[str, Any]] = None
    risk_flags: Optional[List[Dict[str, Any]]] = None

    model_config = {"from_attributes": True}  # Pydantic v2 ORM mode
