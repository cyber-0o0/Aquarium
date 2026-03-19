from typing import Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class UserApiKeyCreate(BaseModel):
    provider: str = Field(..., description="Provider id: openai | anthropic | google | mistral | openai_compatible")
    api_key: str = Field(..., min_length=1, description="Raw API key (will be encrypted)")
    label: Optional[str] = Field(None, max_length=64, description="Friendly name, e.g. 'My OpenAI key'")
    base_url: Optional[str] = Field(None, description="Custom base URL for openai_compatible providers")
    model_name: Optional[str] = Field(None, description="Default model to use with this key")

    @field_validator("provider")
    @classmethod
    def provider_valid(cls, v: str) -> str:
        allowed = {"openai", "anthropic", "google", "mistral", "openai_compatible"}
        if v not in allowed:
            raise ValueError(f"provider must be one of {sorted(allowed)}")
        return v

    @field_validator("api_key")
    @classmethod
    def key_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("API key must not be blank")
        return v.strip()


class UserApiKeyUpdate(BaseModel):
    api_key: Optional[str] = Field(None, min_length=1)
    label: Optional[str] = Field(None, max_length=64)
    base_url: Optional[str] = None
    model_name: Optional[str] = None


class UserApiKeyOut(BaseModel):
    """Safe response — never exposes the raw key."""
    id: str
    provider: str
    label: Optional[str]
    base_url: Optional[str]
    model_name: Optional[str]
    # Show only last 4 chars so the user can identify which key it is
    key_hint: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
