"""
Algeo Verify — Database Seed Script
Run from the backend/ folder:  python seed.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ── Bootstrap Python path so `app.*` imports resolve ──────────────────
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import select

from app.database import create_db_and_tables, get_session
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.admin import Admin
from app.models.delivery_agent import DeliveryAgent
from app.models.delivery import Delivery
from app.models.commune import Wilaya, Commune
from app.models.feedback import Feedback          # noqa: F401  (needed for relationship resolution)
from app.models.verification import AddressVerification  # noqa: F401

# ── Paths ─────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
# JSON files live one level above backend/, in the project-root database/ folder
WILAYA_PATH = BASE.parent / "database" / "wilaya.json"
COMMUNES_PATH = BASE.parent / "database" / "communes.json"


def seed() -> None:
    # 0. Ensure tables exist
    create_db_and_tables()
    db = next(get_session())

    try:
        # ── 1. Skip if already seeded ─────────────────────────────────
        existing_agent = db.exec(select(DeliveryAgent)).first()
        if existing_agent:
         print("Already seeded. Skipping.")
         return

        # ── 2. Create admin user ──────────────────────────────────────
        admin_user = User(
            name="Admin Algeo",
            email="admin@algeo.dz",
            password_hash=hash_password("admin1234"),
            role=UserRole.admin,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        admin_profile = Admin(user_id=admin_user.id)
        db.add(admin_profile)
        db.commit()
        db.refresh(admin_profile)

        # ── 3. Create delivery-agent user ─────────────────────────────
        agent_user = User(
            name="Agent Test",
            email="agent@algeo.dz",
            password_hash=hash_password("agent1234"),
            role=UserRole.delivery_agent,
        )
        db.add(agent_user)
        db.commit()
        db.refresh(agent_user)

        agent_profile = DeliveryAgent(user_id=agent_user.id)
        db.add(agent_profile)
        db.commit()
        db.refresh(agent_profile)

        # ── 4. Load wilayas ───────────────────────────────────────────
        with open(WILAYA_PATH, "r", encoding="utf-8") as f:
            wilayas_data = json.load(f)

        existing_codes = {
            row.code
            for row in db.exec(select(Wilaya)).all()
            if row.code
        }

        wilaya_count = 0
        for w in wilayas_data:
            code = w.get("code")
            if code in existing_codes:
                continue
            wilaya = Wilaya(
                code=code,
                name_fr=w.get("name_fr") or w.get("name"),
                name_ar=w.get("name_ar"),
                name_en=w.get("name_en"),
            )
            db.add(wilaya)
            wilaya_count += 1

        db.commit()
        print(f"  Wilayas inserted: {wilaya_count}")

        # Build lookup: wilaya code -> wilaya DB id  (for commune FK)
        wilaya_code_to_id = {
            row.code: row.id
            for row in db.exec(select(Wilaya)).all()
            if row.code
        }

        # ── 5. Load communes ─────────────────────────────────────────
        with open(COMMUNES_PATH, "r", encoding="utf-8") as f:
            communes_data = json.load(f)

        # Gather existing (name_fr, wilaya_id) pairs for idempotency
        existing_communes = {
            (row.name_fr, row.wilaya_id)
            for row in db.exec(select(Commune)).all()
        }

        commune_count = 0
        for c in communes_data:
            name_fr = c.get("name_fr") or c.get("name")
            # JSON uses 'wilaya_code' (e.g. "01"); map to DB id
            wilaya_code = c.get("wilaya_code") or c.get("wilaya_id")
            wilaya_id = wilaya_code_to_id.get(str(wilaya_code))

            if (name_fr, wilaya_id) in existing_communes:
                continue

            postal = c.get("postal_code") or c.get("post_code")
            commune = Commune(
                name_fr=name_fr,
                name_ar=c.get("name_ar"),
                postal_code=int(postal) if postal is not None else None,
                wilaya_id=wilaya_id,
            )
            db.add(commune)
            commune_count += 1

        db.commit()
        print(f"  Communes inserted: {commune_count}")

        # ── 6. Create 5 sample deliveries ─────────────────────────────
        today = datetime.now(timezone.utc)
        sample_deliveries = [
            {"status": "pending",     "scheduled_date": today,                      "address": "123 rue Didouche Mourad, Constantine 25000"},
            {"status": "in_progress", "scheduled_date": today - timedelta(days=1),  "address": "حي 500 مسكن، باب الواد، الجزائر 16001"},
            {"status": "in_progress", "scheduled_date": today - timedelta(days=2),  "address": "Cité 1000 logements, Bir El Djir, Oran"},
            {"status": "delivered",   "scheduled_date": today - timedelta(days=3),  "address": "en face lycée Lotfi, hai es salam, Batna"},
            {"status": "cancelled",   "scheduled_date": today - timedelta(days=4),  "address": "BLIDA, BOUFARIK 09001"},
        ]

        for d in sample_deliveries:
            delivery = Delivery(
                address=d["address"],
                status=d["status"],
                scheduled_date=d["scheduled_date"],
                delivery_agent_id=agent_profile.id,
            )
            db.add(delivery)
            db.commit()
            db.refresh(delivery)

        # ── 7. Summary ────────────────────────────────────────────────
        print()
        print("  Admin:      admin@algeo.dz / admin1234")
        print("  Agent:      agent@algeo.dz / agent1234")
        print(f"  Wilayas:    {wilaya_count} loaded")
        print(f"  Communes:   {commune_count} loaded")
        print("  Deliveries: 5 created")
        print()
        print("Seed complete.")

    except Exception as e:
        print(f"Seed failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    seed()
