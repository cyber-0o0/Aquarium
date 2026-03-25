from typing import List, Any
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.api.deps import get_agent_service, get_db, get_current_user
from app.models.user import User as UserModel
from app.schemas.agent import Agent, AgentCreate, AgentUpdate, ModelsResponse, ModelInfo
from app.services.agent_service import AgentService
from app.services.agent_runtime import stream_agent_task
from app.core.models_registry import SUPPORTED_MODELS, models_for_plan, get_model_info
from app.models.model_status import ModelStatus
from app.models.user_api_key import UserApiKey
from app.core.config import settings
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Models ---

@router.get("/models", response_model=ModelsResponse)
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> Any:
    key_result = await db.execute(
        select(UserApiKey.provider).where(UserApiKey.user_id == current_user.id)
    )
    user_providers = set(row[0] for row in key_result.fetchall())

    platform_providers = set()
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
            
    status_result = await db.execute(select(ModelStatus))
    model_statuses = {s.id: s for s in status_result.scalars().all()}
    plan_models = models_for_plan(current_user.plan)

    model_list: List[ModelInfo] = []
    for model_id, meta in SUPPORTED_MODELS.items():
        provider = meta["provider"]
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
            in_plan=model_id in plan_models,
            status=health.status if health else "active",
            latency=health.latency if health else 0.0,
            last_checked=health.last_checked if health else None,
        ))

    model_list.sort(key=lambda m: (target := (not m.available, m.tier == "premium", m.status != "active", m.provider, m.label)))
    return ModelsResponse(models=model_list, user_has_custom_keys=bool(user_providers))

# --- CRUD ---

@router.get("", response_model=List[Agent])
async def read_agents(
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
) -> Any:
    return await agent_service.get_agents_for_user(current_user, skip=skip, limit=limit)

@router.post("", response_model=Agent)
async def create_agent(
    agent_in: AgentCreate,
    current_user: UserModel = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
) -> Any:
    return await agent_service.create_agent(current_user, agent_in)

@router.get("/{id}", response_model=Agent)
async def read_agent(
    id: str,
    current_user: UserModel = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
) -> Any:
    agent = await agent_service.agent_repo.get(id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.patch("/{id}", response_model=Agent)
async def update_agent(
    id: str,
    agent_in: AgentUpdate,
    current_user: UserModel = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
) -> Any:
    return await agent_service.update_agent(current_user, id, agent_in)

@router.delete("/{id}", response_model=Agent)
async def delete_agent(
    id: str,
    current_user: UserModel = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
) -> Any:
    agent = await agent_service.agent_repo.get(id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if agent.tg_thread_id:
        from app.services.telegram_bot import close_agent_topic
        await close_agent_topic(agent.tg_thread_id, agent.name, chat_id=settings.TELEGRAM_BOT_CHAT_ID or current_user.telegram_id)

    return await agent_service.agent_repo.remove(id=id)

# --- Execution ---

class RunRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=100_000)

@router.post("/{id}/run")
async def run_agent(
    id: str,
    body: RunRequest,
    current_user: UserModel = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
) -> Any:
    return await agent_service.run_agent(current_user, id, body.input)

@router.post("/{id}/stream")
async def stream_agent(
    id: str,
    body: RunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> StreamingResponse:
    from app.models.agent import Agent as AgentModel
    from app.models.task import Task as TaskModel
    
    result = await db.execute(select(AgentModel).where(AgentModel.id == id, AgentModel.user_id == current_user.id))
    agent = result.scalars().first()
    if not agent: raise HTTPException(status_code=404, detail="Agent not found")

    task = TaskModel(agent_id=agent.id, status="running", input_data={"input": body.input})
    db.add(task)
    agent.status = "active"
    await db.commit()
    await db.refresh(task)

    async def event_generator():
        output_parts = []
        try:
            async for event in stream_agent_task(agent, body.input, db=db):
                if event["type"] == "token": output_parts.append(event["content"])
                if event["type"] == "done": event["task_id"] = task.id
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            task.status = "success"
            task.output_data = {"output": "".join(output_parts)}
            agent.status = "idle"
            await db.commit()
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Execution error'})}\n\n"
            task.status = "failed"
            agent.status = "idle"
            await db.commit()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
