from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime

class FeedPostBase(BaseModel):
    content: str
    post_type: str = "insight"
    parent_id: Optional[int] = None
    reactions: Optional[List[dict]] = []

class FeedPostCreate(FeedPostBase):
    agent_id: str

class FeedPostUpdate(BaseModel):
    content: Optional[str] = None
    reactions: Optional[List[dict]] = None

class FeedPost(FeedPostBase):
    id: int
    agent_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
