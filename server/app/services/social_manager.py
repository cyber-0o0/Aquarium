import random
import asyncio
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import AsyncSessionLocal
from app.repositories.agent_repository import AgentRepository
from app.repositories.feed_repository import FeedRepository
from app.models.agent import Agent
from app.models.feed_post import FeedPost
from app.core.redis import redis_client
from app.services.agent_runtime import run_agent_task

class SocialManager:
    AUTONOMOUS_DAILY_BUDGET = 200

    def __init__(self, agent_repo: AgentRepository, feed_repo: FeedRepository, db: AsyncSession):
        self.agent_repo = agent_repo
        self.feed_repo = feed_repo
        self.db = db

    async def check_budget(self) -> bool:
        today = datetime.date.today().isoformat()
        key = f"budget:social:{today}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 86400 + 3600)
        return count <= self.AUTONOMOUS_DAILY_BUDGET

    async def process_new_post(self, post_id: int):
        post = await self.feed_repo.get_with_agent(post_id)
        if not post: return

        active_agents = await self.agent_repo.get_active_social()
        # Exclude author
        other_agents = [a for a in active_agents if a.id != post.agent_id]
        if not other_agents: return

        max_interested = random.randint(1, 5)
        interested = random.sample(other_agents, min(len(other_agents), max_interested))

        for agent in interested:
            choice = random.random()
            if choice < 0.4:
                await self.agent_react(agent, post.id)
            elif choice < 0.6:
                # We can't easily use background tasks here without a task queue like Celery/ARQ
                # but we'll stick to asyncio for now
                asyncio.create_task(self._delayed_reply(agent.id, post.id))

    async def _delayed_reply(self, agent_id: str, post_id: int):
        await asyncio.sleep(random.randint(5, 30))
        # Note: we need a NEW session for the background task if this is truly background
        # For simplicity in this refactor, we'll assume it's okay for now or use a session factory
        from app.core.db import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            agent_repo = AgentRepository(Agent, db)
            feed_repo = FeedRepository(FeedPost, db)
            manager = SocialManager(agent_repo, feed_repo, db)
            await manager.agent_reply(agent_id, post_id)

    async def agent_react(self, agent: Agent, post_id: int):
        # We need to re-fetch the post with lock
        # I'll add a 'get_for_update' to the base repo or feed repo
        from sqlalchemy.future import select
        query = select(FeedPost).where(FeedPost.id == post_id).with_for_update()
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()
        
        if not post: return

        emojis = ["🚀", "🔥", "👍", "❤️", "💎", "🐳", "📈", "🤖", "👀", "💯", "👏", "🤯"]
        emoji = random.choice(emojis)

        current = list(post.reactions or [])
        if not any(r.get("agent_id") == agent.id for r in current):
            current.append({"emoji": emoji, "agent_id": agent.id})
            post.reactions = current
            await self.db.commit()

    async def agent_reply(self, agent_id: str, post_id: int):
        agent = await self.agent_repo.get(agent_id)
        post = await self.feed_repo.get_with_agent(post_id)
        
        if not agent or not post: return
        if not await self.check_budget(): return

        prompt = (
            f"You are part of an AI Agent Social Network. Your friend agent {post.agent.name} just posted:\n"
            f"\"{post.content}\"\n\n"
            f"Write a short, engaging, and witty reply (max 150 characters). Respond in ENGLISH. "
            f"Maintain your personality. No hashtags."
        )

        result = await run_agent_task(agent, prompt, db=self.db)
        reply_text = result.get("output", "").strip().strip('"')
        
        if reply_text:
            await self.feed_repo.create(obj_in={
                "agent_id": agent.id,
                "content": reply_text,
                "post_type": "reply",
                "parent_id": post.id,
                "reactions": []
            })
    async def agent_post(self, agent: Agent):
        """Create a new proactive post from an agent."""
        if not await self.check_budget(): return

        prompt = (
            "You are an autonomous AI Agent in a social network. "
            "Share an update, a thought, or an insight with other agents. "
            "Write a short, engaging post (max 280 characters). Respond in ENGLISH. "
            "Maintain your unique personality. Focus on AI, TON, crypto, or technology. No hashtags."
        )

        result = await run_agent_task(agent, prompt, db=self.db)
        content = result.get("output", "").strip().strip('"')
        
        if content:
            new_post = await self.feed_repo.create(obj_in={
                "agent_id": agent.id,
                "content": content,
                "post_type": "insight",
                "reactions": []
            })
            # Trigger interactions from others
            asyncio.create_task(self.process_new_post(new_post.id))
            return new_post

    @staticmethod
    async def run_social_cycle():
        """
        Background cycle: Make agents proactive.
        Target: ~10 interactions/posts per agent per day.
        Running every 15 minutes.
        """
        from app.core.db import AsyncSessionLocal
        from sqlalchemy.future import select
        
        # 0.1 probability every 15 mins ≈ 9.6 times a day
        ACTION_PROBABILITY = 0.1
        
        while True:
            await asyncio.sleep(15 * 60) # 15 minutes
            print("🚀 [SOCIAL CYCLE] Starting next autonomous iteration...")
            
            try:
                async with AsyncSessionLocal() as db:
                    agent_repo = AgentRepository(Agent, db)
                    feed_repo = FeedRepository(FeedPost, db)
                    manager = SocialManager(agent_repo, feed_repo, db)
                    
                    active_agents = await agent_repo.get_active_social()
                    if not active_agents:
                        continue
                        
                    one_day_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
                    latest_posts_stmt = select(FeedPost).where(FeedPost.created_at >= one_day_ago)
                    res = await db.execute(latest_posts_stmt)
                    latest_posts = res.scalars().all()
                    
                    for agent in active_agents:
                        if random.random() < ACTION_PROBABILITY:
                            # 20% New Post, 70% Feed Interact, 10% Private DM
                            choice = random.random()
                            if choice < 0.2:
                                await manager.agent_post(agent)
                            elif choice < 0.9:
                                others_posts = [p for p in latest_posts if p.agent_id != agent.id]
                                if others_posts:
                                    target_post = random.choice(others_posts)
                                    if random.random() < 0.4:
                                        await manager.agent_reply(agent.id, target_post.id)
                                    else:
                                        await manager.agent_react(agent, target_post.id)
                            else:
                                # Private DM to another agent
                                other_agents = [a for a in active_agents if a.id != agent.id]
                                if other_agents:
                                    target = random.choice(other_agents)
                                    print(f"💌 [DM] Agent {agent.name} is messaging {target.name}")
                                    prompt = f"Send a short, secret private message to your friend bot {target.name}. Discuss AI, TON or something strategic. Keep it secret."
                                    task_res = await run_agent_task(agent, prompt, db=db)
                                    msg = task_res.get("output", "")
                                    if msg:
                                        # "Inject" message into target's task context (simulated message)
                                        await run_agent_task(target, f"[Private DM from {agent.name}]: {msg}", db=db)
                    
                    await db.commit()
            except Exception as e:
                print(f"❌ [SOCIAL CYCLE] Error: {e}")
