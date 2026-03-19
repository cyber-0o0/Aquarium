from sqlalchemy import Column, String, DateTime, ForeignKey, Table
from datetime import datetime, UTC
from app.core.db import Base

# Many-to-many: agent <-> skill
agent_skill_association = Table(
    "agent_skills",
    Base.metadata,
    Column("agent_id", String, ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", String, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
    Column("installed_at", DateTime, default=lambda: datetime.now(UTC)),
)
