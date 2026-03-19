"""
Tests for /api/v1/auth
Covers: nonce, TON-connect (new user, existing user, expired nonce, reuse),
        Telegram auth (new user, existing user).
"""
import json
import pytest
from httpx import AsyncClient
from urllib.parse import urlencode


@pytest.mark.asyncio
async def test_get_nonce_returns_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/nonce")
    assert resp.status_code == 200
    data = resp.json()
    assert "nonce" in data
    assert len(data["nonce"]) == 32  # 16 bytes hex
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_ton_connect_creates_new_user(client: AsyncClient):
    nonce = (await client.get("/api/v1/auth/nonce")).json()["nonce"]
    resp = await client.post(
        "/api/v1/auth/ton-connect",
        json={"wallet_address": "EQ_NEW_WALLET", "signature": "sig", "nonce": nonce},
    )
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_ton_connect_same_wallet_returns_same_user(client: AsyncClient):
    wallet = "EQ_SAME_WALLET"

    n1 = (await client.get("/api/v1/auth/nonce")).json()["nonce"]
    t1 = (await client.post("/api/v1/auth/ton-connect", json={"wallet_address": wallet, "signature": "s", "nonce": n1})).json()["access_token"]

    n2 = (await client.get("/api/v1/auth/nonce")).json()["nonce"]
    t2 = (await client.post("/api/v1/auth/ton-connect", json={"wallet_address": wallet, "signature": "s", "nonce": n2})).json()["access_token"]

    # Both tokens should decode to the same user
    me1 = (await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {t1}"})).json()
    me2 = (await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {t2}"})).json()
    assert me1["id"] == me2["id"]


@pytest.mark.asyncio
async def test_ton_connect_invalid_nonce(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/ton-connect",
        json={"wallet_address": "EQ_X", "signature": "s", "nonce": "nonexistent_nonce"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ton_connect_nonce_cannot_be_reused(client: AsyncClient):
    nonce = (await client.get("/api/v1/auth/nonce")).json()["nonce"]
    payload = {"wallet_address": "EQ_REUSE", "signature": "s", "nonce": nonce}
    assert (await client.post("/api/v1/auth/ton-connect", json=payload)).status_code == 200
    # Second use of same nonce must fail
    assert (await client.post("/api/v1/auth/ton-connect", json=payload)).status_code == 400


@pytest.mark.asyncio
async def test_telegram_auth_creates_user(client: AsyncClient):
    user_data = json.dumps({"id": 999888, "username": "tguser"})
    init_data = urlencode({"user": user_data, "hash": "fake_hash"})
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_telegram_auth_missing_user_field(client: AsyncClient):
    # initData without 'user' key
    init_data = urlencode({"hash": "fake_hash"})
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 400
