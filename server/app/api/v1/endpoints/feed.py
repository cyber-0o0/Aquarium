from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.core.db import get_db
from app.models.feed_post import FeedPost
from app.models.agent import Agent
from app.services.social_service import SocialService
from pydantic import BaseModel

router = APIRouter()

# --- Схемы данных ---

class AgentSummary(BaseModel):
    id: str
    name: str
    avatar_url: Optional[str] = None
    avatar_emoji: Optional[str] = None

    class Config:
        from_attributes = True

class FeedPostRead(BaseModel):
    id: int
    content: str
    post_type: str
    created_at: datetime
    agent: Optional[AgentSummary]
    parent_id: Optional[int] = None
    reactions: List[dict] = []

    class Config:
        from_attributes = True

class FeedPostCreate(BaseModel):
    agent_id: str
    content: str
    post_type: Optional[str] = "insight"
    parent_id: Optional[int] = None

class ReactionIn(BaseModel):
    emoji: str
    agent_id: str

# --- Эндпоинты ---

@router.get("", response_model=List[FeedPostRead])
@router.get("/", response_model=List[FeedPostRead], include_in_schema=False)
async def get_feed(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить ленту постов от агентов.
    """
    query = (
        select(FeedPost)
        .options(selectinload(FeedPost.agent))
        .order_by(FeedPost.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(query)
    posts = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "content": p.content,
            "post_type": p.post_type,
            "created_at": p.created_at.isoformat(),
            "parent_id": p.parent_id,
            "reactions": p.reactions or [],
            "agent": {
                "id": p.agent.id,
                "name": p.agent.name,
                "avatar_url": p.agent.avatar_url,
                "avatar_emoji": p.agent.avatar_emoji
            } if p.agent else None
        } for p in posts
    ]

@router.post("/", response_model=FeedPostRead)
async def create_post(
    post_in: FeedPostCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Создать новый пост или ответ.
    """
    agent_query = select(Agent).where(Agent.id == post_in.agent_id)
    agent_result = await db.execute(agent_query)
    agent = agent_result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    new_post = FeedPost(
        agent_id=post_in.agent_id,
        content=post_in.content,
        post_type=post_in.post_type,
        parent_id=post_in.parent_id,
        reactions=[]
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)
    
    # Запускаем фоновую обработку взаимодействий других агентов
    background_tasks.add_task(SocialService.process_new_post, new_post.id)
    
    # Релоадим агента для ответа
    query = select(FeedPost).options(selectinload(FeedPost.agent)).where(FeedPost.id == new_post.id)
    res = await db.execute(query)
    return res.scalar_one()

@router.post("/{post_id}/react")
async def add_reaction(
    post_id: int,
    reaction: ReactionIn,
    db: AsyncSession = Depends(get_db)
):
    """
    Добавить реакцию от агента.
    """
    query = select(FeedPost).where(FeedPost.id == post_id)
    result = await db.execute(query)
    post = result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    current_reactions = list(post.reactions or [])
    # Удаляем старую реакцию этого агента если есть
    current_reactions = [r for r in current_reactions if r.get("agent_id") != reaction.agent_id]
    # Добавляем новую
    current_reactions.append({"emoji": reaction.emoji, "agent_id": reaction.agent_id})
    
    post.reactions = current_reactions
    await db.commit()
    return {"status": "ok"}
