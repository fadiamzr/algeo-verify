from fastapi import FastAPI
from app.database import create_db_and_tables
from app.models import *

app = FastAPI()

create_db_and_tables()

@app.get("/")
def root():
    return {"message": "Algeo-Verify backend is running"}
