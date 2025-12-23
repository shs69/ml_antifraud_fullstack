import uuid
from typing import Optional, Union

from sqlmodel import Session, asc, desc, func, select

from app.api.security import get_password_hash, verify_password
from app.celery.worker import check_transaction
from app.models import (
    Transaction,
    TransactionDataForCelery,
    TransactionList,
    Transactions,
    UserRegister,
    Users,
)
from app.utils import get_coordinates


def create_user(*, session: Session, user_create: UserRegister) -> Users:
    db_obj = Users.model_validate(
        user_create,
        update={
            "hashed_password": get_password_hash(user_create.password),
            "home_coord": str(get_coordinates(address=user_create.home_adress)),
        },
    )
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


def create_transaction(
    *,
    session: Session,
    transaction_in: Transaction,
    owner_id: uuid.UUID,
    home_coords: str,
) -> Transactions:
    last_transaction = session.exec(
        select(Transactions)
        .where(Transactions.user_id == owner_id)
        .order_by(desc(Transactions.created_at))
        .limit(1)
    ).first()

    db_obj = Transactions.model_validate(transaction_in, update={"user_id": owner_id})

    median = get_median_price_by_owner(session=session, owner_id=owner_id)

    transaction_data = TransactionDataForCelery(
        id=db_obj.id,
        user_home_coords=home_coords,
        last_transaction_address=last_transaction.shop_adress
        if last_transaction
        else "",
        current_shop_address=db_obj.shop_adress,
        ratio_to_median_purchase_price=db_obj.size / median if median else 1,
        repeat_retailer=last_transaction.shop_name == db_obj.shop_name
        if last_transaction
        else False,
        used_chip=db_obj.used_chip,
        used_pin_number=db_obj.used_pin_number,
        online_order=db_obj.online_order,
    )

    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)

    check_transaction.delay(transaction_data.model_dump_json())

    return db_obj


def update_transaction(
    *,
    session: Session,
    transaction_id: uuid.UUID,
    update_dict: dict[str, Union[str, float]],
):
    transaction = session.get(Transactions, transaction_id)
    if not transaction:
        return None

    for key, value in update_dict.items():
        setattr(transaction, key, value)

    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction.fraud


def read_items(
    *, session: Session, owner_id: uuid.UUID, skip: int = 0, limit: int = 25
) -> TransactionList:
    count_statement = (
        select(func.count())
        .select_from(Transactions)
        .where(Transactions.user_id == owner_id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Transactions)
        .where(Transactions.user_id == owner_id)
        .offset(skip)
        .limit(limit)
        .order_by(desc(Transactions.created_at))
    )
    data = session.exec(statement).all()
    fraud_count_statement = (
        select(func.count())
        .select_from(Transactions)
        .where(Transactions.user_id == owner_id, Transactions.fraud == "1")
    )
    fraud_count = session.exec(fraud_count_statement).one()
    return TransactionList(data=data, count=count, fraud_count=fraud_count)


def update_balance(
    *, session: Session, transaction_in: Transactions, current_user_email: str
) -> int | None:
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


def get_median_price_by_owner(
    *, session: Session, owner_id: uuid.UUID
) -> Optional[float]:
    subquery = select(
        func.percentile_cont(0.5).within_group(asc(Transactions.size))
    ).where(Transactions.user_id == owner_id)
    result = session.exec(subquery).first()
    return result or None


def delete_transaction(
    *, session: Session, transaction_id: uuid.UUID
) -> Union[Transaction, str]:
    transaction = session.get(Transactions, transaction_id)
    if not transaction:
        return "Transaction not exist"
    session.delete(transaction)
    session.commit()
    return transaction.model_dump_json()
