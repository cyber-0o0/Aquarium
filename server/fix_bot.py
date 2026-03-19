
import os

filepath = r"D:\programming\AiHubTon\server\app\services\telegram_bot.py"

with open(filepath, "rb") as f:
    content = f.read().decode("utf-8", errors="ignore")

# Ищем начало и конец каши. 
# Кода после этой строки было: if tokens_used:
# Код функции handle_update начинается ниже.

# Нам нужно найти место, где начинается функция _stream_agent_to_topic и заменить её целиком.
start_marker = "async def _stream_agent_to_topic("
end_marker = "async def handle_update("

parts = content.split(start_marker)
rest = parts[1].split(end_marker)

# parts[0] - начало файла до функции
# rest[0] - сама функция (битая)
# rest[1] - хвост файла после handle_update

new_stream_func = """async def _stream_agent_to_topic(
    agent, input_text: str,
    thread_id: int, chat_id: str,
    reply_to_message_id: int, db,
) -> None:
    from app.services.agent_runtime import stream_agent_task
    from app.models.task import Task as TaskModel
    import time

    target = chat_id or getattr(settings, "TELEGRAM_BOT_CHAT_ID", None)

    task = TaskModel(
        agent_id=agent.id, status="running",
        input_data={"input": input_text, "source": "telegram"},
    )
    db.add(task)
    agent.status = "active"
    db.add(agent)
    await db.commit()
    await db.refresh(task)

    placeholder_id = await send_to_topic(
        thread_id, "⏳ _Думаю..._",
        parse_mode="Markdown",
        reply_to_message_id=reply_to_message_id,
        chat_id=target,
    )

    if not placeholder_id:
        from app.services.agent_runtime import execute_agent_task
        result = await execute_agent_task(agent, input_text, db=db)
        await send_task_result(
            thread_id, result["output"],
            result.get("tools_used", []), result.get("tokens_used", 0),
            "success", reply_to_message_id, target,
        )
        return

    accumulated = ""
    tools_used = []
    tokens_used = 0
    start_time = time.perf_counter()

    try:
        async for event in stream_agent_task(agent, input_text, db=db):
            if event["type"] == "tool_start":
                label = _tool_label(event["tool"])
                tools_used.append(event["tool"])
                await edit_message(target, placeholder_id, f"🔧 _{label}..._")
            elif event["type"] == "token":
                accumulated += event["content"]
            elif event["type"] == "done":
                tokens_used = event.get("tokens_used", 0)
            elif event["type"] == "error":
                raise Exception(event["message"])

        latency = time.perf_counter() - start_time
        final = accumulated or "_(пустой ответ)_"
        
        footer = []
        if tools_used:
            unique = list(dict.fromkeys(tools_used))
            footer.append(f"🔧 _{', '.join(_tool_label(t) for t in unique)}_")
        if tokens_used:
            footer.append(f"📊 _{tokens_used:,} токенов_")
        if latency:
            footer.append(f"⏱ _{latency:.1f} сек_")
            
        if footer:
            final = final.rstrip() + "\\n\\n" + "  ".join(footer)

        if len(final) > 4096:
            final = final[:4090] + "\\n…"

        await edit_message(target, placeholder_id, final)

        task.status = "success"
        task.output_data = {"output": accumulated, "tools_used": list(dict.fromkeys(tools_used))}
        task.tokens_used = tokens_used
        agent.status = "idle"
        db.add(task); db.add(agent)
        await db.commit()

    except Exception as e:
        import logging
        logger = logging.getLogger("telegram_bot")
        logger.exception("Stream error: %s", e)
        friendly_err = "❌ Ошибка при генерации ответа. Попробуйте сменить модель или повторить запрос."
        await edit_message(target, placeholder_id, friendly_err)
        task.status = "failed"
        task.error_msg = str(e)
        agent.status = "idle"
        db.add(task); db.add(agent)
        await db.commit()

"""

# Исправляем handle_update чтобы он вызывал _stream_agent_to_topic
new_handle_update = """async def handle_update(update: dict, db) -> None:
    message = (update.get("message") or update.get("channel_post") or update.get("edited_message"))
    if not message:
        return

    thread_id = message.get("message_thread_id")
    text = (message.get("text") or "").strip()
    message_id = message.get("message_id", 0)
    tg_user_id = str((message.get("from") or {}).get("id", ""))
    chat_id = str(message.get("chat", {}).get("id", ""))

    if text.startswith("/"):
        await _handle_command(message, thread_id, tg_user_id, db)
        return
    if not thread_id:
        return

    agent, user = await _find_agent_by_thread(chat_id, thread_id, tg_user_id, db)
    if not agent:
        return

    await _call("sendChatAction", chat_id=chat_id, action="typing", message_thread_id=thread_id)

    await _stream_agent_to_topic(
        agent=agent, input_text=text,
        thread_id=thread_id, chat_id=chat_id,
        reply_to_message_id=message_id, db=db,
    )
"""

# Нужно аккуратно соединить
# rest[1] в текущем выводе начинался с if text.startswith...
# Мы заменим всю кучу.

# Находим где реально начинается остальной код после handle_update
# В оригинале после handle_update была команда /start.
after_handle_update_marker = "async def _handle_command("
final_rest = content.split(after_handle_update_marker)[1]

final_content = parts[0] + new_stream_func + "\\n\\n# ── handle_update ──\\n\\n" + new_handle_update + "\\n\\nasync def _handle_command(" + final_rest

with open(filepath, "w", encoding="utf-8") as f:
    f.write(final_content)
