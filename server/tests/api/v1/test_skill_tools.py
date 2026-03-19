"""
Tests for built-in skill tool implementations (skill_tools.py).
All external HTTP calls are mocked — no network needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


# ── web_search ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_web_search_returns_abstract(monkeypatch):
    from app.services.skill_tools import web_search

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "AbstractText": "TON is a blockchain.",
        "RelatedTopics": [],
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await web_search("what is TON")

    assert "TON is a blockchain" in result


@pytest.mark.asyncio
async def test_web_search_no_results():
    from app.services.skill_tools import web_search

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"AbstractText": "", "RelatedTopics": []}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await web_search("xyzzy")

    assert "No results" in result


@pytest.mark.asyncio
async def test_web_search_network_error():
    from app.services.skill_tools import web_search

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await web_search("broken")

    assert "error" in result.lower()


# ── ton_balance ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ton_balance_success():
    from app.services.skill_tools import ton_balance

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": {"balance": "5000000000"},  # 5 TON in nanotons
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await ton_balance("EQ_TEST")

    assert "5.0000 TON" in result


@pytest.mark.asyncio
async def test_ton_balance_api_error():
    from app.services.skill_tools import ton_balance

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "error": "invalid address"}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await ton_balance("INVALID")

    assert "invalid address" in result


# ── ton_transactions ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ton_transactions_success():
    from app.services.skill_tools import ton_transactions

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": [
            {"utime": 1700000000, "fee": "1000000", "transaction_id": {"hash": "abcdef1234567890"}},
        ],
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await ton_transactions("EQ_TEST", limit=1)

    assert "abcdef12345678" in result


@pytest.mark.asyncio
async def test_ton_transactions_empty():
    from app.services.skill_tools import ton_transactions

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "result": []}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await ton_transactions("EQ_EMPTY")

    assert "No transactions" in result


# ── crypto_price ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_crypto_price_success():
    from app.services.skill_tools import crypto_price

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "the-open-network": {"usd": 5.23, "usd_24h_change": 2.1}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await crypto_price("the-open-network")

    assert "5.2300" in result
    assert "+2.10%" in result


@pytest.mark.asyncio
async def test_crypto_price_unknown_coin():
    from app.services.skill_tools import crypto_price

    mock_resp = MagicMock()
    mock_resp.json.return_value = {}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await crypto_price("fake-coin-xyz")

    assert "not found" in result


# ── http_fetch ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_http_fetch_success():
    from app.services.skill_tools import http_fetch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Hello World</html>"

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await http_fetch("https://example.com")

    assert "Hello World" in result
    assert "200" in result


@pytest.mark.asyncio
async def test_http_fetch_truncates_long_content():
    from app.services.skill_tools import http_fetch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "x" * 10000

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await http_fetch("https://example.com")

    # Must be truncated to 3000 chars + header overhead
    assert len(result) < 3200


# ── get_datetime ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_datetime_utc():
    from app.services.skill_tools import get_datetime
    result = await get_datetime("UTC")
    assert "UTC" in result


@pytest.mark.asyncio
async def test_get_datetime_moscow():
    from app.services.skill_tools import get_datetime
    result = await get_datetime("Europe/Moscow")
    assert "Moscow" in result or "MSK" in result


@pytest.mark.asyncio
async def test_get_datetime_invalid_timezone():
    from app.services.skill_tools import get_datetime
    result = await get_datetime("Mars/Olympus")
    assert "Unknown timezone" in result


# ── get_weather ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_weather_success():
    from app.services.skill_tools import get_weather

    geo_resp = MagicMock()
    geo_resp.json.return_value = {
        "results": [{"name": "London", "latitude": 51.5, "longitude": -0.1}]
    }
    wx_resp = MagicMock()
    wx_resp.json.return_value = {
        "current_weather": {"temperature": 15.0, "windspeed": 20.0, "weathercode": 1}
    }

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return geo_resp if call_count == 1 else wx_resp

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=mock_get))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_weather("London")

    assert "London" in result
    assert "15" in result


@pytest.mark.asyncio
async def test_get_weather_city_not_found():
    from app.services.skill_tools import get_weather

    geo_resp = MagicMock()
    geo_resp.json.return_value = {"results": []}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=geo_resp)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_weather("FakeCity123")

    assert "not found" in result
