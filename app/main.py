from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager

from app.core.db import engine, init_db
from sqlmodel import Session
from app.core.config import settings
from app.api.routes import login, users, transactions
from app.redis import redis_async
from app.crud import update_transaction
from app.api.deps import SessionDep
import asyncio

print("DB:", settings.POSTGRES_SERVER)
print("USER:", settings.POSTGRES_USER)
print(settings.LR_PATH)
print(settings.XGB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(redis_listener())
    with Session(engine) as session:
        init_db(session)
    yield


async def redis_listener():
    pubsub = redis_async.pubsub()
    await pubsub.psubscribe("transaction:*")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"]
            data = message["data"]
            transaction_id = channel.split(":")[1]
            tx_id, is_fraud = data.split("|")
            with Session(engine) as session:
                update_transaction(
                    session=session,
                    transaction_id=transaction_id,
                    fraud_value=is_fraud
                )

app = FastAPI(lifespan=lifespan)


api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(transactions.router)
app.include_router(api_router)
