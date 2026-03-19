"""
ScenarioExecutor — главный движок выполнения сценариев.

Принцип работы:
  1. Загружает Scenario из агента
  2. Строит map id → ScenarioStep
  3. Запускает граф начиная с entry-шага
  4. Для каждого шага вызывает соответствующий handler
  5. Handler обновляет ScenarioContext и возвращает id следующего шага
  6. Цикл продолжается до None (конец) или StopScenario (ошибка/пауза)

Особенности:
  - Jinja2 рендеринг во всех строковых полях конфигов
  - Защита от бесконечных циклов (max_total_steps)
  - Таймаут на каждый шаг
  - Параллельное выполнение через asyncio.gather
  - Полный лог каждого шага в ScenarioRunResult
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.schemas.scenario import (
    Scenario, ScenarioStep, StepType,
    ScenarioRunResult, StepResult,
    LlmCallConfig, LlmStructuredConfig, LlmLoopConfig,
    SkillCallConfig, HttpRequestConfig, SendMessageConfig, TonActionConfig,
    SetVariableConfig, TransformConfig, InputPromptConfig,
    ConditionConfig, ForeachConfig, ParallelConfig, WaitConfig, GotoConfig,
    OutputConfig, ErrorHandlerConfig, SubagentCallConfig, TriggerConfig,
)
from app.services.scenario_context import ScenarioContext
from app.services.skill_tools import BUILTIN_TOOLS

MAX_TOTAL_STEPS = 500       # защита от бесконечных циклов
DEFAULT_STEP_TIMEOUT = 120  # секунд


# ── Exceptions ────────────────────────────────────────────────────────────────

class ScenarioFinished(Exception):
    def __init__(self, output: Any = None):
        self.output = output

class ScenarioPaused(Exception):
    """Сценарий приостановлен — ждёт ввода пользователя."""
    def __init__(self, step_id: str, prompt: str, output_var: str):
        self.step_id = step_id
        self.prompt = prompt
        self.output_var = output_var

class ScenarioError(Exception):
    pass


# ── Executor ──────────────────────────────────────────────────────────────────

class ScenarioExecutor:
    def __init__(
        self,
        scenario: Scenario,
        agent,                    # AgentModel
        db=None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.scenario = scenario
        self.agent = agent
        self.db = db
        self._api_key = api_key
        self._base_url = base_url
        self._step_map: Dict[str, ScenarioStep] = scenario.as_step_map()

    # ── Public entry point ────────────────────────────────────────────────────

    async def run(
        self,
        trigger_type: str = "manual",
        trigger_data: Optional[Dict[str, Any]] = None,
        user_input: Optional[str] = None,
        resume_context: Optional[Dict[str, Any]] = None,
    ) -> ScenarioRunResult:
        t0 = time.monotonic()

        if resume_context:
            ctx = ScenarioContext.from_snapshot(resume_context)
        else:
            ctx = ScenarioContext(
                trigger_type=trigger_type,
                trigger_data=trigger_data or {},
                initial_vars=dict(self.scenario.variables),
                user_input=user_input,
            )

        step_results: List[StepResult] = []
        total_tokens = 0

        current_id: Optional[str] = self.scenario.entry
        steps_count = 0

        try:
            while current_id is not None:
                if steps_count >= MAX_TOTAL_STEPS:
                    raise ScenarioError(f"Exceeded max steps ({MAX_TOTAL_STEPS}). Possible infinite loop.")

                step = self._step_map.get(current_id)
                if step is None:
                    raise ScenarioError(f"Step '{current_id}' not found in scenario")

                step_t0 = time.monotonic()
                sr = StepResult(
                    step_id=step.id,
                    step_type=step.type.value,
                    label=step.label,
                    status="success",
                )

                try:
                    timeout = step.timeout_sec or DEFAULT_STEP_TIMEOUT
                    next_id = await asyncio.wait_for(
                        self._execute_step(step, ctx),
                        timeout=timeout,
                    )
                    sr.output = ctx.vars.get(self._get_output_var(step))
                    sr.tokens_used = 0  # per-step tokens tracked in ctx delta

                except asyncio.TimeoutError:
                    sr.status = "timeout"
                    sr.error = f"Step timed out after {timeout}s"
                    ctx.record_error(step.id, sr.error)
                    if step.on_error:
                        next_id = step.on_error
                    else:
                        raise ScenarioError(sr.error)

                except (ScenarioFinished, ScenarioPaused):
                    raise

                except Exception as e:
                    sr.status = "failed"
                    sr.error = str(e)
                    ctx.record_error(step.id, str(e))

                    if step.retry and step.retry.max_attempts > 1:
                        next_id = await self._retry_step(step, ctx, step.retry)
                    elif step.on_error:
                        next_id = step.on_error
                    else:
                        raise

                sr.duration_ms = (time.monotonic() - step_t0) * 1000
                step_results.append(sr)
                ctx.record_step(sr.dict())

                current_id = next_id
                steps_count += 1

        except ScenarioFinished as fin:
            total_duration = (time.monotonic() - t0) * 1000
            return ScenarioRunResult(
                status="success",
                output=fin.output if fin.output is not None else ctx.last_output,
                steps_executed=step_results,
                total_tokens=ctx.tokens_used,
                total_duration_ms=total_duration,
            )

        except ScenarioPaused as pause:
            total_duration = (time.monotonic() - t0) * 1000
            return ScenarioRunResult(
                status="paused",
                output=ctx.last_output,
                steps_executed=step_results,
                total_tokens=ctx.tokens_used,
                total_duration_ms=total_duration,
                awaiting_input={
                    "step_id": pause.step_id,
                    "prompt": pause.prompt,
                    "output_var": pause.output_var,
                    "context_snapshot": ctx.snapshot(),
                },
            )

        except Exception as e:
            total_duration = (time.monotonic() - t0) * 1000
            return ScenarioRunResult(
                status="failed",
                output=ctx.last_output,
                steps_executed=step_results,
                total_tokens=ctx.tokens_used,
                total_duration_ms=total_duration,
                error=str(e),
            )

        # Normal end (current_id became None)
        total_duration = (time.monotonic() - t0) * 1000
        return ScenarioRunResult(
            status="success",
            output=ctx.last_output,
            steps_executed=step_results,
            total_tokens=ctx.tokens_used,
            total_duration_ms=total_duration,
        )

    # ── Step dispatcher ───────────────────────────────────────────────────────

    async def _execute_step(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        """Execute one step. Returns the id of the next step, or None."""
        handlers = {
            StepType.TRIGGER:        self._handle_trigger,
            StepType.SET_VARIABLE:   self._handle_set_variable,
            StepType.TRANSFORM:      self._handle_transform,
            StepType.INPUT_PROMPT:   self._handle_input_prompt,
            StepType.LLM_CALL:       self._handle_llm_call,
            StepType.LLM_STRUCTURED: self._handle_llm_structured,
            StepType.LLM_LOOP:       self._handle_llm_loop,
            StepType.SKILL_CALL:     self._handle_skill_call,
            StepType.HTTP_REQUEST:   self._handle_http_request,
            StepType.SEND_MESSAGE:   self._handle_send_message,
            StepType.TON_ACTION:     self._handle_ton_action,
            StepType.CONDITION:      self._handle_condition,
            StepType.FOREACH:        self._handle_foreach,
            StepType.PARALLEL:       self._handle_parallel,
            StepType.WAIT:           self._handle_wait,
            StepType.GOTO:           self._handle_goto,
            StepType.OUTPUT:         self._handle_output,
            StepType.ERROR_HANDLER:  self._handle_error_handler,
            StepType.SUBAGENT_CALL:  self._handle_subagent_call,
        }
        handler = handlers.get(step.type)
        if handler is None:
            raise ScenarioError(f"No handler for step type: {step.type}")
        return await handler(step, ctx)

    def _next(self, step: ScenarioStep) -> Optional[str]:
        return step.next

    def _get_output_var(self, step: ScenarioStep) -> str:
        return step.config.get("output_var", "last_output")

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _handle_trigger(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        # Trigger just marks the start, already populated in ctx.trigger
        return self._next(step)

    async def _handle_set_variable(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = SetVariableConfig(**step.config)
        for key, template in cfg.variables.items():
            rendered = ctx.render(template)
            ctx.set(key, rendered)
        return self._next(step)

    async def _handle_transform(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = TransformConfig(**step.config)
        if cfg.mode == "jinja2":
            result = ctx.render(cfg.expression)
        elif cfg.mode == "jq":
            result = await self._jq_transform(cfg.expression, ctx)
        elif cfg.mode == "python_expr":
            # safe eval using jinja2 render_expr
            result = ctx.render_expr(cfg.expression)
        else:
            raise ScenarioError(f"Unknown transform mode: {cfg.mode}")
        ctx.set(cfg.output_var, result)
        return self._next(step)

    async def _jq_transform(self, expr: str, ctx: ScenarioContext) -> Any:
        try:
            import pyjq  # optional dependency
            return pyjq.first(expr, ctx.vars)
        except ImportError:
            raise ScenarioError("pyjq not installed. Use jinja2 mode or: pip install pyjq")

    async def _handle_input_prompt(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = InputPromptConfig(**step.config)
        rendered_prompt = ctx.render(cfg.prompt)
        raise ScenarioPaused(
            step_id=step.id,
            prompt=rendered_prompt,
            output_var=cfg.output_var,
        )

    async def _handle_llm_call(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = LlmCallConfig(**step.config)
        prompt = ctx.render(cfg.prompt)
        system = ctx.render(cfg.system_prompt) if cfg.system_prompt else self.agent.system_prompt

        from app.services.agent_runtime import wrap_with_fallback, _build_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        async def _run(model_id, api_key, base_url):
            llm = _build_llm(
                model_id=model_id,
                temperature=cfg.temperature if cfg.temperature is not None else self.agent.temperature,
                max_tokens=cfg.max_tokens or self.agent.max_tokens,
                api_key=api_key,
                base_url=base_url,
            )
            messages = [SystemMessage(content=system), HumanMessage(content=prompt)]
            return await llm.ainvoke(messages)

        response = await wrap_with_fallback(self.agent, _run, primary_model=cfg.model, db=self.db)

        output = response.content if isinstance(response.content, str) else str(response.content)
        ctx.set(cfg.output_var, output)
        ctx.last_output = output
        ctx.add_tokens(self._extract_tokens(response))
        return self._next(step)


    async def _handle_llm_structured(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = LlmStructuredConfig(**step.config)
        prompt = ctx.render(cfg.prompt)
        system = ctx.render(cfg.system_prompt) if cfg.system_prompt else self.agent.system_prompt

        # Build schema instruction
        schema_str = json.dumps(cfg.output_schema.dict(), indent=2)
        full_prompt = (
            f"{prompt}\n\n"
            f"Respond ONLY with a valid JSON object matching this schema:\n{schema_str}\n"
            f"Do not include any explanation or markdown."
        )

        from app.services.agent_runtime import wrap_with_fallback, _build_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        async def _run(model_id, api_key, base_url):
            llm = _build_llm(
                model_id=model_id,
                temperature=self.agent.temperature,
                max_tokens=self.agent.max_tokens,
                api_key=api_key,
                base_url=base_url,
            )
            messages = [SystemMessage(content=system), HumanMessage(content=full_prompt)]
            return await llm.ainvoke(messages)

        response = await wrap_with_fallback(self.agent, _run, primary_model=cfg.model, db=self.db)
        raw = response.content if isinstance(response.content, str) else str(response.content)

        # Strip markdown fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ScenarioError(f"LLM did not return valid JSON: {e}\nRaw: {raw[:300]}")

        ctx.set(cfg.output_var, parsed)
        ctx.structured = parsed
        ctx.add_tokens(self._extract_tokens(response))
        return self._next(step)


    async def _handle_llm_loop(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = LlmLoopConfig(**step.config)
        items = ctx.get(cfg.items_var)
        if not isinstance(items, list):
            raise ScenarioError(f"llm_loop: '{cfg.items_var}' is not a list")

        results = []
        sem = asyncio.Semaphore(cfg.max_concurrency)

        from app.services.agent_runtime import wrap_with_fallback, _build_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        async def process_item(item: Any) -> str:
            async with sem:
                ctx_copy_vars = dict(ctx.vars)
                ctx_copy_vars[cfg.item_var] = item

                # Render prompt with item
                tmp_ctx = ScenarioContext(
                    trigger_type=ctx.trigger["type"],
                    trigger_data=ctx.trigger["data"],
                    initial_vars=ctx_copy_vars,
                )
                tmp_ctx.last_output = ctx.last_output
                tmp_ctx.structured = ctx.structured
                prompt = tmp_ctx.render(cfg.prompt)

                async def _run(model_id, api_key, base_url):
                    llm = _build_llm(
                        model_id=model_id,
                        temperature=self.agent.temperature,
                        max_tokens=self.agent.max_tokens,
                        api_key=api_key,
                        base_url=base_url,
                    )
                    messages = [
                        SystemMessage(content=self.agent.system_prompt),
                        HumanMessage(content=prompt),
                    ]
                    return await llm.ainvoke(messages)

                response = await wrap_with_fallback(self.agent, _run, primary_model=cfg.model, db=self.db)
                ctx.add_tokens(self._extract_tokens(response))
                return response.content if isinstance(response.content, str) else str(response.content)

        results = await asyncio.gather(*[process_item(item) for item in items])
        ctx.set(cfg.output_var, list(results))
        return self._next(step)


    async def _handle_skill_call(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = SkillCallConfig(**step.config)
        fn = BUILTIN_TOOLS.get(cfg.skill_name)
        if fn is None:
            # Also check installed agent skills
            fn = self._find_agent_skill(cfg.skill_name)
        if fn is None:
            raise ScenarioError(f"Skill '{cfg.skill_name}' not found")

        rendered_args = ctx.render(cfg.arguments)
        result = await fn(**rendered_args)
        ctx.set(cfg.output_var, result)
        ctx.last_output = str(result)
        return self._next(step)

    def _find_agent_skill(self, skill_name: str):
        """Find HTTP skill from agent's installed skills."""
        skills = getattr(self.agent, "skills", []) or []
        for skill in skills:
            manifest = skill.manifest
            if manifest.get("tool_name") == skill_name and manifest.get("implementation") == "http":
                url = manifest["url"]
                async def _call(_url=url, **kwargs) -> str:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(_url, json=kwargs)
                        return resp.text[:2000]
                return _call
        return None

    async def _handle_http_request(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = HttpRequestConfig(**step.config)
        url = ctx.render(cfg.url)
        headers = ctx.render(cfg.headers)
        body = ctx.render(cfg.body) if cfg.body is not None else None

        async with httpx.AsyncClient(timeout=cfg.timeout_sec) as client:
            response = await client.request(
                method=cfg.method,
                url=url,
                headers=headers,
                json=body if isinstance(body, (dict, list)) else None,
                content=body.encode() if isinstance(body, str) else None,
            )

        if cfg.parse_json and response.headers.get("content-type", "").startswith("application/json"):
            try:
                result = response.json()
            except Exception:
                result = response.text
        else:
            result = response.text[:5000]

        ctx.set(cfg.output_var, result)
        return self._next(step)

    async def _handle_send_message(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = SendMessageConfig(**step.config)

        if cfg.channel == "telegram":
            from app.core.config import settings
            token = settings.TELEGRAM_BOT_TOKEN
            if not token:
                raise ScenarioError("TELEGRAM_BOT_TOKEN not configured")
            chat_id = ctx.render(cfg.chat_id or "")
            text = ctx.render(cfg.text or "")
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": cfg.parse_mode},
                )
            result = r.json()

        elif cfg.channel == "webhook":
            url = ctx.render(cfg.webhook_url or "")
            payload = ctx.render(cfg.webhook_payload or {})
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(url, json=payload)
            result = {"status": r.status_code}
        else:
            raise ScenarioError(f"Unsupported send_message channel: {cfg.channel}")

        ctx.set("send_result", result)
        return self._next(step)

    async def _handle_ton_action(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = TonActionConfig(**step.config)
        address = ctx.render(cfg.address or "")

        if cfg.action == "get_balance":
            from app.services.skill_tools import ton_balance
            result = await ton_balance(address)
        elif cfg.action == "get_transactions":
            from app.services.skill_tools import ton_transactions
            result = await ton_transactions(address)
        elif cfg.action in ("get_nft", "get_jetton"):
            result = await self._ton_asset_info(cfg.action, address)
        elif cfg.action == "send_ton":
            # Stub — реальная отправка требует приватного ключа
            result = f"send_ton stub: {cfg.amount_ton} TON → {address}"
        else:
            raise ScenarioError(f"Unknown ton_action: {cfg.action}")

        ctx.set(cfg.output_var, result)
        ctx.last_output = str(result)
        return self._next(step)

    async def _ton_asset_info(self, action: str, address: str) -> str:
        endpoint = (
            "https://tonapi.io/v2/nfts/" if action == "get_nft"
            else "https://tonapi.io/v2/jettons/"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{endpoint}{address}")
                return r.text[:2000]
        except Exception as e:
            return f"TON API error: {e}"

    async def _handle_condition(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = ConditionConfig(**step.config)
        for branch in cfg.branches:
            try:
                result = ctx.render_expr(branch.condition)
                if result:
                    return branch.next_step
            except Exception:
                continue
        return cfg.else_step or self._next(step)

    async def _handle_foreach(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = ForeachConfig(**step.config)
        items = ctx.get(cfg.items_var)
        if not isinstance(items, list):
            raise ScenarioError(f"foreach: '{cfg.items_var}' is not a list (got {type(items).__name__})")

        results = []
        for i, item in enumerate(items[:cfg.max_iterations]):
            ctx.vars[cfg.item_var] = item
            # Run sub-steps in sequence
            sub_first = cfg.steps[0] if cfg.steps else None
            sub_id = sub_first
            for sub_step_id in cfg.steps:
                sub_step = self._step_map.get(sub_step_id)
                if sub_step is None:
                    raise ScenarioError(f"foreach sub-step '{sub_step_id}' not found")
                await self._execute_step(sub_step, ctx)
            results.append(ctx.last_output)

        ctx.vars.pop(cfg.item_var, None)
        ctx.set(cfg.output_var, results)
        return self._next(step)

    async def _handle_parallel(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = ParallelConfig(**step.config)

        async def run_branch(branch_steps: List[str]) -> Dict[str, Any]:
            # Each branch gets a shallow copy of current vars
            branch_ctx = ScenarioContext(
                trigger_type=ctx.trigger["type"],
                trigger_data=ctx.trigger["data"],
                initial_vars=dict(ctx.vars),
            )
            branch_ctx.last_output = ctx.last_output
            branch_ctx.structured = ctx.structured
            for sid in branch_steps:
                sub_step = self._step_map.get(sid)
                if sub_step is None:
                    raise ScenarioError(f"parallel sub-step '{sid}' not found")
                await self._execute_step(sub_step, branch_ctx)
            ctx.add_tokens(branch_ctx.tokens_used)
            return {"output": branch_ctx.last_output, "vars": branch_ctx.vars}

        branch_results = await asyncio.gather(*[
            run_branch(b.steps) for b in cfg.branches
        ], return_exceptions=True)

        results = {}
        for i, (branch, res) in enumerate(zip(cfg.branches, branch_results)):
            if isinstance(res, Exception):
                results[branch.label] = {"error": str(res)}
            else:
                results[branch.label] = res

        ctx.set(cfg.output_var, results)
        return self._next(step)

    async def _handle_wait(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = WaitConfig(**step.config)

        if cfg.mode == "delay":
            delay = min(cfg.delay_sec or 0, cfg.max_wait_sec)
            await asyncio.sleep(delay)

        elif cfg.mode == "until_condition":
            elapsed = 0.0
            while elapsed < cfg.max_wait_sec:
                try:
                    result = ctx.render_expr(cfg.condition or "false")
                    if result:
                        break
                except Exception:
                    pass
                await asyncio.sleep(cfg.poll_interval_sec)
                elapsed += cfg.poll_interval_sec
            else:
                raise ScenarioError(f"wait timed out after {cfg.max_wait_sec}s")

        elif cfg.mode == "until_event":
            # Simplified: just wait max_wait_sec (real event system needs pub/sub)
            await asyncio.sleep(min(cfg.poll_interval_sec, cfg.max_wait_sec))

        return self._next(step)

    async def _handle_goto(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = GotoConfig(**step.config)
        if cfg.condition:
            result = ctx.render_expr(cfg.condition)
            if not result:
                return self._next(step)
        return cfg.step_id

    async def _handle_output(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = OutputConfig(**step.config)
        output = ctx.render(cfg.value)
        ctx.last_output = output
        raise ScenarioFinished(output=output)

    async def _handle_error_handler(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = ErrorHandlerConfig(**step.config)
        last_error = ctx.errors[-1] if ctx.errors else {}
        message = ctx.render(cfg.message.replace("{{ error.message }}", last_error.get("error", "unknown")))
        ctx.set(cfg.output_var, {"message": message, "errors": ctx.errors})
        if cfg.re_raise and ctx.errors:
            raise ScenarioError(ctx.errors[-1]["error"])
        return self._next(step)

    async def _handle_subagent_call(self, step: ScenarioStep, ctx: ScenarioContext) -> Optional[str]:
        cfg = SubagentCallConfig(**step.config)
        agent_id = ctx.render(cfg.agent_id)
        input_text = ctx.render(cfg.input)

        if self.db is None:
            raise ScenarioError("subagent_call requires a database session")

        from sqlalchemy.future import select
        from app.models.agent import Agent as AgentModel
        result = await self.db.execute(
            select(AgentModel).where(AgentModel.id == agent_id)
        )
        sub_agent = result.scalars().first()
        if not sub_agent:
            raise ScenarioError(f"Sub-agent '{agent_id}' not found")

        from app.services.agent_runtime import run_agent_task
        run_result = await asyncio.wait_for(
            run_agent_task(sub_agent, input_text, db=self.db),
            timeout=cfg.timeout_sec,
        )
        ctx.set(cfg.output_var, run_result.get("output", ""))
        ctx.add_tokens(run_result.get("tokens_used", 0))
        return self._next(step)

    async def _retry_step(self, step: ScenarioStep, ctx: ScenarioContext, retry) -> Optional[str]:
        delay = retry.delay_sec
        for attempt in range(retry.max_attempts - 1):
            await asyncio.sleep(delay)
            try:
                return await self._execute_step(step, ctx)
            except Exception:
                if retry.backoff == "exponential":
                    delay *= 2
        raise ScenarioError(f"Step '{step.id}' failed after {retry.max_attempts} attempts")

    # ── LLM helpers ───────────────────────────────────────────────────────────

    def _get_llm(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        from app.services.agent_runtime import _build_llm
        return _build_llm(
            model_id=model or self.agent.model,
            temperature=temperature if temperature is not None else self.agent.temperature,
            max_tokens=max_tokens or self.agent.max_tokens,
            api_key=self._api_key,
            base_url=self._base_url,
        )

    def _extract_tokens(self, response) -> int:
        from app.services.agent_runtime import _extract_tokens
        return _extract_tokens(response)


# ── Public entry point ────────────────────────────────────────────────────────

async def execute_scenario(
    agent,
    trigger_type: str = "manual",
    trigger_data: Optional[Dict[str, Any]] = None,
    user_input: Optional[str] = None,
    resume_context: Optional[Dict[str, Any]] = None,
    db=None,
) -> ScenarioRunResult:
    """
    Load the agent's scenario and execute it.
    Falls back to plain LLM if no scenario configured.
    """
    from app.services.agent_runtime import run_agent_task, _resolve_api_key

    scenario_data = getattr(agent, "scenario", None)
    if not scenario_data:
        # No scenario — fall back to plain agent runtime
        result = await run_agent_task(agent, user_input or "", db=db)
        return ScenarioRunResult(
            status="success",
            output=result["output"],
            total_tokens=result.get("tokens_used", 0),
            total_duration_ms=0,
        )

    scenario = Scenario(**scenario_data)

    api_key = None
    base_url = None
    if db is not None:
        api_key, base_url = await _resolve_api_key(agent.user_id, agent.model, db)

    executor = ScenarioExecutor(
        scenario=scenario,
        agent=agent,
        db=db,
        api_key=api_key,
        base_url=base_url,
    )
    return await executor.run(
        trigger_type=trigger_type,
        trigger_data=trigger_data,
        user_input=user_input,
        resume_context=resume_context,
    )
