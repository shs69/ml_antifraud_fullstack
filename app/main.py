from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
import asyncio

from app.core.db import engine, init_db
from app.core.config import settings
from app.api.routes import login, users, transactions
from app.redis import redis_listener


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(redis_listener())
    with Session(engine) as session:
        init_db(session)
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(transactions.router)
app.include_router(api_router)
