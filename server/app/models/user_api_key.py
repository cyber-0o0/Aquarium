"""
UserApiKey model — stores encrypted, per-provider API keys for users.

A user can add their own OpenAI / Anthropic / etc. key.
When present, it overrides the platform key for that provider.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid
from app.core.db import Base


class UserApiKey(Base):
    __tablename__ = "user_api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # provider matches SUPPORTED_MODELS[x]["provider"]
    # e.g. "openai", "anthropic", "google", "mistral", "openai_compatible"
    provider = Column(String, nullable=False)

    # For openai_compatible providers: optional custom base_url override
    # e.g. user's own vLLM, Together AI, Ollama proxy, etc.
    label = Column(String, nullable=True)          # human-friendly name
    base_url = Column(String, nullable=True)        # custom endpoint
    model_name = Column(String, nullable=True)      # model to use with this key

    # AES-encrypted key stored as Fernet token string
    encrypted_key = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # One key per provider per user (can be overridden by updating)
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "label", name="uq_user_provider_label"),
    )

    user = relationship("User", backref="api_keys")
