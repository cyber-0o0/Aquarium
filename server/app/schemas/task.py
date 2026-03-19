from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class TaskBase(BaseModel):
    agent_id: str
    status: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_msg: Optional[str] = None
    tokens_used: int = 0
    duration_ms: Optional[float] = None


class Task(TaskBase):
    id: str
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
