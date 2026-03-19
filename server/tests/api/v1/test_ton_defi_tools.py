"""
Tests for TON DeFi skill tools (ton_defi_tools.py).

Goal: Verify that each tool returns a correctly structured string result
that an AI agent can parse and use. All external HTTP calls are mocked.

Coverage:
  - stonfi_swap_simulate
  - stonfi_assets
  - stonfi_pool_info
  - dedust_pools
  - ton_dns_resolve
  - ton_dns_reverse
  - nft_item_info
  - nft_collection_info
  - jetton_info
  - jetton_holders
  - ton_account_info
  - ton_staking_pools
  - _resolve_jetton (alias resolution)
  - BUILTIN_TOOLS registry completeness
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_mock_client(responses: list):
    """
    Build a mock AsyncClient that returns responses in sequence per GET/POST call.
    responses: list of MagicMock objects returned one by one.
    """
    call_count = [0]

    async def mock_request(*args, **kwargs):
        resp = responses[min(call_count[0], len(responses) - 1)]
        call_count[0] += 1
        return resp

    mock_session = MagicMock()
    mock_session.get = mock_request
    mock_session.post = mock_request

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def json_resp(data, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.text = str(data)
    return r


# ══════════════════════════════════════════════════════════════════════════════
# STON.fi
# ══════════════════════════════════════════════════════════════════════════════

class TestStonfiSwapSimulate:

    @pytest.mark.asyncio
    async def test_success_returns_key_fields(self):
        """Agent must receive offer, ask amounts, fee, price impact."""
        from app.services.ton_defi_tools import stonfi_swap_simulate

        resp = json_resp({
            "offer_units": "1000000000",
            "ask_units": "4950000",
            "min_ask_units": "4900000",
            "fee_units": "50000",
            "price_impact": "0.01",
            "router_address": "EQBfBWT7X2BHg9tXAxzhz2aKiNTU1tpt5NsiK0uSDW_YAJ67",
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await stonfi_swap_simulate(
                offer_address="ton",
                ask_address="usdt",
                units="1000000000",
            )

        assert "1000000000" in result
        assert "4950000" in result
        assert "fee" in result.lower()
        assert "price" in result.lower()

    @pytest.mark.asyncio
    async def test_resolves_known_symbols(self):
        """Symbols like 'usdt' must be resolved to actual addresses before API call."""
        from app.services.ton_defi_tools import _resolve_jetton, KNOWN_JETTONS
        assert _resolve_jetton("usdt") == KNOWN_JETTONS["usdt"]
        assert _resolve_jetton("USDT") == KNOWN_JETTONS["usdt"]  # case-insensitive
        assert _resolve_jetton("EQsome_custom_address") == "EQsome_custom_address"

    @pytest.mark.asyncio
    async def test_api_error_returns_error_string(self):
        """On non-200 response, tool must return error string (not raise)."""
        from app.services.ton_defi_tools import stonfi_swap_simulate

        resp = MagicMock()
        resp.status_code = 400
        resp.text = "Bad request"

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await stonfi_swap_simulate("ton", "usdt", "0")

        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_network_error_returns_error_string(self):
        """Network failure must return error string, not raise exception."""
        from app.services.ton_defi_tools import stonfi_swap_simulate
        import httpx

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await stonfi_swap_simulate("ton", "usdt", "1000000")

        assert "error" in result.lower()


class TestStonfiAssets:

    @pytest.mark.asyncio
    async def test_success_returns_list(self):
        from app.services.ton_defi_tools import stonfi_assets

        resp = json_resp({
            "asset_list": [
                {"symbol": "TON", "display_name": "Toncoin", "contract_address": "EQabc", "dex_price_usd": "5.2"},
                {"symbol": "USDT", "display_name": "Tether", "contract_address": "EQdef", "dex_price_usd": "1.0"},
            ]
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await stonfi_assets()

        assert "TON" in result
        assert "USDT" in result

    @pytest.mark.asyncio
    async def test_filter_by_search(self):
        """After filtering by 'usdt', only USDT entry must appear.
        We check by contract_address, not by symbol, to avoid the false positive
        where 'TON' also appears inside the header string 'STON.fi assets'."""
        from app.services.ton_defi_tools import stonfi_assets

        resp = json_resp({
            "asset_list": [
                {"symbol": "TON", "display_name": "Toncoin", "contract_address": "EQabc", "dex_price_usd": "5.2"},
                {"symbol": "USDT", "display_name": "Tether", "contract_address": "EQdef", "dex_price_usd": "1.0"},
            ]
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await stonfi_assets(search="usdt")

        assert "USDT" in result
        assert "EQdef" in result        # USDT contract address must appear
        assert "Toncoin" not in result  # TON display_name must NOT appear
        assert "EQabc" not in result    # TON contract address must NOT appear

    @pytest.mark.asyncio
    async def test_empty_list(self):
        from app.services.ton_defi_tools import stonfi_assets

        resp = json_resp({"asset_list": []})

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await stonfi_assets()

        assert "0 results" in result or "assets" in result.lower()

    @pytest.mark.asyncio
    async def test_limit_applied(self):
        """Hard cap of 50 assets, but user limit of 5 must be respected."""
        from app.services.ton_defi_tools import stonfi_assets

        assets = [
            {"symbol": f"TKN{i}", "display_name": f"Token {i}", "contract_address": f"EQ{i:04d}", "dex_price_usd": "1.0"}
            for i in range(60)
        ]
        resp = json_resp({"asset_list": assets})

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await stonfi_assets(limit=5)

        assert result.count("TKN") <= 5


class TestStonfiPoolInfo:

    @pytest.mark.asyncio
    async def test_success_returns_reserves(self):
        from app.services.ton_defi_tools import stonfi_pool_info

        resp = json_resp({
            "pool": {
                "token0_address": "EQaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "token1_address": "EQbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "reserve0": "10000000000",
                "reserve1": "50000000",
                "lp_total_supply_wc": "7071067811",
            }
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await stonfi_pool_info("EQpool_address_example")

        assert "reserve" in result.lower()
        assert "10000000000" in result

    @pytest.mark.asyncio
    async def test_api_error(self):
        from app.services.ton_defi_tools import stonfi_pool_info

        resp = MagicMock()
        resp.status_code = 404
        resp.text = "Not found"

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await stonfi_pool_info("EQnonexistent")

        assert "error" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# DeDust
# ══════════════════════════════════════════════════════════════════════════════

class TestDedustPools:

    @pytest.mark.asyncio
    async def test_success_returns_pools(self):
        from app.services.ton_defi_tools import dedust_pools

        resp = json_resp([
            {
                "address": "EQpool1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "totalSupply": "1000000",
                "assets": [
                    {"address": "EQa1", "metadata": {"symbol": "TON"}},
                    {"address": "EQa2", "metadata": {"symbol": "USDT"}},
                ],
            }
        ])

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await dedust_pools()

        assert "TON" in result
        assert "USDT" in result

    @pytest.mark.asyncio
    async def test_filter_by_asset(self):
        from app.services.ton_defi_tools import dedust_pools

        resp = json_resp([
            {
                "address": "EQpool_ton_usdt",
                "totalSupply": "100",
                "assets": [
                    {"address": "EQton_addr", "metadata": {"symbol": "TON"}},
                    {"address": "EQusdt_addr", "metadata": {"symbol": "USDT"}},
                ],
            },
            {
                "address": "EQpool_ston_usdc",
                "totalSupply": "200",
                "assets": [
                    {"address": "EQston_addr", "metadata": {"symbol": "STON"}},
                    {"address": "EQusdc_addr", "metadata": {"symbol": "USDC"}},
                ],
            },
        ])

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await dedust_pools(asset_address="EQton_addr")

        assert "EQpool_ton_usdt" in result
        assert "EQpool_ston_usdc" not in result

    @pytest.mark.asyncio
    async def test_empty_list(self):
        from app.services.ton_defi_tools import dedust_pools

        resp = json_resp([])

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await dedust_pools()

        assert "0" in result or "pools" in result.lower()

    @pytest.mark.asyncio
    async def test_api_error(self):
        from app.services.ton_defi_tools import dedust_pools

        resp = MagicMock()
        resp.status_code = 503
        resp.text = "Service unavailable"

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await dedust_pools()

        assert "error" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# TON DNS
# ══════════════════════════════════════════════════════════════════════════════

class TestTonDnsResolve:

    @pytest.mark.asyncio
    async def test_success_returns_address(self):
        from app.services.ton_defi_tools import ton_dns_resolve

        resp = json_resp({
            "wallet": {"address": "EQDns_resolved_wallet_address", "is_scam": False},
            "nft_address": "EQDns_nft_item",
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_dns_resolve("foundation.ton")

        assert "EQDns_resolved_wallet_address" in result
        assert "foundation.ton" in result

    @pytest.mark.asyncio
    async def test_scam_domain_flagged(self):
        from app.services.ton_defi_tools import ton_dns_resolve

        resp = json_resp({
            "wallet": {"address": "EQScam", "is_scam": True},
            "nft_address": None,
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_dns_resolve("scam.ton")

        assert "SCAM" in result.upper()

    @pytest.mark.asyncio
    async def test_not_found(self):
        from app.services.ton_defi_tools import ton_dns_resolve

        resp = MagicMock()
        resp.status_code = 404
        resp.text = "Not found"

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_dns_resolve("notregistered.ton")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_strips_trailing_dot(self):
        """Domain 'example.ton.' should be normalized to 'example.ton' before API call."""
        from app.services.ton_defi_tools import ton_dns_resolve

        captured = {}

        async def mock_get(url, **kwargs):
            captured["url"] = url
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {"wallet": {"address": "EQ1", "is_scam": False}, "nft_address": None}
            return r

        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await ton_dns_resolve("example.ton.")

        assert not captured["url"].endswith(".")


class TestTonDnsReverse:

    @pytest.mark.asyncio
    async def test_success_returns_domains(self):
        from app.services.ton_defi_tools import ton_dns_reverse

        resp = json_resp({"domains": ["mywallet.ton", "alias.ton"]})

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_dns_reverse("EQsome_address")

        assert "mywallet.ton" in result
        assert "alias.ton" in result

    @pytest.mark.asyncio
    async def test_no_domains(self):
        from app.services.ton_defi_tools import ton_dns_reverse

        resp = json_resp({"domains": []})

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_dns_reverse("EQsome_address")

        assert "No domains" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        from app.services.ton_defi_tools import ton_dns_reverse

        resp = MagicMock()
        resp.status_code = 404
        resp.text = ""

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_dns_reverse("EQnotlinked")

        assert "No" in result or "not found" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# NFT
# ══════════════════════════════════════════════════════════════════════════════

class TestNftItemInfo:

    @pytest.mark.asyncio
    async def test_success_returns_name_and_owner(self):
        from app.services.ton_defi_tools import nft_item_info

        resp = json_resp({
            "metadata": {"name": "Cool NFT #1", "image": "https://cdn.example.com/nft.png"},
            "owner": {"address": "EQowner_address"},
            "collection": {"name": "Cool Collection", "address": "EQcollection_address"},
            "approved_by": ["getgems"],
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await nft_item_info("EQnft_item_address")

        assert "Cool NFT #1" in result
        assert "EQowner_address" in result
        assert "Cool Collection" in result
        assert "getgems" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        from app.services.ton_defi_tools import nft_item_info

        resp = MagicMock()
        resp.status_code = 404

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await nft_item_info("EQnonexistent")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_description_truncated(self):
        """Long descriptions must be truncated to prevent agent context overflow."""
        from app.services.ton_defi_tools import nft_item_info

        long_desc = "A" * 500
        resp = json_resp({
            "metadata": {"name": "NFT", "description": long_desc},
            "owner": {"address": "EQx"},
            "collection": {},
            "approved_by": [],
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await nft_item_info("EQsome")

        # Description in result must be capped at 200 chars
        assert long_desc[:200] in result
        assert long_desc[201:] not in result


class TestNftCollectionInfo:

    @pytest.mark.asyncio
    async def test_success_returns_collection_data(self):
        from app.services.ton_defi_tools import nft_collection_info

        resp = json_resp({
            "metadata": {"name": "Mega Collection", "description": "A great collection"},
            "owner": {"address": "EQowner"},
            "next_item_index": 1000,
            "approved_by": ["getgems", "tonkeeper"],
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await nft_collection_info("EQcollection")

        assert "Mega Collection" in result
        assert "1000" in result
        assert "getgems" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        from app.services.ton_defi_tools import nft_collection_info

        resp = MagicMock()
        resp.status_code = 404

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await nft_collection_info("EQbad")

        assert "not found" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Jettons
# ══════════════════════════════════════════════════════════════════════════════

class TestJettonInfo:

    @pytest.mark.asyncio
    async def test_success_returns_token_data(self):
        from app.services.ton_defi_tools import jetton_info

        resp = json_resp({
            "metadata": {
                "name": "Tether USD",
                "symbol": "USDT",
                "decimals": 6,
                "description": "Stablecoin",
            },
            "total_supply": "1000000000000",
            "holders_count": 50000,
            "mintable": True,
            "approved_by": ["tonkeeper"],
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await jetton_info("usdt")

        assert "USDT" in result
        assert "50000" in result
        assert "6" in result  # decimals

    @pytest.mark.asyncio
    async def test_symbol_resolved_before_request(self):
        """Known symbols like 'usdt' must be resolved to their address before the API call."""
        from app.services.ton_defi_tools import jetton_info, KNOWN_JETTONS

        captured_url = {}

        async def mock_get(url, **kwargs):
            captured_url["url"] = url
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "metadata": {"name": "Tether", "symbol": "USDT", "decimals": 6},
                "total_supply": "100", "holders_count": 1, "mintable": False, "approved_by": [],
            }
            return r

        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await jetton_info("usdt")

        assert KNOWN_JETTONS["usdt"] in captured_url["url"]

    @pytest.mark.asyncio
    async def test_not_found(self):
        from app.services.ton_defi_tools import jetton_info

        resp = MagicMock()
        resp.status_code = 404

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await jetton_info("fakecoin")

        assert "not found" in result.lower()


class TestJettonHolders:

    @pytest.mark.asyncio
    async def test_success_returns_holders_list(self):
        from app.services.ton_defi_tools import jetton_holders

        resp = json_resp({
            "addresses": [
                {"owner": {"address": "EQholder1"}, "balance": "999999"},
                {"owner": {"address": "EQholder2"}, "balance": "500000"},
            ]
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await jetton_holders("usdt", limit=2)

        assert "EQholder1" in result
        assert "999999" in result

    @pytest.mark.asyncio
    async def test_empty_holders(self):
        from app.services.ton_defi_tools import jetton_holders

        resp = json_resp({"addresses": []})

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await jetton_holders("usdt")

        assert "No holders" in result

    @pytest.mark.asyncio
    async def test_limit_capped_at_20(self):
        """Limit higher than 20 must be silently capped to 20 before the API call."""
        from app.services.ton_defi_tools import jetton_holders

        captured_params = {}

        async def mock_get(url, params=None, **kwargs):
            captured_params.update(params or {})
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {"addresses": []}
            return r

        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await jetton_holders("usdt", limit=999)

        assert captured_params.get("limit") <= 20


# ══════════════════════════════════════════════════════════════════════════════
# TON Account
# ══════════════════════════════════════════════════════════════════════════════

class TestTonAccountInfo:

    @pytest.mark.asyncio
    async def test_success_returns_balance_and_status(self):
        from app.services.ton_defi_tools import ton_account_info

        resp = json_resp({
            "balance": "10000000000",  # 10 TON
            "status": "active",
            "interfaces": ["wallet_v4r2"],
            "last_activity": 1700000000,
            "is_scam": False,
            "name": "My Wallet",
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_account_info("EQtest_wallet")

        assert "10.0000 TON" in result
        assert "active" in result
        assert "wallet_v4r2" in result

    @pytest.mark.asyncio
    async def test_scam_account_flagged(self):
        from app.services.ton_defi_tools import ton_account_info

        resp = json_resp({
            "balance": "0",
            "status": "active",
            "interfaces": [],
            "last_activity": 0,
            "is_scam": True,
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_account_info("EQscam_address")

        assert "SCAM" in result.upper()

    @pytest.mark.asyncio
    async def test_not_found(self):
        from app.services.ton_defi_tools import ton_account_info

        resp = MagicMock()
        resp.status_code = 404

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_account_info("EQnonexistent")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_balance_formatted_correctly(self):
        """Nanoton balance must be displayed as human-readable TON (4 decimal places)."""
        from app.services.ton_defi_tools import ton_account_info

        resp = json_resp({
            "balance": "1234567890",  # 1.23456789 TON → rounds to 1.2346
            "status": "active",
            "interfaces": [],
            "last_activity": 0,
            "is_scam": False,
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_account_info("EQany")

        assert "1.2346 TON" in result


# ══════════════════════════════════════════════════════════════════════════════
# Staking
# ══════════════════════════════════════════════════════════════════════════════

class TestTonStakingPools:

    @pytest.mark.asyncio
    async def test_success_returns_pool_list(self):
        from app.services.ton_defi_tools import ton_staking_pools

        resp = json_resp({
            "pools": [
                {
                    "name": "Bemo",
                    "apy": 4.5,
                    "min_stake": "1000000000",
                    "total_amount": "100000000000",
                    "address": "EQbemo_pool_address",
                },
                {
                    "name": "TON Whales",
                    "apy": 5.1,
                    "min_stake": "50000000000",
                    "total_amount": "500000000000",
                    "address": "EQwhales_pool_addr",
                },
            ]
        })

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_staking_pools()

        assert "Bemo" in result
        assert "4.5" in result
        assert "TON Whales" in result
        assert "5.1" in result

    @pytest.mark.asyncio
    async def test_limit_applied(self):
        """Only the requested number of pools should appear in the result."""
        from app.services.ton_defi_tools import ton_staking_pools

        pools = [
            {"name": f"Pool{i}", "apy": 4.0, "min_stake": "0", "total_amount": "0", "address": f"EQ{i:04d}"}
            for i in range(20)
        ]
        resp = json_resp({"pools": pools})

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_staking_pools(limit=3)

        assert "Pool0" in result
        assert "Pool1" in result
        assert "Pool2" in result
        assert "Pool3" not in result

    @pytest.mark.asyncio
    async def test_api_error(self):
        from app.services.ton_defi_tools import ton_staking_pools

        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Internal Server Error"

        with patch("httpx.AsyncClient", return_value=make_mock_client([resp])):
            result = await ton_staking_pools()

        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_available_for_param_passed(self):
        """available_for wallet address must be forwarded to the API as a query param."""
        from app.services.ton_defi_tools import ton_staking_pools

        captured = {}

        async def mock_get(url, params=None, **kwargs):
            captured["params"] = params or {}
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {"pools": []}
            return r

        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await ton_staking_pools(available_for="EQmy_wallet")

        assert captured["params"].get("available_for") == "EQmy_wallet"


# ══════════════════════════════════════════════════════════════════════════════
# BUILTIN_TOOLS registry
# ══════════════════════════════════════════════════════════════════════════════

class TestBuiltinToolsRegistry:
    """
    Verify the registry is complete — every tool the agent can call must exist,
    be callable, and be async. This is the single source of truth for the agent.
    """

    def test_all_defi_tools_present(self):
        from app.services.skill_tools import BUILTIN_TOOLS

        expected = [
            "stonfi_swap_simulate",
            "stonfi_assets",
            "stonfi_pool_info",
            "dedust_pools",
            "ton_dns_resolve",
            "ton_dns_reverse",
            "nft_item_info",
            "nft_collection_info",
            "jetton_info",
            "jetton_holders",
            "ton_account_info",
            "ton_staking_pools",
        ]
        for name in expected:
            assert name in BUILTIN_TOOLS, f"DeFi tool '{name}' missing from BUILTIN_TOOLS"

    def test_all_basic_tools_present(self):
        from app.services.skill_tools import BUILTIN_TOOLS

        expected = [
            "web_search",
            "ton_balance",
            "ton_transactions",
            "crypto_price",
            "http_fetch",
            "tg_send_message",
            "get_weather",
            "get_datetime",
        ]
        for name in expected:
            assert name in BUILTIN_TOOLS, f"Basic tool '{name}' missing from BUILTIN_TOOLS"

    def test_all_tools_are_async_callables(self):
        import asyncio
        from app.services.skill_tools import BUILTIN_TOOLS

        for name, fn in BUILTIN_TOOLS.items():
            assert callable(fn), f"Tool '{name}' is not callable"
            assert asyncio.iscoroutinefunction(fn), f"Tool '{name}' is not async (agent requires coroutines)"
