"""
Endpoints для управления сценариями агентов.

POST   /agents/{id}/scenario        — сохранить/обновить сценарий
GET    /agents/{id}/scenario        — получить текущий сценарий
DELETE /agents/{id}/scenario        — удалить сценарий (агент вернётся в режим простого LLM)
POST   /agents/{id}/scenario/run    — запустить сценарий вручную
POST   /agents/{id}/scenario/resume — продолжить сценарий после input_prompt
POST   /agents/{id}/scenario/validate — проверить сценарий без запуска
GET    /agents/{id}/scenario/templates — готовые шаблоны сценариев
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, Field
import time

from app.api import deps
from app.core.db import get_db
from app.models.agent import Agent as AgentModel
from app.models.task import Task as TaskModel
from app.models.user import User as UserModel
from app.schemas.scenario import (
    Scenario, ScenarioUpsert, ScenarioResponse,
    ScenarioRunResult, StepType,
)
from app.services.scenario_executor import execute_scenario

router = APIRouter()

SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def _validate_agent_id(id: str) -> None:
    if not id or not all(c in SAFE_ID_CHARS for c in id.lower()):
        raise HTTPException(status_code=404, detail="Agent not found")


async def _get_agent(id: str, user_id: str, db: AsyncSession) -> AgentModel:
    result = await db.execute(
        select(AgentModel).where(AgentModel.id == id, AgentModel.user_id == user_id)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=ScenarioResponse)
async def get_scenario(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    _validate_agent_id(id)
    agent = await _get_agent(id, current_user.id, db)
    scenario = None
    if agent.scenario:
        try:
            scenario = Scenario(**agent.scenario)
        except Exception:
            scenario = None
    return ScenarioResponse(
        agent_id=id,
        scenario=scenario,
        has_scenario=scenario is not None,
    )


@router.post("", response_model=ScenarioResponse)
async def upsert_scenario(
    id: str,
    body: ScenarioUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Save or replace the agent's scenario. Validates the graph before saving."""
    _validate_agent_id(id)
    agent = await _get_agent(id, current_user.id, db)

    # Scenario is already validated by Pydantic (graph cross-refs checked)
    agent.scenario = body.scenario.model_dump()
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return ScenarioResponse(
        agent_id=id,
        scenario=body.scenario,
        has_scenario=True,
    )


@router.delete("", status_code=204)
async def delete_scenario(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> None:
    _validate_agent_id(id)
    agent = await _get_agent(id, current_user.id, db)
    agent.scenario = None
    db.add(agent)
    await db.commit()


@router.post("/validate", status_code=200)
async def validate_scenario(
    id: str,
    body: ScenarioUpsert,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Validate a scenario without saving it. Returns step count and graph info."""
    _validate_agent_id(id)
    scenario = body.scenario  # already validated by Pydantic

    step_types = [s.type.value for s in scenario.steps]
    type_counts: Dict[str, int] = {}
    for t in step_types:
        type_counts[t] = type_counts.get(t, 0) + 1

    # Find all reachable steps from entry
    reachable = _find_reachable(scenario)
    unreachable = [s.id for s in scenario.steps if s.id not in reachable]

    return {
        "valid": True,
        "step_count": len(scenario.steps),
        "reachable_steps": len(reachable),
        "unreachable_steps": unreachable,
        "step_type_counts": type_counts,
        "has_loops": _detect_cycles(scenario),
        "entry": scenario.entry,
    }


# ── Run ───────────────────────────────────────────────────────────────────────

class ScenarioRunRequest(BaseModel):
    input: Optional[str] = Field(None, max_length=100_000)
    trigger_data: Optional[Dict[str, Any]] = None
    variables: Optional[Dict[str, Any]] = None  # override initial variables


class ScenarioResumeRequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=100_000)
    context_snapshot: Dict[str, Any]  # from awaiting_input.context_snapshot
    resume_step: str                  # from awaiting_input.step_id


@router.post("/run", response_model=ScenarioRunResult)
async def run_scenario(
    id: str,
    body: ScenarioRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Manually trigger the agent's scenario."""
    _validate_agent_id(id)
    agent = await _get_agent(id, current_user.id, db)

    if not agent.scenario:
        raise HTTPException(status_code=422, detail="This agent has no scenario configured")

    # Merge override variables into scenario
    if body.variables:
        scenario_data = dict(agent.scenario)
        merged_vars = {**scenario_data.get("variables", {}), **body.variables}
        scenario_data["variables"] = merged_vars
        agent.scenario = scenario_data

    # Create task record
    task = TaskModel(
        agent_id=agent.id,
        status="running",
        input_data={"input": body.input, "trigger_data": body.trigger_data},
    )
    db.add(task)
    agent.status = "active"
    db.add(agent)
    await db.commit()
    await db.refresh(task)

    t0 = time.monotonic()
    try:
        result = await execute_scenario(
            agent=agent,
            trigger_type="manual",
            trigger_data=body.trigger_data or {},
            user_input=body.input,
            db=db,
        )

        task.status = "success" if result.status == "success" else (
            "paused" if result.status == "paused" else "failed"
        )
        task.output_data = result.model_dump()
        task.tokens_used = result.total_tokens
        task.duration_ms = (time.monotonic() - t0) * 1000
        agent.status = "idle" if result.status in ("success", "paused") else "error"

    except Exception as e:
        task.status = "failed"
        task.error_msg = str(e)
        agent.status = "error"
        result = ScenarioRunResult(
            status="failed",
            error=str(e),
            total_duration_ms=(time.monotonic() - t0) * 1000,
        )

    db.add(task)
    db.add(agent)
    await db.commit()

    return result


@router.post("/resume", response_model=ScenarioRunResult)
async def resume_scenario(
    id: str,
    body: ScenarioResumeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Resume a paused scenario after the user answered an input_prompt.
    The client must pass back the context_snapshot from the awaiting_input field.
    """
    _validate_agent_id(id)
    agent = await _get_agent(id, current_user.id, db)

    if not agent.scenario:
        raise HTTPException(status_code=422, detail="Agent has no scenario")

    # Inject user answer into the snapshot vars
    snapshot = dict(body.context_snapshot)
    snapshot.setdefault("vars", {})

    # Find input_prompt step to get output_var
    scenario = Scenario(**agent.scenario)
    step = scenario.as_step_map().get(body.resume_step)
    if not step or step.type != StepType.INPUT_PROMPT:
        raise HTTPException(status_code=422, detail="Invalid resume step")

    output_var = step.config.get("output_var", "user_input")
    snapshot["vars"][output_var] = body.user_input
    snapshot["last_output"] = body.user_input

    # Continue execution from the step AFTER input_prompt
    resume_scenario_data = dict(agent.scenario)
    resume_scenario_data["entry"] = step.next or scenario.entry

    agent.scenario = resume_scenario_data
    result = await execute_scenario(
        agent=agent,
        trigger_type=snapshot.get("trigger", {}).get("type", "manual"),
        trigger_data=snapshot.get("trigger", {}).get("data", {}),
        user_input=body.user_input,
        resume_context=snapshot,
        db=db,
    )
    # Restore original scenario
    agent.scenario = scenario.model_dump()
    db.add(agent)
    await db.commit()

    return result


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Ready-to-use scenario templates for common use cases."""
    return {"templates": SCENARIO_TEMPLATES}


# ── Graph analysis helpers ────────────────────────────────────────────────────

def _find_reachable(scenario: Scenario) -> set:
    step_map = scenario.as_step_map()
    visited = set()
    queue = [scenario.entry]
    while queue:
        sid = queue.pop()
        if sid in visited or sid not in step_map:
            continue
        visited.add(sid)
        step = step_map[sid]
        if step.next:
            queue.append(step.next)
        if step.on_error:
            queue.append(step.on_error)
        cfg = step.config
        if step.type == StepType.CONDITION:
            for b in cfg.get("branches", []):
                if b.get("next_step"):
                    queue.append(b["next_step"])
            if cfg.get("else_step"):
                queue.append(cfg["else_step"])
        if step.type == StepType.FOREACH:
            queue.extend(cfg.get("steps", []))
        if step.type == StepType.PARALLEL:
            for b in cfg.get("branches", []):
                queue.extend(b.get("steps", []))
        if step.type == StepType.GOTO:
            if cfg.get("step_id"):
                queue.append(cfg["step_id"])
    return visited


def _detect_cycles(scenario: Scenario) -> bool:
    step_map = scenario.as_step_map()
    visited = set()
    rec_stack = set()

    def dfs(sid: str) -> bool:
        visited.add(sid)
        rec_stack.add(sid)
        step = step_map.get(sid)
        if not step:
            rec_stack.discard(sid)
            return False
        neighbors = []
        if step.next:
            neighbors.append(step.next)
        if step.type == StepType.CONDITION:
            for b in step.config.get("branches", []):
                if b.get("next_step"):
                    neighbors.append(b["next_step"])
        if step.type == StepType.GOTO:
            if step.config.get("step_id"):
                neighbors.append(step.config["step_id"])
        for nid in neighbors:
            if nid not in visited:
                if dfs(nid):
                    return True
            elif nid in rec_stack:
                return True
        rec_stack.discard(sid)
        return False

    for step in scenario.steps:
        if step.id not in visited:
            if dfs(step.id):
                return True
    return False


# ── Built-in templates ────────────────────────────────────────────────────────

SCENARIO_TEMPLATES = [
    {
        "id": "simple_qa",
        "name": "Simple Q&A",
        "description": "Простой ответ на вопрос пользователя",
        "tags": ["basic"],
        "scenario": {
            "version": "1",
            "entry": "trigger",
            "steps": [
                {"id": "trigger", "type": "trigger", "config": {"on": "manual"}, "next": "answer"},
                {"id": "answer", "type": "llm_call", "config": {
                    "prompt": "{{ last_output }}",
                    "output_var": "last_output"
                }, "next": "finish"},
                {"id": "finish", "type": "output", "config": {"value": "{{ last_output }}"}}
            ]
        }
    },
    {
        "id": "web_research",
        "name": "Web Research Agent",
        "description": "Ищет информацию в сети и формирует отчёт",
        "tags": ["search", "research"],
        "scenario": {
            "version": "1",
            "entry": "trigger",
            "steps": [
                {"id": "trigger", "type": "trigger", "config": {"on": "manual"}, "next": "search"},
                {"id": "search", "type": "skill_call", "config": {
                    "skill_name": "web_search",
                    "arguments": {"query": "{{ last_output }}"},
                    "output_var": "search_results"
                }, "next": "summarize"},
                {"id": "summarize", "type": "llm_call", "config": {
                    "prompt": "Based on these search results, answer the question '{{ trigger.data.question }}':\n\n{{ vars.search_results }}",
                    "output_var": "last_output"
                }, "next": "finish"},
                {"id": "finish", "type": "output", "config": {"value": "{{ last_output }}"}}
            ]
        }
    },
    {
        "id": "ton_monitor",
        "name": "TON Wallet Monitor",
        "description": "Проверяет баланс кошелька и отправляет уведомление в Telegram",
        "tags": ["ton", "monitoring"],
        "scenario": {
            "version": "1",
            "entry": "trigger",
            "variables": {"wallet": "YOUR_TON_WALLET", "tg_chat_id": "YOUR_CHAT_ID"},
            "steps": [
                {"id": "trigger", "type": "trigger", "config": {"on": "schedule", "interval_sec": 3600}, "next": "get_balance"},
                {"id": "get_balance", "type": "ton_action", "config": {
                    "action": "get_balance",
                    "address": "{{ vars.wallet }}",
                    "output_var": "balance_info"
                }, "next": "notify"},
                {"id": "notify", "type": "send_message", "config": {
                    "channel": "telegram",
                    "chat_id": "{{ vars.tg_chat_id }}",
                    "text": "💰 Wallet balance update:\n{{ vars.balance_info }}"
                }, "next": "finish"},
                {"id": "finish", "type": "output", "config": {"value": "{{ vars.balance_info }}"}}
            ]
        }
    },
    {
        "id": "price_alert",
        "name": "Crypto Price Alert",
        "description": "Следит за ценой монеты и уведомляет при изменении выше порога",
        "tags": ["defi", "monitoring"],
        "scenario": {
            "version": "1",
            "entry": "trigger",
            "variables": {"coin": "the-open-network", "threshold_pct": "5", "tg_chat_id": "YOUR_CHAT_ID"},
            "steps": [
                {"id": "trigger", "type": "trigger", "config": {"on": "schedule", "interval_sec": 900}, "next": "get_price"},
                {"id": "get_price", "type": "skill_call", "config": {
                    "skill_name": "crypto_price",
                    "arguments": {"coin_id": "{{ vars.coin }}"},
                    "output_var": "price_data"
                }, "next": "check_threshold"},
                {"id": "check_threshold", "type": "condition", "config": {
                    "branches": [{"condition": "'5%' in vars.price_data or '-5%' in vars.price_data", "next_step": "alert"}],
                    "else_step": "finish"
                }},
                {"id": "alert", "type": "send_message", "config": {
                    "channel": "telegram",
                    "chat_id": "{{ vars.tg_chat_id }}",
                    "text": "⚠️ Price alert for {{ vars.coin }}:\n{{ vars.price_data }}"
                }, "next": "finish"},
                {"id": "finish", "type": "output", "config": {"value": "{{ vars.price_data }}"}}
            ]
        }
    },
    {
        "id": "structured_extractor",
        "name": "Structured Data Extractor",
        "description": "Извлекает структурированные данные из текста через LLM",
        "tags": ["ai", "data"],
        "scenario": {
            "version": "1",
            "entry": "trigger",
            "steps": [
                {"id": "trigger", "type": "trigger", "config": {"on": "manual"}, "next": "extract"},
                {"id": "extract", "type": "llm_structured", "config": {
                    "prompt": "Extract structured information from: {{ last_output }}",
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "entities": {"type": "array", "items": {"type": "string"}},
                            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                            "summary": {"type": "string"}
                        },
                        "required": ["entities", "sentiment", "summary"]
                    },
                    "output_var": "structured"
                }, "next": "format"},
                {"id": "format", "type": "set_variable", "config": {
                    "variables": {
                        "last_output": "Entities: {{ vars.structured.entities }}\nSentiment: {{ vars.structured.sentiment }}\nSummary: {{ vars.structured.summary }}"
                    }
                }, "next": "finish"},
                {"id": "finish", "type": "output", "config": {"value": "{{ last_output }}"}}
            ]
        }
    },
]
