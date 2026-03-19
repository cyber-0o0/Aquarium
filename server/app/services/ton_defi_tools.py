"""
Built-in TON DeFi & ecosystem skill implementations.

APIs used:
  - STON.fi REST API  (api.ston.fi)      — swap simulation, pools, assets
  - DeDust REST API   (api.dedust.io)    — pools
  - TON API v2        (tonapi.io/v2)     — NFT, Jettons, DNS, Account, Staking
  - TonCenter v2      (toncenter.com)    — balance, transactions (in skill_tools.py)

TON API rate limits:
  - Without key:  1 req/s
  - With key:     set TONAPI_KEY in .env for higher limits
"""

from __future__ import annotations

import json
from typing import Optional

import httpx

TONAPI_BASE = "https://tonapi.io/v2"
STONFI_API  = "https://api.ston.fi/v1"
DEDUST_API  = "https://api.dedust.io/v2"

# TON well-known jetton master addresses (mainnet)
KNOWN_JETTONS = {
    "usdt":  "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs",
    "usdc":  "EQB-MPwrd1G6WKNkLz_VnV6WqBDd142KMQv-g1O-8QUA3728",
    "ston":  "EQA2kCVNwVsil2EM2mB0SkXytxCqQjS4mttjDpnXmwG9T6bO",
    "not":   "EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT",
    "dogs":  "EQCvxJy4eG8hyHBFsZ7eePxrRsUQSFE_jpptRAYBmcG_DOGS",
}


def _fmt_nano(nano: int | str) -> str:
    try:
        return f"{int(nano) / 1_000_000_000:.4f} TON"
    except (ValueError, TypeError):
        return str(nano)


def _short(text: str, n: int = 2000) -> str:
    return text[:n] if len(text) > n else text


def _resolve_jetton(symbol_or_addr: str) -> str:
    lower = symbol_or_addr.strip().lower()
    return KNOWN_JETTONS.get(lower, symbol_or_addr.strip())


def _tonapi_headers() -> dict:
    """Build headers for tonapi.io, including auth if configured."""
    try:
        from app.core.config import settings
        key = getattr(settings, "TONAPI_KEY", None)
        if key:
            return {"Authorization": f"Bearer {key}"}
    except Exception:
        pass
    return {}


def _toncenter_headers() -> dict:
    try:
        from app.core.config import settings
        key = getattr(settings, "TONCENTER_API_KEY", None)
        if key:
            return {"X-API-Key": key}
    except Exception:
        pass
    return {}


# ── STON.fi ────────────────────────────────────────────────────────────────────

async def stonfi_swap_simulate(
    offer_address: str,
    ask_address: str,
    units: str,
    slippage_tolerance: str = "0.001",
) -> str:
    """
    Simulate a token swap on STON.fi DEX (read-only quote, no tx sent).

    Args:
        offer_address: address of the token to sell (or 'ton' for native TON)
        ask_address:   address of the token to buy  (or 'ton' for native TON)
        units:         amount in base units (nanotons for TON)
        slippage_tolerance: e.g. '0.001' = 0.1% (default)
    """
    offer = _resolve_jetton(offer_address)
    ask   = _resolve_jetton(ask_address)
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.post(
                f"{STONFI_API}/swap/simulate",
                json={
                    "offer_address": offer,
                    "ask_address": ask,
                    "units": str(units),
                    "slippage_tolerance": str(slippage_tolerance),
                },
            )
        if r.status_code != 200:
            return f"STON.fi simulate error {r.status_code}: {_short(r.text)}"
        d = r.json()
        return (
            f"STON.fi swap simulation:\n"
            f"  Offer:        {d.get('offer_units', '?')} units of {offer[:24]}…\n"
            f"  Expected out: {d.get('ask_units', '?')} units\n"
            f"  Min received: {d.get('min_ask_units', '?')} units (slippage {slippage_tolerance})\n"
            f"  Fee:          {d.get('fee_units', '?')} units\n"
            f"  Price impact: {d.get('price_impact', '?')}\n"
            f"  Router:       {d.get('router_address', '?')[:24]}…"
        )
    except Exception as e:
        return f"STON.fi simulate error: {e}"


async def stonfi_assets(search: str = "", limit: int = 20) -> str:
    """
    List tradeable assets on STON.fi. Optionally filter by name/symbol.

    Args:
        search: filter string (e.g. 'USDT', 'TON')
        limit:  max results (default 20, max 50)
    """
    limit = min(int(limit), 50)
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.get(f"{STONFI_API}/assets")
        if r.status_code != 200:
            return f"STON.fi assets error {r.status_code}: {_short(r.text)}"
        assets = r.json().get("asset_list", [])
        if search:
            s = search.lower()
            assets = [a for a in assets
                      if s in (a.get("symbol") or "").lower()
                      or s in (a.get("display_name") or "").lower()]
        assets = assets[:limit]
        lines = [f"STON.fi assets ({len(assets)} results):"]
        for a in assets:
            symbol = a.get("symbol", "?")
            name   = a.get("display_name", "")
            addr   = a.get("contract_address", "?")
            price  = a.get("dex_price_usd") or a.get("third_party_price_usd") or "?"
            lines.append(f"  {symbol:10s} {name:20s}  ${price}  {addr[:20]}…")
        return "\n".join(lines)
    except Exception as e:
        return f"STON.fi assets error: {e}"


async def stonfi_pool_info(pool_address: str) -> str:
    """
    Get STON.fi liquidity pool details.

    Args:
        pool_address: TON address of the STON.fi pool
    """
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.get(f"{STONFI_API}/pools/{pool_address}")
        if r.status_code != 200:
            return f"STON.fi pool error {r.status_code}: {_short(r.text)}"
        d = r.json().get("pool", r.json())
        return (
            f"STON.fi pool {pool_address[:16]}…\n"
            f"  Token0:   {d.get('token0_address', '?')[:24]}…  reserve={d.get('reserve0', '?')}\n"
            f"  Token1:   {d.get('token1_address', '?')[:24]}…  reserve={d.get('reserve1', '?')}\n"
            f"  LP supply:{d.get('lp_total_supply_wc', '?')}"
        )
    except Exception as e:
        return f"STON.fi pool error: {e}"


# ── DeDust ─────────────────────────────────────────────────────────────────────

async def dedust_pools(asset_address: str = "", limit: int = 10) -> str:
    """
    Get top liquidity pools from DeDust DEX.

    Args:
        asset_address: optional — filter pools containing this jetton address or symbol
        limit:         max pools (default 10)
    """
    limit = min(int(limit), 30)
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.get(f"{DEDUST_API}/pools")
        if r.status_code != 200:
            return f"DeDust pools error {r.status_code}: {_short(r.text)}"
        pools = r.json()
        if asset_address:
            addr = _resolve_jetton(asset_address).lower()
            pools = [p for p in pools
                     if any(addr in (a.get("address", "").lower()) for a in p.get("assets", []))]
        pools = pools[:limit]
        lines = [f"DeDust pools ({len(pools)}):"]
        for p in pools:
            assets = p.get("assets", [])
            a0 = assets[0].get("metadata", {}).get("symbol", assets[0].get("address", "?")[:8]) if assets else "?"
            a1 = assets[1].get("metadata", {}).get("symbol", assets[1].get("address", "?")[:8]) if len(assets) > 1 else "?"
            tvl  = p.get("totalSupply", "?")
            addr = p.get("address", "?")
            lines.append(f"  {a0}/{a1:10s}  TVL={tvl}  {addr[:20]}…")
        return "\n".join(lines)
    except Exception as e:
        return f"DeDust pools error: {e}"


# ── TON DNS ────────────────────────────────────────────────────────────────────

async def ton_dns_resolve(domain: str) -> str:
    """
    Resolve a TON DNS domain to its wallet address and linked resources.

    Args:
        domain: TON DNS domain, e.g. 'foundation.ton'
    """
    domain = domain.strip().rstrip(".")
    try:
        async with httpx.AsyncClient(timeout=12, headers=_tonapi_headers()) as c:
            r = await c.get(f"{TONAPI_BASE}/dns/{domain}/resolve")
        if r.status_code == 404:
            return f"Domain '{domain}' not found or not registered."
        if r.status_code != 200:
            return f"TON DNS resolve error {r.status_code}: {_short(r.text)}"
        d = r.json()
        wallet   = d.get("wallet", {})
        address  = wallet.get("address", "—")
        is_scam  = wallet.get("is_scam", False)
        nft_addr = d.get("nft_address") or "—"
        lines = [
            f"TON DNS: {domain}",
            f"  Wallet address: {address}",
            f"  NFT address:    {nft_addr}",
        ]
        if is_scam:
            lines.append("  ⚠️  MARKED AS SCAM")
        return "\n".join(lines)
    except Exception as e:
        return f"TON DNS resolve error: {e}"


async def ton_dns_reverse(address: str) -> str:
    """
    Reverse-lookup a TON wallet address to find its TON DNS domain.

    Args:
        address: TON wallet address
    """
    try:
        async with httpx.AsyncClient(timeout=12, headers=_tonapi_headers()) as c:
            r = await c.get(f"{TONAPI_BASE}/accounts/{address}/dns/backresolve")
        if r.status_code == 404:
            return f"No TON DNS domain linked to address {address}."
        if r.status_code != 200:
            return f"TON DNS reverse error {r.status_code}: {_short(r.text)}"
        domains = r.json().get("domains", [])
        if not domains:
            return f"No domains found for address {address}."
        return f"TON DNS reverse for {address}:\n  Domains: {', '.join(domains)}"
    except Exception as e:
        return f"TON DNS reverse error: {e}"


# ── NFTs ───────────────────────────────────────────────────────────────────────

async def nft_item_info(nft_address: str) -> str:
    """
    Get detailed information about a specific TON NFT item.

    Args:
        nft_address: TON address of the NFT item contract
    """
    try:
        async with httpx.AsyncClient(timeout=12, headers=_tonapi_headers()) as c:
            r = await c.get(f"{TONAPI_BASE}/nfts/{nft_address}")
        if r.status_code == 404:
            return f"NFT {nft_address} not found."
        if r.status_code != 200:
            return f"NFT item error {r.status_code}: {_short(r.text)}"
        d    = r.json()
        meta = d.get("metadata", {})
        coll = d.get("collection", {})
        lines = [
            f"NFT: {meta.get('name', d.get('dns', 'Unnamed'))}",
            f"  Owner:      {d.get('owner', {}).get('address', '—')}",
            f"  Collection: {coll.get('name', '—')} ({coll.get('address', '—')[:20]}…)",
            f"  Image:      {meta.get('image', '—')}",
        ]
        desc = (meta.get("description") or "")[:200]
        if desc:
            lines.append(f"  Description: {desc}")
        approved = d.get("approved_by", [])
        if approved:
            lines.append(f"  Approved by: {', '.join(approved)}")
        return "\n".join(lines)
    except Exception as e:
        return f"NFT item info error: {e}"


async def nft_collection_info(collection_address: str) -> str:
    """
    Get information about a TON NFT collection.

    Args:
        collection_address: TON address of the NFT collection contract
    """
    try:
        async with httpx.AsyncClient(timeout=12, headers=_tonapi_headers()) as c:
            r = await c.get(f"{TONAPI_BASE}/nfts/collections/{collection_address}")
        if r.status_code == 404:
            return f"Collection {collection_address} not found."
        if r.status_code != 200:
            return f"NFT collection error {r.status_code}: {_short(r.text)}"
        d    = r.json()
        meta = d.get("metadata", {})
        lines = [
            f"NFT Collection: {meta.get('name', 'Unnamed')}",
            f"  Address:     {collection_address}",
            f"  Owner:       {d.get('owner', {}).get('address', '—')}",
            f"  Items count: {d.get('next_item_index', '?')}",
        ]
        desc = (meta.get("description") or "")[:200]
        if desc:
            lines.append(f"  Description: {desc}")
        approved = d.get("approved_by", [])
        if approved:
            lines.append(f"  Approved by: {', '.join(approved)}")
        return "\n".join(lines)
    except Exception as e:
        return f"NFT collection error: {e}"


# ── Jettons ────────────────────────────────────────────────────────────────────

async def jetton_info(jetton_address: str) -> str:
    """
    Get information about a TON Jetton (fungible token).

    Args:
        jetton_address: master contract address or symbol (usdt, usdc, ston, not, dogs)
    """
    addr = _resolve_jetton(jetton_address)
    try:
        async with httpx.AsyncClient(timeout=12, headers=_tonapi_headers()) as c:
            r = await c.get(f"{TONAPI_BASE}/jettons/{addr}")
        if r.status_code == 404:
            return f"Jetton '{jetton_address}' not found."
        if r.status_code != 200:
            return f"Jetton info error {r.status_code}: {_short(r.text)}"
        d    = r.json()
        meta = d.get("metadata", {})
        lines = [
            f"Jetton: {meta.get('name', 'Unnamed')} ({meta.get('symbol', '?')})",
            f"  Master address: {addr}",
            f"  Decimals:       {meta.get('decimals', 9)}",
            f"  Total supply:   {d.get('total_supply', '?')}",
            f"  Holders:        {d.get('holders_count', '?')}",
            f"  Mintable:       {d.get('mintable', False)}",
        ]
        desc = (meta.get("description") or "")[:200]
        if desc:
            lines.append(f"  Description: {desc}")
        approved = d.get("approved_by", [])
        if approved:
            lines.append(f"  Approved by: {', '.join(approved)}")
        return "\n".join(lines)
    except Exception as e:
        return f"Jetton info error: {e}"


async def jetton_holders(jetton_address: str, limit: int = 10) -> str:
    """
    List top holders of a TON Jetton.

    Args:
        jetton_address: master contract address or symbol (usdt, usdc, ston)
        limit:          number of top holders (default 10, max 20)
    """
    addr  = _resolve_jetton(jetton_address)
    limit = min(int(limit), 20)
    try:
        async with httpx.AsyncClient(timeout=12, headers=_tonapi_headers()) as c:
            r = await c.get(f"{TONAPI_BASE}/jettons/{addr}/holders", params={"limit": limit})
        if r.status_code != 200:
            return f"Jetton holders error {r.status_code}: {_short(r.text)}"
        holders = r.json().get("addresses", [])
        if not holders:
            return f"No holders data for jetton {jetton_address}."
        lines = [f"Top {len(holders)} holders of {jetton_address}:"]
        for i, h in enumerate(holders, 1):
            owner = h.get("owner", {}).get("address", "?")
            bal   = h.get("balance", "?")
            lines.append(f"  {i:2d}. {owner}  balance={bal}")
        return "\n".join(lines)
    except Exception as e:
        return f"Jetton holders error: {e}"


# ── TON Account ────────────────────────────────────────────────────────────────

async def ton_account_info(address: str) -> str:
    """
    Get full account info: balance, status, interfaces, last activity.

    Args:
        address: TON wallet or contract address
    """
    try:
        async with httpx.AsyncClient(timeout=12, headers=_tonapi_headers()) as c:
            r = await c.get(f"{TONAPI_BASE}/accounts/{address}")
        if r.status_code == 404:
            return f"Account {address} not found."
        if r.status_code != 200:
            return f"TON account error {r.status_code}: {_short(r.text)}"
        d = r.json()
        from datetime import datetime
        last_tx = d.get("last_activity", 0)
        last_dt = datetime.utcfromtimestamp(last_tx).strftime("%Y-%m-%d %H:%M UTC") if last_tx else "never"
        lines = [
            f"TON Account: {d.get('name') or d.get('dns') or address[:20]}",
            f"  Address:       {address}",
            f"  Balance:       {_fmt_nano(d.get('balance', 0))}",
            f"  Status:        {d.get('status', '?')}",
            f"  Interfaces:    {', '.join(d.get('interfaces', [])) or '—'}",
            f"  Last activity: {last_dt}",
        ]
        if d.get("is_scam"):
            lines.append("  ⚠️  MARKED AS SCAM")
        return "\n".join(lines)
    except Exception as e:
        return f"TON account error: {e}"


# ── Staking ────────────────────────────────────────────────────────────────────

async def ton_staking_pools(available_for: str = "", limit: int = 10) -> str:
    """
    Get TON liquid staking pools with APY and TVL.

    Args:
        available_for: optional wallet address for personalized info
        limit:         max pools (default 10)
    """
    limit = min(int(limit), 30)
    try:
        params = {}
        if available_for:
            params["available_for"] = available_for
        async with httpx.AsyncClient(timeout=12, headers=_tonapi_headers()) as c:
            r = await c.get(f"{TONAPI_BASE}/staking/pools", params=params)
        if r.status_code != 200:
            return f"Staking pools error {r.status_code}: {_short(r.text)}"
        pools = r.json().get("pools", [])[:limit]
        lines = [f"TON staking pools ({len(pools)}):"]
        for p in pools:
            name      = p.get("name", "?")
            apy       = p.get("apy", "?")
            min_stake = _fmt_nano(p.get("min_stake", 0))
            total     = _fmt_nano(p.get("total_amount", 0))
            addr      = p.get("address", "?")
            lines.append(f"  {name:25s}  APY={apy}%  min={min_stake}  TVL={total}  {addr[:16]}…")
        return "\n".join(lines)
    except Exception as e:
        return f"TON staking pools error: {e}"


# ── Registry ──────────────────────────────────────────────────────────────────

TON_DEFI_TOOLS = {
    "stonfi_swap_simulate": stonfi_swap_simulate,
    "stonfi_assets":        stonfi_assets,
    "stonfi_pool_info":     stonfi_pool_info,
    "dedust_pools":         dedust_pools,
    "ton_dns_resolve":      ton_dns_resolve,
    "ton_dns_reverse":      ton_dns_reverse,
    "nft_item_info":        nft_item_info,
    "nft_collection_info":  nft_collection_info,
    "jetton_info":          jetton_info,
    "jetton_holders":       jetton_holders,
    "ton_account_info":     ton_account_info,
    "ton_staking_pools":    ton_staking_pools,
}
