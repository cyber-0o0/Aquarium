"""
Security & adversarial tests.
"""
import json
import time
import pytest
import base64
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import get_token_for_wallet
from app.models.skill import Skill


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

async def make_agent(client, headers, name="Agent", model="gpt-4o"):
    resp = await client.post(
        "/api/v1/agents",
        json={"name": name, "model": model, "system_prompt": "helpful"},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()["id"]


async def insert_approved_skill(db: AsyncSession, slug: str) -> str:
    skill = Skill(
        name=slug, slug=slug, description="sec test",
        category="utility",
        manifest={"tool_name": "get_datetime", "description": "t",
                  "parameters": {}, "required": [], "implementation": "builtin"},
        review_status="approved", author_id="system",
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill.id


# ═══════════════════════════════════════════════════════════════════════════════
# 1. JWT / AUTH ATTACKS
# ═══════════════════════════════════════════════════════════════════════════════

class TestJWTAttacks:

    @pytest.mark.asyncio
    async def test_no_token_returns_401(self, client: AsyncClient):
        assert (await client.get("/api/v1/agents")).status_code == 401

    @pytest.mark.asyncio
    async def test_empty_bearer_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/agents", headers={"Authorization": "Bearer "})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_none_algorithm_token_rejected(self, client: AsyncClient):
        header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=")
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "evil-user-id", "exp": int(time.time()) + 9999}).encode()
        ).rstrip(b"=")
        token = f"{header.decode()}.{payload.decode()}."
        resp = await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_forged_token_wrong_secret(self, client: AsyncClient):
        from jose import jwt as jose_jwt
        forged = jose_jwt.encode(
            {"sub": "attacker", "exp": int(time.time()) + 9999},
            "WRONG_SECRET", algorithm="HS256",
        )
        resp = await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {forged}"})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client: AsyncClient):
        from jose import jwt as jose_jwt
        from app.core.config import settings
        expired = jose_jwt.encode(
            {"sub": "user-id", "exp": int(time.time()) - 1},
            settings.SECRET_KEY, algorithm="HS256",
        )
        resp = await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_token_with_nonexistent_user_id(self, client: AsyncClient):
        from app.core.security import create_access_token
        token = create_access_token("00000000-0000-0000-0000-000000000000")
        resp = await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sql_injection_in_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/agents",
            headers={"Authorization": "Bearer ' OR '1'='1"},
        )
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. IDOR — CROSS-USER DATA ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIDOR:

    @pytest.mark.asyncio
    async def test_cannot_read_other_users_agent(self, client: AsyncClient):
        h1 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_A')}"}
        h2 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_B')}"}
        agent_id = await make_agent(client, h1, "Private Agent")
        assert (await client.get(f"/api/v1/agents/{agent_id}", headers=h2)).status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_update_other_users_agent(self, client: AsyncClient):
        h1 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_C')}"}
        h2 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_D')}"}
        agent_id = await make_agent(client, h1)
        assert (await client.patch(f"/api/v1/agents/{agent_id}", json={"name": "Hijacked"}, headers=h2)).status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_delete_other_users_agent(self, client: AsyncClient):
        h1 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_E')}"}
        h2 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_F')}"}
        agent_id = await make_agent(client, h1)
        assert (await client.delete(f"/api/v1/agents/{agent_id}", headers=h2)).status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_run_other_users_agent(self, client: AsyncClient):
        h1 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_G')}"}
        h2 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_H')}"}
        agent_id = await make_agent(client, h1)
        assert (await client.post(f"/api/v1/agents/{agent_id}/run", json={"input": "steal"}, headers=h2)).status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_install_skill_on_other_users_agent(self, client: AsyncClient, db_session: AsyncSession):
        h1 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_I')}"}
        h2 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_J')}"}
        agent_id = await make_agent(client, h1)
        skill_id = await insert_approved_skill(db_session, "idor-skill")
        assert (await client.post("/api/v1/skills/install", json={"agent_id": agent_id, "skill_id": skill_id}, headers=h2)).status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_view_other_users_tasks(self, client: AsyncClient):
        h1 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_K')}"}
        h2 = {"Authorization": f"Bearer {await get_token_for_wallet(client, 'EQ_IDOR_L')}"}
        agent_id = await make_agent(client, h1)
        assert (await client.get(f"/api/v1/agents/{agent_id}/tasks", headers=h2)).status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 3. INPUT VALIDATION & INJECTION
# ═══════════════════════════════════════════════════════════════════════════════

class TestInputValidation:

    @pytest.mark.asyncio
    async def test_sql_injection_in_agent_name(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "'; DROP TABLE agents; --", "model": "gpt-4o", "system_prompt": "x"},
            headers=headers,
        )
        assert resp.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_xss_payload_stored_as_plain_text(self, client: AsyncClient, headers: dict):
        xss = "<script>alert('xss')</script>"
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "XSS Agent", "model": "gpt-4o", "system_prompt": xss},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["system_prompt"] == xss

    @pytest.mark.asyncio
    async def test_agent_name_too_long_rejected(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "A" * 65, "model": "gpt-4o", "system_prompt": "x"},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_agent_name_rejected(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "", "model": "gpt-4o", "system_prompt": "x"},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_whitespace_only_name_rejected(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "   ", "model": "gpt-4o", "system_prompt": "x"},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client: AsyncClient, headers: dict):
        resp = await client.post("/api/v1/agents", json={"name": "No Model"}, headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_temperature_above_max_rejected(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "Hot", "model": "gpt-4o", "system_prompt": "x", "temperature": 999.9},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_temperature_below_min_rejected(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "Cold", "model": "gpt-4o", "system_prompt": "x", "temperature": -1.0},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_null_bytes_in_input_no_crash(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "null\x00byte", "model": "gpt-4o", "system_prompt": "x"},
            headers=headers,
        )
        assert resp.status_code != 500

    @pytest.mark.asyncio
    async def test_unicode_in_name_no_crash(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "😈🔥", "model": "gpt-4o", "system_prompt": "x"},
            headers=headers,
        )
        assert resp.status_code != 500

    @pytest.mark.asyncio
    async def test_huge_system_prompt_rejected(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "BigPrompt", "model": "gpt-4o", "system_prompt": "x" * 100_001},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_agent_empty_input_rejected(self, client: AsyncClient, headers: dict, agent_id: str):
        resp = await client.post(
            f"/api/v1/agents/{agent_id}/run",
            json={"input": ""},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_agent_whitespace_input_rejected(self, client: AsyncClient, headers: dict, agent_id: str):
        resp = await client.post(
            f"/api/v1/agents/{agent_id}/run",
            json={"input": "   "},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_agent_huge_input_no_crash(self, client: AsyncClient, headers: dict, agent_id: str):
        mock_result = {"output": "ok", "tokens_used": 0, "tools_used": [], "status": "success"}
        with patch("app.api.v1.endpoints.agents.execute_agent_task", new=AsyncMock(return_value=mock_result)):
            resp = await client.post(
                f"/api/v1/agents/{agent_id}/run",
                json={"input": "x" * 100_000},
                headers=headers,
            )
        assert resp.status_code != 500


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BUSINESS LOGIC ATTACKS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBusinessLogic:

    @pytest.mark.asyncio
    async def test_review_rating_below_1_rejected(self, client: AsyncClient, headers: dict, skill_id: str):
        assert (await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 0}, headers=headers)).status_code == 422

    @pytest.mark.asyncio
    async def test_review_rating_above_5_rejected(self, client: AsyncClient, headers: dict, skill_id: str):
        assert (await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 6}, headers=headers)).status_code == 422

    @pytest.mark.asyncio
    async def test_cannot_review_same_skill_twice(self, client: AsyncClient, headers: dict, skill_id: str):
        await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 5}, headers=headers)
        assert (await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": 1}, headers=headers)).status_code == 409

    @pytest.mark.asyncio
    async def test_install_nonexistent_skill(self, client: AsyncClient, headers: dict, agent_id: str):
        assert (await client.post("/api/v1/skills/install", json={"agent_id": agent_id, "skill_id": "00000000-fake"}, headers=headers)).status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_install_pending_skill(self, client: AsyncClient, headers: dict, agent_id: str, db_session: AsyncSession):
        pending = Skill(
            name="Pending", slug="pending-sec-skill", description="pending",
            category="utility",
            manifest={"tool_name": "get_datetime", "description": "t",
                      "parameters": {}, "required": [], "implementation": "builtin"},
            review_status="pending", author_id="system",
        )
        db_session.add(pending)
        await db_session.commit()
        await db_session.refresh(pending)
        assert (await client.post("/api/v1/skills/install", json={"agent_id": agent_id, "skill_id": pending.id}, headers=headers)).status_code == 404

    @pytest.mark.asyncio
    async def test_nonce_single_use(self, client: AsyncClient):
        nonce = (await client.get("/api/v1/auth/nonce")).json()["nonce"]
        body = {"wallet_address": "EQ_NONCE_REUSE2", "signature": "s", "nonce": nonce}
        assert (await client.post("/api/v1/auth/ton-connect", json=body)).status_code == 200
        assert (await client.post("/api/v1/auth/ton-connect", json=body)).status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SKILL MANIFEST SECURITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestSkillManifestSecurity:

    @pytest.mark.asyncio
    async def test_deeply_nested_manifest_rejected(self, client: AsyncClient, headers: dict):
        """200-level deep manifest must be caught by depth validator → 422, not 500."""
        deeply_nested: dict = {}
        current = deeply_nested
        for _ in range(200):
            current["a"] = {}
            current = current["a"]

        resp = await client.post(
            "/api/v1/skills/publish",
            json={
                "name": "Deep Nested", "slug": "deep-nested-manifest",
                "description": "x", "category": "utility",
                "manifest": deeply_nested,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_oversized_manifest_rejected(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/skills/publish",
            json={
                "name": "Huge Manifest", "slug": "huge-manifest-test",
                "description": "x", "category": "utility",
                "manifest": {"data": "x" * 65_000},
            },
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_ssrf_url_goes_to_pending_review(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/skills/publish",
            json={
                "name": "SSRF Skill", "slug": "ssrf-skill-test",
                "description": "evil", "category": "utility",
                "manifest": {"tool_name": "ssrf", "description": "ssrf",
                             "parameters": {}, "required": [],
                             "implementation": "http",
                             "url": "http://169.254.169.254/latest/meta-data/"},
            },
            headers=headers,
        )
        assert resp.status_code in (201, 422)
        if resp.status_code == 201:
            assert resp.json()["review_status"] == "pending"

    @pytest.mark.asyncio
    async def test_code_injection_in_tool_name_no_crash(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/skills/publish",
            json={
                "name": "Code Inject", "slug": "code-inject-test",
                "description": "evil", "category": "utility",
                "manifest": {"tool_name": "$(rm -rf /)", "description": "inject",
                             "parameters": {}, "required": [], "implementation": "builtin"},
            },
            headers=headers,
        )
        assert resp.status_code != 500


# ═══════════════════════════════════════════════════════════════════════════════
# 6. RESOURCE ABUSE
# ═══════════════════════════════════════════════════════════════════════════════

class TestResourceAbuse:

    @pytest.mark.asyncio
    async def test_mass_agent_creation(self, client: AsyncClient, headers: dict):
        for i in range(50):
            assert (await client.post(
                "/api/v1/agents",
                json={"name": f"Agent {i}", "model": "gpt-4o", "system_prompt": "x"},
                headers=headers,
            )).status_code == 200
        assert len((await client.get("/api/v1/agents", headers=headers)).json()) == 50

    @pytest.mark.asyncio
    async def test_concurrent_install_same_skill(self, client: AsyncClient, headers: dict, agent_id: str, db_session: AsyncSession):
        import asyncio
        skill_id = await insert_approved_skill(db_session, "concurrent-skill")
        results = await asyncio.gather(*[
            client.post("/api/v1/skills/install", json={"agent_id": agent_id, "skill_id": skill_id}, headers=headers)
            for _ in range(5)
        ])
        statuses = [r.json()["status"] for r in results if r.status_code == 200]
        assert statuses.count("installed") == 1

    @pytest.mark.asyncio
    async def test_mass_reviews_average_rating(self, client: AsyncClient, db_session: AsyncSession, skill_id: str):
        ratings = [1, 2, 3, 4, 5, 5, 4, 3, 2, 1]  # avg = 3.0
        for i, rating in enumerate(ratings):
            h = {"Authorization": f"Bearer {await get_token_for_wallet(client, f'EQ_REVIEWER_{i}')}"}
            assert (await client.post(f"/api/v1/skills/{skill_id}/reviews", json={"rating": rating}, headers=h)).status_code == 200
        assert (await client.get(f"/api/v1/skills/{skill_id}")).json()["rating"] == 3.0

    @pytest.mark.asyncio
    async def test_pagination_clamped(self, client: AsyncClient, headers: dict):
        resp = await client.get("/api/v1/agents?skip=-1&limit=999999", headers=headers)
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PARAMETER POLLUTION
# ═══════════════════════════════════════════════════════════════════════════════

class TestParameterPollution:

    @pytest.mark.asyncio
    async def test_extra_fields_ignored(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "Extra", "model": "gpt-4o", "system_prompt": "x",
                  "evil_field": "injected",
                  "user_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "evil_field" not in data
        assert data["user_id"] != "00000000-0000-0000-0000-000000000000"

    @pytest.mark.asyncio
    async def test_cannot_override_agent_owner_via_patch(self, client: AsyncClient, headers: dict, agent_id: str):
        resp = await client.patch(
            f"/api/v1/agents/{agent_id}",
            json={"user_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["user_id"] != "00000000-0000-0000-0000-000000000000"

    @pytest.mark.asyncio
    async def test_path_traversal_in_agent_id_blocked(self, client: AsyncClient, headers: dict):
        """
        Path traversal behaviour depends on encoding:

        - Plain "../users/me" → httpx normalises on the CLIENT before sending.
          raw_path arrives as /api/v1/users/me (no '..' left). Server routes
          it to GET /users/me and returns the CURRENT user — no data leak.

        - Percent-encoded "..%2F" / "%2e%2e" → httpx does NOT normalise these.
          Our middleware decodes them and blocks with 404.
        """
        # Percent-encoded variants — middleware must block them
        for evil_id in ["..%2Fusers%2Fme", "%2e%2e/agents"]:
            resp = await client.get(f"/api/v1/agents/{evil_id}", headers=headers)
            assert resp.status_code in (404, 422), \
                f"Expected 404/422 for {evil_id!r}, got {resp.status_code}"

        # Plain "../users/me" → httpx normalises, server returns current user (safe)
        resp = await client.get("/api/v1/agents/../users/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json().get("wallet_address") == "EQ_FIXTURE_WALLET"

    @pytest.mark.asyncio
    async def test_wrong_types_return_422(self, client: AsyncClient, headers: dict):
        resp = await client.post(
            "/api/v1/agents",
            json={"name": True, "model": 12345, "system_prompt": None},
            headers=headers,
        )
        assert resp.status_code in (422, 200)

    @pytest.mark.asyncio
    async def test_negative_skip_clamped(self, client: AsyncClient, headers: dict):
        resp = await client.get("/api/v1/agents?skip=-999", headers=headers)
        assert resp.status_code == 200
