from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from jose import jwt, JWTError
from pydantic import BaseModel

from app.database import get_session
from app.models.user import User
from app.core.security import verify_password, create_access_token, SECRET_KEY, ALGORITHM

class LoginRequest(BaseModel):
    email: str
    password: str

router = APIRouter()
security = HTTPBearer()


# --- LOGIN ---
@router.post("/auth/login")
def login(data: LoginRequest, session: Session = Depends(get_session)):
    # Case-insensitive email comparison
    user = session.exec(
        select(User).where(User.email.ilike(data.email.strip()))
    ).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


# --- VERIFY TOKEN ---
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id = int(payload.get("sub"))

        user = session.get(User, user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
# --- CURRENT USER ---
@router.get("/auth/me")
def get_me(user=Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at
    }