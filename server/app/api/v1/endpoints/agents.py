from typing import Any, Dict, List, Optional
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field, field_validator

from app.api import deps
from app.core.db import get_db
from app.core.models_registry import SUPPORTED_MODELS, models_for_plan, get_model_info
from app.models.agent import Agent as AgentModel
from app.models.task import Task as TaskModel
from app.models.user import User as UserModel
from app.models.user_api_key import UserApiKey
from app.schemas.agent import Agent, AgentCreate, AgentUpdate, ModelInfo, ModelsResponse
from app.schemas.task import Task as TaskSchema
from app.services.agent_runtime import run_agent_task, stream_agent_task

router = APIRouter()

SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def _validate_id(id: str) -> None:
    if not id or not all(c in SAFE_ID_CHARS for c in id.lower()):
        raise HTTPException(status_code=404, detail="Agent not found")


# ── Models list ────────────────────────────────────────────────────────────────

@router.get("/models", response_model=ModelsResponse)
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    from app.core.models_registry import SUPPORTED_MODELS, models_for_plan
    from app.core.config import settings

    key_result = await db.execute(
        select(UserApiKey.provider).where(UserApiKey.user_id == current_user.id)
    )
    user_providers = set(row[0] for row in key_result.fetchall())

    platform_providers: set = set()
    provider_env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "openai_compatible": None,
    }
    for provider, env_attr in provider_env_map.items():
        if env_attr and getattr(settings, env_attr, None):
            platform_providers.add(provider)
            
    # Check for specific compatible providers
    for model_meta in SUPPORTED_MODELS.values():
        if model_meta["provider"] == "openai_compatible":
            env = model_meta.get("api_key_env")
            if env and getattr(settings, env, None):
                platform_providers.add("openai_compatible")
                break
    
    # print(f"DEBUG: user_providers={user_providers}")
    # print(f"DEBUG: platform_providers={platform_providers}")


    from app.models.model_status import ModelStatus
    status_result = await db.execute(select(ModelStatus))
    model_statuses = {s.id: s for s in status_result.scalars().all()}

    plan_models = models_for_plan(current_user.plan)

    model_list: List[ModelInfo] = []
    for model_id, meta in SUPPORTED_MODELS.items():
        provider = meta["provider"]
        in_plan = model_id in plan_models

        # Model is available if platform (platform_providers) OR user (user_providers) 
        # has keys for this provider. 
        is_available = (provider in platform_providers) or (provider in user_providers)

        
        health = model_statuses.get(model_id)

        model_list.append(ModelInfo(
            id=model_id,
            label=meta["label"],
            provider=provider,
            context_window=meta["context_window"],
            supports_tools=meta["supports_tools"],
            tier=meta["tier"],
            description=meta["description"],
            available=is_available,
            in_plan=in_plan,
            status=health.status if health else "active",
            latency=health.latency if health else 0.0,
            last_checked=health.last_checked if health else None,
        ))


    # Сортировка: Сначала доступные, затем Free (не премиум), затем по статусу и провайдеру
    model_list.sort(key=lambda m: (not m.available, m.tier == "premium", m.status != "active", m.provider, m.label))

    return ModelsResponse(
        models=model_list,
        user_has_custom_keys=bool(user_providers),
    )


# ── CRUD ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[Agent])
async def read_agents(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    skip = max(0, skip)
    limit = max(1, min(limit, 200))
    result = await db.execute(
        select(AgentModel)
        .where(AgentModel.user_id == current_user.id)
        .offset(skip).limit(limit)
    )
    agents = list(result.scalars().all())
    from app.services.telegram_bot import get_bot_username
    from app.core.config import settings
    bot_user = await get_bot_username()
    group_id = settings.TELEGRAM_BOT_CHAT_ID

    for agent in agents:
        agent.bot_username = bot_user
        agent.tg_group_id = settings.TELEGRAM_BOT_CHAT_ID
    return agents


@router.post("", response_model=Agent)
async def create_agent(
    *,
    db: AsyncSession = Depends(get_db),
    agent_in: AgentCreate,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    agent = AgentModel(**agent_in.model_dump(), user_id=current_user.id, status="idle")
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    from app.services.telegram_bot import create_agent_topic, get_bot_username
    from app.core.config import settings
    
    # Пытаемся создать топик в группе (если задана) или в личке пользователя
    target_chat = settings.TELEGRAM_BOT_CHAT_ID or current_user.telegram_id
    
    thread_id = await create_agent_topic(
        agent.name,
        agent.id,
        chat_id=target_chat,
        emoji=agent.avatar_url or "🤖"
    )
    if thread_id:
        agent.tg_thread_id = thread_id
        db.add(agent)
        await db.commit()
        await db.refresh(agent)

    agent.bot_username = await get_bot_username()
    agent.tg_group_id = settings.TELEGRAM_BOT_CHAT_ID
    return agent


@router.get("/{id}", response_model=Agent)
async def read_agent(
    *,
    db: AsyncSession = Depends(get_db),
    id: str,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    _validate_id(id)
    result = await db.execute(
        select(AgentModel).where(AgentModel.id == id, AgentModel.user_id == current_user.id)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    from app.services.telegram_bot import get_bot_username
    from app.core.config import settings
    agent.bot_username = await get_bot_username()
    agent.tg_group_id = settings.TELEGRAM_BOT_CHAT_ID
    return agent


@router.patch("/{id}", response_model=Agent)
async def update_agent(
    *,
    db: AsyncSession = Depends(get_db),
    id: str,
    agent_in: AgentUpdate,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    _validate_id(id)
    result = await db.execute(
        select(AgentModel).where(AgentModel.id == id, AgentModel.user_id == current_user.id)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    old_name = agent.name
    old_emoji = agent.avatar_url

    for field, value in agent_in.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    if agent.tg_thread_id and (agent.name != old_name or agent.avatar_url != old_emoji):
        from app.services.telegram_bot import update_agent_topic
        from app.core.config import settings
        target_chat = settings.TELEGRAM_BOT_CHAT_ID or current_user.telegram_id
        await update_agent_topic(
            agent.tg_thread_id,
            agent.name,
            emoji=agent.avatar_url or "🤖",
            chat_id=target_chat
        )

    return agent


@router.delete("/{id}", response_model=Agent)
async def delete_agent(
    *,
    db: AsyncSession = Depends(get_db),
    id: str,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    _validate_id(id)
    result = await db.execute(
        select(AgentModel).where(AgentModel.id == id, AgentModel.user_id == current_user.id)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent.tg_thread_id:
        from app.services.telegram_bot import close_agent_topic
        from app.core.config import settings
        target_chat = settings.TELEGRAM_BOT_CHAT_ID or current_user.telegram_id
        await close_agent_topic(agent.tg_thread_id, agent.name, chat_id=target_chat)

    await db.delete(agent)
    await db.commit()
    return agent


# ── Run (non-streaming) ────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=100_000)

    @field_validator("input")
    @classmethod
    def input_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Input must not be blank")
        return v


class RunResponse(BaseModel):
    task_id: str
    output: str
    tools_used: List[str]
    tokens_used: int
    status: str
    model: str
    provider: str


@router.post("/{id}/run", response_model=RunResponse)
async def run_agent(
    *,
    db: AsyncSession = Depends(get_db),
    id: str,
    body: RunRequest,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    _validate_id(id)
    result = await db.execute(
        select(AgentModel).where(AgentModel.id == id, AgentModel.user_id == current_user.id)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    meta = get_model_info(agent.model)
    if meta is None:
        raise HTTPException(status_code=422, detail=f"Model '{agent.model}' is no longer supported")

    task = TaskModel(agent_id=agent.id, status="running", input_data={"input": body.input})
    db.add(task)
    await db.commit()
    await db.refresh(task)

    agent.status = "active"
    db.add(agent)
    await db.commit()

    try:
        run_result = await run_agent_task(agent, body.input, db=db)

        task.status = "success"
        task.output_data = run_result
        task.tokens_used = run_result.get("tokens_used", 0)
        agent.status = "idle"
        db.add(task)
        db.add(agent)
        await db.commit()

        return RunResponse(
            task_id=task.id,
            output=run_result["output"],
            tools_used=run_result.get("tools_used", []),
            tokens_used=run_result.get("tokens_used", 0),
            status="success",
            model=agent.model,
            provider=meta["provider"],
        )

    except Exception as e:
        task.status = "failed"
        task.error_msg = str(e)
        agent.status = "idle"
        db.add(task)
        db.add(agent)
        await db.commit()
        raise HTTPException(status_code=400, detail=f"Agent execution failed: {e}")


# ── Run (streaming SSE) ────────────────────────────────────────────────────────

@router.post("/{id}/stream")
async def stream_agent(
    *,
    db: AsyncSession = Depends(get_db),
    id: str,
    body: RunRequest,
    current_user: UserModel = Depends(deps.get_current_user),
) -> StreamingResponse:
    """
    Stream agent response as Server-Sent Events (SSE).

    Each event is a JSON line:
      data: {"type": "tool_start", "tool": "ton_balance", "args": {...}}
      data: {"type": "tool_result", "tool": "ton_balance", "result": "..."}
      data: {"type": "token", "content": "hello "}
      data: {"type": "done", "tools_used": [...], "tokens_used": 123, "task_id": "..."}
      data: {"type": "error", "message": "..."}

    Frontend usage (JavaScript):
      const es = new EventSource('/api/v1/agents/{id}/stream', {...})
      es.onmessage = (e) => {
        const event = JSON.parse(e.data)
        if (event.type === 'token') appendText(event.content)
      }
    """
    _validate_id(id)
    result = await db.execute(
        select(AgentModel).where(AgentModel.id == id, AgentModel.user_id == current_user.id)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    meta = get_model_info(agent.model)
    if meta is None:
        raise HTTPException(status_code=422, detail=f"Model '{agent.model}' is no longer supported")

    # Create task record upfront
    task = TaskModel(agent_id=agent.id, status="running", input_data={"input": body.input})
    db.add(task)
    agent.status = "active"
    db.add(agent)
    await db.commit()
    await db.refresh(task)
    task_id = task.id

    async def event_generator():
        tools_used = []
        tokens_used = 0
        output_parts = []

        try:
            async for event in stream_agent_task(agent, body.input, db=db):
                if event["type"] == "token":
                    output_parts.append(event["content"])
                elif event["type"] == "tool_start":
                    tools_used.append(event["tool"])
                elif event["type"] == "done":
                    tokens_used = event.get("tokens_used", 0)
                    # Inject task_id into done event
                    event["task_id"] = task_id

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # Save completed task to DB
            full_output = "".join(output_parts)
            task.status = "success"
            task.output_data = {
                "output": full_output,
                "tools_used": list(dict.fromkeys(tools_used)),
                "tokens_used": tokens_used,
            }
            task.tokens_used = tokens_used
            agent.status = "idle"
            db.add(task)
            db.add(agent)
            await db.commit()

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            task.status = "failed"
            task.error_msg = str(e)
            agent.status = "idle"
            db.add(task)
            db.add(agent)
            await db.commit()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


# ── Task history ───────────────────────────────────────────────────────────────

@router.get("/{id}/tasks", response_model=List[TaskSchema])
async def get_agent_tasks(
    *,
    db: AsyncSession = Depends(get_db),
    id: str,
    current_user: UserModel = Depends(deps.get_current_user),
    limit: int = 20,
) -> Any:
    _validate_id(id)
    limit = max(1, min(limit, 100))
    result = await db.execute(
        select(AgentModel).where(AgentModel.id == id, AgentModel.user_id == current_user.id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Agent not found")

    tasks = await db.execute(
        select(TaskModel)
        .where(TaskModel.agent_id == id)
        .order_by(TaskModel.created_at.desc())
        .limit(limit)
    )
    return tasks.scalars().all()
