import sys
from sqlmodel import create_engine, Session, select
from app.config import get_settings
from app.models import Delivery, AddressVerification

settings = get_settings()
engine = create_engine(settings.DATABASE_URL)

with Session(engine) as session:
    deliveries = session.exec(select(Delivery).order_by(Delivery.id.desc()).limit(5)).all()
    print("Deliveries:")
    for d in deliveries:
        print(f"ID: {d.id}, Addr: {repr(d.address)}, Norm: {repr(d.normalized_address)}, AI: {d.ai_preprocessed}, Geo: {d.geocoding_status}")
    
    verifications = session.exec(select(AddressVerification).order_by(AddressVerification.id.desc()).limit(5)).all()
    print("\nVerifications:")
    for v in verifications:
        print(f"ID: {v.id}, Raw: {repr(v.raw_address)}, Norm: {repr(v.normalized_address)}")
