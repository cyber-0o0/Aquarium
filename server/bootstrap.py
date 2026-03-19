#!/usr/bin/env python
"""
Bootstrap script — creates tables and seeds all built-in skills.
Run once after cloning or after wiping the database:

    python bootstrap.py

Equivalent to:
    python init_db.py
    python -m app.seeds.skills
"""
import asyncio


async def main():
    print("=" * 50)
    print("AiHubTon — Database Bootstrap")
    print("=" * 50)

    # 1. Create all tables
    print("\n[1/2] Creating database tables...")
    from app.core.db import engine, Base
    from app.models.user import User                    # noqa
    from app.models.user_api_key import UserApiKey      # noqa
    from app.models.agent import Agent                  # noqa
    from app.models.skill import Skill, SkillReview     # noqa
    from app.models.task import Task                    # noqa
    from app.models.transaction import Transaction      # noqa
    from app.models.agent_skill import agent_skill_association  # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("    ✅ Tables created")

    # 2. Seed skills
    print("\n[2/2] Seeding built-in skills...")
    from app.seeds.skills import seed
    await seed()

    print("\n" + "=" * 50)
    print("Bootstrap complete! Start the server with:")
    print("  uvicorn app.main:app --reload")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
