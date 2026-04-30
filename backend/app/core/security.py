import os
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecret")
ALGORITHM = "HS256"

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)