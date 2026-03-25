import json
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from urllib.parse import parse_qsl, unquote_plus
from app.repositories.user_repository import UserRepository
from app.models.user import User as UserModel
from app.core import security
from app.core.config import settings
from app.core.redis import redis_client
from app.services.ton_service import verify_ton_signature
from datetime import timedelta

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def verify_tg_data(self, init_data: str) -> Optional[Dict[str, Any]]:
        if not settings.TELEGRAM_BOT_TOKEN:
            return None

        raw = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_val = raw.pop("hash", None)
        if not hash_val: return None

        data_check = "\n".join(f"{k}={v}" for k, v in sorted(raw.items()))
        secret = hmac.new(b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calc, hash_val):
            return None
        
        user_json = raw.get("user")
        if not user_json: return None
        
        try:
            return json.loads(user_json)
        except:
            return json.loads(unquote_plus(user_json))

    async def authenticate_telegram(self, init_data: str) -> UserModel:
        user_data = self.verify_tg_data(init_data)
        if not user_data:
            raise Exception("Invalid Telegram data")
        
        tg_id = str(user_data.get("id"))
        username = user_data.get("username")
        
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if not user:
            user = await self.user_repo.create(obj_in={
                "telegram_id": tg_id,
                "username": username
            })
        elif username and user.username != username:
            await self.user_repo.update(db_obj=user, obj_in={"username": username})
        
        return user

    async def authenticate_ton(self, address: str, pubkey: str, signature: str, nonce: str, current_user: Optional[UserModel]=None) -> UserModel:
        # Verify nonce
        key = f"nonce:{nonce}"
        if not await redis_client.exists(key):
            raise Exception("Expired nonce")
        
        # Verify signature
        if not await verify_ton_signature(address, pubkey, signature, nonce):
            raise Exception("Invalid signature")
        
        await redis_client.delete(key)
        
        if current_user:
            await self.user_repo.update(db_obj=current_user, obj_in={"wallet_address": address})
            return current_user
        
        user = await self.user_repo.get_by_wallet(address)
        if not user:
            user = await self.user_repo.create(obj_in={"wallet_address": address})
        return user

    def create_token(self, user_id: str) -> str:
        delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return security.create_access_token(user_id, expires_delta=delta)
