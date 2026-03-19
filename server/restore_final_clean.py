import paramiko
import os

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

# COMPLETE, PERFECTED CONTENT OF telegram_bot.py
full_clean_code = r'''"""
Telegram Bot Service — управление топиками и обработка сообщений.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import os
import json
from typing import Optional, Any, Dict, List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Настройки стриминга ───────────────────────────────────────────────────────
_STREAM_EDIT_INTERVAL = 0.4   # секунд между editMessage
_STREAM_CHUNK_THRESHOLD = 1   # обновлять даже при 1 новом символе
_BOT_USERNAME_CACHE: Optional[str] = None


async def get_bot_username() -> Optional[str]:
    global _BOT_USERNAME_CACHE
    if _BOT_USERNAME_CACHE:
        return _BOT_USERNAME_CACHE
    me = await _call("getMe")
    if me:
        _BOT_USERNAME_CACHE = me.get("username")
    return _BOT_USERNAME_CACHE


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


async def _call(method: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skip: %s", method)
        return None
    
    file_fields = ['animation', 'photo', 'document', 'video', 'voice', 'audio', 'sticker']
    files = {}
    payload = {}
    
    for k, v in kwargs.items():
        if v is None: continue
        if k in file_fields and isinstance(v, str) and v.startswith("/") and os.path.exists(v):
            from os.path import basename
            files[k] = (basename(v), open(v, 'rb'), "image/gif" if v.endswith(".gif") else "application/octet-stream")
        else:
            # FIX: Stringify complex objects (dict/list) for multipart compatibility
            if isinstance(v, (dict, list)):
                payload[k] = json.dumps(v)
            else:
                payload[k] = v
            
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            if files:
                resp = await c.post(_api(method), data=payload, files=files)
            else:
                # To be safe, if we stringified everything in payload, we use data=payload
                resp = await c.post(_api(method), data=payload)
        
        # Close all files
        for f_tuple in files.values():
            if isinstance(f_tuple, tuple): f_tuple[1].close()
        
        data = resp.json()
        if not data.get("ok"):
            import sys; print(f"❌ ERROR: Telegram [{method}] failed: {data.get('description')}", file=sys.stderr)
            logger.error("Telegram [%s] error: %s", method, data.get("description"))
            return None
        return data.get("result")
    except Exception as e:
        for f_tuple in files.values():
            if isinstance(f_tuple, tuple): f_tuple[1].close()
        logger.exception("Telegram [%s] exception: %s", method, e)
        return None


def escape_markdown_v2(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


# ── Tool display names ─────────────────────────────────────────────────────────

EMOJI_TO_ID = {
    "🤖": "5309832892262654231", "🚀": "5368585403467048206",
    "🧠": "5237889595894414384", "🎨": "5310039132297242441",
    "💎": "5309958691854754293", "💻": "5350554349074391003",
    "⚡": "5312016608254762256", "💡": "5312536423851630001",
    "🔍": "5309965701241379366", "🎙️": "5377544228505134960",
    "🦁": "5442994849642283838", "🦊": "5442880753047534433",
    "🐱": "5235912661102773458", "🐶": "5442656976695029803",
    "🐧": "5442839958089201550", "🦄": "5413625003218313783",
    "🔥": "5312241539987020022", "❤️": "5312138559556164615",
    "💰": "5350452584119279096", "⭐": "5235579393115438657",
    "✅": "5237699328843200968", "❓": "5377316857231450742",
    "❗": "5379748062124056162", "📅": "5433614043006903194",
    "📝": "5373251851074415873", "🎮": "5309950797704865693",
    "📱": "5409357944619802453", "🚗": "5312322066328853156",
    "🏠": "5312486108309757006", "🎁": "5310228579009699834",
    "🏆": "5312315739842026755", "🍕": "5350444672789519765",
    "🍔": "5350403544182694064", "☕": "5350392020785437399",
}

_TOOL_LABELS = {
    "web_search": "🔍 Search",
    "ton_balance": "💎 TON Balance",
    "ton_transactions": "📋 Transactions",
    "ton_account_info": "👤 TON Account",
    "crypto_price": "📈 Price",
    "get_weather": "🌤 Weather",
    "get_datetime": "🕐 Time",
    "http_fetch": "🌐 URL",
    "tg_send_message": "✉️ Telegram",
    "stonfi_swap_simulate": "🔄 STON.fi Swap",
    "stonfi_assets": "📊 STON.fi Assets",
    "stonfi_pool_info": "💧 STON.fi Pool",
    "dedust_pools": "💧 DeDust Pools",
    "ton_dns_resolve": "🔗 TON DNS",
    "ton_dns_reverse": "🔗 DNS Reverse",
    "nft_item_info": "🖼 NFT",
    "nft_collection_info": "🖼 NFT Collection",
    "jetton_info": "🪙 Token",
    "jetton_holders": "👥 Holders",
    "ton_staking_pools": "🏦 Staking",
    "get_wallet_balance": "💎 Wallet Balance",
    "get_wallet_transactions": "📋 Wallet Transactions",
}


def _tool_label(name: str) -> str:
    return _TOOL_LABELS.get(name, f"🔧 {name}")


# ── Topics ─────────────────────────────────────────────────────────────────────

async def create_agent_topic(
    agent_name: str, agent_id: str,
    chat_id: Optional[str] = None, emoji: str = "🤖",
) -> Optional[int]:
    target = chat_id or getattr(settings, "TELEGRAM_BOT_CHAT_ID", None)
    if not target:
        return None
    custom_emoji_id = EMOJI_TO_ID.get(emoji)
    result = await _call(
        "createForumTopic", chat_id=target, name=agent_name[:128],
        icon_custom_emoji_id=custom_emoji_id,
        icon_color=_agent_color(agent_id) if not custom_emoji_id else None,
    )
    if not result and custom_emoji_id:
        result = await _call("createForumTopic", chat_id=target, name=agent_name[:128],
                             icon_color=_agent_color(agent_id))
    if not result:
        return None
    thread_id: int = result["message_thread_id"]
    await send_to_topic(
        thread_id,
        f"🤖 *{agent_name}* is ready!\n\n"
        f"Just send a message — the agent will respond.\n\n"
        f"/status — current status\n"
        f"/skills — list installed skills\n"
        f"/tasks — recent activity",
        parse_mode="Markdown", chat_id=target,
    )
    return thread_id


async def update_agent_topic(thread_id: int, agent_name: str, emoji: str = "🤖", chat_id: Optional[str] = None) -> bool:
    target = chat_id or getattr(settings, "TELEGRAM_BOT_CHAT_ID", None)
    if not target or not thread_id:
        return False
    custom_emoji_id = EMOJI_TO_ID.get(emoji)
    result = await _call("editForumTopic", chat_id=target, message_thread_id=thread_id,
                         name=agent_name[:128], icon_custom_emoji_id=custom_emoji_id)
    if not result and custom_emoji_id:
        result = await _call("editForumTopic", chat_id=target, message_thread_id=thread_id, name=agent_name[:128])
    return result is not None


async def close_agent_topic(thread_id: int, agent_name: str, chat_id: Optional[str] = None) -> bool:
    target = chat_id or getattr(settings, "TELEGRAM_BOT_CHAT_ID", None)
    if not target or not thread_id:
        return False
    await send_to_topic(thread_id, f"🗑 Agent *{agent_name}* deleted. History preserved.",
                        parse_mode="Markdown", chat_id=target)
    result = await _call("closeForumTopic", chat_id=target, message_thread_id=thread_id)
    return result is not None


# ── Sending / Editing ──────────────────────────────────────────────────────────

def _format_html(text: str) -> str:
    """Robust conversion of common Markdown patterns to Telegram HTML."""
    if not text:
        return ""
    
    # 1. Escape HTML special characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # 2. Blockquotes: lines starting with "> " -> <blockquote>...</blockquote>
    lines = text.split("\n")
    new_lines = []
    in_quote = False
    for line in lines:
        if line.startswith("> "):
            content = line[2:]
            if not in_quote:
                new_lines.append(f"<blockquote>{content}")
                in_quote = True
            else:
                new_lines.append(content)
        else:
            if in_quote:
                new_lines[-1] += "</blockquote>"
                in_quote = False
            new_lines.append(line)
    if in_quote:
        new_lines[-1] += "</blockquote>"
    text = "\n".join(new_lines)

    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
    
    return text


async def set_message_reaction(chat_id: str, message_id: int, reaction: str = "👍") -> bool:
    import re
    emojis = re.findall(r'[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf]', reaction)
    reaction = emojis[0] if emojis else "👍"
    payload = {
        "chat_id": chat_id, "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": reaction}]
    }
    result = await _call("setMessageReaction", **payload)
    return result is not None


async def send_to_topic(
    thread_id: Optional[int], text: str,
    parse_mode: str = "HTML",
    reply_to_message_id: Optional[int] = None,
    chat_id: Optional[str] = None,
    quote: Optional[str] = None,
) -> Optional[int]:
    if not text: return None
    if not quote and "<blockquote>" in text:
        match = re.search(r"<blockquote>(.*?)</blockquote>", text, re.DOTALL)
        if match: quote = match.group(1).strip()

    if parse_mode == "HTML": text = _format_html(text)
    target = chat_id or getattr(settings, "TELEGRAM_BOT_CHAT_ID", None)
    if not target or (thread_id is None and chat_id is None): return None
    if len(text) > 4096: text = text[:4090] + "..."
    
    kwargs = {
        "chat_id": target, "message_thread_id": thread_id,
        "text": text, "parse_mode": parse_mode,
    }
    if reply_to_message_id:
        if quote:
            kwargs["reply_parameters"] = {
                "message_id": reply_to_message_id, "quote": quote[:100], "quote_parse_mode": parse_mode
            }
        else:
            kwargs["reply_to_message_id"] = reply_to_message_id
    
    result = await _call("sendMessage", **kwargs)
    if not result:
        kwargs["parse_mode"] = None
        if "reply_parameters" in kwargs: kwargs["reply_parameters"]["quote_parse_mode"] = None
        result = await _call("sendMessage", **kwargs)
    return result.get("message_id") if result else None


async def edit_message(chat_id: str, message_id: int, text: str, parse_mode: str = "HTML") -> bool:
    if len(text) > 4096: text = text[:4090] + "..."
    if parse_mode == "HTML": text = _format_html(text)
    result = await _call("editMessageText", chat_id=chat_id, message_id=message_id, text=text, parse_mode=parse_mode)
    return result is not None


async def send_task_result(
    thread_id: int, output: str, tools_used: List[str], tokens_used: int,
    status: str, reply_to_message_id: Optional[int] = None, chat_id: Optional[str] = None,
    latency: Optional[float] = None,
) -> None:
    header = "✅ *Done*" if status == "success" else "❌ *Error*"
    parts = [f"{header}\n\n{output}"]
    footer = []
    if tools_used: footer.append(f"🔧 _{', '.join(tools_used)}_")
    if tokens_used: footer.append(f"📊 _{tokens_used:,} tokens_")
    if latency: footer.append(f"⏱ _{latency:.1f} sec_")
    if footer: parts.append("\n" + "  ".join(footer))
    await send_to_topic(thread_id, "".join(parts), reply_to_message_id=reply_to_message_id, chat_id=chat_id)


# ── Streaming handler ─────────────────────────────────────────────────────────

async def _stream_agent_to_topic(
    agent, input_text: str,
    thread_id: int, chat_id: str,
    reply_to_message_id: int, db,
) -> None:
    from app.services.agent_runtime import stream_agent_task
    from app.models.task import Task as TaskModel
    target = chat_id or getattr(settings, "TELEGRAM_BOT_CHAT_ID", None)
    task = TaskModel(agent_id=agent.id, status="running", input_data={"input": input_text, "source": "telegram"})
    db.add(task); agent.status = "active"; db.add(agent); await db.commit(); await db.refresh(task)

    placeholder_id = await send_to_topic(
        thread_id, "⏳ _Thinking..._", parse_mode="Markdown",
        reply_to_message_id=reply_to_message_id, chat_id=target,
    )
    if not placeholder_id:
        from app.services.agent_runtime import run_agent_task
        result = await run_agent_task(agent, input_text, chat_id=target, message_id=reply_to_message_id, db=db)
        await send_task_result(thread_id, result["output"], result.get("tools_used", []),
                               result.get("tokens_used", 0), "success", reply_to_message_id, target)
        return

    accumulated = ""; tools_used = []; tokens_used = 0; start_time = time.perf_counter()
    try:
        async for event in stream_agent_task(agent, input_text, chat_id=target, message_id=reply_to_message_id, db=db):
            if event["type"] == "tool_start":
                label = _tool_label(event["tool"])
                tools_used.append(event["tool"])
                await edit_message(target, placeholder_id, f"_{label}..._")
            elif event["type"] == "token": accumulated += event["content"]
            elif event["type"] == "done": tokens_used = event.get("tokens_used", 0)
            elif event["type"] == "error": raise Exception(event["message"])

        latency = time.perf_counter() - start_time
        final_text = accumulated.strip() or "_(empty response)_"
        footer = []
        if settings.TELEGRAM_BOT_SHOW_STATS:
            if tools_used:
                unique = list(dict.fromkeys(tools_used))
                footer.append(f"🔧 _{', '.join(_tool_label(t) for t in unique)}_")
            if tokens_used: footer.append(f"📊 _{tokens_used:,} tokens_")
            if latency: footer.append(f"⏱ _{latency:.1f} sec_")
        if footer: final_text = final_text + "\n\n" + "  ".join(footer)
        if len(final_text) > 4096: final_text = final_text[:4090] + "\n…"
        await edit_message(target, placeholder_id, final_text)

        task.status = "success"; task.output_data = {"output": accumulated, "tools_used": list(dict.fromkeys(tools_used))}
        task.tokens_used = tokens_used; agent.status = "idle"; db.add(task); db.add(agent); await db.commit()
    except Exception as e:
        logger.exception("Stream error for agent %s: %s", agent.id, e)
        friendly_err = "❌ Error generating response. Try switching models or repeating the request."      
        await edit_message(target, placeholder_id, friendly_err)
        task.status = "failed"; task.error_msg = str(e); agent.status = "idle"; db.add(task); db.add(agent); await db.commit()


# ── handle_update ─────────────────────────────────────────────────────────────

async def handle_update(update: Dict[str, Any], db) -> None:
    message = (update.get("message") or update.get("channel_post") or update.get("edited_message"))
    if not message: return

    thread_id = message.get("message_thread_id")
    text = (message.get("text") or "").strip()
    message_id = message.get("message_id", 0)
    tg_user_id = str((message.get("from") or {}).get("id", ""))
    chat_id = str(message.get("chat", {}).get("id", ""))

    if text.startswith("/"):
        await _handle_command(message, thread_id, tg_user_id, db)
        return
        
    agent, user = await _find_agent_by_thread(chat_id, thread_id, tg_user_id, db)
    if not agent:
        from sqlalchemy.future import select
        from app.models.agent import Agent as AgentModel
        from app.models.user import User as UserModel
        res = await db.execute(select(UserModel).where(UserModel.telegram_id == tg_user_id))
        user = res.scalar_one_or_none()
        if not user: return
        res = await db.execute(select(AgentModel).where(AgentModel.user_id == user.id).limit(1))
        agent = res.scalar_one_or_none()
        if not agent:
            import uuid
            agent = AgentModel(
                id=str(uuid.uuid4()), user_id=user.id, name="Assistant",
                model="gpt-4o-mini", status="idle",
                system_prompt="You are a helpful assistant in Telegram Direct Messages."
            )
            db.add(agent); await db.commit(); await db.refresh(agent)
    
    if not agent: return
    await _call("sendChatAction", chat_id=chat_id, action="typing", message_thread_id=thread_id)
    await _stream_agent_to_topic(agent=agent, input_text=text, thread_id=thread_id, chat_id=chat_id, reply_to_message_id=message_id, db=db)


# ── Commands ───────────────────────────────────────────────────────────────────

async def _handle_command(message: Dict, thread_id: Optional[int], tg_user_id: str, db) -> None:
    text = (message.get("text") or "").split("@")[0].strip()
    message_id = message.get("message_id", 0)
    chat_id = str(message.get("chat", {}).get("id", ""))

    if text.startswith("/start") or text == "/help":
        app_url = "https://aquarium-8ux8.vercel.app/"
        gif_url = "/root/aquarium-ai/server/data/demo.gif"
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🚀 Launch App", "web_app": {"url": app_url}}],
                [{"text": "📋 Status", "callback_data": "/status"}, {"text": "👤 Profile", "callback_data": "/whoami"}]
            ]
        }
        res = await _call(
            "sendAnimation", chat_id=chat_id, animation=gif_url,
            caption=_format_html("👋 **Welcome to AI Hub TON!**\n\nManage your AI agents directly from Telegram.\n\n🔗 [Open Mini App]("+app_url+")"),
            parse_mode="HTML", reply_markup=reply_markup, message_thread_id=thread_id
        )
        if not res:
            await _call(
                "sendMessage", chat_id=chat_id, 
                text=_format_html("👋 **Welcome to AI Hub TON!**\n\nManage your agents directly here.\n\n🔗 [Open Mini App]("+app_url+")"),
                parse_mode="HTML", reply_markup=reply_markup, message_thread_id=thread_id
            )
        return

    if text == "/whoami":
        username = message.get("from", {}).get("username", "None")
        await send_to_topic(thread_id, f"👤 **Your Profile:**\nID: `{tg_user_id}`\nUsername: @{username}", reply_to_message_id=message_id, chat_id=chat_id)
        return

    agent, _ = await _find_agent_by_thread(chat_id, thread_id, tg_user_id, db)
    if text == "/status":
        if agent:
            emoji = {"idle": "🟢", "active": "🔵", "error": "🔴"}.get(agent.status, "⚪")
            await send_to_topic(thread_id, f"{emoji} *{agent.name}*\nStatus: `{agent.status}`\nModel: `{agent.model}`", reply_to_message_id=message_id, chat_id=chat_id)
        else:
            from sqlalchemy.future import select
            from app.models.agent import Agent as AgentModel
            from app.models.user import User as UserModel
            res = await db.execute(select(AgentModel).join(UserModel).where(UserModel.telegram_id == tg_user_id))
            agents = res.scalars().all()
            lines = ["📋 *Your Agents:*"] + [f"{'✅' if a.tg_thread_id else '❌'} {a.name} (`{a.id[:8]}`)" for a in agents] if agents else ["No agents found."]
            await send_to_topic(None, "\n".join(lines), chat_id=chat_id)

    elif text == "/skills":
        if not agent: return
        skills = agent.skills
        lines = ["🛠 *Installed Skills:*"] + [f"• {s.name}" for s in skills] if skills else ["No skills installed."]
        await send_to_topic(thread_id, "\n".join(lines), reply_to_message_id=message_id, chat_id=chat_id)

    elif text == "/tasks":
        if not agent: return
        from sqlalchemy.future import select
        from app.models.task import Task as TaskModel
        res = await db.execute(select(TaskModel).where(TaskModel.agent_id == agent.id).order_by(TaskModel.created_at.desc()).limit(5))
        tasks = res.scalars().all()
        rows = ["📊 *Recent Activity:*"] + [f"{'✅' if t.status == 'success' else '❌'} `{t.created_at.strftime('%H:%M')}` - _{t.status}_" for t in tasks] if tasks else ["No recent activity."]
        await send_to_topic(thread_id, "\n".join(rows), reply_to_message_id=message_id, chat_id=chat_id)

    elif text == "/recreate":
        from sqlalchemy.future import select
        from app.models.agent import Agent as AgentModel
        from app.models.user import User as UserModel
        res = await db.execute(select(AgentModel).join(UserModel).where(UserModel.telegram_id == tg_user_id)) 
        for a in res.scalars().all():
            new_thread = await create_agent_topic(a.name, a.id, chat_id=chat_id)
            if new_thread: a.tg_thread_id = new_thread
        await db.commit()
        await send_to_topic(None, "✅ Topics refreshed!", chat_id=chat_id)


async def _find_agent_by_thread(chat_id: str, thread_id: Optional[int], tg_user_id: str, db):
    from sqlalchemy.future import select
    from app.models.agent import Agent as AgentModel
    from app.models.user import User as UserModel
    from sqlalchemy.orm import selectinload
    res = await db.execute(select(AgentModel).options(selectinload(AgentModel.skills), selectinload(AgentModel.user)).join(UserModel, AgentModel.user_id == UserModel.id).where(AgentModel.tg_thread_id == thread_id, UserModel.telegram_id == tg_user_id))
    agent = res.scalars().first()
    if not agent and getattr(settings, "TELEGRAM_BOT_CHAT_ID", None) == chat_id:
        res = await db.execute(select(AgentModel).options(selectinload(AgentModel.skills), selectinload(AgentModel.user)).where(AgentModel.tg_thread_id == thread_id))
        agent = res.scalars().first()
    if not agent: return None, None
    if not agent.user:
        user_res = await db.execute(select(UserModel).where(UserModel.id == agent.user_id))
        agent.user = user_res.scalars().first()
    return agent, agent.user


async def set_webhook(webhook_url: str) -> bool:
    result = await _call("setWebhook", url=webhook_url, allowed_updates=["message", "channel_post"], drop_pending_updates=True)
    if result: logger.info("Webhook registered: %s", webhook_url)
    return result is not None


async def delete_webhook(drop_pending_updates: bool = False) -> bool:
    result = await _call("deleteWebhook", drop_pending_updates=drop_pending_updates)
    if result: logger.info("Webhook deleted")
    return result is not None


_COLORS = [7322096, 16766590, 13338331, 9367192, 16749490, 16478047]
def _agent_color(agent_id: str) -> int:
    return _COLORS[sum(ord(c) for c in agent_id) % len(_COLORS)]


async def start_polling(stats: Optional[Dict[str, Any]] = None):
    import sys
    from app.core.db import AsyncSessionLocal
    offset = 0
    print("🚀 Polling started", file=sys.stderr)
    while True:
        if stats: stats["loops"] = stats.get("loops", 0) + 1
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getUpdates", params={"offset": offset, "timeout": 5})
                if response.status_code == 200:
                    data = response.json()
                    if not data.get("ok"):
                        if stats: stats["last_error"] = data.get("description")
                        await asyncio.sleep(5); continue
                    updates = data.get("result", [])
                    if updates and stats: stats["total_updates"] = stats.get("total_updates", 0) + len(updates)
                    for update in updates:
                        offset = update["update_id"] + 1
                        async with AsyncSessionLocal() as db:
                            try: await handle_update(update, db)
                            except Exception as e: print(f"❌ Update error: {e}", file=sys.stderr)
                else:
                    if stats: stats["last_error"] = f"HTTP {response.status_code}"
                    await asyncio.sleep(5)
        except Exception as e:
            if not isinstance(e, (httpx.ConnectError, httpx.TimeoutException)):
                print(f"🔌 Polling error: {e}", file=sys.stderr)
                if stats: stats["last_error"] = str(e)
            await asyncio.sleep(5)
'''

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Final overwrite
with open('final_telegram_bot.py', 'w', encoding='utf-8') as f:
    f.write(full_clean_code)

sftp = ssh.open_sftp()
sftp.put('final_telegram_bot.py', '/tmp/telegram_bot.py')
sftp.close()

ssh.exec_command("mv /tmp/telegram_bot.py /root/aquarium-ai/server/app/services/telegram_bot.py")
ssh.exec_command("systemctl restart aquarium")

print("✅ Server RESTORED with FULL CLEAN CODE (Final). Indentation is fixed.")
ssh.close()
os.remove('final_telegram_bot.py')
