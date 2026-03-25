import redis.asyncio as redis
from app.core.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)

async def set_nonce(nonce: str, expires_in_seconds: int = 300):
    await redis_client.setex(f"nonce:{nonce}", expires_in_seconds, "1")

async def verify_nonce(nonce: str) -> bool:
    key = f"nonce:{nonce}"
    exists = await redis_client.exists(key)
    if exists:
        await redis_client.delete(key)
        return True
    return False
