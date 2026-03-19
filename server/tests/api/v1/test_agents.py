"""
Tests for /api/v1/agents
Covers: CRUD, ownership isolation, run endpoint (mocked LLM), task history.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


AGENT_PAYLOAD = {
    "name": "My Agent",
    "model": "gpt-4o",
    "system_prompt": "You are a helpful assistant.",
    "temperature": 0.7,
    "max_tokens": 512,
}


# ── CRUD ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_agent(client: AsyncClient, headers: dict):
    resp = await client.post("/api/v1/agents", json=AGENT_PAYLOAD, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Agent"
    assert data["status"] == "idle"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_agents_empty(client: AsyncClient, headers: dict):
    resp = await client.get("/api/v1/agents", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_agents_returns_own_only(client: AsyncClient):
    from tests.conftest import get_token_for_wallet

    h1 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_USER_A')}"}
    h2 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_USER_B')}"}

    await client.post("/api/v1/agents", json=AGENT_PAYLOAD, headers=h1)
    await client.post("/api/v1/agents", json={**AGENT_PAYLOAD, "name": "B Agent"}, headers=h2)

    agents_a = (await client.get("/api/v1/agents", headers=h1)).json()
    agents_b = (await client.get("/api/v1/agents", headers=h2)).json()

    assert len(agents_a) == 1
    assert len(agents_b) == 1
    assert agents_a[0]["name"] == "My Agent"
    assert agents_b[0]["name"] == "B Agent"


@pytest.mark.asyncio
async def test_get_agent(client: AsyncClient, headers: dict, agent_id: str):
    resp = await client.get(f"/api/v1/agents/{agent_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == agent_id


@pytest.mark.asyncio
async def test_get_agent_not_found(client: AsyncClient, headers: dict):
    resp = await client.get("/api/v1/agents/nonexistent-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_agent_wrong_owner(client: AsyncClient, agent_id: str):
    from tests.conftest import get_token_for_wallet
    other_headers = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_OTHER_OWNER')}"}
    resp = await client.get(f"/api/v1/agents/{agent_id}", headers=other_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_agent(client: AsyncClient, headers: dict, agent_id: str):
    resp = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Renamed", "temperature": 0.2},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Renamed"
    assert data["temperature"] == 0.2


@pytest.mark.asyncio
async def test_delete_agent(client: AsyncClient, headers: dict, agent_id: str):
    del_resp = await client.delete(f"/api/v1/agents/{agent_id}", headers=headers)
    assert del_resp.status_code == 200
    get_resp = await client.get(f"/api/v1/agents/{agent_id}", headers=headers)
    assert get_resp.status_code == 404


# ── Run ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_agent_no_skills(client: AsyncClient, headers: dict, agent_id: str):
    """Agent with no skills → plain LLM call (mocked)."""
    mock_result = {
        "output": "Hello from mock LLM",
        "tokens_used": 42,
        "tools_used": [],
        "status": "success",
    }
    with patch(
        "app.api.v1.endpoints.agents.execute_agent_task",
        new=AsyncMock(return_value=mock_result),
    ):
        resp = await client.post(
            f"/api/v1/agents/{agent_id}/run",
            json={"input": "Say hello"},
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["output"] == "Hello from mock LLM"
    assert data["status"] == "success"
    assert "task_id" in data


@pytest.mark.asyncio
async def test_run_agent_with_tools_used(client: AsyncClient, headers: dict, agent_id: str):
    mock_result = {
        "output": "TON price is $5.10",
        "tokens_used": 100,
        "tools_used": ["crypto_price"],
        "status": "success",
    }
    with patch(
        "app.api.v1.endpoints.agents.execute_agent_task",
        new=AsyncMock(return_value=mock_result),
    ):
        resp = await client.post(
            f"/api/v1/agents/{agent_id}/run",
            json={"input": "What is the price of TON?"},
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()["tools_used"] == ["crypto_price"]


@pytest.mark.asyncio
async def test_run_agent_failure_recorded(client: AsyncClient, headers: dict, agent_id: str):
    with patch(
        "app.api.v1.endpoints.agents.execute_agent_task",
        new=AsyncMock(side_effect=Exception("LLM timeout")),
    ):
        resp = await client.post(
            f"/api/v1/agents/{agent_id}/run",
            json={"input": "fail me"},
            headers=headers,
        )
    assert resp.status_code == 500
    assert "LLM timeout" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_run_agent_not_found(client: AsyncClient, headers: dict):
    resp = await client.post(
        "/api/v1/agents/ghost-id/run",
        json={"input": "hello"},
        headers=headers,
    )
    assert resp.status_code == 404


# ── Task history ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_task_history_saved_after_run(client: AsyncClient, headers: dict, agent_id: str):
    mock_result = {"output": "done", "tokens_used": 10, "tools_used": [], "status": "success"}
    with patch(
        "app.api.v1.endpoints.agents.execute_agent_task",
        new=AsyncMock(return_value=mock_result),
    ):
        await client.post(f"/api/v1/agents/{agent_id}/run", json={"input": "go"}, headers=headers)

    resp = await client.get(f"/api/v1/agents/{agent_id}/tasks", headers=headers)
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "success"


@pytest.mark.asyncio
async def test_task_history_multiple_runs(client: AsyncClient, headers: dict, agent_id: str):
    mock_result = {"output": "ok", "tokens_used": 5, "tools_used": [], "status": "success"}
    with patch("app.api.v1.endpoints.agents.execute_agent_task", new=AsyncMock(return_value=mock_result)):
        for _ in range(3):
            await client.post(f"/api/v1/agents/{agent_id}/run", json={"input": "ping"}, headers=headers)

    tasks = (await client.get(f"/api/v1/agents/{agent_id}/tasks", headers=headers)).json()
    assert len(tasks) == 3
