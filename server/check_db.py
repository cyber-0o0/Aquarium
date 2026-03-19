
import asyncio
from app.core.db import AsyncSessionLocal
from app.models.user import User
from sqlalchemy.future import select

async def check_user(tg_id: str):
    print(f"Checking user with telegram_id: {tg_id}")
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = res.scalars().first()
        if user:
            print(f"User found: {user.username or 'No Username'}")
            print(f"Plan: {user.plan}")
            print(f"Wallet: {user.wallet_address or 'NOT SET'}")
        else:
            print("❌ User not found in database.")

if __name__ == "__main__":
    import sys
    # Using the ID from the logs if available, but let's try to find any user first
    asyncio.run(check_user("6665780")) # This is a placeholder, I'll try to get it from context if possible
    # Actually wait, the logs showed: '7e9d01c7-b668-47c9-9502-42d7d925b585' as user_id
    # Let's check by UUID.
