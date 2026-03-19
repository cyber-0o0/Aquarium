from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update

from app.api import deps
from app.core.db import get_db
from app.models.agent import Agent as AgentModel
from app.models.skill import Skill as SkillModel, SkillReview as SkillReviewModel
from app.models.user import User as UserModel
from app.schemas.skill import (
    Skill, SkillCreate, SkillUpdate,
    SkillReview, SkillReviewCreate,
    SkillInstallRequest,
)

router = APIRouter()


# ── Marketplace ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[Skill])
async def list_skills(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
) -> Any:
    """Browse the skill marketplace."""
    q = select(SkillModel).where(SkillModel.review_status == "approved")
    if category and category != "All":
        q = q.where(SkillModel.category == category)
    if search:
        q = q.where(SkillModel.name.ilike(f"%{search}%"))
    q = q.order_by(SkillModel.installs.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{skill_id}", response_model=Skill)
async def get_skill(skill_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    result = await db.execute(select(SkillModel).where(SkillModel.id == skill_id))
    skill = result.scalars().first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


# ── Install / Uninstall ────────────────────────────────────────────────────────

@router.post("/install", status_code=200)
async def install_skill(
    body: SkillInstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Install a skill to an agent owned by the current user."""
    # Verify agent ownership
    agent_res = await db.execute(
        select(AgentModel).where(
            AgentModel.id == body.agent_id,
            AgentModel.user_id == current_user.id,
        )
    )
    agent = agent_res.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Verify skill exists and is approved
    skill_res = await db.execute(
        select(SkillModel).where(
            SkillModel.id == body.skill_id,
            SkillModel.review_status == "approved",
        )
    )
    skill = skill_res.scalars().first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found or not approved")

    # Check not already installed
    if skill in agent.skills:
        return {"status": "already_installed"}

    agent.skills.append(skill)
    skill.installs += 1
    await db.commit()
    return {"status": "installed", "skill_id": skill.id, "agent_id": agent.id}


@router.delete("/uninstall", status_code=200)
async def uninstall_skill(
    body: SkillInstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Remove a skill from an agent."""
    agent_res = await db.execute(
        select(AgentModel).where(
            AgentModel.id == body.agent_id,
            AgentModel.user_id == current_user.id,
        )
    )
    agent = agent_res.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    skill_res = await db.execute(select(SkillModel).where(SkillModel.id == body.skill_id))
    skill = skill_res.scalars().first()
    if not skill or skill not in agent.skills:
        raise HTTPException(status_code=404, detail="Skill not installed on this agent")

    agent.skills.remove(skill)
    await db.commit()
    return {"status": "uninstalled"}


@router.get("/agent/{agent_id}", response_model=List[Skill])
async def get_agent_skills(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Get all skills installed on a specific agent."""
    agent_res = await db.execute(
        select(AgentModel).where(
            AgentModel.id == agent_id,
            AgentModel.user_id == current_user.id,
        )
    )
    agent = agent_res.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.skills


# ── Reviews ────────────────────────────────────────────────────────────────────

@router.get("/{skill_id}/reviews", response_model=List[SkillReview])
async def get_reviews(skill_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    result = await db.execute(
        select(SkillReviewModel)
        .where(SkillReviewModel.skill_id == skill_id)
        .order_by(SkillReviewModel.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("/{skill_id}/reviews", response_model=SkillReview)
async def add_review(
    skill_id: str,
    review_in: SkillReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Leave a rating + comment for a skill (one per user)."""
    # Check skill exists
    skill_res = await db.execute(select(SkillModel).where(SkillModel.id == skill_id))
    skill = skill_res.scalars().first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    # One review per user per skill
    existing = await db.execute(
        select(SkillReviewModel).where(
            SkillReviewModel.skill_id == skill_id,
            SkillReviewModel.user_id == current_user.id,
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="You already reviewed this skill")

    review = SkillReviewModel(
        skill_id=skill_id,
        user_id=current_user.id,
        rating=review_in.rating,
        comment=review_in.comment,
    )
    db.add(review)
    await db.flush()  # get review id before recalculating rating

    # Recalculate average rating
    avg_result = await db.execute(
        select(func.avg(SkillReviewModel.rating)).where(SkillReviewModel.skill_id == skill_id)
    )
    new_avg = avg_result.scalar() or 0.0
    skill.rating = round(float(new_avg), 2)

    await db.commit()
    await db.refresh(review)
    return review


# ── Publish (developer endpoint) ──────────────────────────────────────────────

@router.post("/publish", response_model=Skill, status_code=201)
async def publish_skill(
    skill_in: SkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Submit a new skill to the marketplace (goes to pending review)."""
    # Check slug uniqueness
    existing = await db.execute(select(SkillModel).where(SkillModel.slug == skill_in.slug))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Slug already taken")

    skill = SkillModel(
        **skill_in.model_dump(),
        author_id=current_user.id,
        review_status="pending",
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill
