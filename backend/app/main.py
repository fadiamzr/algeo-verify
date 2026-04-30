import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session

from app.config import get_settings
from app.database import create_db_and_tables, get_session
from app.models import *  # noqa: F401, F403
from app.middleware import APILoggingMiddleware

from app.routes import auth
from app.routes import admin
from app.routes import deliveries
from app.routes.sync import router_sync
from app.routes.verifications import router_verifications

logger = logging.getLogger(__name__)

_settings = get_settings()

app = FastAPI(
    title=_settings.APP_NAME,
    description="Address verification API for Algerian logistics",
    version="0.1.0",
)

# --- Routers ---
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(deliveries.router)
app.include_router(router_sync)
app.include_router(router_verifications)

# --- Middleware (order matters: last added = outermost) ---
# 1. Logging middleware (inner — runs after CORS is handled)
app.add_middleware(APILoggingMiddleware)

# 2. CORS middleware (outer — must be outermost to handle OPTIONS preflight)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

create_db_and_tables()


class VerifyRequest(BaseModel):
    raw_address: str


@app.get("/")
def root():
    return {"message": "Algeo-Verify backend is running"}


@app.post("/verify")
def verify_address(
    body: VerifyRequest,
    db: Session = Depends(get_session),
):
    from app.services.verification import verifyAddress
    return verifyAddress(body.raw_address, db)


@app.on_event("startup")
def run_seed():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from seed import seed
    seed()