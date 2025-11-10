from sqlmodel import Session, select, func, desc, text

from app.models import Users, UserRegister, Transaction, Transactions, TransactionList, TransactionDataForModel
from app.api.security import get_password_hash, verify_password
from app.utils import calculate_transaction_distances, get_coordinates, str_coord_to_tuple
from app.worker import check_transaction
from typing import Optional
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
    
    print(last_transaction)
    print(distance_from_last_transaction)

    db_obj = Transactions.model_validate(
        transaction_in, update={"user_id": owner_id, "shop_coords": str(shop_coords),
                                "distance_from_home": distance_from_home,
                                "distance_from_last_transaction": distance_from_last_transaction,
                                "fraud": "pending"})
    
    median = get_median_price_by_owner(session=session, owner_id=owner_id)

    transaction_data = TransactionDataForModel(
        id=db_obj.id,
        distance_from_home=db_obj.distance_from_home,
        distance_from_last_transaction=db_obj.distance_from_last_transaction,
        ratio_to_median_purchase_price=db_obj.size / median if median else 1, 
        repeat_retailer=last_transaction.shop_name == db_obj.shop_name if last_transaction else False,
        used_chip=db_obj.used_chip,
        used_pin_number=db_obj.used_pin_number,
        online_order=db_obj.online_order
        )

    check_transaction.delay(transaction_data.model_dump_json())

    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_transaction(*, session: Session, transaction_id: uuid.UUID, fraud_value: str):
    transaction = session.get(Transactions, transaction_id)
    if not transaction:
        return None
    transaction.fraud = fraud_value
    transaction.sqlmodel_update(transaction)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction.fraud


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


def get_median_price_by_owner(session: Session, owner_id: uuid.UUID) -> Optional[float]:
    sql = text("""
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY size) AS median_price
    FROM transactions
    WHERE user_id = :owner_id
    """)
    result = session.execute(sql, {"owner_id": owner_id}).first()
    if not result:
        return None
    return result[0]
