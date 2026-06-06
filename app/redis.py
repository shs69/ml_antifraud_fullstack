from redis import Redis, asyncio as aioredis
from sqlmodel import Session
import json
import asyncio

redis_sync = Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)

redis_async = aioredis.Redis(
    host="127.0.0.1", port=6379, db=0, decode_responses=True)


sse_queue: asyncio.Queue = asyncio.Queue()


async def redis_listener():
    from app.crud import update_transaction
    from app.core.db import engine

    pubsub = redis_async.pubsub()
    await pubsub.psubscribe("transaction:*")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"]
            data = message["data"]
            transaction_id = channel.split(":")[1]

            with Session(engine) as session:
                update_transaction(
                    session=session,
                    transaction_id=transaction_id,
                    update_dict=json.loads(message['data']))

            await sse_queue.put(data)
