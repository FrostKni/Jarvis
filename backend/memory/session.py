import json
import redis.asyncio as aioredis
from backend.config import get_settings

settings = get_settings()

SESSION_TTL = 3600  # 1 hour
MAX_TURNS = 20


class SessionCache:
    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def connect(self):
        self._redis = await aioredis.from_url(settings.redis_url, decode_responses=True)

    async def close(self):
        if self._redis:
            await self._redis.aclose()

    async def add_turn(self, session_id: str, role: str, content: str):
        key = f"session:{session_id}:turns"
        turn = json.dumps({"role": role, "content": content})
        await self._redis.rpush(key, turn)
        await self._redis.ltrim(key, -MAX_TURNS, -1)
        await self._redis.expire(key, SESSION_TTL)

    async def get_turns(self, session_id: str) -> list[dict]:
        key = f"session:{session_id}:turns"
        turns = await self._redis.lrange(key, 0, -1)
        return [json.loads(t) for t in turns]

    async def publish_event(self, channel: str, event: dict):
        await self._redis.publish(channel, json.dumps(event))

    async def subscribe(self, channel: str):
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    async def cache_set(self, key: str, value: str, ttl: int = 300):
        await self._redis.setex(key, ttl, value)

    async def cache_get(self, key: str) -> str | None:
        return await self._redis.get(key)
