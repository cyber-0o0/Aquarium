"""
Wallet service — real TON blockchain data for user wallets.

Sources:
  - tonapi.io/v2  — rich account info, jetton balances, transaction history
  - toncenter.com — raw balance fallback

Responsibilities:
  1. Fetch real on-chain balance for a wallet address
  2. Fetch jetton (token) balances
  3. Parse and normalize transaction history with type detection
  4. Cache results in-memory for 30s to avoid rate-limiting
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

def _get_network_config() -> tuple[str, str, str]:
    """Returns (network_name, tonapi_base, toncenter_base) dynamically."""
    network = getattr(settings, "TON_NETWORK", "mainnet").lower()
    if network == "testnet":
        return "testnet", "https://testnet.tonapi.io/v2", "https://testnet.toncenter.com/api/v2"
    return "mainnet", "https://tonapi.io/v2", "https://toncenter.com/api/v2"

# ── Simple TTL cache ───────────────────────────────────────────────────────────
_cache: Dict[str, tuple[float, Any]] = {}
CACHE_TTL = 30.0  # seconds


def _cache_get(key: str) -> Optional[Any]:
    if key in _cache:
        ts, val = _cache[key]
        if time.monotonic() - ts < CACHE_TTL:
            return val
        del _cache[key]
    return None


def _cache_set(key: str, val: Any) -> None:
    _cache[key] = (time.monotonic(), val)


# ── Headers ────────────────────────────────────────────────────────────────────

def _headers() -> Dict[str, str]:
    try:
        from app.core.config import settings
        key = getattr(settings, "TONAPI_KEY", None)
        if key:
            return {"Authorization": f"Bearer {key}"}
    except Exception:
        pass
    return {}


def _toncenter_headers() -> Dict[str, str]:
    try:
        from app.core.config import settings
        key = getattr(settings, "TONCENTER_API_KEY", None)
        if key:
            return {"X-API-Key": key}
    except Exception:
        pass
    return {}


# ── Balance ────────────────────────────────────────────────────────────────────

async def get_wallet_balance(address: str) -> Dict[str, Any]:
    """
    Returns:
        {
          "address": str,
          "ton_balance": float,      # TON (not nanotons)
          "ton_balance_raw": str,    # nanotons string
          "usd_value": float,
          "ton_price_usd": float,
          "status": str,             # "active" | "uninitialized" | "frozen"
          "name": str | None,        # TON DNS name or nickname
          "icon": str | None,
          "is_scam": bool,
        }
    """
    cache_key = f"balance:{address}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    _, tonapi_base, _ = _get_network_config()
    try:
        async with httpx.AsyncClient(timeout=10, headers=_headers()) as c:
            account_task = c.get(f"{tonapi_base}/accounts/{address}")
            price_task = c.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "the-open-network", "vs_currencies": "usd"},
            )
            account_resp, price_resp = await asyncio.gather(
                account_task, price_task, return_exceptions=True
            )

        ton_price = 0.0
        if not isinstance(price_resp, Exception) and price_resp.status_code == 200:
            price_data = price_resp.json()
            ton_price = price_data.get("the-open-network", {}).get("usd", 0.0)

        if isinstance(account_resp, Exception) or account_resp.status_code != 200:
            # Fallback to toncenter
            return await _get_balance_toncenter(address, ton_price)

        d = account_resp.json()
        nano = int(d.get("balance", 0))
        ton_balance = nano / 1_000_000_000

        result = {
            "address": address,
            "ton_balance": round(ton_balance, 6),
            "ton_balance_raw": str(nano),
            "usd_value": round(ton_balance * ton_price, 2),
            "ton_price_usd": ton_price,
            "status": d.get("status", "unknown"),
            "name": d.get("name") or d.get("dns"),
            "icon": d.get("icon"),
            "is_scam": d.get("is_scam", False),
        }
        _cache_set(cache_key, result)
        return result

    except Exception as e:
        return {
            "address": address,
            "ton_balance": 0.0,
            "ton_balance_raw": "0",
            "usd_value": 0.0,
            "ton_price_usd": 0.0,
            "status": "error",
            "name": None,
            "icon": None,
            "is_scam": False,
            "error": str(e),
        }


async def _get_balance_toncenter(address: str, ton_price: float) -> Dict[str, Any]:
    """Fallback balance fetch via TonCenter."""
    _, _, toncenter_base = _get_network_config()
    try:
        async with httpx.AsyncClient(timeout=10, headers=_toncenter_headers()) as c:
            r = await c.get(
                f"{toncenter_base}/getAddressInformation",
                params={"address": address},
            )
        if r.status_code == 200 and r.json().get("ok"):
            nano = int(r.json()["result"]["balance"])
            ton = nano / 1_000_000_000
            return {
                "address": address,
                "ton_balance": round(ton, 6),
                "ton_balance_raw": str(nano),
                "usd_value": round(ton * ton_price, 2),
                "ton_price_usd": ton_price,
                "status": r.json()["result"].get("state", "unknown"),
                "name": None,
                "icon": None,
                "is_scam": False,
            }
    except Exception:
        pass
    return {
        "address": address,
        "ton_balance": 0.0,
        "ton_balance_raw": "0",
        "usd_value": 0.0,
        "ton_price_usd": 0.0,
        "status": "unknown",
        "name": None,
        "icon": None,
        "is_scam": False,
    }


# ── Jetton balances ────────────────────────────────────────────────────────────

async def get_jetton_balances(address: str) -> List[Dict[str, Any]]:
    """
    Returns list of jetton (token) balances for a wallet.

    Each item:
        {
          "symbol": str,
          "name": str,
          "balance": float,
          "balance_raw": str,
          "decimals": int,
          "usd_value": float | None,
          "address": str,       # jetton master address
          "image": str | None,
          "verified": bool,
        }
    """
    cache_key = f"jettons:{address}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    _, tonapi_base, _ = _get_network_config()
    try:
        async with httpx.AsyncClient(timeout=10, headers=_headers()) as c:
            r = await c.get(f"{tonapi_base}/accounts/{address}/jettons")

        if r.status_code != 200:
            return []

        items = r.json().get("balances", [])
        result = []
        for item in items:
            jetton = item.get("jetton", {})
            meta = jetton.get("metadata", {}) if isinstance(jetton, dict) else {}
            decimals = int(meta.get("decimals", 9))
            raw = item.get("balance", "0")
            try:
                balance = int(raw) / (10 ** decimals)
            except (ValueError, ZeroDivisionError):
                balance = 0.0

            # skip dust (< 0.001 of any token)
            if balance < 0.001:
                continue

            price = item.get("price", {})
            usd_per_token = None
            if price and price.get("prices"):
                usd_per_token = price["prices"].get("USD")
            usd_value = round(balance * float(usd_per_token), 2) if usd_per_token else None

            result.append({
                "symbol": meta.get("symbol", "?"),
                "name": meta.get("name", "Unknown"),
                "balance": round(balance, 6),
                "balance_raw": raw,
                "decimals": decimals,
                "usd_value": usd_value,
                "address": jetton.get("address", "") if isinstance(jetton, dict) else "",
                "image": meta.get("image"),
                "verified": jetton.get("verification") == "whitelist" if isinstance(jetton, dict) else False,
            })

        # Sort by USD value desc, then by balance
        result.sort(key=lambda x: (x["usd_value"] or 0), reverse=True)
        _cache_set(cache_key, result)
        return result

    except Exception:
        return []


# ── Transaction history ────────────────────────────────────────────────────────

_TX_ICON_MAP = {
    "JettonTransfer": "transfer",
    "JettonMint": "mint",
    "JettonBurn": "burn",
    "NftItemTransfer": "nft",
    "ContractDeploy": "deploy",
    "Subscribe": "subscribe",
    "UnSubscribe": "unsubscribe",
    "TonTransfer": "transfer",
    "SmartContractExec": "contract",
    "ElectionsRecoverStake": "unstake",
    "ElectionsDepositStake": "stake",
    "DepositStake": "stake",
    "RecoverStake": "unstake",
    "JettonSwap": "swap",
    "NftPurchase": "nft_buy",
    "AuctionBid": "bid",
    "DomainRenew": "domain",
}


async def get_transaction_history(
    address: str,
    limit: int = 30,
    before_lt: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Returns normalized transaction list.

    Each item:
        {
          "hash": str,
          "lt": int,
          "type": str,        # "transfer" | "swap" | "stake" | "nft" | "contract" | ...
          "direction": str,   # "in" | "out" | "self"
          "title": str,
          "time_unix": int,
          "time_iso": str,
          "amount_ton": float | None,
          "amount_usd": float | None,
          "token_symbol": str | None,
          "token_amount": float | None,
          "from_address": str | None,
          "to_address": str | None,
          "comment": str | None,
          "fee_ton": float,
          "status": str,      # "ok" | "failed"
          "explorer_url": str,
        }
    """
    cache_key = f"txs:{address}:{limit}:{before_lt}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    _, tonapi_base, _ = _get_network_config()
    params: Dict[str, Any] = {"limit": min(limit, 100)}
    if before_lt:
        params["before_lt"] = before_lt

    try:
        async with httpx.AsyncClient(timeout=12, headers=_headers()) as c:
            r = await c.get(
                f"{tonapi_base}/accounts/{address}/events",
                params=params,
            )

        if r.status_code != 200:
            return []

        events = r.json().get("events", [])
        result = []

        for event in events:
            tx = _parse_event(event, address)
            if tx:
                result.append(tx)

        _cache_set(cache_key, result)
        return result

    except Exception:
        return []


def _parse_event(event: Dict[str, Any], viewer_address: str) -> Optional[Dict[str, Any]]:
    """Normalize a tonapi event into our transaction schema."""
    try:
        actions = event.get("actions", [])
        if not actions:
            return None

        action = actions[0]  # primary action
        action_type = action.get("type", "unknown")
        status = action.get("status", "ok")

        # Determine display type
        tx_type = _TX_ICON_MAP.get(action_type, "contract")

        # Parse time
        ts = event.get("timestamp", 0)
        from datetime import datetime, UTC
        time_iso = datetime.fromtimestamp(ts, UTC).isoformat()

        # Fee
        fee_nano = int(event.get("fees", {}).get("total", 0))
        fee_ton = fee_nano / 1_000_000_000

        # Extract amount and addresses from action detail
        amount_ton = None
        amount_usd = None
        token_symbol = None
        token_amount = None
        from_addr = None
        to_addr = None
        comment = None
        title = action_type
        direction = "self"

        detail = action.get(action_type, {})
        if not isinstance(detail, dict):
            detail = {}

        if action_type == "TonTransfer":
            nano = int(detail.get("amount", 0))
            amount_ton = nano / 1_000_000_000
            from_addr = detail.get("sender", {}).get("address")
            to_addr = detail.get("recipient", {}).get("address")
            comment = detail.get("comment")
            if from_addr and viewer_address and _addr_eq(from_addr, viewer_address):
                direction = "out"
                title = "Send TON"
            else:
                direction = "in"
                title = "Receive TON"

        elif action_type == "JettonTransfer":
            jetton = detail.get("jetton", {})
            decimals = int(jetton.get("decimals", 9))
            raw = int(detail.get("amount", 0))
            token_amount = raw / (10 ** decimals)
            token_symbol = jetton.get("symbol", "?")
            from_addr = detail.get("sender", {}).get("address")
            to_addr = detail.get("recipient", {}).get("address")
            comment = detail.get("comment")
            if from_addr and viewer_address and _addr_eq(from_addr, viewer_address):
                direction = "out"
                title = f"Send {token_symbol}"
            else:
                direction = "in"
                title = f"Receive {token_symbol}"

        elif action_type == "JettonSwap":
            token_in = detail.get("jetton_master_in", {})
            token_out = detail.get("jetton_master_out", {})
            sym_in = token_in.get("symbol") if token_in else "TON"
            sym_out = token_out.get("symbol") if token_out else "TON"
            title = f"Swap {sym_in} → {sym_out}"
            tx_type = "swap"
            direction = "self"

        elif action_type in ("DepositStake", "ElectionsDepositStake"):
            nano = int(detail.get("amount", 0))
            amount_ton = nano / 1_000_000_000
            title = "Stake TON"
            direction = "out"

        elif action_type in ("RecoverStake", "ElectionsRecoverStake"):
            nano = int(detail.get("amount", 0))
            amount_ton = nano / 1_000_000_000
            title = "Unstake TON"
            direction = "in"

        elif action_type == "NftItemTransfer":
            nft = detail.get("nft", {})
            title = f"NFT Transfer: {nft.get('name', nft.get('address', '?')[:8])}"
            tx_type = "nft"

        elif action_type == "NftPurchase":
            price = detail.get("amount", {})
            nano = int(price.get("value", 0)) if isinstance(price, dict) else 0
            amount_ton = nano / 1_000_000_000
            nft = detail.get("nft", {})
            title = f"Buy NFT: {nft.get('name', '?')[:24]}"
            tx_type = "nft_buy"
            direction = "out"

        elif action_type == "ContractDeploy":
            title = "Deploy Contract"
            tx_type = "deploy"

        elif action_type == "SmartContractExec":
            nano = int(detail.get("ton_attached", 0))
            amount_ton = nano / 1_000_000_000 if nano else None
            title = "Contract Call"
            direction = "out"

        elif action_type == "DomainRenew":
            title = f"Renew Domain: {detail.get('domain', '?')}"
            tx_type = "domain"

        return {
            "hash": event.get("event_id", ""),
            "lt": event.get("lt", 0),
            "type": tx_type,
            "direction": direction,
            "title": title,
            "time_unix": ts,
            "time_iso": time_iso,
            "amount_ton": round(amount_ton, 6) if amount_ton is not None else None,
            "amount_usd": amount_usd,
            "token_symbol": token_symbol,
            "token_amount": round(token_amount, 6) if token_amount is not None else None,
            "from_address": from_addr,
            "to_address": to_addr,
            "comment": comment,
            "fee_ton": round(fee_ton, 6),
            "status": status,
            "explorer_url": f"https://tonviewer.com/transaction/{event.get('event_id', '')}",
        }

    except Exception:
        return None


def _addr_eq(a: str, b: str) -> bool:
    """Compare two TON addresses ignoring case."""
    return a.strip().lower() == b.strip().lower()


# ── Deposit address (receive) ─────────────────────────────────────────────────

async def get_deposit_info(address: str) -> Dict[str, Any]:
    """
    Returns deposit address info: QR-friendly data, bounceable/non-bounceable.
    Tonapi converts to both formats.
    """
    cache_key = f"deposit:{address}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    _, tonapi_base, _ = _get_network_config()
    try:
        async with httpx.AsyncClient(timeout=8, headers=_headers()) as c:
            r = await c.get(f"{tonapi_base}/address/{address}/parse")

        if r.status_code == 200:
            d = r.json()
            result = {
                "raw_form": d.get("raw_form", address),
                "bounceable": d.get("bounceable", {}).get("b64url", address),
                "non_bounceable": d.get("non_bounceable", {}).get("b64url", address),
                "given": address,
                # ton:// deep link for TON wallets
                "ton_link": f"ton://transfer/{address}",
                # tonconnect QR value
                "qr_value": f"ton://transfer/{address}",
            }
            _cache_set(cache_key, result)
            return result
    except Exception:
        pass

    return {
        "raw_form": address,
        "bounceable": address,
        "non_bounceable": address,
        "given": address,
        "ton_link": f"ton://transfer/{address}",
        "qr_value": f"ton://transfer/{address}",
    }
