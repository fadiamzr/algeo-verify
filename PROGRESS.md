## Done
- `config.py` — Settings class, loads `.env`, exposes DATABASE_URL, GEO_DATA_DIR, CORS, DEBUG
- `database.py` — SQLModel engine (SQLite/PostgreSQL auto-detect), `create_db_and_tables()`, `get_session()`
- `requirements.txt` — added sqlmodel, python-dotenv, pydantic-settings

## In progress
(none — waiting for next instruction)

## Pending
- `models/verification.py` — AddressVerification table (SQLModel)
- `schemas/verification.py` — VerifyRequest, VerifyResponse, DetectedEntities, RiskFlag
- `utils/geo_data.py` — load wilayas/communes JSON, build lookup maps
- `utils/normalizer.py` — normalize(raw): whitespace, diacritics, Arabic/French
- `utils/entity_detector.py` — detect wilaya, commune, postalCode, street
- `utils/scorer.py` — weighted confidence score (wilaya=0.35, commune=0.30, postal=0.15, street=0.20)
- `utils/risk_flagger.py` — flag missing fields, mismatches
- `services/verification.py` — orchestrate full pipeline, persist to DB
- `routes/verification.py` — POST /api/v1/verify, GET verifications
- `main.py` — wire router, startup event, CORS middleware

## Important decisions
- SQLite for dev, PostgreSQL for prod — switched via DATABASE_URL env var
- `check_same_thread=False` added only for SQLite (FastAPI is multi-threaded)
- Geo data paths auto-resolved relative to project root, overridable via GEO_DATA_DIR env var
- `get_settings()` cached as singleton via `@lru_cache`