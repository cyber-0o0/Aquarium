"""
Scenario schema — полная типизация всех шагов сценария.

Сценарий = граф шагов. Каждый шаг имеет:
  - id:          уникальный идентификатор в рамках сценария
  - type:        тип шага (см. StepType)
  - label:       человекочитаемое название (для UI)
  - config:      конфигурация шага (зависит от типа)
  - next:        id следующего шага (None = конец)
  - on_error:    id шага при ошибке (None = пробросить исключение)
  - retry:       политика повтора при ошибке
  - timeout_sec: максимальное время выполнения шага

ScenarioContext передаётся через все шаги и накапливает результаты.
Jinja2-шаблоны {{ ctx.vars.X }}, {{ ctx.last_output }}, {{ trigger.data.X }}
доступны в любом строковом поле конфига.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Step types ─────────────────────────────────────────────────────────────────

class StepType(str, Enum):
    # Triggers
    TRIGGER         = "trigger"

    # Variables / data
    SET_VARIABLE    = "set_variable"
    TRANSFORM       = "transform"
    INPUT_PROMPT    = "input_prompt"

    # AI
    LLM_CALL        = "llm_call"
    LLM_STRUCTURED  = "llm_structured"
    LLM_LOOP        = "llm_loop"

    # Actions
    SKILL_CALL      = "skill_call"
    HTTP_REQUEST    = "http_request"
    SEND_MESSAGE    = "send_message"
    TON_ACTION      = "ton_action"

    # Flow control
    CONDITION       = "condition"
    FOREACH         = "foreach"
    PARALLEL        = "parallel"
    WAIT            = "wait"
    GOTO            = "goto"

    # Output / finish
    OUTPUT          = "output"
    ERROR_HANDLER   = "error_handler"
    SUBAGENT_CALL   = "subagent_call"


# ── Retry policy ──────────────────────────────────────────────────────────────

class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=1, ge=1, le=10)
    delay_sec: float = Field(default=1.0, ge=0, le=300)
    backoff: Literal["fixed", "exponential"] = "fixed"


# ══════════════════════════════════════════════════════════════════════════════
# Step config models (one per StepType)
# ══════════════════════════════════════════════════════════════════════════════

class TriggerConfig(BaseModel):
    on: Literal["manual", "schedule", "webhook", "event", "ton_event", "tg_message"] = "manual"
    # schedule
    cron: Optional[str] = None          # "*/5 * * * *"
    interval_sec: Optional[int] = None  # альтернатива cron
    # webhook
    webhook_secret: Optional[str] = None
    # event
    event_name: Optional[str] = None
    event_filter: Optional[Dict[str, Any]] = None


class SetVariableConfig(BaseModel):
    variables: Dict[str, Any]  # {"price": "{{ ctx.last_output }}", "ts": "{{ now() }}"}


class TransformConfig(BaseModel):
    """Применяет Jinja2-шаблон или jq-выражение к данным."""
    mode: Literal["jinja2", "jq", "python_expr"] = "jinja2"
    expression: str
    output_var: str   # куда записать результат в ctx.vars


class InputPromptConfig(BaseModel):
    """Приостанавливает сценарий и ждёт ввода от пользователя."""
    prompt: str
    output_var: str = "user_input"
    timeout_sec: Optional[int] = 300


class LlmCallConfig(BaseModel):
    prompt: str                          # Jinja2-шаблон
    system_prompt: Optional[str] = None  # переопределяет system_prompt агента
    model: Optional[str] = None          # переопределяет модель агента
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=128_000)
    output_var: str = "last_output"      # куда сохранить ответ в ctx.vars


class JsonSchema(BaseModel):
    """Произвольная JSON Schema для структурированного вывода."""
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class LlmStructuredConfig(BaseModel):
    """LLM возвращает валидный JSON по заданной схеме (structured output / tool-call trick)."""
    prompt: str
    output_schema: JsonSchema
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    output_var: str = "structured"


class LlmLoopConfig(BaseModel):
    """Прогоняет LLM-вызов для каждого элемента списка из ctx.vars."""
    items_var: str          # имя переменной в ctx.vars содержащей List
    item_var: str = "item"  # как называть текущий элемент в шаблоне
    prompt: str             # Jinja2-шаблон с {{ item }}
    model: Optional[str] = None
    output_var: str = "loop_results"  # List[str] с результатами
    max_concurrency: int = Field(default=1, ge=1, le=10)


class SkillCallConfig(BaseModel):
    skill_name: str              # tool_name из манифеста скилла
    arguments: Dict[str, Any]    # Jinja2-шаблоны в значениях
    output_var: str = "skill_result"


class HttpRequestConfig(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    url: str                     # Jinja2-шаблон
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None   # Jinja2 в строковых значениях
    timeout_sec: float = 15
    output_var: str = "http_result"
    parse_json: bool = True      # автоматически парсить JSON-ответ


class SendMessageConfig(BaseModel):
    channel: Literal["telegram", "webhook", "email"] = "telegram"
    # telegram
    chat_id: Optional[str] = None   # Jinja2
    text: Optional[str] = None      # Jinja2
    parse_mode: Literal["HTML", "Markdown", "MarkdownV2"] = "HTML"
    # webhook
    webhook_url: Optional[str] = None
    webhook_payload: Optional[Dict[str, Any]] = None


class TonActionConfig(BaseModel):
    action: Literal["get_balance", "get_transactions", "send_ton", "get_nft", "get_jetton"]
    address: Optional[str] = None   # Jinja2
    amount_ton: Optional[str] = None
    comment: Optional[str] = None
    output_var: str = "ton_result"


# ── Condition ─────────────────────────────────────────────────────────────────

class ConditionBranch(BaseModel):
    condition: str    # Jinja2-выражение, должно вернуть truthy
    next_step: str    # id шага при выполнении условия


class ConditionConfig(BaseModel):
    """
    if/elif/else ветвление.
    Проверяются ветки по порядку; первая truthy → переход.
    else_step — переход если ни одна ветка не сработала.
    """
    branches: List[ConditionBranch]
    else_step: Optional[str] = None


class ForeachConfig(BaseModel):
    """Итерация по списку — выполняет steps для каждого элемента."""
    items_var: str            # имя переменной в ctx.vars (должна быть List)
    item_var: str = "item"    # имя переменной итерации
    steps: List[str]          # id шагов в теле цикла (выполняются последовательно)
    max_iterations: int = Field(default=100, ge=1, le=10_000)
    output_var: str = "foreach_results"


class ParallelBranch(BaseModel):
    label: str
    steps: List[str]   # id шагов в этой ветке


class ParallelConfig(BaseModel):
    """Выполняет несколько веток параллельно, ждёт все."""
    branches: List[ParallelBranch]
    output_var: str = "parallel_results"


class WaitConfig(BaseModel):
    mode: Literal["delay", "until_condition", "until_event"] = "delay"
    delay_sec: Optional[float] = None           # для mode=delay
    condition: Optional[str] = None             # Jinja2 для mode=until_condition
    poll_interval_sec: float = 5.0
    max_wait_sec: float = 3600.0
    event_name: Optional[str] = None            # для mode=until_event


class GotoConfig(BaseModel):
    step_id: str
    condition: Optional[str] = None  # прыгнуть только если условие выполнено


class OutputConfig(BaseModel):
    value: str = "{{ ctx.last_output }}"  # Jinja2-шаблон финального ответа
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorHandlerConfig(BaseModel):
    message: str = "Step failed: {{ error.message }}"
    output_var: str = "error_info"
    re_raise: bool = False  # если True, ошибка пробрасывается выше


class SubagentCallConfig(BaseModel):
    agent_id: str              # id другого агента (Jinja2)
    input: str                 # Jinja2-шаблон входного текста
    wait_for_result: bool = True
    output_var: str = "subagent_result"
    timeout_sec: float = 120.0


# ── Step config union ─────────────────────────────────────────────────────────

StepConfig = Union[
    TriggerConfig,
    SetVariableConfig,
    TransformConfig,
    InputPromptConfig,
    LlmCallConfig,
    LlmStructuredConfig,
    LlmLoopConfig,
    SkillCallConfig,
    HttpRequestConfig,
    SendMessageConfig,
    TonActionConfig,
    ConditionConfig,
    ForeachConfig,
    ParallelConfig,
    WaitConfig,
    GotoConfig,
    OutputConfig,
    ErrorHandlerConfig,
    SubagentCallConfig,
]

# Map type → config class для валидации
STEP_CONFIG_MAP: Dict[StepType, type] = {
    StepType.TRIGGER:        TriggerConfig,
    StepType.SET_VARIABLE:   SetVariableConfig,
    StepType.TRANSFORM:      TransformConfig,
    StepType.INPUT_PROMPT:   InputPromptConfig,
    StepType.LLM_CALL:       LlmCallConfig,
    StepType.LLM_STRUCTURED: LlmStructuredConfig,
    StepType.LLM_LOOP:       LlmLoopConfig,
    StepType.SKILL_CALL:     SkillCallConfig,
    StepType.HTTP_REQUEST:   HttpRequestConfig,
    StepType.SEND_MESSAGE:   SendMessageConfig,
    StepType.TON_ACTION:     TonActionConfig,
    StepType.CONDITION:      ConditionConfig,
    StepType.FOREACH:        ForeachConfig,
    StepType.PARALLEL:       ParallelConfig,
    StepType.WAIT:           WaitConfig,
    StepType.GOTO:           GotoConfig,
    StepType.OUTPUT:         OutputConfig,
    StepType.ERROR_HANDLER:  ErrorHandlerConfig,
    StepType.SUBAGENT_CALL:  SubagentCallConfig,
}


# ── Step ──────────────────────────────────────────────────────────────────────

class ScenarioStep(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    type: StepType
    label: Optional[str] = Field(None, max_length=128)
    config: Dict[str, Any] = Field(default_factory=dict)
    next: Optional[str] = None       # id следующего шага (None = конец)
    on_error: Optional[str] = None   # id шага обработчика ошибок
    retry: Optional[RetryPolicy] = None
    timeout_sec: Optional[float] = Field(None, ge=0, le=3600)
    # Мета для UI (позиция на холсте)
    ui_position: Optional[Dict[str, float]] = None  # {"x": 100, "y": 200}

    @field_validator("id")
    @classmethod
    def id_safe(cls, v: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
        if not all(c in allowed for c in v.lower()):
            raise ValueError("Step id may only contain letters, digits, _ and -")
        return v

    def get_typed_config(self) -> StepConfig:
        """Parse and validate config dict into the correct typed model."""
        cfg_cls = STEP_CONFIG_MAP.get(self.type)
        if cfg_cls is None:
            raise ValueError(f"No config class for step type: {self.type}")
        return cfg_cls(**self.config)


# ── Scenario ──────────────────────────────────────────────────────────────────

class Scenario(BaseModel):
    version: str = "1"
    entry: str                          # id стартового шага
    steps: List[ScenarioStep]
    variables: Dict[str, Any] = Field(default_factory=dict)  # начальные переменные
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def steps_not_empty(cls, v: List[ScenarioStep]) -> List[ScenarioStep]:
        if not v:
            raise ValueError("Scenario must have at least one step")
        if len(v) > 200:
            raise ValueError("Scenario may not exceed 200 steps")
        return v

    @model_validator(mode="after")
    def validate_graph(self) -> "Scenario":
        step_ids = {s.id for s in self.steps}

        # Entry must exist
        if self.entry not in step_ids:
            raise ValueError(f"entry step '{self.entry}' not found in steps")

        for step in self.steps:
            # next / on_error must point to existing steps
            if step.next and step.next not in step_ids:
                raise ValueError(f"step '{step.id}' → next='{step.next}' does not exist")
            if step.on_error and step.on_error not in step_ids:
                raise ValueError(f"step '{step.id}' → on_error='{step.on_error}' does not exist")

            # Type-specific cross-ref validation
            cfg = step.config
            if step.type == StepType.CONDITION:
                for branch in cfg.get("branches", []):
                    ns = branch.get("next_step")
                    if ns and ns not in step_ids:
                        raise ValueError(f"condition branch next_step='{ns}' does not exist")
                else_step = cfg.get("else_step")
                if else_step and else_step not in step_ids:
                    raise ValueError(f"condition else_step='{else_step}' does not exist")

            if step.type == StepType.FOREACH:
                for sub_id in cfg.get("steps", []):
                    if sub_id not in step_ids:
                        raise ValueError(f"foreach sub-step '{sub_id}' does not exist")

            if step.type == StepType.PARALLEL:
                for branch in cfg.get("branches", []):
                    for sub_id in branch.get("steps", []):
                        if sub_id not in step_ids:
                            raise ValueError(f"parallel sub-step '{sub_id}' does not exist")

            if step.type == StepType.GOTO:
                target = cfg.get("step_id")
                if target and target not in step_ids:
                    raise ValueError(f"goto step_id='{target}' does not exist")

        return self

    def as_step_map(self) -> Dict[str, ScenarioStep]:
        return {s.id: s for s in self.steps}


# ── API request/response ──────────────────────────────────────────────────────

class ScenarioUpsert(BaseModel):
    scenario: Scenario


class ScenarioResponse(BaseModel):
    agent_id: str
    scenario: Optional[Scenario]
    has_scenario: bool


# ── Execution result schemas ──────────────────────────────────────────────────

class StepResult(BaseModel):
    step_id: str
    step_type: str
    label: Optional[str]
    status: Literal["success", "skipped", "failed", "timeout"]
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    tokens_used: int = 0


class ScenarioRunResult(BaseModel):
    status: Literal["success", "failed", "paused", "timeout"]
    output: Any = None
    steps_executed: List[StepResult] = Field(default_factory=list)
    total_tokens: int = 0
    total_duration_ms: float = 0
    error: Optional[str] = None
    # Если status=paused: ожидаем input_prompt
    awaiting_input: Optional[Dict[str, Any]] = None
