import asyncio
from sqlalchemy.future import select
from app.core.db import AsyncSessionLocal
from app.models.feed_post import FeedPost

async def check_db():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(FeedPost))
        posts = result.scalars().all()
        print(f"--- Database Check ---")
        print(f"Total posts in DB: {len(posts)}")
        for i, p in enumerate(posts):
            print(f"{i+1}. Agent ID: {p.agent_id} | Type: {p.post_type}")
            print(f"   Content: {p.content[:100]}...")
        print(f"----------------------")

if __name__ == "__main__":
    asyncio.run(check_db())
