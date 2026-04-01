"""
Algeo Verify — FastAPI Application
====================================
Main entry point.  Start with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session

from app.config import get_settings
from app.database import create_db_and_tables, get_session
from app.models import *  # noqa: F401, F403  — registers all SQLModel tables

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
_settings = get_settings()

app = FastAPI(
    title=_settings.APP_NAME,
    description="Address verification API for Algerian logistics",
    version="0.1.0",
)

# ── CORS ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Create tables on startup ─────────────────────────────────────────
create_db_and_tables()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class VerifyRequest(BaseModel):
    """Body for address verification endpoints."""
    raw_address: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Algeo-Verify backend is running"}


@app.post("/verify")
def verify_address(
    body: VerifyRequest,
    db: Session = Depends(get_session),
):
    """Verify a raw address through the full pipeline.

    Accepts a JSON body ``{"raw_address": "..."}`` and returns the
    verification result with confidence score, detected entities,
    and risk flags.
    """
    from app.services.verification import verifyAddress

    return verifyAddress(body.raw_address, db)


@app.post("/deliveries/{delivery_id}/verify")
def verify_delivery_address(
    delivery_id: int,
    db: Session = Depends(get_session),
):
    """Verify an address for a specific delivery.

    Looks up the delivery by ID (to confirm it exists), then runs
    the address verification pipeline on its address field.
    """
    from app.models import Delivery
    from app.services.verification import verifyAddress

    # Confirm the delivery exists
    delivery = db.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery {delivery_id} not found")

    # Detect address field
    address = getattr(delivery, "address", getattr(delivery, "raw_address", None))
    if not address:
        raise HTTPException(status_code=400, detail="Delivery does not have a raw_address or address field")

    result = verifyAddress(address, db)
    result["deliveryId"] = delivery_id
    return result
