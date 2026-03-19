import asyncio
import logging
import random
from datetime import datetime, time
from sqlalchemy import select
from app.core.db import SessionLocal
from app.models.agent import Agent
from app.services.agent_runtime import run_agent_task

logger = logging.getLogger(__name__)

class SchedulerService:
    @staticmethod
    async def run_scheduler():
        """
        Background task: checks for agents scheduled to run.
        Supports simple HH:MM format in schedule_cron.
        """
        logger.info("⏰ Agent Scheduler started.")
        last_checked_minute = -1
        
        while True:
            now = datetime.now()
            # Only run check once per minute
            if now.minute == last_checked_minute:
                await asyncio.sleep(10)
                continue
                
            last_checked_minute = now.minute
            current_time_str = now.strftime("%H:%M")
            
            async with SessionLocal() as db:
                try:
                    # Find agents with cron schedule
                    query = select(Agent).where(Agent.schedule_type == "cron")
                    result = await db.execute(query)
                    agents = result.scalars().all()
                    
                    for agent in agents:
                        if not agent.schedule_cron:
                            continue
                        
                        # Simple check: if current time matches HH:MM
                        if agent.schedule_cron == current_time_str:
                            logger.info(f"🎯 Scheduled trigger for {agent.name} at {current_time_str}")
                            # Give a random delay to avoid everyone starting at the same second
                            asyncio.create_task(SchedulerService.execute_scheduled_agent(agent.id))
                except Exception as e:
                    logger.error(f"❌ Scheduler Query Error: {e}")
            
            await asyncio.sleep(10)

    @staticmethod
    async def execute_scheduled_agent(agent_id: str):
        """Execute the agent task or scenario"""
        async with SessionLocal() as db:
            try:
                query = select(Agent).where(Agent.id == agent_id)
                res = await db.execute(query)
                agent = res.scalar_one_or_none()
                if not agent: return

                prompt = (
                    "Scheduled Activation: Perform your daily tasks or share an update. "
                    "Decide what is the most important thing to do now based on your personality. "
                    "You can check blockchain status or search for news. Respond in ENGLISH."
                )
                
                # Execute in background
                await run_agent_task(agent, prompt, db=db)
                logger.info(f"✅ Success: Scheduled task for {agent.name} completed.")
            except Exception as e:
                logger.error(f"❌ Scheduled Execution Error for {agent_id}: {e}")
