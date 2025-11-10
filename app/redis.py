from redis import Redis, asyncio as aioredis

redis_sync = Redis(host="localhost", port=6379, db=0, decode_responses=True)

redis_async = aioredis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
