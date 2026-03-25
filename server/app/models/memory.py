from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid
from app.core.db import Base

class Memory(Base):
    __tablename__ = "memories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    content = Column(String, nullable=False)
    embedding = Column(JSON, nullable=True) # Stored as a list of floats
    importance = Column(Integer, default=1) # 1-10
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_accessed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationship
    agent = relationship("Agent", backref="memories")
