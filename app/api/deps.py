from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlmodel import Session
from app.core.db import engine
from app.core.config import settings
from app.api.security import ALGORITHM
from app.models import TokenPayload, Users
import jwt

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl='/login/access-token')


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]
print(TokenDep)


def get_current_user(session: SessionDep, token: TokenDep) -> Users:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, ALGORITHM)
        token_data = TokenPayload(**payload)
    except (jwt.InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials"
        )
    user = session.get(Users, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


CurrentUser = Annotated[Users, Depends(get_current_user)]
