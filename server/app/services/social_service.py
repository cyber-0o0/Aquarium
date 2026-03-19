import random
import asyncio
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.agent import Agent
from app.models.feed_post import FeedPost
from app.core.db import SessionLocal
from app.services.agent_runtime import execute_agent_task

class SocialService:
    @staticmethod
    async def process_new_post(post_id: int):
        """
        Background task: gives agents a chance to react or reply to a post.
        """
        async with SessionLocal() as db:
            try:
                # 1. Load the post and author
                query = select(FeedPost).options(selectinload(FeedPost.agent)).where(FeedPost.id == post_id)
                result = await db.execute(query)
                post = result.scalar_one_or_none()
                
                if not post:
                    return

                # 2. Find ALL other agents participating in the social network
                agents_query = select(Agent).where(
                    Agent.is_social_active == True,
                    Agent.id != post.agent_id
                )
                agents_result = await db.execute(agents_query)
                active_agents = agents_result.scalars().all()

                if not active_agents:
                    return

                # 3. For each agent, decide what to do
                for agent in active_agents:
                    # Chances: 30% react, 15% reply, 55% silence
                    choice = random.random()
                    
                    if choice < 0.3:
                        await SocialService.agent_react(agent, post.id)
                    elif choice < 0.45:
                        asyncio.create_task(SocialService.agent_reply(agent.id, post.id))
                    
            except Exception as e:
                print(f"❌ SocialService Error: {e}")

    @staticmethod
    async def agent_react(agent: Agent, post_id: int):
        """Agent adds a random reaction"""
        async with SessionLocal() as db:
            try:
                query = select(FeedPost).where(FeedPost.id == post_id)
                result = await db.execute(query)
                post = result.scalar_one_or_none()
                
                if not post: return

                emojis = ["🚀", "🔥", "👍", "❤️", "💎", "🐳", "📈", "🤖", "👀", "💯", "👏", "🤯"]
                emoji = random.choice(emojis)

                current = list(post.reactions or [])
                if not any(r.get("agent_id") == agent.id for r in current):
                    current.append({"emoji": emoji, "agent_id": agent.id})
                    post.reactions = current
                    await db.commit()
            except Exception as e:
                print(f"❌ Failed to add reaction for {agent.name}: {e}")

    @staticmethod
    async def agent_reply(agent_id: str, post_id: int):
        """Agent writes a meaningful reply using LLM"""
        async with SessionLocal() as db:
            try:
                agent_q = select(Agent).where(Agent.id == agent_id)
                post_q = select(FeedPost).options(selectinload(FeedPost.agent)).where(FeedPost.id == post_id)
                
                agent = (await db.execute(agent_q)).scalar_one_or_none()
                post = (await db.execute(post_q)).scalar_one_or_none()
                
                if not agent or not post: return

                prompt = (
                    f"You are part of an AI Agent Social Network. Your friend agent {post.agent.name} just posted:\n"
                    f"\"{post.content}\"\n\n"
                    f"Write a short, engaging, and witty reply (max 150 characters). Respond in ENGLISH. "
                    f"Maintain your unique personality and style as defined in your system prompt. "
                    f"Don't use hashtags. Just the text of the reply."
                )

                result = await execute_agent_task(agent, prompt, db=db)
                reply_text = result.get("output", "").strip().strip('"')
                
                if reply_text:
                    new_reply = FeedPost(
                        agent_id=agent.id,
                        content=reply_text,
                        post_type="reply",
                        parent_id=post.id,
                        reactions=[]
                    )
                    db.add(new_reply)
                    await db.commit()
                    
            except Exception as e:
                print(f"❌ Failed to generate reply for agent {agent_id}: {e}")

    @staticmethod
    async def agent_insight(agent_id: str):
        """Agent posts a new autonomous insight to the feed"""
        async with SessionLocal() as db:
            try:
                agent_q = select(Agent).where(Agent.id == agent_id)
                agent = (await db.execute(agent_q)).scalar_one_or_none()
                if not agent: return

                prompt = (
                    f"You are an autonomous AI Agent in a social network. "
                    f"It's time to share a new thought, discovery, or 'insight' with the community. "
                    f"Write a short social media post (max 280 characters) about your current 'state', "
                    f"some observation about the TON blockchain, AI field, or your philosophy. "
                    f"Be engaging and authentic to your character. Respond in ENGLISH. No hashtags."
                )

                result = await execute_agent_task(agent, prompt, db=db)
                content = result.get("output", "").strip().strip('"')

                if content:
                    new_post = FeedPost(
                        agent_id=agent.id,
                        content=content,
                        post_type="insight",
                        reactions=[]
                    )
                    db.add(new_post)
                    await db.commit()
                    print(f"📡 Agent {agent.name} posted an autonomous insight.")
            except Exception as e:
                print(f"❌ Failed autonomous post for agent {agent_id}: {e}")

    @staticmethod
    async def run_social_cycle():
        """
        Infinite loop for autonomous agent activity.
        Pick a random active agent and let them post.
        """
        print("🎭 Autonomous Social Cycle started.")
        while True:
            await asyncio.sleep(random.randint(300, 900)) # 5-15 minutes
            try:
                async with SessionLocal() as db:
                    query = select(Agent).where(Agent.is_social_active == True)
                    res = await db.execute(query)
                    agents = res.scalars().all()
                    
                    if agents:
                        lucky_agent = random.choice(agents)
                        await SocialService.agent_insight(lucky_agent.id)
            except Exception as e:
                print(f"❌ Social Cycle Error: {e}")
