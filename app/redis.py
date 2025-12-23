import asyncio
import json

from redis import Redis
from redis import asyncio as aioredis
from sqlmodel import Session

redis_sync = Redis(host="redis", port=6379, db=0, decode_responses=True)

redis_async = aioredis.Redis(host="redis", port=6379, db=0, decode_responses=True)


sse_queue: asyncio.Queue = asyncio.Queue()


async def redis_listener():
    from app.core.db import engine
    from app.crud import delete_transaction, update_transaction

    pubsub = redis_async.pubsub()
    await pubsub.psubscribe("transaction:*")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"]
            data = message["data"]
            transaction_id = channel.split(":")[1]
            with Session(engine) as session:
                if transaction_id == "error":
                    transaction = delete_transaction(
                        session=session, transaction_id=data
                    )
                    await sse_queue.put(f"Deleted: {transaction}")
                else:
                    update_transaction(
                        session=session,
                        transaction_id=transaction_id,
                        update_dict=json.loads(message["data"]),
                    )
                    await sse_queue.put("Updated")
