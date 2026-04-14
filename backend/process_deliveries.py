"""
Run the full AI + normalization + detection + scoring + geocoding pipeline
on all deliveries that haven't been processed yet (normalized_address is null).

Usage: py process_deliveries.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import select
from app.database import create_db_and_tables, get_session
from app.models.delivery import Delivery
from app.services.verification import verifyAddress
from app.services.geocoding import geocode_address

create_db_and_tables()
db = next(get_session())

# Find unprocessed deliveries
deliveries = db.exec(
    select(Delivery).where(Delivery.normalized_address == None)
).all()

print(f"Found {len(deliveries)} unprocessed deliveries\n")

for d in deliveries:
    if not d.address:
        print(f"  #{d.id} — no address, skipping")
        continue

    print(f"  #{d.id} — {d.address!r}")

    # Step 1: Full verification pipeline (AI preprocess → normalize → detect → score)
    try:
        result = verifyAddress(d.address, db)
        d.normalized_address = result.get("normalizedAddress")
        d.confidence_score = result.get("confidenceScore")
        d.ai_preprocessed = result.get("aiPreprocessed", False)

        entities = result.get("detectedEntities", {})
        print(f"         → normalized: {d.normalized_address!r}")
        print(f"         → score: {d.confidence_score}, ai: {d.ai_preprocessed}")
        print(f"         → entities: wilaya={entities.get('wilaya')}, commune={entities.get('commune')}, postal={entities.get('postalCode')}")

        # Step 2: Geocode
        geo = geocode_address(
            d.normalized_address or d.address,
            wilaya=entities.get("wilaya"),
            commune=entities.get("commune"),
        )
        d.latitude = geo.get("latitude")
        d.longitude = geo.get("longitude")
        d.geocoding_status = geo.get("status")
        print(f"         → coords: ({d.latitude}, {d.longitude}) [{d.geocoding_status}]")

        db.add(d)
        db.commit()

    except Exception as e:
        print(f"         → ERROR: {e}")

    # Nominatim rate limit: 1 request per second
    time.sleep(1.1)

print(f"\nDone. Processed {len(deliveries)} deliveries.")

# Summary
all_deliveries = db.exec(select(Delivery)).all()
geocoded = [d for d in all_deliveries if d.latitude is not None]
ai_processed = [d for d in all_deliveries if d.ai_preprocessed]
print(f"\n=== Summary ===")
print(f"  Total deliveries: {len(all_deliveries)}")
print(f"  Geocoded: {len(geocoded)}")
print(f"  AI preprocessed: {len(ai_processed)}")