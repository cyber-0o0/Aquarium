"""
AgentRuntime — runs an agent with its installed skills as LangChain tools.
"""

from __future__ import annotations

import os
import sys
import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional, Type

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.core.config import settings
from app.core.models_registry import SUPPORTED_MODELS, get_model_info
from app.models.agent import Agent as AgentModel
from app.models.feed_post import FeedPost
from app.services.skill_tools import BUILTIN_TOOLS
from app.services.memory_service import get_memory_context, update_memory

MAX_ITERATIONS = 10


# ── Args schema builder ───────────────────────────────────────────────────────

_JSON_TYPE_MAP = {
    "string":  (str, ...),
    "integer": (int, ...),
    "number":  (float, ...),
    "boolean": (bool, ...),
}


def _build_args_schema(tool_name: str, manifest: Dict[str, Any]) -> Optional[Type[BaseModel]]:
    params: Dict[str, Any] = manifest.get("parameters") or {}
    required: List[str] = manifest.get("required") or []
    if not params:
        return None
    fields: Dict[str, Any] = {}
    for field_name, field_spec in params.items():
        if not isinstance(field_spec, dict):
            continue
        json_type = field_spec.get("type", "string")
        py_type, _ = _JSON_TYPE_MAP.get(json_type, (str, ...))
        description = field_spec.get("description", "")
        default = field_spec.get("default", ...)
        if field_name not in required and default is ...:
            fields[field_name] = (Optional[py_type], Field(default=None, description=description))
        elif default is not ...:
            fields[field_name] = (py_type, Field(default=default, description=description))
        else:
            fields[field_name] = (py_type, Field(..., description=description))
    model_name = "".join(w.capitalize() for w in tool_name.split("_")) + "Args"
    return create_model(model_name, **fields)


# ── LLM factory ───────────────────────────────────────────────────────────────

def _build_llm(
    model_id: str,
    temperature: float,
    max_tokens: int,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    streaming: bool = False,
):
    meta = get_model_info(model_id)
    if meta is None:
        raise ValueError(f"Unknown model: {model_id}")
    provider = meta["provider"]

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_id, temperature=temperature, max_tokens=max_tokens,
            api_key=(api_key if api_key else settings.OPENAI_API_KEY) or None, 
            base_url=base_url,
            streaming=streaming,
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_id, temperature=temperature, max_tokens=max_tokens,
            api_key=(api_key if api_key else settings.ANTHROPIC_API_KEY) or None, 
            base_url=base_url,
            streaming=streaming,
        )
    if provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("pip install langchain-google-genai")
        return ChatGoogleGenerativeAI(
            model=model_id, temperature=temperature, max_output_tokens=max_tokens,
            google_api_key=(api_key if api_key else settings.GOOGLE_API_KEY) or None,
        )
    if provider == "mistral":
        try:
            from langchain_mistralai import ChatMistralAI
        except ImportError:
            raise ImportError("pip install langchain-mistralai")
        return ChatMistralAI(
            model=model_id, temperature=temperature, max_tokens=max_tokens,
            api_key=(api_key if api_key else settings.MISTRAL_API_KEY) or None, 
            endpoint=base_url,
            streaming=streaming,
        )
    if provider == "openai_compatible":
        from langchain_openai import ChatOpenAI
        env_key = _env_key(meta.get("api_key_env"))
        return ChatOpenAI(
            model=model_id, temperature=temperature, max_tokens=max_tokens,
            api_key=(api_key if api_key else env_key) or None,
            base_url=base_url or meta.get("base_url"),
            streaming=streaming,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def _env_key(env_var: Optional[str]) -> Optional[str]:
    if not env_var:
        return None
    return getattr(settings, env_var, None) or os.environ.get(env_var)


# ── Key resolver ──────────────────────────────────────────────────────────────

async def _resolve_api_key(user_id: str, model_id: str, db) -> tuple[Optional[str], Optional[str]]:
    from sqlalchemy.future import select
    from app.models.user_api_key import UserApiKey
    from app.core.encryption import decrypt_key

    meta = get_model_info(model_id)
    if meta is None:
        return None, None
    provider = meta["provider"]

    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
        ).order_by(UserApiKey.created_at.desc()).limit(1)
    )
    user_key_row = result.scalars().first()
    if user_key_row:
        raw_key = decrypt_key(user_key_row.encrypted_key)
        if raw_key:
            return raw_key, user_key_row.base_url

    # Fallback to platform settings
    key_env = meta.get("api_key_env")
    base_env = key_env.replace("_KEY", "_BASE") if key_env else None
    
    key = _env_key(key_env)
    base = _env_key(base_env) or meta.get("base_url")
    
    return key, base


# ── AgentRuntime ──────────────────────────────────────────────────────────────

class AgentRuntime:
    def __init__(
        self,
        agent: AgentModel,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        message_id: Optional[int] = None,
    ):
        self.agent = agent
        self.model = model_id or agent.model
        self._api_key = api_key
        self._base_url = base_url
        self.chat_id = chat_id
        self.message_id = message_id

    def _get_llm(self, streaming: bool = False):
        return _build_llm(
            model_id=self.model,
            temperature=self.agent.temperature,
            max_tokens=self.agent.max_tokens,
            api_key=self._api_key,
            base_url=self._base_url,
            streaming=streaming,
        )

    def _build_tools(self) -> List[StructuredTool]:
        tools = []
        for skill in (getattr(self.agent, "skills", []) or []):
            manifest = skill.manifest
            tool_name = manifest.get("tool_name")
            impl = manifest.get("implementation", "builtin")
            args_schema = _build_args_schema(tool_name, manifest)

            if impl == "builtin":
                fn = BUILTIN_TOOLS.get(tool_name)
                if fn is None:
                    continue
                tools.append(StructuredTool.from_function(
                    coroutine=fn, name=tool_name,
                    description=manifest.get("description", skill.description),
                    args_schema=args_schema,
                ))
            elif impl == "http":
                url = manifest.get("url")
                if not url:
                    continue
                async def _http_call(_url=url, **kwargs) -> str:
                    import httpx
                    try:
                        async with httpx.AsyncClient(timeout=15) as client:
                            resp = await client.post(_url, json=kwargs)
                            return resp.text[:2000]
                    except Exception as e:
                        return f"Skill call error: {e}"
                tools.append(StructuredTool.from_function(
                    coroutine=_http_call, name=tool_name,
                    description=manifest.get("description", skill.description),
                    args_schema=args_schema,
                ))
        # Add Standard Skills (Default enabled)
        for tool_name in ["get_wallet_balance", "get_wallet_transactions", "set_message_reaction"]:
            fn = BUILTIN_TOOLS.get(tool_name)
            if fn:
                if tool_name == "set_message_reaction":
                    async def _react_tool(reaction: str = "👍", cid=self.chat_id, mid=self.message_id, _fn=fn):
                        print(f"DEBUG: Calling react tool for chat={cid}, msg={mid}, emoji={reaction}")
                        if not cid or not mid:
                            return "Error: Chat ID or Message ID not provided for reaction."
                        return await _fn(cid, mid, reaction)
                    
                    tools.append(StructuredTool.from_function(
                        coroutine=_react_tool, name=tool_name,
                        description="Set an emoji reaction on the user's current message. Use this to acknowledge or like a message.",
                    ))
                else:
                    description = "Get wallet balance" if "balance" in tool_name else "Get recent wallet transactions"
                    tools.append(StructuredTool.from_function(
                        coroutine=fn, name=tool_name,
                        description=f"{description}. Use the wallet address from the context if not provided.",
                    ))

        return tools

    def get_full_system_prompt(self, memory_ctx: str = "") -> str:
        wallet_context = ""
        if self.agent.user and self.agent.user.wallet_address:
            wallet_context = (
                f"\n\n[USER WALLET INFO]\n"
                f"Connected TON Wallet: `{self.agent.user.wallet_address}`\n"
                f"ALWAYS use this address for balance, transactions, or DeFi tool calls unless the user specifies a different one."
            )
        
        format_instruction = (
            "\n\n[TELEGRAM FORMATTING]\n"
            "- Use standard Markdown for formatting (**bold**, _italic_, `code`).\n"
            "- Use '> text' for quoting fragments or replying to specific points.\n"
            "- Lists and links are supported.\n"
        )
        chat_context = ""
        if self.chat_id and self.message_id:
            chat_context = f"\n\n[CHAT CONTEXT]\n- Chat ID: {self.chat_id}\n- Message ID: {self.message_id}\n"

        return (self.agent.system_prompt or "You are a helpful assistant.") + memory_ctx + wallet_context + chat_context + format_instruction

    def _build_messages(self, input_text: str, memory_ctx: str = "") -> list:
        system_prompt = self.get_full_system_prompt(memory_ctx=memory_ctx)
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=input_text),
        ]

    # ── Non-streaming ─────────────────────────────────────────────────────────

    async def run_task(self, input_text: str, context: Optional[Dict[str, Any]] = None, db: Optional[Any] = None) -> Dict[str, Any]:
        llm = self._get_llm()
        tools = self._build_tools()
        tools_used: List[str] = []
        
        memory_ctx = await get_memory_context(self.agent)
        messages = self._build_messages(input_text, memory_ctx=memory_ctx)
        meta = get_model_info(self.model) or {}

        if not tools or not meta.get("supports_tools", True):
            response = await llm.ainvoke(messages)
            return {"output": response.content, "tokens_used": _extract_tokens(response), "tools_used": [], "status": "success"}

        llm_with_tools = llm.bind_tools(tools)
        tool_map = {t.name: t for t in tools}
        last_response = None

        for _ in range(MAX_ITERATIONS):
            response: AIMessage = await llm_with_tools.ainvoke(messages)
            messages.append(response)
            last_response = response
            if not getattr(response, "tool_calls", None):
                break
            for tc in response.tool_calls:
                tools_used.append(tc["name"])
                tool = tool_map.get(tc["name"])
                try:
                    result = await tool.ainvoke(tc["args"]) if tool else f"Unknown tool: {tc['name']}"
                except Exception as e:
                    result = f"Tool error: {e}"
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

        final = messages[-1]
        result = {
            "output": final.content if isinstance(final.content, str) else str(final.content),
            "tokens_used": _extract_tokens(last_response) if last_response else 0,
            "tools_used": list(dict.fromkeys(tools_used)),
            "status": "success",
        }

        # Update summary memory in background
        asyncio.create_task(
            update_memory(self.agent.id, input_text, result["output"])
        )

        return result

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream_task(self, input_text: str, db: Optional[Any] = None) -> AsyncIterator[Dict[str, Any]]:
        """
        True token-by-token streaming using astream_events (LangChain v2 API).

        Yields:
          {"type": "tool_start",  "tool": "ton_balance", "args": {...}}
          {"type": "tool_result", "tool": "ton_balance", "result": "..."}
          {"type": "token",       "content": "hello "}       ← real LLM tokens
          {"type": "done",        "tools_used": [...], "tokens_used": 123}
          {"type": "error",       "message": "..."}

        How it works:
          - astream_events emits fine-grained events as the LLM generates them.
          - "on_chat_model_stream" fires for every token the LLM produces.
          - "on_tool_start" / "on_tool_end" fire when tools are called.
          - This gives real sub-100ms per-token latency, not batched chunks.
        """
        from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        tools = self._build_tools()
        meta = get_model_info(self.model) or {}
        force_plain = not meta.get("supports_tools", True)

        memory_ctx = await get_memory_context(self.agent)

        # ── Case 1: no tools or model doesn't support tool-calling ────────────
        # Use plain astream — real token-by-token from the LLM
        if not tools or force_plain:
            llm = self._get_llm(streaming=True)
            messages = self._build_messages(input_text, memory_ctx=memory_ctx)
            tokens_used = 0
            accumulated = ""
            try:
                async for chunk in llm.astream(messages):
                    content = chunk.content
                    if content:
                        accumulated += content
                        yield {"type": "token", "content": content}
                    tokens_used += _extract_tokens(chunk)
                yield {"type": "done", "tools_used": [], "tokens_used": tokens_used}
                # Постинг в ленту (простой режим)
                if accumulated:
                    content_preview = (accumulated[:200] + "...") if len(accumulated) > 200 else accumulated
                    asyncio.create_task(_add_feed_post(self.agent.id, content_preview))
            except Exception as e:
                yield {"type": "error", "message": str(e)}
            return

        # ── Case 2: tools available — use AgentExecutor with astream_events ──
        # AgentExecutor handles the tool-call loop internally and
        # astream_events lets us intercept every token and tool event.
        llm = self._get_llm(streaming=True)

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_full_system_prompt(memory_ctx=memory_ctx)),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=MAX_ITERATIONS,
            return_intermediate_steps=False,
            handle_parsing_errors=True,
        )

        tools_used: List[str] = []
        tokens_used = 0
        accumulated = ""

        try:
            async for event in executor.astream_events(
                {"input": input_text},
                version="v2",  # use LangChain events API v2
            ):
                kind = event["event"]

                # Real token from the LLM — fire immediately
                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and chunk.content:
                        accumulated += chunk.content
                        yield {"type": "token", "content": chunk.content}

                # Tool is being called
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tools_used.append(tool_name)
                    yield {
                        "type": "tool_start",
                        "tool": tool_name,
                        "args": event["data"].get("input", {}),
                    }

                # Tool returned a result
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    output = event["data"].get("output", "")
                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": str(output)[:500],
                    }

                # LLM finished — grab token usage from metadata
                elif kind == "on_chat_model_end":
                    response = event["data"].get("output")
                    if response:
                        tokens_used += _extract_tokens(response)

            yield {
                "type": "done",
                "tools_used": list(dict.fromkeys(tools_used)),
                "tokens_used": tokens_used,
            }

            # Update summary memory
            asyncio.create_task(
                update_memory(self.agent.id, input_text, accumulated)
            )

            # --- Добавляем пост в ленту агентов ---
            if accumulated:
                # Берем кусок результата как "мысль" для ленты
                # В идеале здесь можно вызвать LLM еще раз, чтобы она написала "краткий пост"
                # Но для скорости берем первые 200 символов
                content_preview = (accumulated[:200] + "...") if len(accumulated) > 200 else accumulated
                asyncio.create_task(_add_feed_post(self.agent.id, content_preview))

        except Exception as e:
            yield {"type": "error", "message": str(e)}

async def _add_feed_post(agent_id: str, content: str):
    """
    Вспомогательная функция для создания поста в фоне.
    """
    from app.core.db import SessionLocal
    async with SessionLocal() as db:
        try:
            new_post = FeedPost(
                agent_id=agent_id,
                content=content,
                post_type="insight"
            )
            db.add(new_post)
            await db.commit()
        except Exception as e:
            print(f"❌ Failed to auto-post to feed: {e}")


def _extract_tokens(response) -> int:
    if response is None:
        return 0
    meta = getattr(response, "response_metadata", {}) or {}
    usage = meta.get("token_usage") or meta.get("usage") or {}
    if isinstance(usage, dict):
        return usage.get("total_tokens") or (
            (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
        )
    usage_meta = getattr(response, "usage_metadata", None)
    if usage_meta:
        return getattr(usage_meta, "total_tokens", 0) or (
            getattr(usage_meta, "input_tokens", 0) + getattr(usage_meta, "output_tokens", 0)
        )
    return 0


# ── Fallback runner ───────────────────────────────────────────────────────────

DEFAULT_FALLBACKS = [
    "gpt-5-nano",
    "gemini-2.0-flash", 
    "gpt-4o-mini", 
    "llama-3.3-70b-versatile", 
    "claude-3-5-haiku-20241022",
    "deepseek-chat"
]


async def wrap_with_fallback(agent: AgentModel, task_fn, primary_model=None, db=None) -> Any:
    p_model = primary_model or agent.model
    # Строим список моделей для попыток: сначала основная, потом фолбеки
    models_to_try = [p_model] + [m for m in DEFAULT_FALLBACKS if m != p_model]
    last_err = None

    for i, model_id in enumerate(models_to_try):
        try:
            if db is not None:
                api_key, base_url = await _resolve_api_key(agent.user_id, model_id, db)
            else:
                m = get_model_info(model_id) or {}
                api_key = _env_key(m.get("api_key_env"))
                base_url = m.get("base_url")

            # Если ключа вообще нет (даже в платформе), и это не основная модель — пропускаем
            if not api_key and model_id != p_model:
                continue
                
            if i > 0:
                print(f"🔄 [FALLBACK] Attempting with {model_id} after error in previous attempt", file=sys.stderr)
            
            return await task_fn(model_id, api_key, base_url)

        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            
            # Список критических ошибок, на которых НЕТ смысла пробовать другой провайдер
            # (например, ошибка в самом промпте или слишком длинный текст)
            terminal_errors = ["validation_error", "too many messages", "maximum context length"]
            
            # Если это 400 ошибка (Bad Request) и она в списке терминальных — выходим сразу
            if "400" in err_str and any(te in err_str for te in terminal_errors):
                raise
            
            # Ошибки API ключей (401), отсутствие ключа, таймауты и 5xx ошибки — ПОВОД для фолбека
            # Мы пробуем следующий доступный вариант
            if i < len(models_to_try) - 1:
                wait_time = 0.5 * (i + 1)
                await asyncio.sleep(wait_time)
                continue
            else:
                # Если все попытки исчерпаны — прокидываем последнюю ошибку
                raise

    raise last_err or Exception("All attempts failed.")


async def run_agent_task(
    agent: AgentModel, input_text: str, 
    chat_id: Optional[str] = None, message_id: Optional[int] = None,
    db=None
) -> Dict[str, Any]:
    async def _run(model_id, api_key, base_url):
        # Ensure user data is pre-loaded for tools
        if not getattr(agent, "user", None) and db:
             from app.models.user import User
             from sqlalchemy.future import select
             user_res = await db.execute(select(User).where(User.id == agent.user_id))
             agent.user = user_res.scalars().first()
             
        runtime = AgentRuntime(
            agent, api_key=api_key, base_url=base_url, model_id=model_id,
            chat_id=chat_id, message_id=message_id
        )
        return await runtime.run_task(input_text, db=db)
    return await wrap_with_fallback(agent, _run, db=db)


async def stream_agent_task(
    agent: AgentModel, input_text: str, 
    chat_id: Optional[str] = None, message_id: Optional[int] = None,
    db=None
) -> AsyncIterator[Dict[str, Any]]:
    """
    Wrapper for streaming with fallback support.
    """
    p_model = agent.model
    # Модели для попыток: основная + фолбеки
    models_to_try = [p_model] + [m for m in DEFAULT_FALLBACKS if m != p_model]
    
    last_err = None
    
    for i, model_id in enumerate(models_to_try):
        try:
            if db is not None:
                api_key, base_url = await _resolve_api_key(agent.user_id, model_id, db)
            else:
                m = get_model_info(model_id) or {}
                api_key = _env_key(m.get("api_key_env"))
                base_url = m.get("base_url")

            # Если ключа нет и это фолбек — пропускаем
            if not api_key and model_id != p_model:
                continue

            # Ensure user data is pre-loaded
            if not getattr(agent, "user", None) and db:
                 from app.models.user import User
                 from sqlalchemy.future import select
                 user_res = await db.execute(select(User).where(User.id == agent.user_id))
                 agent.user = user_res.scalars().first()

            runtime = AgentRuntime(
                agent, api_key=api_key, base_url=base_url, model_id=model_id,
                chat_id=chat_id, message_id=message_id
            )
            
            # Попытка запустить поток
            success_started = False
            async for event in runtime.stream_task(input_text, db=db):
                if event["type"] == "error":
                    # Если ошибка случилась ВНУТРИ потока — выходим из итератора
                    # и попадаем в блок catch (если это auth/provider error)
                    raise Exception(event["message"])
                
                # Если пошли токены или инструменты — значит модель рабочая
                success_started = True
                yield event
            
            # Если дошли до конца без ошибок — прерываем цикл попыток
            if success_started:
                return

        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            
            # Критические ошибки (валидация промпта и т.д.) — не фолбекаемся
            terminal_errors = ["validation_error", "too many messages", "maximum context length"]
            if "400" in err_str and any(te in err_str for te in terminal_errors):
                yield {"type": "error", "message": str(e)}
                return
            
            # Если это последняя попытка — отдаём ошибку пользователю
            if i == len(models_to_try) - 1:
                yield {"type": "error", "message": str(e)}
                return
            
            # Иначе — логируем и пробуем следующий фолбек
            if i < len(models_to_try) - 1:
                print(f"🔄 [FALLBACK-STREAM] {model_id} failed: {err_str[:150]}... Trying next.", file=sys.stderr)
                continue

    if last_err:
        yield {"type": "error", "message": str(last_err)}
