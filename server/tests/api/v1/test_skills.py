"""
Tests for /api/v1/skills
Covers: list/filter, get, install, uninstall, reviews, publish.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill


async def insert_skill(db: AsyncSession, slug: str, category: str = "search", status: str = "approved") -> Skill:
    skill = Skill(
        name=slug.replace("-", " ").title(),
        slug=slug,
        description="Test skill",
        category=category,
        manifest={
            "tool_name": slug.replace("-", "_"),
            "description": "test",
            "parameters": {},
            "required": [],
            "implementation": "builtin",
        },
        review_status=status,
        author_id="system",
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


# ── List & Filter ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_skills_empty(client: AsyncClient):
    resp = await client.get("/api/v1/skills")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_skills_returns_approved_only(client: AsyncClient, db_session: AsyncSession):
    await insert_skill(db_session, "approved-skill", status="approved")
    await insert_skill(db_session, "pending-skill", status="pending")

    resp = await client.get("/api/v1/skills")
    slugs = [s["slug"] for s in resp.json()]
    assert "approved-skill" in slugs
    assert "pending-skill" not in slugs


@pytest.mark.asyncio
async def test_list_skills_filter_by_category(client: AsyncClient, db_session: AsyncSession):
    await insert_skill(db_session, "ton-tool", category="ton")
    await insert_skill(db_session, "defi-tool", category="defi")

    resp = await client.get("/api/v1/skills?category=ton")
    slugs = [s["slug"] for s in resp.json()]
    assert "ton-tool" in slugs
    assert "defi-tool" not in slugs


@pytest.mark.asyncio
async def test_list_skills_search(client: AsyncClient, db_session: AsyncSession):
    await insert_skill(db_session, "web-search-skill")
    await insert_skill(db_session, "ton-balance-skill")

    resp = await client.get("/api/v1/skills?search=web")
    slugs = [s["slug"] for s in resp.json()]
    assert "web-search-skill" in slugs
    assert "ton-balance-skill" not in slugs


@pytest.mark.asyncio
async def test_get_skill_by_id(client: AsyncClient, skill_id: str):
    resp = await client.get(f"/api/v1/skills/{skill_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == skill_id


@pytest.mark.asyncio
async def test_get_skill_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/skills/nonexistent")
    assert resp.status_code == 404


# ── Install / Uninstall ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_install_skill(client: AsyncClient, headers: dict, agent_id: str, skill_id: str):
    resp = await client.post(
        "/api/v1/skills/install",
        json={"agent_id": agent_id, "skill_id": skill_id},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "installed"


@pytest.mark.asyncio
async def test_install_skill_idempotent(client: AsyncClient, headers: dict, agent_id: str, skill_id: str):
    payload = {"agent_id": agent_id, "skill_id": skill_id}
    await client.post("/api/v1/skills/install", json=payload, headers=headers)
    resp = await client.post("/api/v1/skills/install", json=payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_installed"


@pytest.mark.asyncio
async def test_install_increments_installs_counter(client: AsyncClient, headers: dict, agent_id: str, skill_id: str):
    before = (await client.get(f"/api/v1/skills/{skill_id}")).json()["installs"]
    await client.post("/api/v1/skills/install", json={"agent_id": agent_id, "skill_id": skill_id}, headers=headers)
    after = (await client.get(f"/api/v1/skills/{skill_id}")).json()["installs"]
    assert after == before + 1


@pytest.mark.asyncio
async def test_install_wrong_owner(client: AsyncClient, agent_id: str, skill_id: str):
    from tests.conftest import get_token_for_wallet
    other = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_NOT_OWNER')}"}
    resp = await client.post(
        "/api/v1/skills/install",
        json={"agent_id": agent_id, "skill_id": skill_id},
        headers=other,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_uninstall_skill(client: AsyncClient, headers: dict, agent_id: str, skill_id: str):
    await client.post("/api/v1/skills/install", json={"agent_id": agent_id, "skill_id": skill_id}, headers=headers)
    resp = await client.request(
        "DELETE",
        "/api/v1/skills/uninstall",
        json={"agent_id": agent_id, "skill_id": skill_id},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "uninstalled"


@pytest.mark.asyncio
async def test_uninstall_not_installed(client: AsyncClient, headers: dict, agent_id: str, skill_id: str):
    resp = await client.request(
        "DELETE",
        "/api/v1/skills/uninstall",
        json={"agent_id": agent_id, "skill_id": skill_id},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_agent_skills(client: AsyncClient, headers: dict, agent_id: str, skill_id: str):
    await client.post("/api/v1/skills/install", json={"agent_id": agent_id, "skill_id": skill_id}, headers=headers)
    resp = await client.get(f"/api/v1/skills/agent/{agent_id}", headers=headers)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert skill_id in ids


# ── Reviews ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_review(client: AsyncClient, headers: dict, skill_id: str):
    resp = await client.post(
        f"/api/v1/skills/{skill_id}/reviews",
        json={"rating": 5, "comment": "Great skill!"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rating"] == 5
    assert data["comment"] == "Great skill!"


@pytest.mark.asyncio
async def test_review_updates_skill_rating(client: AsyncClient, headers: dict, skill_id: str):
    from tests.conftest import get_token_for_wallet

    h1 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_R1')}"}
    h2 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_R2')}"}

    await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 4}, headers=h1)
    await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 2}, headers=h2)

    skill = (await client.get(f"/api/v1/skills/{skill_id}")).json()
    assert skill["rating"] == 3.0  # (4+2)/2


@pytest.mark.asyncio
async def test_duplicate_review_rejected(client: AsyncClient, headers: dict, skill_id: str):
    await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 5}, headers=headers)
    resp = await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 3}, headers=headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_review_invalid_rating(client: AsyncClient, headers: dict, skill_id: str):
    resp = await client.post(
        f"/api/v1/skills/{skill_id}/reviews",
        json={"rating": 10},
        headers=headers,
    )
    assert resp.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_get_reviews(client: AsyncClient, headers: dict, skill_id: str):
    await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 4, "comment": "Good"}, headers=headers)
    resp = await client.get(f"/api/v1/skills/{skill_id}/reviews")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Publish ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_skill(client: AsyncClient, headers: dict):
    resp = await client.post(
        "/api/v1/skills/publish",
        json={
            "name": "My Custom Tool",
            "slug": "my-custom-tool",
            "description": "Does stuff",
            "category": "utility",
            "manifest": {
                "tool_name": "my_custom_tool",
                "description": "Does stuff",
                "parameters": {},
                "required": [],
                "implementation": "http",
                "url": "https://example.com/tool",
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["review_status"] == "pending"
    assert data["slug"] == "my-custom-tool"


@pytest.mark.asyncio
async def test_publish_duplicate_slug(client: AsyncClient, headers: dict):
    payload = {
        "name": "Tool",
        "slug": "duplicate-slug",
        "description": "x",
        "category": "utility",
        "manifest": {"tool_name": "t", "description": "t", "parameters": {}, "required": [], "implementation": "builtin"},
    }
    await client.post("/api/v1/skills/publish", json=payload, headers=headers)
    resp = await client.post("/api/v1/skills/publish", json=payload, headers=headers)
    assert resp.status_code == 409
