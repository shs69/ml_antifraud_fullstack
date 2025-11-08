from sqlmodel import SQLModel, Session, create_engine, select
from app.core.config import settings
from app.models import Users, UserRegister
from app import crud

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
print(settings.SQLALCHEMY_DATABASE_URI)


def init_db(session: Session):
    SQLModel.metadata.create_all(engine)
    user = session.exec(
        select(Users)
    ).first()
    if not user:
        user_in = UserRegister(
            email="test@email.com",
            password="testfdasfsdfas",
            home_adress="г.Москва, улица Маршала Тухачевского, 18",
        )
        user = crud.create_user(session=session, user_create=user_in)
