"""
Миграция: добавляет колонку tg_thread_id в таблицу agents.
Запустить один раз: python -m app.migrations.add_tg_thread_id
"""
import asyncio
from sqlalchemy import text
from app.core.db import engine


async def migrate():
    async with engine.begin() as conn:
        # Проверяем есть ли уже колонка
        try:
            await conn.execute(text("SELECT tg_thread_id FROM agents LIMIT 1"))
            print("OK: column tg_thread_id already exists.")
            return
        except Exception:
            pass

        await conn.execute(
            text("ALTER TABLE agents ADD COLUMN tg_thread_id INTEGER DEFAULT NULL")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_agents_tg_thread_id ON agents (tg_thread_id)")
        )
        print("OK: column tg_thread_id added to agents table.")


if __name__ == "__main__":
    asyncio.run(migrate())
