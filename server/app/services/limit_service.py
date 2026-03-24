from datetime import datetime, timedelta, UTC
from sqlalchemy import func
from sqlalchemy.future import select
from app.models.task import Task
from app.models.agent import Agent
from app.models.user import User

class LimitService:
    # Generous default limits
    LIMITS = {
        "free": 100,
        "premium": 1000,
        "enterprise": 10000
    }

    @staticmethod
    async def get_user_usage_24h(user_id: str, db) -> int:
        """Counts successful or running tasks for a user in the last 24 hours."""
        since = datetime.now(UTC) - timedelta(hours=24)
        
        # Count tasks for all agents belonging to this user
        query = (
            select(func.count(Task.id))
            .join(Agent, Task.agent_id == Agent.id)
            .where(Agent.user_id == user_id)
            .where(Task.created_at >= since)
        )
        
        result = await db.execute(query)
        return result.scalar() or 0

    @staticmethod
    async def check_user_limit(user: User, db) -> tuple[bool, int, int]:
        """
        Checks if user has reached their daily limit.
        Returns: (is_allowed, current_usage, limit)
        """
        from app.core.config import settings
        
        plan = user.plan or "free"
        if plan == "premium":
            limit = settings.LIMIT_PREMIUM
        elif plan == "enterprise":
            limit = settings.LIMIT_ENTERPRISE
        else:
            limit = settings.LIMIT_FREE
        
        usage = await LimitService.get_user_usage_24h(user.id, db)
        
        return usage < limit, usage, limit
