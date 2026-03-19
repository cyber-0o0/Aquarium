"""
Seed built-in skills into the database.
Run: python -m app.seeds.skills
"""
import asyncio
from app.core.db import AsyncSessionLocal
from app.models.skill import Skill
import app.models.agent
import app.models.feed_post
import app.models.task
import app.models.user
import app.models.user_api_key
import app.models.transaction

BUILTIN_SKILLS = [

    # ── Search ────────────────────────────────────────────────────────────────
    {
        "name": "Web Search",
        "slug": "web-search",
        "description": "Search the live web in real-time using DuckDuckGo. Returns top results with titles, snippets, and URLs.",
        "category": "search",
        "color": "#10B981",
        "manifest": {
            "tool_name": "web_search",
            "description": "Search the web for up-to-date information",
            "parameters": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
            "implementation": "builtin",
        },
    },

    # ── TON Basic ─────────────────────────────────────────────────────────────
    {
        "name": "TON Balance",
        "slug": "ton-balance",
        "description": "Check the TON balance of any wallet address on the TON blockchain via TonCenter API.",
        "category": "ton",
        "color": "#0088CC",
        "manifest": {
            "tool_name": "ton_balance",
            "description": "Get TON balance for a wallet address",
            "parameters": {"address": {"type": "string", "description": "TON wallet address"}},
            "required": ["address"],
            "implementation": "builtin",
        },
    },
    {
        "name": "TON Transactions",
        "slug": "ton-transactions",
        "description": "Fetch recent transactions for a TON wallet. Useful for monitoring wallet activity.",
        "category": "ton",
        "color": "#0088CC",
        "manifest": {
            "tool_name": "ton_transactions",
            "description": "Get recent transactions for a TON wallet address",
            "parameters": {
                "address": {"type": "string", "description": "TON wallet address"},
                "limit": {"type": "integer", "description": "Number of transactions (max 20)", "default": 10},
            },
            "required": ["address"],
            "implementation": "builtin",
        },
    },
    {
        "name": "TON Account Info",
        "slug": "ton-account-info",
        "description": "Get full account details for any TON address: balance, status, contract interfaces, last activity time.",
        "category": "ton",
        "color": "#0088CC",
        "manifest": {
            "tool_name": "ton_account_info",
            "description": "Get full account information for a TON address",
            "parameters": {"address": {"type": "string", "description": "TON wallet or contract address"}},
            "required": ["address"],
            "implementation": "builtin",
        },
    },

    # ── TON DNS ───────────────────────────────────────────────────────────────
    {
        "name": "TON DNS Resolve",
        "slug": "ton-dns-resolve",
        "description": "Resolve a TON DNS domain (e.g. foundation.ton) to its wallet address and linked resources.",
        "category": "ton",
        "color": "#1A73E8",
        "manifest": {
            "tool_name": "ton_dns_resolve",
            "description": "Resolve a TON DNS domain to its wallet address",
            "parameters": {"domain": {"type": "string", "description": "TON DNS domain, e.g. 'foundation.ton'"}},
            "required": ["domain"],
            "implementation": "builtin",
        },
    },
    {
        "name": "TON DNS Reverse",
        "slug": "ton-dns-reverse",
        "description": "Reverse-lookup a TON wallet address to find its associated TON DNS domain name.",
        "category": "ton",
        "color": "#1A73E8",
        "manifest": {
            "tool_name": "ton_dns_reverse",
            "description": "Reverse-lookup a TON address to find its DNS domain",
            "parameters": {"address": {"type": "string", "description": "TON wallet address"}},
            "required": ["address"],
            "implementation": "builtin",
        },
    },

    # ── NFTs ──────────────────────────────────────────────────────────────────
    {
        "name": "NFT Item Info",
        "slug": "nft-item-info",
        "description": "Get details about a specific TON NFT: name, owner, collection, image, metadata.",
        "category": "ton",
        "color": "#7C3AED",
        "manifest": {
            "tool_name": "nft_item_info",
            "description": "Get info about a TON NFT item",
            "parameters": {"nft_address": {"type": "string", "description": "TON address of the NFT item"}},
            "required": ["nft_address"],
            "implementation": "builtin",
        },
    },
    {
        "name": "NFT Collection Info",
        "slug": "nft-collection-info",
        "description": "Get information about a TON NFT collection: name, owner, total items, description.",
        "category": "ton",
        "color": "#7C3AED",
        "manifest": {
            "tool_name": "nft_collection_info",
            "description": "Get info about a TON NFT collection",
            "parameters": {"collection_address": {"type": "string", "description": "TON address of the NFT collection"}},
            "required": ["collection_address"],
            "implementation": "builtin",
        },
    },

    # ── Jettons ───────────────────────────────────────────────────────────────
    {
        "name": "Jetton Info",
        "slug": "jetton-info",
        "description": "Get information about any TON Jetton (fungible token): name, symbol, supply, holders count, price. Supports shortcuts: usdt, usdc, ston.",
        "category": "defi",
        "color": "#F59E0B",
        "manifest": {
            "tool_name": "jetton_info",
            "description": "Get info about a TON Jetton token",
            "parameters": {"jetton_address": {"type": "string", "description": "Jetton master address or symbol (usdt/usdc/ston)"}},
            "required": ["jetton_address"],
            "implementation": "builtin",
        },
    },
    {
        "name": "Jetton Holders",
        "slug": "jetton-holders",
        "description": "List top holders of any TON Jetton. Useful for whale tracking and distribution analysis.",
        "category": "defi",
        "color": "#F59E0B",
        "manifest": {
            "tool_name": "jetton_holders",
            "description": "List top holders of a TON Jetton",
            "parameters": {
                "jetton_address": {"type": "string", "description": "Jetton master address or symbol"},
                "limit": {"type": "integer", "description": "Number of top holders (max 20)", "default": 10},
            },
            "required": ["jetton_address"],
            "implementation": "builtin",
        },
    },

    # ── STON.fi ───────────────────────────────────────────────────────────────
    {
        "name": "STON.fi Swap Simulate",
        "slug": "stonfi-swap-simulate",
        "description": "Simulate a token swap on STON.fi DEX — get expected output, fees, min received, and price impact without executing any transaction.",
        "category": "defi",
        "color": "#00B2FF",
        "manifest": {
            "tool_name": "stonfi_swap_simulate",
            "description": "Simulate a token swap on STON.fi and get a quote",
            "parameters": {
                "offer_address": {"type": "string", "description": "Token to sell (address or 'ton')"},
                "ask_address":   {"type": "string", "description": "Token to buy (address or 'ton')"},
                "units":         {"type": "string", "description": "Amount in base units (nanotons for TON)"},
                "slippage_tolerance": {"type": "string", "description": "Slippage tolerance e.g. '0.001' = 0.1%", "default": "0.001"},
            },
            "required": ["offer_address", "ask_address", "units"],
            "implementation": "builtin",
        },
    },
    {
        "name": "STON.fi Assets",
        "slug": "stonfi-assets",
        "description": "List tradeable tokens on STON.fi DEX with prices. Optional search by name or symbol.",
        "category": "defi",
        "color": "#00B2FF",
        "manifest": {
            "tool_name": "stonfi_assets",
            "description": "List or search tradeable assets on STON.fi",
            "parameters": {
                "search": {"type": "string", "description": "Optional filter by name or symbol", "default": ""},
                "limit":  {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
            "required": [],
            "implementation": "builtin",
        },
    },
    {
        "name": "STON.fi Pool Info",
        "slug": "stonfi-pool-info",
        "description": "Get STON.fi liquidity pool details: token pair, reserves, and LP supply.",
        "category": "defi",
        "color": "#00B2FF",
        "manifest": {
            "tool_name": "stonfi_pool_info",
            "description": "Get STON.fi liquidity pool details",
            "parameters": {"pool_address": {"type": "string", "description": "TON address of the STON.fi pool"}},
            "required": ["pool_address"],
            "implementation": "builtin",
        },
    },

    # ── DeDust ────────────────────────────────────────────────────────────────
    {
        "name": "DeDust Pools",
        "slug": "dedust-pools",
        "description": "Get top liquidity pools from DeDust DEX with TVL and token pair info. Optionally filter by asset.",
        "category": "defi",
        "color": "#E84142",
        "manifest": {
            "tool_name": "dedust_pools",
            "description": "List top DeDust DEX liquidity pools",
            "parameters": {
                "asset_address": {"type": "string", "description": "Optional: filter by jetton address or symbol", "default": ""},
                "limit": {"type": "integer", "description": "Max pools to show (default 10)", "default": 10},
            },
            "required": [],
            "implementation": "builtin",
        },
    },

    # ── Staking ───────────────────────────────────────────────────────────────
    {
        "name": "TON Staking Pools",
        "slug": "ton-staking-pools",
        "description": "Get TON liquid staking pools with APY, minimum stake, and TVL. Supports Tonstakers, Bemo, and more.",
        "category": "defi",
        "color": "#16A34A",
        "manifest": {
            "tool_name": "ton_staking_pools",
            "description": "Get TON liquid staking pools with APY info",
            "parameters": {
                "available_for": {"type": "string", "description": "Optional wallet address for personalized info", "default": ""},
                "limit": {"type": "integer", "description": "Max pools to show (default 10)", "default": 10},
            },
            "required": [],
            "implementation": "builtin",
        },
    },

    # ── Crypto price ──────────────────────────────────────────────────────────
    {
        "name": "Crypto Price",
        "slug": "crypto-price",
        "description": "Get current price of any cryptocurrency from CoinGecko. Supports 10,000+ coins including TON.",
        "category": "defi",
        "color": "#F59E0B",
        "manifest": {
            "tool_name": "crypto_price",
            "description": "Get current USD price for a cryptocurrency",
            "parameters": {"coin_id": {"type": "string", "description": "CoinGecko coin id, e.g. 'the-open-network' for TON"}},
            "required": ["coin_id"],
            "implementation": "builtin",
        },
    },

    # ── Utility ───────────────────────────────────────────────────────────────
    {
        "name": "HTTP Fetch",
        "slug": "http-fetch",
        "description": "Fetch content from any public URL. Returns page text. Useful for monitoring websites or APIs.",
        "category": "utility",
        "color": "#8B5CF6",
        "manifest": {
            "tool_name": "http_fetch",
            "description": "Fetch text content from a URL",
            "parameters": {"url": {"type": "string", "description": "URL to fetch"}},
            "required": ["url"],
            "implementation": "builtin",
        },
    },
    {
        "name": "Send Telegram Message",
        "slug": "tg-send-message",
        "description": "Send a Telegram message to a chat or user. Requires TELEGRAM_BOT_TOKEN in agent settings.",
        "category": "telegram",
        "color": "#2AABEE",
        "manifest": {
            "tool_name": "tg_send_message",
            "description": "Send a message via Telegram bot",
            "parameters": {
                "chat_id": {"type": "string", "description": "Telegram chat ID or username"},
                "text": {"type": "string", "description": "Message text to send"},
            },
            "required": ["chat_id", "text"],
            "implementation": "builtin",
        },
    },
    {
        "name": "Weather",
        "slug": "weather",
        "description": "Get current weather and forecast for any city using Open-Meteo (free, no API key needed).",
        "category": "data",
        "color": "#06B6D4",
        "manifest": {
            "tool_name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
            "implementation": "builtin",
        },
    },
    {
        "name": "Date & Time",
        "slug": "datetime",
        "description": "Get the current date and time in any timezone. Useful for scheduling logic inside agents.",
        "category": "utility",
        "color": "#64748B",
        "manifest": {
            "tool_name": "get_datetime",
            "description": "Get the current date and time",
            "parameters": {
                "timezone": {"type": "string", "description": "Timezone name, e.g. 'UTC' or 'Europe/Moscow'", "default": "UTC"},
            },
            "required": [],
            "implementation": "builtin",
        },
    },
    {
        "name": "Python Interpreter",
        "slug": "python-interpreter",
        "description": "Execute arbitrary Python code and see the output. High performance, direct access to basic libs. Use carefully.",
        "category": "developer",
        "color": "#3776AB",
        "manifest": {
            "tool_name": "python_interpreter",
            "description": "Execute Python code and return stdout. Use print() for output.",
            "parameters": {"code": {"type": "string", "description": "Python source code to run"}},
            "required": ["code"],
            "implementation": "builtin",
        },
    },
]


async def seed():
    async with AsyncSessionLocal() as db:
        for data in BUILTIN_SKILLS:
            from sqlalchemy.future import select
            existing = await db.execute(select(Skill).where(Skill.slug == data["slug"]))
            if existing.scalars().first():
                print(f"  skip (exists): {data['slug']}")
                continue
            skill = Skill(**data, author_id="system", review_status="approved")
            db.add(skill)
            print(f"  added: {data['slug']}")
        await db.commit()
        print(f"\n✅ Skills seeded. Total: {len(BUILTIN_SKILLS)}")


if __name__ == "__main__":
    asyncio.run(seed())
