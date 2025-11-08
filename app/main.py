from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager

from app.core.db import engine, init_db
from sqlmodel import Session
from app.core.config import settings
from app.api.routes import login, users, transactions

print("DB:", settings.POSTGRES_SERVER)
print("USER:", settings.POSTGRES_USER)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with Session(engine) as session:
        init_db(session)
    yield

app = FastAPI(lifespan=lifespan)


api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(transactions.router)
app.include_router(api_router)
