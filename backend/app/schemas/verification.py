"""
Algeo Verify — Pydantic Schemas for the verification endpoint.
Request/response shapes with camelCase aliases for the JSON API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    """POST /api/v1/verify body."""
    raw_address: str = Field(
        ..., min_length=1, description="The raw address string to verify"
    )


# ── Sub-models ────────────────────────────────────────────────────────

class DetectedEntities(BaseModel):
    """Entities extracted from the address."""
    wilaya: Optional[str] = None
    commune: Optional[str] = None
    postal_code: Optional[str] = Field(default=None, alias="postalCode")
    street: Optional[str] = None

    model_config = {"populate_by_name": True}


class RiskFlag(BaseModel):
    """A single risk flag raised during verification."""
    label: str
    severity: str = Field(..., pattern="^(low|medium|high)$")
    description: str


class MatchDetail(BaseModel):
    """Breakdown of how each component contributed to the score."""
    component: str
    weight: float
    found: bool
    matched_value: Optional[str] = Field(default=None, alias="matchedValue")
    score_contribution: float = Field(alias="scoreContribution")

    model_config = {"populate_by_name": True}


# ── Response ──────────────────────────────────────────────────────────

class VerifyResponse(BaseModel):
    """Full verification result returned by the API."""
    id: int
    raw_address: str = Field(alias="rawAddress")
    normalized_address: str = Field(alias="normalizedAddress")
    confidence_score: float = Field(alias="confidenceScore")
    match_details: list[MatchDetail] = Field(alias="matchDetails")
    detected_entities: DetectedEntities = Field(alias="detectedEntities")
    risk_flags: list[RiskFlag] = Field(alias="riskFlags")
    created_at: datetime = Field(alias="createdAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }
