from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, UTC, timedelta
import secrets
from typing import Optional, Any
from app.api.deps import get_db, get_auth_service, get_current_user_optional
from app.models.user import User as UserModel
from app.schemas.token import Token
from app.services.auth_service import AuthService
from app.core.redis import redis_client
from pydantic import BaseModel

router = APIRouter()

class TelegramAuth(BaseModel):
    init_data: str

class TonAuth(BaseModel):
    wallet_address: str
    public_key: str
    signature: str
    nonce: str

@router.get("/nonce")
async def get_nonce():
    nonce = secrets.token_hex(16)
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    await redis_client.setex(f"nonce:{nonce}", 300, "1")
    return {"nonce": nonce, "expires_at": expires_at.isoformat()}

@router.post("/telegram", response_model=Token)
async def telegram_auth(
    auth_in: TelegramAuth,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        user = await auth_service.authenticate_telegram(auth_in.init_data)
        return {
            "access_token": auth_service.create_token(user.id),
            "token_type": "bearer",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ton-connect", response_model=Token)
async def ton_connect(
    auth_in: TonAuth,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: Optional[UserModel] = Depends(get_current_user_optional)
):
    try:
        user = await auth_service.authenticate_ton(
            auth_in.wallet_address,
            auth_in.public_key,
            auth_in.signature,
            auth_in.nonce,
            current_user=current_user
        )
        return {
            "access_token": auth_service.create_token(user.id),
            "token_type": "bearer",
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
