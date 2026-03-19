"""
Tests for /api/v1/users
Covers: get me, update me, unauthenticated access.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, headers: dict):
    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["wallet_address"] == "EQ_FIXTURE_WALLET"
    assert "id" in data
    assert "plan" in data


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    # deps.py raises 403 for malformed/invalid JWT (standard jose behaviour)
    resp = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_me_plan(client: AsyncClient, headers: dict):
    resp = await client.patch("/api/v1/users/me", json={"plan": "premium"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["plan"] == "premium"


@pytest.mark.asyncio
async def test_update_me_metadata(client: AsyncClient, headers: dict):
    meta = {"theme": "dark", "lang": "ru"}
    resp = await client.patch("/api/v1/users/me", json={"user_metadata": meta}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_metadata"]["theme"] == "dark"
    assert data["user_metadata"]["lang"] == "ru"


@pytest.mark.asyncio
async def test_update_me_partial(client: AsyncClient, headers: dict):
    """Partial update must not overwrite unrelated fields."""
    await client.patch("/api/v1/users/me", json={"plan": "premium"}, headers=headers)
    resp = await client.patch("/api/v1/users/me", json={"user_metadata": {"x": 1}}, headers=headers)
    assert resp.status_code == 200
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    assert me["plan"] == "premium"
