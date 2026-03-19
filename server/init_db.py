import asyncio
from app.core.db import engine, Base
from sqlalchemy import text

from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.models.agent import Agent
from app.models.skill import Skill, SkillReview
from app.models.task import Task
from app.models.transaction import Transaction
from app.models.model_status import ModelStatus
from app.models.feed_post import FeedPost
from app.models.agent_skill import agent_skill_association  # noqa: F401



# Columns to add if missing: (table, column, sql_type, default)
MIGRATIONS = [
    ("agents", "scenario", "JSON", None),
    ("agents", "schedule_type", "VARCHAR", "'manual'"),
    ("agents", "schedule_cron", "VARCHAR", None),
    ("agents", "schedule_event", "VARCHAR", None),
    ("agents", "avatar_emoji", "VARCHAR(16)", None),
    ("agents", "is_social_active", "BOOLEAN", "0"),
    ("feed_posts", "parent_id", "INTEGER", None),
    ("feed_posts", "reactions", "JSON", "'[]'"),
    ("agents", "memory_summary", "TEXT", None),
    ("agents", "memory_updated_at", "DATETIME", None),
]


async def get_existing_columns(conn, table: str) -> set:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


async def run_migrations():
    async with engine.begin() as conn:
        for table, column, col_type, default in MIGRATIONS:
            existing = await get_existing_columns(conn, table)
            if column not in existing:
                default_clause = f" DEFAULT {default}" if default else ""
                sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
                await conn.execute(text(sql))
                print(f"  + Added column {table}.{column}")
            else:
                print(f"  ✓ Column {table}.{column} already exists")


async def init_db():
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")

    print("Running migrations...")
    await run_migrations()
    print("Migrations done!")


if __name__ == "__main__":
    asyncio.run(init_db())
