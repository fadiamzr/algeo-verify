from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session
from app.config import get_settings
from app.database import create_db_and_tables, get_session
from app.models import *  # noqa: F401, F403

from app.routes import auth, admin, deliveries, verification, sync
from app.routes.import_deliveries import router_import

_settings = get_settings()

app = FastAPI(
    title=_settings.APP_NAME,
    description="Address verification API for Algerian logistics",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(router_import)
app.include_router(deliveries.router)
app.include_router(verification.router)
app.include_router(sync.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.middleware import APILoggingMiddleware
app.add_middleware(APILoggingMiddleware)

create_db_and_tables()

@app.get("/")
def root():
    return {"message": "Algeo-Verify backend is running"}

@app.on_event("startup")
def run_seed():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from seed import seed
    seed()