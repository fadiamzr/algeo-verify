"""
One-off script: geocode existing deliveries that have NULL coordinates.
Run from backend/:  python geocode_existing.py
"""

import sys
import os
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import select
from app.database import create_db_and_tables, get_session
from app.models.delivery import Delivery
from app.services.verification import verifyAddress
from app.services.geocoding import geocode_address
from app.config import get_settings


def main() -> None:
    create_db_and_tables()
    db = next(get_session())
    settings = get_settings()

    # Find deliveries without coordinates
    deliveries = db.exec(
        select(Delivery).where(Delivery.latitude == None)  # noqa: E711
    ).all()

    if not deliveries:
        print("All deliveries already have coordinates. Nothing to do.")
        return

    print(f"Found {len(deliveries)} deliveries without coordinates.\n")

    for delivery in deliveries:
        print(f"  [{delivery.id}] {delivery.address!r}")

        try:
            result = verifyAddress(delivery.address, db)
            delivery.normalized_address = result.get("normalizedAddress")
            delivery.confidence_score = result.get("confidenceScore")
            delivery.ai_preprocessed = result.get("aiPreprocessed", False)

            if settings.GEOCODING_ENABLED and delivery.normalized_address:
                entities = result.get("detectedEntities", {})
                geo = geocode_address(
                    delivery.normalized_address,
                    wilaya=entities.get("wilaya"),
                    commune=entities.get("commune"),
                )
                delivery.latitude = geo.get("latitude")
                delivery.longitude = geo.get("longitude")
                delivery.geocoding_status = geo.get("status")

            db.add(delivery)
            db.commit()
            db.refresh(delivery)

            print(f"       -> ({delivery.latitude}, {delivery.longitude}) "
                  f"[{delivery.geocoding_status}]")

        except Exception as e:
            print(f"       [!] Failed: {e}")

        # Be nice to Nominatim (1 req/sec policy)
        time.sleep(1.1)

    print(f"\nDone. Geocoded {len(deliveries)} deliveries.")


if __name__ == "__main__":
    main()
