from typing import List, Optional, Dict, Any
from pydantic import BaseModel, field_validator, Field
from datetime import datetime

from app.core.models_registry import is_valid_model


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = Field(None, max_length=512)
    avatar_url: Optional[str] = None
    avatar_emoji: Optional[str] = Field(None, max_length=16)
    is_social_active: bool = False
    model: str
    system_prompt: Optional[str] = Field(
        default="You are a helpful AI assistant.", max_length=100_000
    )
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2048, ge=1, le=128_000)
    schedule_type: Optional[str] = "manual"
    schedule_cron: Optional[str] = None
    schedule_event: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Agent name must not be blank")
        return v

    @field_validator("model")
    @classmethod
    def model_must_be_supported(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Model must not be blank")
        if not is_valid_model(v):
            from app.core.models_registry import SUPPORTED_MODELS
            raise ValueError(
                f"Model '{v}' is not supported. "
                f"Available: {sorted(SUPPORTED_MODELS.keys())}"
            )
        return v


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = Field(None, max_length=512)
    avatar_url: Optional[str] = None
    avatar_emoji: Optional[str] = Field(None, max_length=16)
    is_social_active: Optional[bool] = None
    status: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = Field(None, max_length=100_000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=128_000)
    schedule_type: Optional[str] = None
    schedule_cron: Optional[str] = None
    schedule_event: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Agent name must not be blank")
        return v

    @field_validator("model")
    @classmethod
    def model_must_be_supported(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not is_valid_model(v):
                from app.core.models_registry import SUPPORTED_MODELS
                raise ValueError(
                    f"Model '{v}' is not supported. "
                    f"Available: {sorted(SUPPORTED_MODELS.keys())}"
                )
        return v


class Agent(AgentBase):
    id: str
    user_id: str
    status: str
    scenario: Optional[Dict[str, Any]] = None
    tg_thread_id: Optional[int] = None
    tg_group_id: Optional[str] = None
    bot_username: Optional[str] = None
    avatar_emoji: Optional[str] = None
    is_social_active: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Model info response schemas ────────────────────────────────────────────────

class ModelInfo(BaseModel):
    id: str
    label: str
    provider: str
    context_window: int
    supports_tools: bool
    tier: str
    description: str
    available: bool
    in_plan: bool
    status: Optional[str] = "active"
    latency: Optional[float] = 0.0
    last_checked: Optional[datetime] = None



class ModelsResponse(BaseModel):
    models: List[ModelInfo]
    user_has_custom_keys: bool
