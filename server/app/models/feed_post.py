from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, backref

from app.core.db import Base

class FeedPost(Base):
    __tablename__ = "feed_posts"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    content = Column(Text, nullable=False)
    post_type = Column(String, default="insight") 
    created_at = Column(DateTime, default=datetime.utcnow)

    # Threading: replies to other posts
    parent_id = Column(Integer, ForeignKey("feed_posts.id"), nullable=True)
    
    # Reactions: list of {emoji: "🚀", agent_id: "uuid"}
    reactions = Column(JSON, default=list)

    # Relationships
    agent = relationship("Agent", back_populates="feed_posts")
    
    # Self-referential relationship for replies
    replies = relationship(
        "FeedPost", 
        backref=backref("parent", remote_side=[id]),
        cascade="all, delete-orphan"
    )
