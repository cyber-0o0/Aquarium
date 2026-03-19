from typing import Optional, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Aquarium AI"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    ALLOWED_CORS_ORIGINS: list[str] = ["*"]  # Set to actual frontend URLs in production

    # Security
    SECRET_KEY: str = "supersecretkey"  # Change in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # DATABASE
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "aihubton"
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str) and v:
            return v
        data = info.data
        user = data.get("POSTGRES_USER")
        pwd = data.get("POSTGRES_PASSWORD")
        server = data.get("POSTGRES_SERVER")
        port = data.get("POSTGRES_PORT", "5432")
        db = data.get("POSTGRES_DB")
        if all([user, pwd, server, db]):
            return f"postgresql+asyncpg://{user}:{pwd}@{server}:{port}/{db}"
        return "sqlite+aiosqlite:///./sql_app.db"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # ── Platform AI keys (optional — users can provide their own) ────────────
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_API_BASE: Optional[str] = None

    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_API_BASE: Optional[str] = None

    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_API_BASE: Optional[str] = None

    GROQ_API_KEY: Optional[str] = None
    GROQ_API_BASE: Optional[str] = None

    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_BASE: Optional[str] = None

    # ── Cocoon — TON decentralized AI (Confidential Compute Open Network) ────
    # Get access at https://cocoon.ton.org
    # Runs DeepSeek, Qwen, Llama via decentralised GPU network, payments in TON
    COCOON_API_KEY: Optional[str] = None
    COCOON_API_BASE: Optional[str] = None

    # ── TON ecosystem ─────────────────────────────────────────────────────────
    TON_NETWORK: str = "mainnet"
    TONCENTER_API_KEY: Optional[str] = None  # optional, for higher rate limits
    TONAPI_KEY: Optional[str] = None          # tonapi.io key for higher limits

    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_BOT_CHAT_ID: Optional[str] = None   # Global chat ID (legacy supergroup) - optional if using private threaded chats
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None  # защита webhook
    TELEGRAM_BOT_SHOW_STATS: bool = False   # Показывать ли тех-инфо (токены, латентность) в Telegram

    model_config = {
        "case_sensitive": True,
        "env_file": (".env", "../.env"),  # works whether launched from app/ or server/
    }


settings = Settings()
