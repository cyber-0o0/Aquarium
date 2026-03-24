from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from urllib.parse import unquote
import sys

from app.api.v1.endpoints import (
    agents, skills, wallet, users, auth, api_keys, scenario, telegram_webhook, feed
)
from app.core.config import settings

app = FastAPI(
    title="Aquarium AI",
    description="Backend for managing autonomous AI agents on TON",
    version="1.0.0",
)


# ── Security middleware ────────────────────────────────────────────────────────

@app.middleware("http")
async def block_path_traversal(request: Request, call_next):
    raw_bytes: bytes = request.scope.get("raw_path", b"")
    raw_str = raw_bytes.decode("latin-1")
    decoded_str = unquote(raw_str)

    dangerous = ["..", "//", "\\"]
    for seq in dangerous:
        if seq in raw_str or seq in decoded_str:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

    return await call_next(request)


# ── CORS ───────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Aquarium AI API is running", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(agents.router,   prefix="/api/v1/agents",               tags=["Agents"])
app.include_router(auth.router,     prefix="/api/v1/auth",                 tags=["Auth"])
app.include_router(skills.router,   prefix="/api/v1/skills",               tags=["Skills"])
app.include_router(wallet.router,   prefix="/api/v1/wallet",               tags=["Wallet"])
app.include_router(users.router,    prefix="/api/v1/users",                tags=["Users"])
app.include_router(api_keys.router, prefix="/api/v1/api-keys",             tags=["API Keys"])

# Scenario router — nested under /agents/{id}/scenario
app.include_router(scenario.router,          prefix="/api/v1/agents/{id}/scenario", tags=["Scenario"])
app.include_router(telegram_webhook.router,  prefix="/api/v1/telegram",             tags=["Telegram"])
app.include_router(feed.router,              prefix="/api/v1/feed",                 tags=["Social Feed"])


@app.on_event("startup")
async def startup_event():
    import asyncio
    from app.services.social_service import SocialService
    from app.services.scheduler import SchedulerService
    from app.services.telegram_bot import start_polling
    from app.core.config import settings
    
    # 1. Start Autonomous Social Feed Cycle (AI agents posting/replying)
    asyncio.create_task(SocialService.run_social_cycle())

    # 2. Start Agent Scheduler (Daily activations based on cron field)
    asyncio.create_task(SchedulerService.run_scheduler())

    # 3. Start Telegram Bot Polling (if not disabled and token provided)
    if settings.TELEGRAM_BOT_TOKEN and not settings.TELEGRAM_BOT_POLLING_DISABLED:
        asyncio.create_task(start_polling())
        print("🚀 Telegram Bot polling started.")

    print("🚀 Background services (Social, Scheduler, TG Bot) started successfully.")
