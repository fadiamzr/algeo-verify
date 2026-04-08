"""
Algeo Verify — Database Seeder
================================
Populates the database with test data for development.
Run from backend/ folder:
    python -m app.services.seed
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timezone, timedelta
from sqlmodel import Session, create_engine, SQLModel

from app.config import get_settings
from app.models import (
    User, UserRole, DeliveryAgent, Admin,
    Delivery, AddressVerification, DetectedEntities,
    VerificationRecord, APILog, Feedback
)
from app.core.security import hash_password

_settings = get_settings()
engine = create_engine(_settings.DATABASE_URL, connect_args={"check_same_thread": False})


def seed():
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        # ── Check if already seeded ──────────────────────────────────────
        existing = db.query(User).filter(User.email == "admin@algeo.dz").first()
        if existing:
            print("✓ Database already seeded — skipping.")
            return

        print("🌱 Seeding database...")

        # ── Users ────────────────────────────────────────────────────────
        admin_user = User(
            name="Yacine Benmoussa",
            email="admin@algeo.dz",
            password_hash=hash_password("admin123"),
            role=UserRole.admin,
        )
        agent_user1 = User(
            name="Amina Boudiaf",
            email="amina@algeo.dz",
            password_hash=hash_password("agent123"),
            role=UserRole.delivery_agent,
        )
        agent_user2 = User(
            name="Youcef Khedira",
            email="youcef@algeo.dz",
            password_hash=hash_password("agent123"),
            role=UserRole.delivery_agent,
        )
        agent_user3 = User(
            name="Fatima Zerhouni",
            email="fatima@algeo.dz",
            password_hash=hash_password("agent123"),
            role=UserRole.delivery_agent,
        )

        db.add_all([admin_user, agent_user1, agent_user2, agent_user3])
        db.commit()
        db.refresh(admin_user)
        db.refresh(agent_user1)
        db.refresh(agent_user2)
        db.refresh(agent_user3)
        print("  ✓ Users created")

        # ── Admin profile ─────────────────────────────────────────────────
        admin_profile = Admin(user_id=admin_user.id)
        db.add(admin_profile)

        # ── Delivery Agents ───────────────────────────────────────────────
        agent1 = DeliveryAgent(user_id=agent_user1.id, company_id=1001)
        agent2 = DeliveryAgent(user_id=agent_user2.id, company_id=1001)
        agent3 = DeliveryAgent(user_id=agent_user3.id, company_id=1002)
        db.add_all([agent1, agent2, agent3])
        db.commit()
        db.refresh(agent1)
        db.refresh(agent2)
        db.refresh(agent3)
        print("  ✓ Agents created")

        # ── Address Verifications ─────────────────────────────────────────
        now = datetime.now(timezone.utc)
        verifications_data = [
            ("12 Rue Didouche Mourad, Alger Centre", "12 Rue Didouche Mourad, Alger-Centre, 16000", 0.92, "Alger", "Alger-Centre", "16000", "Rue Didouche Mourad"),
            ("45 Blvd Mohamed V, Oran", "45 Boulevard Mohamed V, Oran, 31000", 0.85, "Oran", "Oran", "31000", "Boulevard Mohamed V"),
            ("Cité 500 Logements, Bt C, Batna", "Cité 500 Logements, Bâtiment C, Batna, 05000", 0.67, "Batna", "Batna", "05000", "Cité 500 Logements"),
            ("Hai el Badr, près du marché, Constantine", "Hai El Badr, Constantine, 25000", 0.38, "Constantine", "Constantine", "25000", None),
            ("8 Rue des Frères Bouadou, Tizi Ouzou", "8 Rue des Frères Bouadou, Tizi-Ouzou, 15000", 0.95, "Tizi-Ouzou", "Tizi-Ouzou", "15000", "Rue des Frères Bouadou"),
            ("Lotissement 23, Zone Industrielle, Sétif", "Lotissement 23, Zone Industrielle, Sétif, 19000", 0.72, "Sétif", "Sétif", "19000", "Zone Industrielle"),
            ("17 Avenue 1er Novembre, Blida", "17 Avenue du 1er Novembre 1954, Blida, 09000", 0.88, "Blida", "Blida", "09000", "Avenue du 1er Novembre 1954"),
            ("Quartier résidentiel, derrière la mosquée, Annaba", "Quartier Résidentiel, Annaba, 23000", 0.42, "Annaba", "Annaba", "23000", None),
            ("15 Rue Ben Mhidi, Tlemcen", "15 Rue Larbi Ben Mhidi, Tlemcen, 13000", 0.91, "Tlemcen", "Tlemcen", "13000", "Rue Larbi Ben Mhidi"),
            ("Cité Boussouf, Bt D, Constantine", "Cité Boussouf, Bâtiment D, Constantine, 25000", 0.65, "Constantine", "Constantine", "25000", "Cité Boussouf"),
            ("Route Nationale 5, Bordj Bou Arréridj", "Route Nationale 5, Bordj Bou Arréridj, 34000", 0.78, "Bordj Bou Arréridj", "Bordj Bou Arréridj", "34000", "Route Nationale 5"),
            ("Hai Sabah, Mostaganem", "Hai Sabah, Mostaganem, 27000", 0.55, "Mostaganem", "Mostaganem", "27000", None),
            ("23 Rue des Martyrs, Béjaïa", "23 Rue des Martyrs, Béjaïa, 06000", 0.89, "Béjaïa", "Béjaïa", "06000", "Rue des Martyrs"),
            ("Cité AADL, Bt 12, Alger", "Cité AADL, Bâtiment 12, Bab Ezzouar, Alger, 16000", 0.61, "Alger", "Bab Ezzouar", "16000", "Cité AADL"),
            ("Près de la gare, Oran", "Gare d'Oran, Oran, 31000", 0.35, "Oran", "Oran", "31000", None),
        ]

        verifications = []
        for i, (raw, normalized, score, wilaya, commune, postal, street) in enumerate(verifications_data):
            v = AddressVerification(
                raw_address=raw,
                normalized_address=normalized,
                confidence_score=score,
                match_details=f"Matched: {wilaya}, {commune}" if wilaya else "Partial match",
                created_at=now - timedelta(days=i, hours=i * 2),
            )
            db.add(v)
            db.commit()
            db.refresh(v)
            verifications.append(v)

            # DetectedEntities
            entities = DetectedEntities(
                wilaya=wilaya,
                commune=commune,
                postal_code=postal,
                street=street,
            )
            db.add(entities)

            # VerificationRecord
            rec = VerificationRecord(
                verification_date=now - timedelta(days=i),
                result_score=score,
                address_verification_id=v.id,
            )
            db.add(rec)

        db.commit()
        print("  ✓ Verifications created")

        # ── Deliveries ────────────────────────────────────────────────────
        statuses = ["pending", "inProgress", "completed", "failed", "completed", "pending", "completed", "inProgress", "failed", "completed"]
        for i, (status, v) in enumerate(zip(statuses, verifications[:10])):
            agent = [agent1, agent2, agent3][i % 3]
            d = Delivery(
                status=status,
                scheduled_date=now + timedelta(hours=i * 3 - 10),
                delivery_agent_id=agent.id,
            )
            db.add(d)
            db.commit()
            db.refresh(d)

            if status == "completed":
                fb = Feedback(
                    outcome="delivered",
                    notes="Delivered successfully.",
                    delivery_id=d.id,
                )
                db.add(fb)

        db.commit()
        print("  ✓ Deliveries created")

        # ── API Logs ──────────────────────────────────────────────────────
        endpoints = [
            ("/verify", "POST", 200),
            ("/auth/login", "POST", 200),
            ("/api/admin/statistics", "GET", 200),
            ("/api/admin/agents", "GET", 200),
            ("/verify", "POST", 200),
            ("/api/admin/verifications", "GET", 200),
            ("/verify", "POST", 422),
            ("/auth/login", "POST", 401),
            ("/api/admin/logs", "GET", 200),
            ("/verify", "POST", 200),
            ("/api/admin/deliveries", "GET", 200),
            ("/verify", "POST", 200),
        ]

        for i, (endpoint, method, status_code) in enumerate(endpoints):
            log = APILog(
                endpoint=endpoint,
                method=method,
                request_time=now - timedelta(hours=i),
                status_code=status_code,
            )
            db.add(log)

        db.commit()
        print("  ✓ API Logs created")

        print("\n✅ Database seeded successfully!")
        print("   Admin login: admin@algeo.dz / admin123")
        print("   Agent login: amina@algeo.dz / agent123")


if __name__ == "__main__":
    seed()