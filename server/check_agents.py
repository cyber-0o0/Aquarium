
import asyncio
from app.core.db import AsyncSessionLocal
from app.models.agent import Agent
from sqlalchemy.future import select

async def check_agent_prompt():
    print("Checking agent naming and prompts...")
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Agent))
        agents = res.scalars().all()
        for a in agents:
            print(f"[{a.id[:8]}] - Name: {a.name}")
            print(f"Model: {a.model}")
            print(f"Prompt (first 100): {a.system_prompt[:100] if a.system_prompt else 'None'}")
            print(f"User ID: {a.user_id}")
            print("---")

if __name__ == "__main__":
    asyncio.run(check_agent_prompt())
