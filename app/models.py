import uuid

from datetime import datetime
from pydantic import EmailStr
from typing import Sequence
from sqlmodel import Field, Relationship, SQLModel


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True,
                            max_length=255, nullable=False)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    home_adress: str = Field(nullable=False)
    balance: int = 10000


class UserPublic(UserBase):
    id: uuid.UUID


class UserUpdate(SQLModel):
    full_name: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=255)
    balance: int | None = Field(default=None)


class Users(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    home_coord: str
    transactions: list["Transactions"] = Relationship(
        back_populates="owner", cascade_delete=True)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)
    home_adress: str = Field(nullable=False)


class Transaction(SQLModel):
    shop_name: str = Field(max_length=255, nullable=False)
    shop_adress: str = Field(nullable=False)
    is_refill: bool = Field(nullable=False)
    size: int = Field(nullable=False)
    used_chip: bool
    used_pin_number: bool
    online_order: bool


class Transactions(Transaction, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4,
                          primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    user_id: uuid.UUID = Field(
        foreign_key="users.id", nullable=False, ondelete="CASCADE")
    owner: Users | None = Relationship(back_populates="transactions")
    shop_coords: str = Field(nullable=False)
    distance_from_home: float | None = Field(nullable=True, default=None)
    distance_from_last_transaction: float | None = Field(
        nullable=True, default=None)


class TransactionPublic(Transaction):
    id: uuid.UUID
    created_at: datetime


class TransactionList(SQLModel):
    data: Sequence[Transactions]
    count: int


class TransactionPublicList(SQLModel):
    data: Sequence[TransactionPublic]
    count: int

# class TransactionCreate(TransactionBase):
#     pass

# class TransactionPublic(TransactionBase):
#     pass


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None
