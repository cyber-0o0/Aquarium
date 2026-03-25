import logging
from typing import List, Optional, Any, Dict
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.agent_repository import AgentRepository
from app.models.agent import Agent as AgentModel
from app.models.task import Task as TaskModel
from app.models.user import User as UserModel
from app.schemas.agent import AgentCreate, AgentUpdate
from app.core.models_registry import get_model_info
from app.services.agent_runtime import run_agent_task, stream_agent_task
from app.services.telegram_bot import create_agent_topic, update_agent_topic, close_agent_topic, get_bot_username
from app.core.config import settings

logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self, agent_repo: AgentRepository, db: AsyncSession):
        self.agent_repo = agent_repo
        self.db = db

    async def get_agents_for_user(self, user: UserModel, skip: int = 0, limit: int = 100) -> List[AgentModel]:
        agents = await self.agent_repo.get_by_user(user.id, skip=skip, limit=limit)
        bot_user = await get_bot_username()
        for agent in agents:
            agent.bot_username = bot_user
            agent.tg_group_id = settings.TELEGRAM_BOT_CHAT_ID
        return agents

    async def create_agent(self, user: UserModel, agent_in: AgentCreate) -> AgentModel:
        agent = await self.agent_repo.create(obj_in={**agent_in.model_dump(), "user_id": user.id, "status": "idle"})
        
        # Telegram topic creation
        target_chat = settings.TELEGRAM_BOT_CHAT_ID or user.telegram_id
        thread_id = await create_agent_topic(
            agent.name,
            agent.id,
            chat_id=target_chat,
            emoji=agent.avatar_url or "🤖"
        )
        if thread_id:
            agent.tg_thread_id = thread_id
            await self.db.commit()
            await self.db.refresh(agent)

        agent.bot_username = await get_bot_username()
        agent.tg_group_id = settings.TELEGRAM_BOT_CHAT_ID
        return agent

    async def update_agent(self, user: UserModel, agent_id: str, agent_in: AgentUpdate) -> AgentModel:
        agent = await self.agent_repo.get(agent_id)
        if not agent or agent.user_id != user.id:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        old_name = agent.name
        old_emoji = agent.avatar_url
        
        updated_agent = await self.agent_repo.update(db_obj=agent, obj_in=agent_in)
        
        if updated_agent.tg_thread_id and (updated_agent.name != old_name or updated_agent.avatar_url != old_emoji):
            target_chat = settings.TELEGRAM_BOT_CHAT_ID or user.telegram_id
            await update_agent_topic(
                updated_agent.tg_thread_id,
                updated_agent.name,
                emoji=updated_agent.avatar_url or "🤖",
                chat_id=target_chat
            )
        return updated_agent

    async def run_agent(self, user: UserModel, agent_id: str, input_text: str) -> Dict[str, Any]:
        agent = await self.agent_repo.get(agent_id)
        if not agent or agent.user_id != user.id:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        meta = get_model_info(agent.model)
        if not meta:
            raise HTTPException(status_code=422, detail="Model not supported")

        # Create task
        task = TaskModel(agent_id=agent.id, status="running", input_data={"input": input_text})
        self.db.add(task)
        agent.status = "active"
        await self.db.commit()
        await self.db.refresh(task)

        try:
            run_result = await run_agent_task(agent, input_text, db=self.db)
            task.status = "success"
            task.output_data = run_result
            task.tokens_used = run_result.get("tokens_used", 0)
            agent.status = "idle"
            await self.db.commit()
            
            return {
                "task_id": task.id,
                "output": run_result["output"],
                "tools_used": run_result.get("tools_used", []),
                "tokens_used": run_result.get("tokens_used", 0),
                "model": agent.model,
                "provider": meta["provider"]
            }
        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            task.status = "failed"
            task.error_msg = str(e)
            agent.status = "idle"
            await self.db.commit()
            raise HTTPException(status_code=400, detail="Execution failed")
