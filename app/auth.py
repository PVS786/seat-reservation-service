import jwt
from fastapi import Header, HTTPException, status
import os

JWT_SECRET = os.getenv("JWT_SECRET", "test_secret")

def get_current_user(authorization: str = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if not payload.get("sub"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No sub in token")
        return payload
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

from fastapi import Depends

def get_current_user_id(payload: dict = Depends(get_current_user)) -> str:
    return str(payload.get("sub"))

def require_admin(payload: dict = Depends(get_current_user)) -> str:
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return str(payload.get("sub"))
