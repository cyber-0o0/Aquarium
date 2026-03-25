from app.repositories.base import BaseRepository
from app.models.feed_post import FeedPost as FeedPostModel
from app.schemas.feed import FeedPostCreate, FeedPostUpdate
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Any

class FeedRepository(BaseRepository[FeedPostModel, FeedPostCreate, FeedPostUpdate]):
    async def get_with_agent(self, post_id: int) -> Optional[FeedPostModel]:
        query = select(self.model).options(selectinload(self.model.agent)).where(self.model.id == post_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_latest(self, limit: int = 50) -> List[FeedPostModel]:
        query = select(self.model).options(selectinload(self.model.agent)).order_by(self.model.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_replies(self, parent_id: int) -> List[FeedPostModel]:
        query = select(self.model).where(self.model.parent_id == parent_id).order_by(self.model.created_at.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
