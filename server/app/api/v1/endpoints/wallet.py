"""
Wallet endpoints — real TON blockchain data for the authenticated user.

GET  /wallet/overview        — TON balance + all jettons + USD totals
GET  /wallet/balance         — TON balance only (fast)
GET  /wallet/jettons         — jetton (token) balances
GET  /wallet/transactions    — paginated tx history
GET  /wallet/deposit         — deposit address info + QR deep-link
POST /wallet/sync            — force re-fetch (clears cache for this address)

All endpoints require an authenticated user with a connected wallet_address.
If wallet_address is null, returns 404 with a clear message.
"""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.user import User as UserModel
from app.schemas.wallet import (
    WalletBalance, WalletOverview, JettonBalance,
    Transaction, TransactionHistory, DepositInfo,
)
from app.services import wallet_service

router = APIRouter()


def _require_wallet(user: UserModel) -> str:
    """Return wallet address or raise 404."""
    if not user.wallet_address:
        raise HTTPException(
            status_code=404,
            detail="No wallet connected. Use TON Connect to link a wallet first.",
        )
    return user.wallet_address


# ── Overview (balance + tokens) ────────────────────────────────────────────────

@router.get("/overview", response_model=WalletOverview)
async def get_wallet_overview(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Full wallet overview: TON balance, all token balances, total USD value.
    Results are cached 30s to avoid rate limiting.
    """
    address = _require_wallet(current_user)

    ton_data, jettons_data = await _gather(
        wallet_service.get_wallet_balance(address),
        wallet_service.get_jetton_balances(address),
    )
    network_name, _, _ = wallet_service._get_network_config()

    ton = WalletBalance(**ton_data)
    jettons = [JettonBalance(**j) for j in jettons_data]

    jetton_usd = sum(j.usd_value for j in jettons if j.usd_value is not None)
    total_usd = round(ton.usd_value + jetton_usd, 2)

    network_name, _, _ = wallet_service._get_network_config()
    return WalletOverview(
        ton=ton,
        jettons=jettons,
        total_usd=total_usd,
        has_wallet=True,
        network=network_name,
    )


@router.get("/balance", response_model=WalletBalance)
async def get_balance(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Get TON balance for the connected wallet."""
    address = _require_wallet(current_user)
    data = await wallet_service.get_wallet_balance(address)
    return WalletBalance(**data)


@router.get("/jettons", response_model=List[JettonBalance])
async def get_jettons(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Get all jetton (token) balances for the connected wallet."""
    address = _require_wallet(current_user)
    data = await wallet_service.get_jetton_balances(address)
    return [JettonBalance(**j) for j in data]


# ── Transaction history ────────────────────────────────────────────────────────

@router.get("/transactions", response_model=TransactionHistory)
async def get_transactions(
    current_user: UserModel = Depends(deps.get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
    before_lt: Optional[int] = Query(default=None, description="Pagination cursor (lt of last tx)"),
) -> Any:
    """
    Get paginated transaction history from the TON blockchain.
    Use `before_lt` from the last transaction to fetch the next page.
    """
    address = _require_wallet(current_user)
    txs_data = await wallet_service.get_transaction_history(
        address, limit=limit + 1, before_lt=before_lt
    )

    has_more = len(txs_data) > limit
    if has_more:
        txs_data = txs_data[:limit]

    transactions = [Transaction(**tx) for tx in txs_data]
    next_lt = transactions[-1].lt if has_more and transactions else None

    return TransactionHistory(
        transactions=transactions,
        address=address,
        has_more=has_more,
        next_lt=next_lt,
    )


# ── Deposit info ───────────────────────────────────────────────────────────────

@router.get("/deposit", response_model=DepositInfo)
async def get_deposit_info(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Get deposit address info: both bounceable and non-bounceable formats,
    plus a ton:// deep-link for QR code display.
    """
    address = _require_wallet(current_user)
    data = await wallet_service.get_deposit_info(address)
    return DepositInfo(**data)


# ── Address info (public, no auth) ────────────────────────────────────────────

@router.get("/address/{address}", response_model=WalletBalance)
async def get_address_balance(address: str) -> Any:
    """
    Get TON balance for any wallet address (no auth required).
    Useful for showing balances of other wallets (e.g. agent wallets).
    """
    _validate_address(address)
    data = await wallet_service.get_wallet_balance(address)
    return WalletBalance(**data)


# ── Sync (cache bust) ──────────────────────────────────────────────────────────

@router.post("/sync", status_code=200)
async def sync_wallet(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Force a fresh fetch from the blockchain (clears 30s cache for this address).
    Call after sending a transaction to see updated balance immediately.
    """
    address = _require_wallet(current_user)
    # Clear all cache entries for this address
    from app.services.wallet_service import _cache
    keys_to_delete = [k for k in list(_cache.keys()) if address.lower() in k.lower()]
    for key in keys_to_delete:
        _cache.pop(key, None)

    # Re-fetch fresh data
    ton_data = await wallet_service.get_wallet_balance(address)
    return {"status": "synced", "address": address, "ton_balance": ton_data.get("ton_balance")}


# ── TON price ──────────────────────────────────────────────────────────────────

@router.get("/price")
async def get_ton_price() -> Any:
    """Get current TON/USD price. No auth required."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "the-open-network",
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                },
            )
        if r.status_code == 200:
            data = r.json().get("the-open-network", {})
            return {
                "usd": data.get("usd", 0),
                "usd_24h_change": data.get("usd_24h_change", 0),
                "usd_market_cap": data.get("usd_market_cap", 0),
            }
    except Exception as e:
        pass
    return {"usd": 0, "usd_24h_change": 0, "usd_market_cap": 0, "error": "price unavailable"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _validate_address(address: str) -> None:
    """Basic TON address validation."""
    addr = address.strip()
    if len(addr) < 10 or len(addr) > 100:
        raise HTTPException(status_code=422, detail="Invalid TON address")
    # TON addresses are base64url or raw hex
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_+/=:0")
    if not all(c in allowed for c in addr):
        raise HTTPException(status_code=422, detail="Invalid TON address characters")


import asyncio

async def _gather(*coros):
    """Run coroutines in parallel, returning results in order."""
    return await asyncio.gather(*coros, return_exceptions=False)
