from sqlalchemy import Column, String, Float, DateTime
from app.core.db import Base
from datetime import datetime, UTC

class ModelStatus(Base):
    __tablename__ = "model_status"

    id = Column(String, primary_key=True)  # model_id (e.g., 'gpt-4o')
    provider = Column(String)              # (e.g., 'openai')
    status = Column(String)                # 'active', 'unstable', 'offline'
    latency = Column(Float, nullable=True) # In seconds
    error = Column(String, nullable=True)
    last_checked = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
