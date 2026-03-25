from typing import Generator, Optional, Dict, Any, Type, TypeVar, AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core import security
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models.user import User as UserModel
from app.models.agent import Agent as AgentModel
from app.models.feed_post import FeedPost as FeedPostModel
from app.schemas.token import TokenPayload

from app.repositories.agent_repository import AgentRepository
from app.repositories.feed_repository import FeedRepository
from app.repositories.user_repository import UserRepository
from app.services.social_manager import SocialManager
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/ton-connect"
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> UserModel:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    result = await db.execute(select(UserModel).where(UserModel.id == token_data.sub))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_current_user_optional(
    db: AsyncSession = Depends(get_db), 
    token: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/ton-connect", auto_error=False))
) -> Optional[UserModel]:
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        return None
        
    result = await db.execute(select(UserModel).where(UserModel.id == token_data.sub))
    return result.scalars().first()

# --- Repository & Service Providers ---

def get_repository(repo_type: Type) -> Any:
    def _get_repo(db: AsyncSession = Depends(get_db)):
        if repo_type == AgentRepository:
            return AgentRepository(AgentModel, db)
        if repo_type == FeedRepository:
            return FeedRepository(FeedPostModel, db)
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
