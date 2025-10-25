from app.models import UserRegister, UserPublic, UserCreate
from app.api.deps import SessionDep
from app import crud
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/reg", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister):
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists"
        )
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    return user
