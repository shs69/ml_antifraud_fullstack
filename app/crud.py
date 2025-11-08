from sqlmodel import Session, select, func, desc

from app.models import Users, UserRegister, Transaction, Transactions, TransactionList
from app.api.security import get_password_hash, verify_password
from app.utils import calculate_transaction_distances, get_coordinates, str_coord_to_tuple
from typing import Tuple
import uuid


def create_user(*, session: Session, user_create: UserRegister) -> Users:
    db_obj = Users.model_validate(user_create, update={
                                  "hashed_password": get_password_hash(user_create.password),
                                  "home_coord": str(get_coordinates(adress=user_create.home_adress))})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_user_by_email(*, session: Session, email: str) -> Users | None:
    statement = select(Users).where(Users.email == email)
    session_user = session.exec(statement).first()
    return session_user


def autheticate(*, session: Session, email: str, password: str) -> Users | None:
    user = get_user_by_email(session=session, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_transaction(*, session: Session, transaction_in: Transaction, owner_id: uuid.UUID, home_coords: str) -> Transactions:
    last_transaction = session.exec(
        select(Transactions)
        .where(Transactions.user_id == owner_id)
        .order_by(desc(Transactions.created_at))
        .limit(1)
    ).first()

    shop_coords, \
        distance_from_home, \
        distance_from_last_transaction = await calculate_transaction_distances(
            transaction_in=transaction_in,
            home_coords=str_coord_to_tuple(coord_string=home_coords),
            last_transaction=last_transaction
        )

    db_obj = Transactions.model_validate(
        transaction_in, update={"user_id": owner_id, "shop_coords": str(shop_coords),
                                "distance_from_home": distance_from_home,
                                "distance_from_last_transaction": distance_from_last_transaction})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def read_items(*, session: Session, owner_id: uuid.UUID, skip: int = 0, limit: int = 25) -> TransactionList:
    count_statement = select(func.count()).select_from(
        Transactions).where(Transactions.user_id == owner_id)
    count = session.exec(count_statement).one()
    statement = select(Transactions).where(
        Transactions.user_id == owner_id).offset(skip).limit(limit)
    data = session.exec(statement).all()
    return TransactionList(data=data, count=count)


def update_balance(*, session: Session, transaction_in: Transactions, current_user_email: str) -> int | None:
    current_user = get_user_by_email(session=session, email=current_user_email)
    if not current_user:
        return None

    if transaction_in.is_refill:
        current_user.balance += transaction_in.size
    else:
        current_user.balance -= transaction_in.size

    current_user.sqlmodel_update(current_user)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user.balance
