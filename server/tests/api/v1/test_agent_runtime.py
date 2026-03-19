"""
Unit tests for AgentRuntime.
LLM and external calls are fully mocked — fast, no API keys needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage


def make_agent(skills=None):
    agent = MagicMock()
    agent.model = "gpt-4o"
    agent.temperature = 0.7
    agent.max_tokens = 512
    agent.system_prompt = "You are helpful."
    agent.skills = skills or []
    return agent


def make_skill(tool_name: str, implementation: str = "builtin"):
    skill = MagicMock()
    skill.description = f"Tool: {tool_name}"
    skill.manifest = {
        "tool_name": tool_name,
        "description": f"Runs {tool_name}",
        "parameters": {"query": {"type": "string", "description": "input"}},
        "required": ["query"],
        "implementation": implementation,
    }
    return skill


# ── _setup_llm ─────────────────────────────────────────────────────────────────

def test_setup_llm_gpt():
    from app.services.agent_runtime import AgentRuntime
    with patch("app.services.agent_runtime.ChatOpenAI") as mock_llm:
        AgentRuntime(make_agent())
        mock_llm.assert_called_once()


def test_setup_llm_claude():
    from app.services.agent_runtime import AgentRuntime
    agent = make_agent()
    agent.model = "claude-3-5-sonnet"
    with patch("app.services.agent_runtime.ChatAnthropic") as mock_llm:
        AgentRuntime(agent)
        mock_llm.assert_called_once()


def test_setup_llm_unsupported():
    from app.services.agent_runtime import AgentRuntime
    agent = make_agent()
    agent.model = "llama-3"
    with pytest.raises(ValueError, match="Unsupported model"):
        AgentRuntime(agent)


# ── _build_tools ───────────────────────────────────────────────────────────────

def test_build_tools_no_skills():
    from app.services.agent_runtime import AgentRuntime
    with patch("app.services.agent_runtime.ChatOpenAI"):
        runtime = AgentRuntime(make_agent(skills=[]))
    assert runtime._build_tools() == []


def test_build_tools_known_builtin():
    from app.services.agent_runtime import AgentRuntime
    with patch("app.services.agent_runtime.ChatOpenAI"):
        runtime = AgentRuntime(make_agent(skills=[make_skill("web_search")]))
    tools = runtime._build_tools()
    assert len(tools) == 1
    assert tools[0].name == "web_search"


def test_build_tools_unknown_builtin_skipped():
    from app.services.agent_runtime import AgentRuntime
    with patch("app.services.agent_runtime.ChatOpenAI"):
        runtime = AgentRuntime(make_agent(skills=[make_skill("does_not_exist")]))
    assert runtime._build_tools() == []


def test_build_tools_multiple():
    from app.services.agent_runtime import AgentRuntime
    skills = [make_skill("web_search"), make_skill("crypto_price"), make_skill("get_datetime")]
    with patch("app.services.agent_runtime.ChatOpenAI"):
        runtime = AgentRuntime(make_agent(skills=skills))
    names = [t.name for t in runtime._build_tools()]
    assert set(names) == {"web_search", "crypto_price", "get_datetime"}


# ── run_task — no skills ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_task_no_skills_plain_llm():
    from app.services.agent_runtime import AgentRuntime

    mock_response = MagicMock()
    mock_response.content = "Hello!"
    mock_response.response_metadata = {"token_usage": {"total_tokens": 20}}

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.agent_runtime.ChatOpenAI", return_value=mock_llm):
        runtime = AgentRuntime(make_agent(skills=[]))
        result = await runtime.run_task("Say hello")

    assert result["output"] == "Hello!"
    assert result["tokens_used"] == 20
    assert result["tools_used"] == []
    assert result["status"] == "success"


# ── run_task — with skills, no tool calls needed ───────────────────────────────

@pytest.mark.asyncio
async def test_run_task_with_skills_no_tool_calls():
    """LLM answers directly without calling any tool."""
    from app.services.agent_runtime import AgentRuntime

    # AIMessage with no tool_calls → final answer on first round
    ai_response = AIMessage(content="The answer is 42.")
    ai_response.response_metadata = {"token_usage": {"total_tokens": 15}}

    mock_llm_bound = MagicMock()
    mock_llm_bound.ainvoke = AsyncMock(return_value=ai_response)

    mock_llm = MagicMock()
    mock_llm.bind_tools = MagicMock(return_value=mock_llm_bound)

    with patch("app.services.agent_runtime.ChatOpenAI", return_value=mock_llm):
        runtime = AgentRuntime(make_agent(skills=[make_skill("web_search")]))
        result = await runtime.run_task("What is 6 * 7?")

    assert result["output"] == "The answer is 42."
    assert result["tools_used"] == []
    assert result["status"] == "success"


# ── run_task — with skills, one tool call ─────────────────────────────────────

@pytest.mark.asyncio
async def test_run_task_with_one_tool_call():
    """LLM calls crypto_price, gets result, then answers."""
    from app.services.agent_runtime import AgentRuntime
    from langchain_core.messages import AIMessage

    # Round 1: LLM requests a tool call
    tool_call_response = AIMessage(content="")
    tool_call_response.tool_calls = [
        {"name": "crypto_price", "args": {"coin_id": "the-open-network"}, "id": "call_001"}
    ]
    tool_call_response.response_metadata = {}

    # Round 2: LLM gives final answer after seeing tool result
    final_response = AIMessage(content="TON is $5.10")
    final_response.tool_calls = []
    final_response.response_metadata = {"token_usage": {"total_tokens": 50}}

    mock_llm_bound = MagicMock()
    mock_llm_bound.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])

    mock_llm = MagicMock()
    mock_llm.bind_tools = MagicMock(return_value=mock_llm_bound)

    # Mock the actual tool execution
    with patch("app.services.agent_runtime.ChatOpenAI", return_value=mock_llm), \
         patch("app.services.skill_tools.BUILTIN_TOOLS", {"crypto_price": AsyncMock(return_value="TON: $5.10")}):
        runtime = AgentRuntime(make_agent(skills=[make_skill("crypto_price")]))
        result = await runtime.run_task("What is TON price?")

    assert result["output"] == "TON is $5.10"
    assert "crypto_price" in result["tools_used"]
    assert result["status"] == "success"


# ── execute_agent_task ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_agent_task():
    from app.services.agent_runtime import execute_agent_task

    mock_response = MagicMock()
    mock_response.content = "Done"
    mock_response.response_metadata = {"token_usage": {"total_tokens": 5}}

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.agent_runtime.ChatOpenAI", return_value=mock_llm):
        result = await execute_agent_task(make_agent(), "Do something")

    assert result["status"] == "success"
    assert result["output"] == "Done"
