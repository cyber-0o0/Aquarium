"""
Shared fixtures for all tests.
Uses in-memory SQLite — fast, isolated, no external deps.
"""
import asyncio
import json
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from urllib.parse import urlencode

from app.main import app
from app.core.db import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="function", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Reusable auth helpers ──────────────────────────────────────────────────────

async def get_token_for_wallet(client: AsyncClient, wallet: str) -> str:
    nonce_resp = await client.get("/api/v1/auth/nonce")
    nonce = nonce_resp.json()["nonce"]
    resp = await client.post(
        "/api/v1/auth/ton-connect",
        json={"wallet_address": wallet, "signature": "sig", "nonce": nonce},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def get_token_for_tg(client: AsyncClient, tg_id: int = 111222, username: str = "testuser") -> str:
    user_data = json.dumps({"id": tg_id, "username": username})
    init_data = urlencode({"user": user_data, "hash": "fake_hash"})
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def token(client: AsyncClient) -> str:
    return await get_token_for_wallet(client, "EQ_FIXTURE_WALLET")


@pytest.fixture
async def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def agent_id(client: AsyncClient, headers: dict) -> str:
    """Creates a default agent and returns its id."""
    resp = await client.post(
        "/api/v1/agents",
        json={
            "name": "Fixture Agent",
            "model": "gpt-4o",
            "system_prompt": "You are helpful.",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.fixture
async def skill_id(client: AsyncClient, db_session: AsyncSession) -> str:
    """Inserts a free approved skill and returns its id."""
    from app.models.skill import Skill
    skill = Skill(
        name="Test Web Search",
        slug="test-web-search",
        description="Search the web",
        category="search",
        manifest={
            "tool_name": "web_search",
            "description": "Search the web",
            "parameters": {"query": {"type": "string", "description": "query"}},
            "required": ["query"],
            "implementation": "builtin",
        },
        review_status="approved",
        author_id="system",
    )
    db_session.add(skill)
    await db_session.commit()
    await db_session.refresh(skill)
    return skill.id
