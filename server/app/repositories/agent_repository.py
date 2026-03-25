from app.repositories.base import BaseRepository
from app.models.agent import Agent as AgentModel
from app.schemas.agent import AgentCreate, AgentUpdate
from sqlalchemy.future import select
from typing import List

class AgentRepository(BaseRepository[AgentModel, AgentCreate, AgentUpdate]):
    async def get_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> List[AgentModel]:
        query = select(self.model).where(self.model.user_id == user_id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_social(self) -> List[AgentModel]:
        query = select(self.model).where(self.model.is_social_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())
