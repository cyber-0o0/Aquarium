import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# The fix: JSON-stringify + WebApp integration
updated_call_func = r'''async def _call(method: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skip: %s", method)
        return None
    
    import json
    file_fields = ['animation', 'photo', 'document', 'video', 'voice', 'audio', 'sticker']
    files = {}
    payload = {}
    
    for k, v in kwargs.items():
        if v is None: continue
        if k in file_fields and isinstance(v, str) and v.startswith("/") and os.path.exists(v):
            from os.path import basename
            files[k] = (basename(v), open(v, 'rb'), "image/gif" if v.endswith(".gif") else "application/octet-stream")
        else:
            if isinstance(v, (dict, list)):
                payload[k] = json.dumps(v)
            else:
                payload[k] = v
            
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            if files:
                resp = await c.post(_api(method), data=payload, files=files)
            else:
                # To avoid issues with nested dicts being stringified twice or NOT being passed as json,
                # we'll always use data=payload for simple types and correctly formatted JSON strings.
                # However, Telegram is fine with standard multipart-form if everything is stringified.
                resp = await c.post(_api(method), data=payload)
        
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
        return None'''

# Update handle_command to use the Vercel Web App URL
updated_start_logic = r'''    if text.startswith("/start") or text == "/help":
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
        return'''

remote_update_script = r'''
import os
import re
path = '/root/aquarium-ai/server/app/services/telegram_bot.py'
with open(path, 'r') as f:
    content = f.read()

# Replace _call function
pattern_call = r'async def _call\(method: str, \*\*kwargs: Any\) -> Optional\[Dict\[str, Any\]\]:.*?return None'
content = re.sub(pattern_call, r"""''' + updated_call_func + r'''""", content, flags=re.DOTALL)

# Replace start logic
pattern_start = r'if text\.startswith\("/start"\) or text == "/help":.*?return'
content = re.sub(pattern_start, r"""''' + updated_start_logic + r'''""", content, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(content)
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/finalize_webapp.py', 'w') as f:
    f.write(remote_update_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("/root/aquarium-ai/server/venv/bin/python /tmp/finalize_webapp.py")

print("🔄 Restarting aquarium (Web App + JSON Fix)...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
