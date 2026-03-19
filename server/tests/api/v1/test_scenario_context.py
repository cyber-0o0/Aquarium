"""
Tests for ScenarioContext (scenario_context.py).

Goal: Verify that the context engine works correctly so that
AI agents can read/write variables, render Jinja2 templates,
evaluate conditions, and resume paused scenarios properly.

Coverage:
  - Variable set/get
  - Jinja2 render (strings, dicts, lists, fast-path)
  - render_expr (condition evaluation for CONDITION step)
  - Snapshot / restore (for INPUT_PROMPT pause/resume)
  - Token counter
  - Error recording
  - Foreach loop stack (push / advance / pop)
  - _ContextProxy attribute access
"""

import pytest
from app.services.scenario_context import ScenarioContext


# ══════════════════════════════════════════════════════════════════════════════
# Variable management
# ══════════════════════════════════════════════════════════════════════════════

class TestVariableManagement:

    def test_set_and_get(self):
        ctx = ScenarioContext()
        ctx.set("price", 42)
        assert ctx.get("price") == 42

    def test_get_missing_key_returns_default(self):
        ctx = ScenarioContext()
        assert ctx.get("missing") is None
        assert ctx.get("missing", "fallback") == "fallback"

    def test_set_last_output_updates_attribute(self):
        """Setting 'last_output' key must also update ctx.last_output."""
        ctx = ScenarioContext()
        ctx.set("last_output", "Hello agent")
        assert ctx.last_output == "Hello agent"

    def test_initial_vars_available(self):
        ctx = ScenarioContext(initial_vars={"token": "ABC", "limit": 10})
        assert ctx.get("token") == "ABC"
        assert ctx.get("limit") == 10

    def test_user_input_stored_as_last_output(self):
        ctx = ScenarioContext(user_input="What is TON price?")
        assert ctx.last_output == "What is TON price?"


# ══════════════════════════════════════════════════════════════════════════════
# Jinja2 rendering
# ══════════════════════════════════════════════════════════════════════════════

class TestRender:

    def test_render_plain_string(self):
        """Strings without {{ }} must be returned unchanged (fast path)."""
        ctx = ScenarioContext()
        assert ctx.render("no template here") == "no template here"

    def test_render_variable_substitution(self):
        ctx = ScenarioContext(initial_vars={"coin": "TON", "price": 5})
        result = ctx.render("The price of {{ coin }} is ${{ price }}")
        assert result == "The price of TON is $5"

    def test_render_dict_values_recursively(self):
        ctx = ScenarioContext(initial_vars={"name": "Alice"})
        template = {"greeting": "Hello {{ name }}", "static": "unchanged"}
        result = ctx.render(template)
        assert result["greeting"] == "Hello Alice"
        assert result["static"] == "unchanged"

    def test_render_list_elements_recursively(self):
        ctx = ScenarioContext(initial_vars={"x": 7})
        result = ctx.render(["value is {{ x }}", "static"])
        assert result[0] == "value is 7"
        assert result[1] == "static"

    def test_render_non_string_passthrough(self):
        """Non-string values (int, None) must be returned as-is."""
        ctx = ScenarioContext()
        assert ctx.render(42) == 42
        assert ctx.render(None) is None
        assert ctx.render(3.14) == 3.14

    def test_render_last_output_accessible(self):
        ctx = ScenarioContext(user_input="initial message")
        result = ctx.render("Echo: {{ last_output }}")
        assert result == "Echo: initial message"

    def test_render_trigger_data_accessible(self):
        ctx = ScenarioContext(trigger_type="schedule", trigger_data={"job": "daily"})
        result = ctx.render("trigger={{ trigger.type }}")
        assert result == "trigger=schedule"

    def test_render_builtin_functions(self):
        """now() and uuid() must be available inside templates."""
        ctx = ScenarioContext()
        result_now = ctx.render("{{ now() }}")
        result_uuid = ctx.render("{{ uuid() }}")
        assert "T" in result_now  # ISO datetime
        assert len(result_uuid) == 36  # UUID format

    def test_render_undefined_variable_raises(self):
        """Accessing an undefined variable inside a template must raise ValueError."""
        ctx = ScenarioContext()
        with pytest.raises(ValueError, match="Template render error"):
            ctx.render("{{ undefined_var }}")

    def test_render_nested_dict_recursion(self):
        ctx = ScenarioContext(initial_vars={"val": "deep"})
        template = {"outer": {"inner": "{{ val }}"}}
        result = ctx.render(template)
        assert result["outer"]["inner"] == "deep"


# ══════════════════════════════════════════════════════════════════════════════
# render_expr — condition evaluation
# ══════════════════════════════════════════════════════════════════════════════

class TestRenderExpr:
    """render_expr is used by CONDITION step to branch the scenario graph."""

    def test_true_condition(self):
        ctx = ScenarioContext(initial_vars={"score": 100})
        assert ctx.render_expr("score > 50") is True

    def test_false_condition(self):
        ctx = ScenarioContext(initial_vars={"score": 10})
        assert ctx.render_expr("score > 50") is False

    def test_string_true(self):
        ctx = ScenarioContext()
        assert ctx.render_expr("'yes'") is True  # non-empty string → True? No — keep as-is
        # Actually render_expr returns the raw string 'yes' which is truthy
        result = ctx.render_expr("'yes'")
        # The 'yes' string isn't in the special mapping, so it comes back as the string
        assert result  # truthy

    def test_string_false_values(self):
        """'false', '0', 'no', 'none', 'null', '' must evaluate to False."""
        ctx = ScenarioContext()
        for val in ("false", "0", "no", "none", "null", ""):
            # We can't render these as literals directly, but we can set a var
            ctx.set("flag", val)
            result = ctx.render_expr("flag")
            assert result is False, f"Expected False for '{val}', got {result!r}"

    def test_string_true_values(self):
        """'true', '1', 'yes' must evaluate to True."""
        ctx = ScenarioContext()
        for val in ("true", "1", "yes"):
            ctx.set("flag", val)
            result = ctx.render_expr("flag")
            assert result is True, f"Expected True for '{val}', got {result!r}"

    def test_equality_check(self):
        ctx = ScenarioContext(initial_vars={"status": "success"})
        assert ctx.render_expr("status == 'success'") is True
        assert ctx.render_expr("status == 'failed'") is False

    def test_arithmetic_expression(self):
        ctx = ScenarioContext(initial_vars={"a": 3, "b": 4})
        result = ctx.render_expr("a + b")
        assert result == "7"  # rendered as string by Jinja2

    def test_boolean_and(self):
        ctx = ScenarioContext(initial_vars={"x": 5, "y": 10})
        assert ctx.render_expr("x > 0 and y > 0") is True
        assert ctx.render_expr("x > 0 and y > 100") is False


# ══════════════════════════════════════════════════════════════════════════════
# Snapshot / Restore (pause & resume for INPUT_PROMPT)
# ══════════════════════════════════════════════════════════════════════════════

class TestSnapshotRestore:

    def test_snapshot_captures_state(self):
        ctx = ScenarioContext(
            trigger_type="telegram",
            trigger_data={"chat_id": "12345"},
            initial_vars={"step": "ask_address"},
        )
        ctx.last_output = "Please enter your wallet"
        ctx.tokens_used = 150

        snap = ctx.snapshot()

        assert snap["trigger"]["type"] == "telegram"
        assert snap["vars"]["step"] == "ask_address"
        assert snap["last_output"] == "Please enter your wallet"
        assert snap["tokens_used"] == 150

    def test_restore_from_snapshot(self):
        snap = {
            "trigger": {"type": "schedule", "data": {"cron": "* * * * *"}, "started_at": "2024-01-01T00:00:00+00:00"},
            "vars": {"wallet": "EQuser_wallet", "amount": 5},
            "last_output": "processing",
            "structured": {"parsed": True},
            "tokens_used": 300,
        }

        ctx = ScenarioContext.from_snapshot(snap)

        assert ctx.trigger["type"] == "schedule"
        assert ctx.get("wallet") == "EQuser_wallet"
        assert ctx.last_output == "processing"
        assert ctx.structured == {"parsed": True}
        assert ctx.tokens_used == 300

    def test_snapshot_roundtrip(self):
        """Snapshot then restore must produce identical state."""
        ctx = ScenarioContext(
            trigger_type="manual",
            initial_vars={"key": "value", "num": 99},
        )
        ctx.last_output = "done"
        ctx.tokens_used = 42

        snap = ctx.snapshot()
        ctx2 = ScenarioContext.from_snapshot(snap)

        assert ctx2.get("key") == "value"
        assert ctx2.get("num") == 99
        assert ctx2.last_output == "done"
        assert ctx2.tokens_used == 42

    def test_restored_context_can_render_templates(self):
        """After restore, Jinja2 rendering must still work with restored variables."""
        snap = {
            "trigger": {"type": "manual", "data": {}, "started_at": "2024-01-01T00:00:00+00:00"},
            "vars": {"city": "Moscow"},
            "last_output": "",
            "structured": None,
            "tokens_used": 0,
        }
        ctx = ScenarioContext.from_snapshot(snap)
        assert ctx.render("Weather in {{ city }}") == "Weather in Moscow"


# ══════════════════════════════════════════════════════════════════════════════
# Token tracking
# ══════════════════════════════════════════════════════════════════════════════

class TestTokenTracking:

    def test_add_tokens_accumulates(self):
        ctx = ScenarioContext()
        ctx.add_tokens(100)
        ctx.add_tokens(250)
        assert ctx.tokens_used == 350

    def test_initial_tokens_zero(self):
        ctx = ScenarioContext()
        assert ctx.tokens_used == 0


# ══════════════════════════════════════════════════════════════════════════════
# Error recording
# ══════════════════════════════════════════════════════════════════════════════

class TestErrorRecording:

    def test_record_error(self):
        ctx = ScenarioContext()
        ctx.record_error("step_1", "Timeout after 30s")
        assert len(ctx.errors) == 1
        assert ctx.errors[0]["step_id"] == "step_1"
        assert ctx.errors[0]["error"] == "Timeout after 30s"

    def test_multiple_errors_appended(self):
        ctx = ScenarioContext()
        ctx.record_error("step_a", "error A")
        ctx.record_error("step_b", "error B")
        assert len(ctx.errors) == 2
        assert ctx.errors[-1]["step_id"] == "step_b"


# ══════════════════════════════════════════════════════════════════════════════
# Foreach loop stack
# ══════════════════════════════════════════════════════════════════════════════

class TestLoopStack:

    def test_push_loop_sets_first_item(self):
        ctx = ScenarioContext()
        ctx.push_loop(["a", "b", "c"], "item")
        assert ctx.get("item") == "a"

    def test_advance_loop_moves_to_next(self):
        ctx = ScenarioContext()
        ctx.push_loop(["x", "y", "z"], "item")
        assert ctx.advance_loop() is True
        assert ctx.get("item") == "y"

    def test_advance_loop_returns_false_at_end(self):
        ctx = ScenarioContext()
        ctx.push_loop(["only"], "item")
        assert ctx.advance_loop() is False

    def test_pop_loop_removes_variable(self):
        ctx = ScenarioContext()
        ctx.push_loop([1, 2, 3], "num")
        ctx.pop_loop()
        assert ctx.get("num") is None
        assert len(ctx.loop_stack) == 0

    def test_empty_list_push(self):
        """Pushing an empty list should not set the item variable."""
        ctx = ScenarioContext()
        ctx.push_loop([], "item")
        assert ctx.get("item") is None

    def test_nested_loops(self):
        ctx = ScenarioContext()
        ctx.push_loop(["outer_a", "outer_b"], "outer")
        ctx.push_loop([1, 2], "inner")
        assert ctx.get("inner") == 1
        assert ctx.get("outer") == "outer_a"

        ctx.advance_loop()
        assert ctx.get("inner") == 2

        ctx.pop_loop()
        assert ctx.get("inner") is None
        assert ctx.get("outer") == "outer_a"


# ══════════════════════════════════════════════════════════════════════════════
# _ContextProxy
# ══════════════════════════════════════════════════════════════════════════════

class TestContextProxy:
    """ctx proxy is exposed as 'ctx' inside Jinja2 templates."""

    def test_ctx_vars_accessible_in_template(self):
        ctx = ScenarioContext(initial_vars={"balance": "5.0 TON"})
        result = ctx.render("Balance: {{ ctx.vars.balance }}")
        assert result == "Balance: 5.0 TON"

    def test_ctx_last_output_in_template(self):
        ctx = ScenarioContext(user_input="user said this")
        result = ctx.render("{{ ctx.last_output }}")
        assert result == "user said this"

    def test_ctx_get_method_in_template(self):
        ctx = ScenarioContext(initial_vars={"x": 10})
        result = ctx.render("{{ ctx.get('x', 0) }}")
        assert result == "10"

    def test_ctx_attribute_shortcut(self):
        """ctx.myvar should be equivalent to ctx.vars['myvar'] inside templates."""
        ctx = ScenarioContext(initial_vars={"myvar": "hello"})
        result = ctx.render("{{ ctx.myvar }}")
        assert result == "hello"

    def test_ctx_missing_attribute_raises(self):
        """Accessing undefined ctx attribute must raise (StrictUndefined)."""
        ctx = ScenarioContext()
        with pytest.raises(ValueError, match="Template render error"):
            ctx.render("{{ ctx.no_such_var }}")
