from typing import AsyncGenerator, Type, TypeVar, Any, Optional
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import AsyncSessionLocal
from app.api import deps as api_deps
from app.models.agent import Agent
from app.models.feed_post import FeedPost
from app.models.user import User as UserModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.feed_repository import FeedRepository
from app.repositories.user_repository import UserRepository
from app.services.social_manager import SocialManager
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

def get_repository(repo_type: Type) -> Any:
    def _get_repo(db: AsyncSession = Depends(get_db)):
        if repo_type == AgentRepository:
            return AgentRepository(Agent, db)
        if repo_type == FeedRepository:
            return FeedRepository(FeedPost, db)
        if repo_type == UserRepository:
            return UserRepository(UserModel, db)
        return repo_type(db)
    return _get_repo

def get_social_manager(
    db: AsyncSession = Depends(get_db),
    agent_repo: AgentRepository = Depends(get_repository(AgentRepository)),
    feed_repo: FeedRepository = Depends(get_repository(FeedRepository))
) -> SocialManager:
    return SocialManager(agent_repo, feed_repo, db)

def get_agent_service(
    db: AsyncSession = Depends(get_db),
    agent_repo: AgentRepository = Depends(get_repository(AgentRepository))
) -> AgentService:
    return AgentService(agent_repo, db)

def get_auth_service(
    db: AsyncSession = Depends(get_db),
    user_repo: UserRepository = Depends(get_repository(UserRepository))
) -> AuthService:
    return AuthService(user_repo)

async def get_current_user(user: UserModel = Depends(api_deps.get_current_user)) -> UserModel:
    return user

async def get_current_user_optional(user: Optional[UserModel] = Depends(api_deps.get_current_user_optional)) -> Optional[UserModel]:
    return user
