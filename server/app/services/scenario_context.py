"""
ScenarioContext — изолированная среда выполнения одного запуска сценария.

Хранит:
  - vars:        пользовательские переменные (set_variable / transform / output_var)
  - trigger:     данные триггера (тип, payload)
  - steps:       история выполненных шагов
  - last_output: последний текстовый вывод LLM
  - structured:  последний структурированный вывод
  - tokens_used: счётчик токенов
  - errors:      список ошибок
  - loop_stack:  стек итераторов для foreach-шагов

Jinja2-шаблоны рендерятся через render(template_str) — доступны все vars,
плюс специальные: ctx, trigger, now(), uuid(), etc.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from jinja2 import Environment, Undefined, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


class ScenarioContext:
    def __init__(
        self,
        trigger_type: str = "manual",
        trigger_data: Optional[Dict[str, Any]] = None,
        initial_vars: Optional[Dict[str, Any]] = None,
        user_input: Optional[str] = None,
    ):
        self.trigger = {
            "type": trigger_type,
            "data": trigger_data or {},
            "started_at": datetime.now(UTC).isoformat(),
        }
        self.vars: Dict[str, Any] = dict(initial_vars or {})
        self.last_output: str = user_input or ""
        self.structured: Any = None
        self.tokens_used: int = 0
        self.errors: List[Dict[str, Any]] = []
        self.steps_results: List[Dict[str, Any]] = []

        # Foreach/loop stack: List of {"items": [...], "index": 0, "item_var": "item"}
        self.loop_stack: List[Dict[str, Any]] = []

        # Jinja2 sandbox
        self._jinja: SandboxedEnvironment = SandboxedEnvironment(
            undefined=StrictUndefined,
            autoescape=False,
        )
        self._jinja.globals.update({
            "now": lambda: datetime.now(UTC).isoformat(),
            "uuid": lambda: str(_uuid.uuid4()),
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
        })

    # ── Jinja2 rendering ──────────────────────────────────────────────────────

    def render(self, template: Any) -> Any:
        """
        Render a value through Jinja2.
        - str  → render as template
        - dict → render all string values recursively
        - list → render all string elements recursively
        - other → return as-is
        """
        if isinstance(template, str):
            return self._render_str(template)
        elif isinstance(template, dict):
            return {k: self.render(v) for k, v in template.items()}
        elif isinstance(template, list):
            return [self.render(item) for item in template]
        return template

    def _render_str(self, template: str) -> str:
        if "{{" not in template and "{%" not in template:
            return template  # fast path — no template syntax
        ctx_proxy = _ContextProxy(self)
        try:
            tmpl = self._jinja.from_string(template)
            return tmpl.render(
                ctx=ctx_proxy,
                trigger=self.trigger,
                vars=self.vars,
                last_output=self.last_output,
                structured=self.structured,
                **self.vars,               # allow {{ price }} directly
            )
        except Exception as e:
            raise ValueError(f"Template render error in '{template[:80]}': {e}")

    def render_expr(self, expr: str) -> Any:
        """
        Evaluate a Jinja2 expression and return the Python value.
        Used by condition branches.
        Example: "ctx.vars.price > 100" → True/False
        """
        wrapped = "{{ " + expr + " }}"
        raw = self.render(wrapped)
        # Convert string truthy values
        if isinstance(raw, str):
            low = raw.strip().lower()
            if low in ("true", "1", "yes"):
                return True
            if low in ("false", "0", "no", "none", "null", ""):
                return False
        return raw

    # ── Variable management ───────────────────────────────────────────────────

    def set(self, key: str, value: Any) -> None:
        self.vars[key] = value
        # Also update last_output if key is the conventional one
        if key == "last_output" and isinstance(value, str):
            self.last_output = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.vars.get(key, default)

    # ── Token tracking ────────────────────────────────────────────────────────

    def add_tokens(self, n: int) -> None:
        self.tokens_used += n

    # ── Step result recording ─────────────────────────────────────────────────

    def record_step(self, result: Dict[str, Any]) -> None:
        self.steps_results.append(result)

    def record_error(self, step_id: str, error: str) -> None:
        self.errors.append({"step_id": step_id, "error": error})

    # ── Foreach loop stack ────────────────────────────────────────────────────

    def push_loop(self, items: List[Any], item_var: str) -> None:
        self.loop_stack.append({"items": items, "index": 0, "item_var": item_var})
        if items:
            self.vars[item_var] = items[0]

    def advance_loop(self) -> bool:
        """Move to next iteration. Returns True if there are more items."""
        if not self.loop_stack:
            return False
        frame = self.loop_stack[-1]
        frame["index"] += 1
        if frame["index"] < len(frame["items"]):
            self.vars[frame["item_var"]] = frame["items"][frame["index"]]
            return True
        return False

    def pop_loop(self) -> None:
        if self.loop_stack:
            frame = self.loop_stack.pop()
            # Remove loop variable from vars
            self.vars.pop(frame["item_var"], None)

    def snapshot(self) -> Dict[str, Any]:
        """Serializable snapshot for pause/resume (input_prompt)."""
        return {
            "trigger": self.trigger,
            "vars": self.vars,
            "last_output": self.last_output,
            "structured": self.structured,
            "tokens_used": self.tokens_used,
        }

    @classmethod
    def from_snapshot(cls, snap: Dict[str, Any]) -> "ScenarioContext":
        ctx = cls(
            trigger_type=snap["trigger"]["type"],
            trigger_data=snap["trigger"]["data"],
            initial_vars=snap.get("vars", {}),
        )
        ctx.last_output = snap.get("last_output", "")
        ctx.structured = snap.get("structured")
        ctx.tokens_used = snap.get("tokens_used", 0)
        return ctx


class _ContextProxy:
    """Proxy object exposed as `ctx` inside Jinja2 templates."""
    def __init__(self, ctx: ScenarioContext):
        self._ctx = ctx

    @property
    def vars(self) -> Dict[str, Any]:
        return self._ctx.vars

    @property
    def last_output(self) -> str:
        return self._ctx.last_output

    @property
    def structured(self) -> Any:
        return self._ctx.structured

    @property
    def tokens_used(self) -> int:
        return self._ctx.tokens_used

    def get(self, key: str, default: Any = None) -> Any:
        return self._ctx.vars.get(key, default)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._ctx.vars[name]
        except KeyError:
            raise AttributeError(f"ctx has no variable '{name}'")
