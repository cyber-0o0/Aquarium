"""
Built-in skill implementations — unified registry.

Imports basic tools + TON DeFi tools and exposes BUILTIN_TOOLS dict
that AgentRuntime and ScenarioExecutor use to call tools by name.
"""

import httpx
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.ton_defi_tools import TON_DEFI_TOOLS


# ── Basic skills ──────────────────────────────────────────────────────────────

async def web_search(query: str) -> str:
    """Search the web via DuckDuckGo instant answer API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            data = resp.json()
            results = []
            if data.get("AbstractText"):
                results.append(data["AbstractText"])
            for topic in data.get("RelatedTopics", [])[:4]:
                if "Text" in topic:
                    results.append(topic["Text"])
            return "\n".join(results) if results else f"No results found for: {query}"
    except Exception as e:
        return f"Search error: {e}"


async def ton_balance(address: str) -> str:
    """Get TON balance for a wallet address."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://toncenter.com/api/v2/getAddressInformation",
                params={"address": address},
            )
            data = resp.json()
            if data.get("ok"):
                nano = int(data["result"]["balance"])
                ton = nano / 1_000_000_000
                return f"Balance of {address}: {ton:.4f} TON"
            return f"Could not fetch balance: {data.get('error', 'unknown error')}"
    except Exception as e:
        return f"TON balance error: {e}"


async def ton_transactions(address: str, limit: int = 10) -> str:
    """Get recent transactions for a TON wallet."""
    try:
        limit = min(int(limit), 20)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://toncenter.com/api/v2/getTransactions",
                params={"address": address, "limit": limit},
            )
            data = resp.json()
            if not data.get("ok"):
                return f"Error: {data.get('error', 'unknown')}"
            txs = data["result"]
            if not txs:
                return "No transactions found."
            lines = [f"Last {len(txs)} transactions for {address}:"]
            for tx in txs:
                ts = datetime.utcfromtimestamp(tx.get("utime", 0)).strftime("%Y-%m-%d %H:%M")
                fee = int(tx.get("fee", 0)) / 1_000_000_000
                lines.append(f"  [{ts}] fee={fee:.6f} TON  hash={tx['transaction_id']['hash'][:16]}...")
            return "\n".join(lines)
    except Exception as e:
        return f"TON transactions error: {e}"


async def crypto_price(coin_id: str) -> str:
    """Get current USD price from CoinGecko."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"},
            )
            data = resp.json()
            if coin_id not in data:
                return f"Coin '{coin_id}' not found on CoinGecko."
            price = data[coin_id]["usd"]
            change = data[coin_id].get("usd_24h_change", 0)
            return f"{coin_id}: ${price:,.4f} USD  (24h: {change:+.2f}%)"
    except Exception as e:
        return f"Price fetch error: {e}"


async def http_fetch(url: str) -> str:
    """Fetch text content from a URL."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AiHubTon-Agent/1.0"})
            text = resp.text[:3000]
            return f"Content from {url} (status {resp.status_code}):\n{text}"
    except Exception as e:
        return f"Fetch error: {e}"


async def tg_send_message(chat_id: str, text: str) -> str:
    """Send a Telegram message via bot token stored in settings."""
    try:
        from app.core.config import settings
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        if not token:
            return "Error: TELEGRAM_BOT_TOKEN not configured."
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            data = resp.json()
            if data.get("ok"):
                return f"Message sent to {chat_id}."
            return f"Telegram error: {data.get('description', 'unknown')}"
    except Exception as e:
        return f"Telegram send error: {e}"


async def get_weather(city: str) -> str:
    """Get current weather via Open-Meteo (no API key needed)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            geo = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1},
            )
            geo_data = geo.json()
            if not geo_data.get("results"):
                return f"City '{city}' not found."
            loc = geo_data["results"][0]
            lat, lon = loc["latitude"], loc["longitude"]
            name = loc["name"]
            wx = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": "true",
                    "hourly": "precipitation_probability",
                },
            )
            wx_data = wx.json()
            cw = wx_data.get("current_weather", {})
            temp = cw.get("temperature", "?")
            wind = cw.get("windspeed", "?")
            code = cw.get("weathercode", 0)
            return f"Weather in {name}: {temp}°C, wind {wind} km/h, code={code}"
    except Exception as e:
        return f"Weather error: {e}"


async def get_datetime(timezone: str = "UTC") -> str:
    """Get current date and time in given timezone."""
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return now.strftime(f"%Y-%m-%d %H:%M:%S %Z (timezone: {timezone})")
    except ZoneInfoNotFoundError:
        return f"Unknown timezone: {timezone}. Use standard names like 'UTC', 'Europe/Moscow'."


async def python_interpreter(code: str) -> str:
    """Execute Python code and return stdout. Use print() to see results."""
    import sys
    import io
    import traceback

    output_buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = output_buffer
    
    try:
        # We use a shared globals dict to allow persistence if needed, 
        # but for a simple tool, a fresh one is fine.
        exec_globals = {}
        exec(code, exec_globals)
        result = output_buffer.getvalue()
        return result if result.strip() else "Code executed successfully (no output)."
    except Exception:
        return f"Python Error:\n{traceback.format_exc()}"
    finally:
        sys.stdout = old_stdout


async def ton_set_reaction(chat_id: str, message_id: int, reaction: str = "👍") -> str:
    """Set an emoji reaction on a message."""
    from app.services.telegram_bot import set_message_reaction
    # If reaction is a dict (like Gemini sometimes sends), extract the emoji
    if isinstance(reaction, dict):
        reaction = reaction.get("emoji", "👍")
    
    success = await set_message_reaction(chat_id, message_id, reaction)
    return "Reaction set successfully." if success else "Failed to set reaction."


# ── Unified registry ──────────────────────────────────────────────────────────

BUILTIN_TOOLS: Dict[str, Any] = {
    # Basic
    "web_search":      web_search,
    "ton_balance":     ton_balance,
    "ton_transactions": ton_transactions,
    "crypto_price":    crypto_price,
    "http_fetch":      http_fetch,
    "tg_send_message": tg_send_message,
    "get_weather":     get_weather,
    "get_datetime":    get_datetime,
    "python_interpreter": python_interpreter,
    # Wallet & Personal tools
    "get_wallet_balance": ton_balance,
    "get_wallet_transactions": ton_transactions,
    "set_message_reaction": ton_set_reaction,
    # TON DeFi & ecosystem (from ton_defi_tools.py)
    **TON_DEFI_TOOLS,
}
