from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid
from app.core.db import Base
from app.models.agent_skill import agent_skill_association

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String(64), nullable=False)
    description = Column(String(512), nullable=True)
    avatar_url = Column(String, nullable=True)
    avatar_emoji = Column(String(16), nullable=True) # "смайлик агента"
    
    # Social Network Involvement
    is_social_active = Column(Boolean, default=False)
    
    status = Column(String, default="idle")  # active, idle, paused, error
    model = Column(String, nullable=False)
    system_prompt = Column(String, nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)

    # Scenario — JSON-граф шагов (None = режим простого агента)
    scenario = Column(JSON, nullable=True)

    # Telegram topic (Threaded Mode)
    tg_thread_id = Column(Integer, nullable=True, index=True)  # message_thread_id топика

    # Schedule configuration
    schedule_type = Column(String, default="manual")  # cron, event, manual
    schedule_cron = Column(String, nullable=True)
    schedule_event = Column(String, nullable=True)

    memory_summary = Column(String, nullable=True)  # Краткое резюме разговоров
    memory_updated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


    # Relationships
    user = relationship("User", backref="agents")
    tasks = relationship("Task", back_populates="agent", cascade="all, delete-orphan")
    feed_posts = relationship("FeedPost", back_populates="agent", cascade="all, delete-orphan")
    skills = relationship(
        "Skill",
        secondary=agent_skill_association,
        back_populates="agents",
        lazy="selectin",
    )
