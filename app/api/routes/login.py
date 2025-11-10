from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import CurrentUser, SessionDep
from app.api.security import create_access_token
from app.models import Token, UserPublic
from app.core.config import settings
from app import crud
from typing import Annotated
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

router = APIRouter(prefix="/login", tags=['login'])


@router.post("/access-token")
def login_access_token(session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    user = crud.autheticate(
        session=session, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = Token(
        access_token=create_access_token(user.id, access_token_expires)
    )
    return token

@router.post("/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser):
    return current_user