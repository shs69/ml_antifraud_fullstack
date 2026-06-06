"""initial schema

Revision ID: 20260529_0001
Revises:
Create Date: 2026-05-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "20260529_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("home_adress", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hashed_password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("home_coord", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "transactions",
        sa.Column("shop_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("shop_adress", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_refill", sa.Boolean(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("used_chip", sa.Boolean(), nullable=False),
        sa.Column("used_pin_number", sa.Boolean(), nullable=False),
        sa.Column("online_order", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("shop_coords", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("distance_from_home", sa.Float(), nullable=True),
        sa.Column("distance_from_last_transaction", sa.Float(), nullable=True),
        sa.Column("fraud", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
