from typing import List, Dict, Any, Optional
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent import Agent
from app.models.memory import Memory
from app.core.db import SessionLocal
from app.services.embedding_service import EmbeddingService, cosine_similarity
from datetime import datetime, UTC
import asyncio
import json

# Max messages in conversation history before compression
MAX_HISTORY_MESSAGES = 10

async def get_memory_context(agent_id: str, query: str, db: AsyncSession) -> str:
    """
    RAG: Retrieve relevant memories based on direct vector similarity.
    """
    agent = await db.get(Agent, agent_id)
    if not agent: return ""

    # 1. Provide conversation history context
    history_ctx = ""
    history = agent.conversation_history or []
    if history:
        history_ctx = "\n\n[RECENT CONVERSATION HISTORY]\n"
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_ctx += f"{role}: {msg['content']}\n"

    # 2. RAG: Retrieve similar long-term memories
    rag_ctx = ""
    from app.services.agent_runtime import _resolve_api_key
    api_key, base_url = await _resolve_api_key(agent.user_id, agent.model, db)
    
    emb_service = EmbeddingService(api_key=api_key, base_url=base_url)
    query_vector = await emb_service.get_embedding(query)
    
    if query_vector:
        # Fetch all memories for this agent (for simple implementation)
        # In production with 10k+ memories, use pgvector or FAISS
        stmt = select(Memory).where(Memory.agent_id == agent_id)
        res = await db.execute(stmt)
        memories = res.scalars().all()
        
        scored_memories = []
        for m in memories:
            if m.embedding:
                score = cosine_similarity(query_vector, m.embedding)
                scored_memories.append((score, m))
        
        # Sort by score descending and take top 3
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        top_memories = scored_memories[:3]
        
        if top_memories and top_memories[0][0] > 0.7:  # Similarity threshold
            rag_ctx = "\n\n[RELEVANT LONG-TERM MEMORIES]\n"
            for score, m in top_memories:
                rag_ctx += f"- {m.content}\n"
                m.last_accessed_at = datetime.now(UTC)
    
    summary_ctx = f"\n\n[CONTEXT SUMMARY]\n{agent.memory_summary}\n" if agent.memory_summary else ""
    
    return history_ctx + rag_ctx + summary_ctx

async def update_memory(
    agent_id: str,
    user_input: str,
    agent_output: str,
):
    """
    Update both short-term history and provide long-term RAG persistence.
    """
    async with SessionLocal() as db:
        agent = await db.get(Agent, agent_id)
        if not agent: return

        # 1. Update Short-term History
        history = list(agent.conversation_history or [])
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": agent_output})
        
        # 2. Compression: If history is too long, move oldest pair to Long-term RAG
        if len(history) > MAX_HISTORY_MESSAGES:
            old_user = history.pop(0)
            old_assistant = history.pop(0)
            
            # Combine into a "fact" or "memory chunk"
            memory_chunk = f"User asked: {old_user['content']}. Agent replied: {old_assistant['content']}"
            
            # Generate embedding and save to RAG
            from app.services.agent_runtime import _resolve_api_key
            api_key, base_url = await _resolve_api_key(agent.user_id, agent.model, db)
            emb_service = EmbeddingService(api_key=api_key, base_url=base_url)
            vector = await emb_service.get_embedding(memory_chunk)
            
            new_memory = Memory(
                agent_id=agent_id,
                content=memory_chunk,
                embedding=vector,
                importance=5
            )
            db.add(new_memory)

        agent.conversation_history = history
        
        # 3. Update Global Summary (Contextual compression)
        # We reuse the existing summary logic but make it more concise
        from app.services.agent_runtime import _build_llm, _resolve_api_key
        from langchain_core.messages import SystemMessage, HumanMessage

        current_summary = agent.memory_summary or "None"
        prompt = f"""Update the memory summary for an AI agent. 
Keep it very concise. Capture only enduring facts about the user and the agent's current mission.

Old summary: {current_summary}
Recent turn:
User: {user_input}
Agent: {agent_output}

Return the new consolidated summary (max 200 words)."""

        try:
            api_key, base_url = await _resolve_api_key(agent.user_id, agent.model, db)
            llm = _build_llm(model_id=agent.model, temperature=0, max_tokens=300, api_key=api_key, base_url=base_url)
            resp = await llm.ainvoke([
                SystemMessage(content="You are a factual memory compressor."),
                HumanMessage(content=prompt)
            ])
            agent.memory_summary = str(resp.content).strip()
            agent.memory_updated_at = datetime.now(UTC)
        except Exception as e:
            print(f"Summary update error: {e}")

        db.add(agent)
        await db.commit()
