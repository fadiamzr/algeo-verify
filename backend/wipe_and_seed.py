import sys
import os

# Ensure the backend directory is in the path
sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, SQLModel
from app.models import (
    Wilaya, Commune, AddressVerification,
    VerificationRecord, APILog,
    User, Admin, DeliveryAgent, Delivery, Feedback,
)

print("Dropping all tables from the database...")
SQLModel.metadata.drop_all(engine)
print("All tables dropped successfully!")

print("\nRunning the seed script...")
from seed import seed
seed()
