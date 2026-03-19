from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta, UTC
import secrets
import hmac
import hashlib
import json
import logging
from urllib.parse import parse_qsl, unquote_plus
from typing import Optional, Any

from app.core import security
from app.core.db import get_db
from app.models.user import User
from app.schemas.token import Token
from app.core.config import settings
from app.api import deps

from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class TelegramAuth(BaseModel):
    init_data: str

class TonAuth(BaseModel):
    wallet_address: str
    signature: str
    nonce: str

# Simple in-memory storage for nonces (should use Redis in production)
NONCES = {}


def verify_telegram_webapp_data(init_data: str, bot_token: Optional[str]) -> bool:
    """
    Verify Telegram Mini App initData signature.
    Docs: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not bot_token:
        logger.error("[TG verify] No bot token configured")
        return False

    data_raw = dict(parse_qsl(init_data, keep_blank_values=True))
    logger.info(
        "[TG verify] Verifying initData | token prefix: %s... | keys: %s",
        bot_token[:10],
        sorted(data_raw.keys()),
    )

    try:
        data = dict(data_raw)
        hash_str = data.pop("hash", None)

        if not hash_str:
            logger.error("[TG verify] No 'hash' field in initData")
            return False

        # Build data-check-string: sorted key=value pairs joined by \n
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(data.items())
        )
        logger.debug("[TG verify] data_check_string: %s", repr(data_check_string[:120]))

        # HMAC-SHA256(key=HMAC-SHA256(key="WebAppData", data=bot_token), data=data_check_string)
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        match = hmac.compare_digest(calculated_hash, hash_str)
        if match:
            logger.info("[TG verify] ✅ Hash verified OK")
        else:
            logger.error(
                "[TG verify] ❌ Hash MISMATCH | received: %s... | calculated: %s...",
                hash_str[:20],
                calculated_hash[:20],
            )
            logger.error("[TG verify] Full data_check_string: %s", repr(data_check_string))
        return match

    except Exception as exc:
        logger.exception("[TG verify] Unexpected exception: %s", exc)
        return False

@router.get("/nonce")
async def get_nonce():
    nonce = secrets.token_hex(16)
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    NONCES[nonce] = expires_at
    return {"nonce": nonce, "expires_at": expires_at.isoformat()}

@router.post("/telegram", response_model=Token)
async def telegram_auth(
    auth_in: TelegramAuth,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user using Telegram Mini App initData.
    """
    init_data = auth_in.init_data
    logger.info("[auth/telegram] initData prefix: %s", init_data[:100])
    logger.info("[auth/telegram] BOT_TOKEN configured: %s", bool(settings.TELEGRAM_BOT_TOKEN))

    if not verify_telegram_webapp_data(init_data, settings.TELEGRAM_BOT_TOKEN):
        logger.error("[auth/telegram] Verification failed — returning 400")
        raise HTTPException(status_code=400, detail="Invalid Telegram data")

    # Parse telegram user data from initData
    # parse_qsl handles URL-decoding automatically, so user JSON is already decoded
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    logger.info("[auth/telegram] Parsed keys: %s", list(data.keys()))
    user_data_json = data.get('user')
    if not user_data_json:
        logger.error("[auth/telegram] No 'user' key in initData. Keys: %s", list(data.keys()))
        raise HTTPException(status_code=400, detail="User data missing in initData")
    
    try:
        user_data = json.loads(user_data_json)
    except json.JSONDecodeError:
        # Try unquoting once more in case of double-encoding
        user_data = json.loads(unquote_plus(user_data_json))
    tg_id = str(user_data.get('id'))
    username = user_data.get('username')
    
    if not tg_id:
        raise HTTPException(status_code=400, detail="Telegram user ID missing")

    # Get or create user
    try:
        result = await db.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalars().first()
        
        if not user:
            user = User(telegram_id=tg_id, username=username)
            db.add(user)
        else:
            # Update username if changed
            if username and user.username != username:
                user.username = username
                
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("DB error during telegram auth: %s", e)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/ton-connect", response_model=Token)
async def ton_connect(
    auth_in: TonAuth,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(deps.get_current_user_optional)
):
    """
    Connect TON wallet. If user is already authenticated (via Telegram), 
    links the wallet to their account. Otherwise, performs wallet-based login.
    """
    wallet_address = auth_in.wallet_address
    signature = auth_in.signature
    nonce = auth_in.nonce
    # 1. Verify nonce
    if nonce not in NONCES:
        raise HTTPException(status_code=400, detail="Invalid nonce")
    
    if datetime.now(UTC) > NONCES[nonce]:
        NONCES.pop(nonce, None)
        raise HTTPException(status_code=400, detail="Nonce expired")
    
    # In production: Verify wallet signature using tonsdk or similar
    # For now, we trust the frontend (placeholder for signature verification)

    user = None
    
    # 2. Link to current user or find/create by wallet
    if current_user:
        # User is already logged in (e.g. via Telegram), link this wallet
        current_user.wallet_address = wallet_address
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        user = current_user
    else:
        # Classic wallet-first login or registration
        result = await db.execute(select(User).where(User.wallet_address == wallet_address))
        user = result.scalars().first()
        
        if not user:
            user = User(wallet_address=wallet_address)
            db.add(user)
            await db.commit()
            await db.refresh(user)
    
    # 3. Success! Delete used nonce
    NONCES.pop(nonce, None)

    # 4. Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }
