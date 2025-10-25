from app.core.config import settings
from pwdlib import PasswordHash
from typing import Any
from datetime import timedelta, datetime, timezone
import jwt

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(subject: str | Any, expires_delta: timedelta):
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, ALGORITHM)
    return encoded_jwt
