from sqlmodel import Session, select, func

from app.models import Users, UserCreate, UserUpdate, Transaction, Transactions, TransactionList
from app.api.security import get_password_hash, verify_password
import uuid


def create_user(*, session: Session, user_create: UserCreate) -> Users:
    db_obj = Users.model_validate(user_create, update={
                                  "hashed_password": get_password_hash(user_create.password)})
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


def create_transaction(*, session: Session, transaction_in: Transaction, owner_id: uuid.UUID) -> Transactions:
    db_obj = Transactions.model_validate(
        transaction_in, update={"user_id": owner_id})
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
