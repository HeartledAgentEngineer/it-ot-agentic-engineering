"""Authentication API routes (prepared for future use)."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header

from app.config import settings

logger = logging.getLogger(__name__)

# python-jose ist optional – wird erst bei Bedarf installiert
try:
    from jose import JWTError, jwt
    JWT_AVAILABLE = True
except ImportError:
    JWTError = None
    jwt = None
    JWT_AVAILABLE = False
    logger.warning("python-jose nicht installiert. Auth-Endpunkte deaktiviert.")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify API key from header (MVP simple auth)."""
    if settings.api_key:
        if x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@router.post("/token")
async def get_token(x_api_key: Optional[str] = Header(None)):
    """Exchange API key for a JWT token."""
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    token = create_access_token(subject="sebastian")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
    }


@router.get("/check")
async def auth_check(authenticated: bool = Depends(verify_api_key)):
    """Check if authentication is working."""
    return {"status": "authenticated", "user": "sebastian"}