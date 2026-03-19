import asyncio
import os
import sys

# Добавляем текущую директорию в путь импорта
sys.path.append(os.getcwd())

from app.core.db import AsyncSessionLocal
from app.models.agent import Agent
from sqlalchemy.future import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Agent))
        agents = res.scalars().all()
        print("\n" + "="*50)
        print("🔍 DB AGENTS LIST:")
        for a in agents:
            print(f"- Name: {a.name:20} | Model: {a.model}")
        print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
