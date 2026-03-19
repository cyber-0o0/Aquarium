from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class UserBase(BaseModel):
    wallet_address: Optional[str] = None
    telegram_id: Optional[str] = None
    username: Optional[str] = None
    plan: Optional[str] = "free"


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    plan: Optional[str] = None
    user_metadata: Optional[Dict[str, Any]] = None
    telegram_id: Optional[str] = None
    username: Optional[str] = None


class User(UserBase):
    id: str
    user_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}
