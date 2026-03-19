from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid
from app.core.db import Base
from app.models.agent_skill import agent_skill_association


class Skill(Base):
    __tablename__ = "skills"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(64), nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    description = Column(String(2048), nullable=False)
    category = Column(String, nullable=False)  # search, ton, defi, telegram, utility, data
    version = Column(String, default="1.0.0")
    price_ton = Column(String, default="0")    # "0" = free
    rating = Column(Float, default=0.0)
    installs = Column(Integer, default=0)
    icon_url = Column(String, nullable=True)
    color = Column(String, default="#6366F1")  # hex color for UI

    # manifest describes the tool callable by the agent runtime:
    # {
    #   "tool_name": "web_search",
    #   "description": "Search the web for up-to-date info",
    #   "parameters": { "query": {"type": "string", "description": "..."} },
    #   "required": ["query"],
    #   "implementation": "builtin"   # or "http" with "url" field
    # }
    manifest = Column(JSON, nullable=False)

    review_status = Column(String, default="approved")  # pending, approved, rejected
    author_id = Column(String, nullable=True)           # user id or "system"

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    agents = relationship(
        "Agent",
        secondary=agent_skill_association,
        back_populates="skills",
    )
    reviews = relationship("SkillReview", back_populates="skill", cascade="all, delete-orphan")


class SkillReview(Base):
    __tablename__ = "skill_reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    skill_id = Column(String, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)        # 1-5
    comment = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    skill = relationship("Skill", back_populates="reviews")
