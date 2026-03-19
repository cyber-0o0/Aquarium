from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent import Agent
from app.core.db import SessionLocal
from datetime import datetime, UTC
import asyncio

async def get_memory_context(agent: Agent) -> str:
    if not agent.memory_summary:
        return ""
    return f"\n\n--- Memory from previous conversations ---\n{agent.memory_summary}\n---\n"

async def update_memory(
    agent_id: str,
    user_input: str,
    agent_output: str,
):
    """
    Update the summary memory of an agent in the background.
    """
    async with SessionLocal() as db:
        agent = await db.get(Agent, agent_id)
        if not agent:
            return

        from app.services.agent_runtime import _build_llm, _resolve_api_key
        from langchain_core.messages import SystemMessage, HumanMessage

        current_summary = agent.memory_summary or "No previous memory."

        prompt = f"""Update the memory summary for an AI agent based on a new conversation.

Current memory summary:
{current_summary}

New conversation:
User: {user_input[:500]}
Agent: {agent_output[:500]}

Write a concise updated summary (max 300 words) that captures:
- Key facts learned about the user
- Important decisions or preferences mentioned
- Ongoing tasks or context
- TON wallet activity if mentioned

Return only the updated summary text, nothing else."""

        try:
            api_key, base_url = await _resolve_api_key(agent.user_id, agent.model, db)
            llm = _build_llm(
                model_id=agent.model,
                temperature=0.3,
                max_tokens=400,
                api_key=api_key,
                base_url=base_url,
            )
            response = await llm.ainvoke([
                SystemMessage(content="You are a memory manager. Be concise and factual."),
                HumanMessage(content=prompt),
            ])
            new_summary = response.content if isinstance(response.content, str) else str(response.content)

            agent.memory_summary = new_summary
            agent.memory_updated_at = datetime.now(UTC)
            db.add(agent)
            await db.commit()
        except Exception as e:
            print(f"❌ Failed to update memory for agent {agent_id}: {e}")
