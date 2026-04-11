"""Run the verification + geocoding pipeline on all existing deliveries."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import select
from app.database import create_db_and_tables, get_session
from app.models.delivery import Delivery
from app.services.verification import verifyAddress
from app.services.geocoding import geocode_address

create_db_and_tables()
db = next(get_session())

deliveries = db.exec(select(Delivery)).all()
print(f"Found {len(deliveries)} deliveries\n")

for d in deliveries:
    if not d.address:
        print(f"  #{d.id} — no address, skipping")
        continue

    print(f"  #{d.id} — {d.address!r}")

    # Step 1: Verify (normalize + detect + score)
    result = verifyAddress(d.address, db)
    d.normalized_address = result.get("normalizedAddress")
    d.confidence_score = result.get("confidenceScore")
    d.ai_preprocessed = result.get("aiPreprocessed", False)

    # Step 2: Geocode
    entities = result.get("detectedEntities", {})
    geo = geocode_address(
        d.normalized_address or d.address,
        wilaya=entities.get("wilaya"),
        commune=entities.get("commune"),
    )
    d.latitude = geo.get("latitude")
    d.longitude = geo.get("longitude")
    d.geocoding_status = geo.get("status")

    db.add(d)
    db.commit()

    print(f"         → lat={d.latitude}, lng={d.longitude}, status={d.geocoding_status}")

print("\nDone.")