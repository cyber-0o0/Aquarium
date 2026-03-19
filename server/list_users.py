
import asyncio
from app.core.db import AsyncSessionLocal
from app.models.user import User
from sqlalchemy.future import select

async def list_users():
    print("Listing top 10 users and wallet addresses...")
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User).limit(10))
        users = res.scalars().all()
        for u in users:
            print(f"[{u.id[:8]}] @{u.username or 'N/A'} - Wallet: {u.wallet_address or '---'}")

if __name__ == "__main__":
    asyncio.run(list_users())
