"""
Telegram Webhook endpoint.

POST /api/v1/telegram/webhook  — принимает updates от Telegram
GET  /api/v1/telegram/setup    — регистрирует webhook URL (вызвать один раз)
GET  /api/v1/telegram/info     — информация о боте и текущем webhook
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.db import get_db
from app.core.config import settings
from app.services.telegram_bot import handle_update, set_webhook, delete_webhook, _call

router = APIRouter()


def _verify_secret(x_telegram_bot_api_secret_token: Optional[str] = Header(None)) -> None:
    """
    Опциональная защита webhook через секретный токен.
    Установи TELEGRAM_WEBHOOK_SECRET в .env для защиты.
    """
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None)
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_secret),
) -> JSONResponse:
    """Принимает Telegram update и обрабатывает его."""
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Обрабатываем асинхронно — отвечаем Telegram сразу
    try:
        await handle_update(update, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Error handling update: %s", e)

    return JSONResponse({"ok": True})


@router.get("/setup")
async def setup_webhook(webhook_url: str) -> dict:
    """
    Регистрирует webhook в Telegram.
    Пример: GET /api/v1/telegram/setup?webhook_url=https://yourdomain.com/api/v1/telegram/webhook

    Нужно вызвать один раз после деплоя.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not configured")

    ok = await set_webhook(webhook_url)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to set webhook")

    return {"ok": True, "webhook_url": webhook_url}


@router.get("/info")
async def bot_info() -> dict:
    """Информация о боте и текущем webhook."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not configured")

    me = await _call("getMe")
    webhook = await _call("getWebhookInfo")

    return {
        "bot": me,
        "webhook": webhook,
        "chat_id": getattr(settings, "TELEGRAM_BOT_CHAT_ID", None),
    }


@router.delete("/webhook")
async def remove_webhook() -> dict:
    """Удалить webhook (переключиться на polling)."""
    ok = await delete_webhook()
    return {"ok": ok}
