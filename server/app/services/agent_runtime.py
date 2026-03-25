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
            elif impl == "mcp":
                mcp_url = manifest.get("mcp_url")
                if not mcp_url:
                    continue
                
                async def _mcp_call(_url=mcp_url, _tool_name=tool_name, **kwargs) -> str:
                    from mcp.client.session import ClientSession
                    from mcp.client.sse import sse_client
                    try:
                        async with sse_client(_url) as (read, write):
                            async with ClientSession(read, write) as session:
                                await session.initialize()
                                result = await session.call_tool(_tool_name, arguments=kwargs)
                                texts = [c.text for c in getattr(result, "content", []) if getattr(c, "type", "") == "text"]
                                return "\n".join(texts)
                    except Exception as e:
                        return f"MCP call error: {e}"

                tools.append(StructuredTool.from_function(
                    coroutine=_mcp_call, name=tool_name,
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

        # Add Social & Cooperation Tools
        if getattr(self.agent, "is_social_active", False):
            class PostFeedArgs(BaseModel):
                content: str = Field(..., description="The content of your post. Keep it engaging.")
                reply_to_post_id: Optional[int] = Field(None, description="The ID of the post you are replying to, if any.")

            async def _post_feed_tool(content: str, reply_to_post_id: Optional[int] = None) -> str:
                from app.core.db import AsyncSessionLocal
                from app.models.feed_post import FeedPost
                try:
                    async with AsyncSessionLocal() as _db:
                        new_post = FeedPost(agent_id=self.agent.id, content=content, post_type="insight", parent_id=reply_to_post_id)
                        _db.add(new_post)
                        await _db.commit()
                        if reply_to_post_id:
                            return f"Successfully replied to post {reply_to_post_id}!"
                        return "Successfully posted to the social feed!"
                except Exception as e:
                    return f"Failed to post: {e}"

            tools.append(StructuredTool.from_function(
                coroutine=_post_feed_tool, name="post_to_social_feed",
                description="Post a message, thought, or status update to the global Agent Social Feed. Other agents and users will see this.",
                args_schema=PostFeedArgs,
            ))

            class ReadPostsArgs(BaseModel):
                limit: int = Field(10, description="The maximum number of recent posts to read.")

            async def _read_posts_tool(limit: int = 10) -> str:
                from app.core.db import AsyncSessionLocal
                from sqlalchemy.future import select
                from app.models.feed_post import FeedPost
                from sqlalchemy.orm import selectinload
                try:
                    async with AsyncSessionLocal() as _db:
                        res = await _db.execute(
                            select(FeedPost)
                            .options(selectinload(FeedPost.agent))
                            .order_by(FeedPost.created_at.desc())
                            .limit(limit)
                        )
                        posts = res.scalars().all()
                        if not posts:
                            return "No recent posts in the feed."
                        output = []
                        for p in posts:
                            author = p.agent.name if p.agent else "Unknown"
                            reacts = p.reactions or []
                            react_summary = ", ".join([r.get("emoji", "") for r in reacts]) if reacts else "None"
                            output.append(f"Post ID: {p.id}\nAuthor: {author}\nContent: {p.content}\nReactions: {react_summary}")
                        return "\n\n---\n\n".join(output)
                except Exception as e:
                    return f"Failed to read posts: {e}"

            tools.append(StructuredTool.from_function(
                coroutine=_read_posts_tool, name="read_recent_posts",
                description="Read recent posts from the global Agent Social Feed to see what others are discussing. Returns a list of recent posts with their IDs.",
                args_schema=ReadPostsArgs,
            ))

            class ReactPostArgs(BaseModel):
                post_id: int = Field(..., description="The ID of the post you want to react to.")
                emoji: str = Field(..., description="A single emoji characterizing your reaction (e.g. '👍', '🔥', '❤️').")

            async def _react_to_post_tool(post_id: int, emoji: str) -> str:
                from app.core.db import AsyncSessionLocal
                from sqlalchemy.future import select
                from app.models.feed_post import FeedPost
                import sqlalchemy.orm.attributes
                try:
                    async with AsyncSessionLocal() as _db:
                        res = await _db.execute(select(FeedPost).where(FeedPost.id == post_id))
                        post = res.scalars().first()
                        if not post:
                            return f"Post ID {post_id} not found."
                        
                        reactions = list(post.reactions) if post.reactions else []
                        for r in reactions:
                            if r.get("agent_id") == self.agent.id and r.get("emoji") == emoji:
                                return f"You already reacted with {emoji} to post {post_id}."
                        reactions.append({"emoji": emoji, "agent_id": self.agent.id})
                        post.reactions = reactions
                        sqlalchemy.orm.attributes.flag_modified(post, "reactions")
                        
                        await _db.commit()
                        return f"Successfully reacted with {emoji} to post {post_id}!"
                except Exception as e:
                    return f"Failed to react: {e}"

            tools.append(StructuredTool.from_function(
                coroutine=_react_to_post_tool, name="react_to_post",
                description="React to a specific post in the social feed using its Post ID and an emoji.",
                args_schema=ReactPostArgs,
            ))
            
        async def _ask_agent_tool(target_agent_name: str, query: str) -> str:
            from app.core.db import AsyncSessionLocal
            from sqlalchemy.future import select
            from app.models.agent import Agent as AgentModel
            try:
                async with AsyncSessionLocal() as _db:
                    res = await _db.execute(select(AgentModel).where(AgentModel.name.ilike(f"%{target_agent_name}%")).limit(1))
                    target_agent = res.scalars().first()
                    if not target_agent:
                        return f"Agent '{target_agent_name}' not found."
                    if target_agent.id == self.agent.id:
                        return "You cannot ask yourself."
                    full_query = f"[Incoming query from agent '{self.agent.name}']\n{query}"
                    result = await run_agent_task(target_agent, full_query, db=_db)
                    return f"{target_agent.name} answered:\n{result['output']}"
            except Exception as e:
                return f"Failed to contact agent: {e}"

        tools.append(StructuredTool.from_function(
            coroutine=_ask_agent_tool, name="ask_another_agent",
            description="Ask another AI agent for information, analysis, or help. Provide the agent's name (e.g. 'Wise Sage') and your specific question.",
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

        social_context = ""
        if getattr(self.agent, "is_social_active", False):
            social_context = (
                "\n\n[SOCIAL NETWORK INSTRUCTIONS]\n"
                "You are an active participant in the AI Social Network (Feed).\n"
                "Use 'read_recent_posts' to check what others are thinking, 'post_to_social_feed' to share your thoughts or reply, and 'react_to_post' to leave emojis."
            )

        return (self.agent.system_prompt or "You are a helpful assistant.") + memory_ctx + wallet_context + chat_context + social_context + format_instruction

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
        
        memory_ctx = ""
        if db:
            memory_ctx = await get_memory_context(self.agent.id, input_text, db)
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
        True token-by-token streaming with manual tool-calling loop.
        Avoids dependency on AgentExecutor (which is missing in some environments).
        """
        tools = self._build_tools()
        tool_map = {t.name: t for t in tools}
        meta = get_model_info(self.model) or {}
        supports_tools = meta.get("supports_tools", True)
        
        memory_ctx = ""
        if db:
            memory_ctx = await get_memory_context(self.agent.id, input_text, db)

        messages = self._build_messages(input_text, memory_ctx=memory_ctx)
        tools_used: List[str] = []
        tokens_used = 0
        accumulated_output = ""

        try:
            for _ in range(MAX_ITERATIONS):
                llm = self._get_llm(streaming=True)
                if tools and supports_tools:
                    llm = llm.bind_tools(tools)
                
                last_ai_message = None
                
                # Step 1: Stream chunks from the LLM
                async for chunk in llm.astream(messages):
                    if last_ai_message is None:
                        last_ai_message = chunk
                    else:
                        try:
                            last_ai_message = last_ai_message + chunk
                        except:
                            # Fallback if + operator is missing or inconsistent in this LangChain version
                            if hasattr(last_ai_message, "content") and hasattr(chunk, "content"):
                                last_ai_message.content += chunk.content
                    
                    if hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        if not isinstance(content, str):
                            content = str(content)
                        yield {"type": "token", "content": content}
                        accumulated_output += content
                    
                    tokens_used += _extract_tokens(chunk)

                if last_ai_message is None:
                    break
                    
                messages.append(last_ai_message)

                # Step 2: Check for tool calls
                tool_calls = getattr(last_ai_message, "tool_calls", None)
                if not tool_calls:
                    break # No tool calls, we're done

                # Step 3: Execute tool calls sequentially
                for tc in tool_calls:
                    name = tc["name"]
                    args = tc["args"]
                    call_id = tc["id"]
                    
                    tools_used.append(name)
                    yield {"type": "tool_start", "tool": name, "args": args}
                    
                    tool = tool_map.get(name)
                    try:
                        result_obj = await tool.ainvoke(args) if tool else f"Error: Tool '{name}' not found"
                        result_str = str(result_obj)
                    except Exception as e:
                        result_str = f"Tool Execution Error: {e}"

                    yield {"type": "tool_result", "tool": name, "result": result_str[0:1000]}
                    messages.append(ToolMessage(content=result_str, tool_call_id=call_id))

            yield {
                "type": "done",
                "tools_used": list(dict.fromkeys(tools_used)),
                "tokens_used": tokens_used
            }

            # Update memory in background
            if accumulated_output:
                asyncio.create_task(update_memory(self.agent.id, input_text, accumulated_output))

        except Exception as e:
            yield {"type": "error", "message": f"Stream Loop Error: {str(e)}"}


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

                if not api_key and model_id != p_model:
                    continue
                
            if i > 0:
                print(f"🔄 [FALLBACK] Attempting with {model_id} after error in previous attempt", file=sys.stderr)
            
            return await task_fn(model_id, api_key, base_url)

        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            
            # Список критических ошибок, на которых НЕТ смысла пробовать другой провайдер
            terminal_errors = ["validation_error", "too many messages", "maximum context length"]
            
            if "400" in err_str and any(te in err_str for te in terminal_errors):
                raise
            
            if i < len(models_to_try) - 1:
                wait_time = 0.5 * (i + 1)
                await asyncio.sleep(wait_time)
                continue
            else:
                raise

    if last_err:
        raise last_err
    raise Exception("All attempts failed.")



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
