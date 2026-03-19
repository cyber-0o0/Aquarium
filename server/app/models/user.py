from sqlalchemy import Column, String, DateTime, Enum, JSON
from datetime import datetime, UTC
import uuid
from app.core.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id = Column(String, unique=True, index=True, nullable=True)
    username = Column(String, nullable=True)
    wallet_address = Column(String, unique=True, index=True, nullable=True)
    plan = Column(String, default="free") # free, premium, enterprise
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    # Store user preferences or metadata
    user_metadata = Column(JSON, nullable=True)
