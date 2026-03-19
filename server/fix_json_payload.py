import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# The fix: JSON-stringify dicts when sending files
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
            # IMPORTANT FIX: Stringify complex objects if files are present
            if isinstance(v, (dict, list)):
                payload[k] = json.dumps(v)
            else:
                payload[k] = v
            
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            if files:
                resp = await c.post(_api(method), data=payload, files=files)
            else:
                # If no files, we can still use json=payload which handles dicts
                # BUT to be safe and consistent with multipart logic, we can use JSON if all are primitive
                # OR just use payload as is if they are already stringified.
                # Let's re-parse for JSON mode to avoid double-stringification
                final_payload = {k: (json.loads(v) if isinstance(v, str) and (v.startswith("{") or v.startswith("[")) else v) for k, v in payload.items()}
                resp = await c.post(_api(method), json=final_payload)
        
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

remote_update_script = r'''
import os
import re
path = '/root/aquarium-ai/server/app/services/telegram_bot.py'
with open(path, 'r') as f:
    content = f.read()

new_func = r"""''' + updated_call_func + r'''"""

pattern = r'async def _call\(method: str, \*\*kwargs: Any\) -> Optional\[Dict\[str, Any\]\]:.*?return None'
new_content = re.sub(pattern, new_func, content, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(new_content)
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/fix_json_payload.py', 'w') as f:
    f.write(remote_update_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("/root/aquarium-ai/server/venv/bin/python /tmp/fix_json_payload.py")
print(stdout.read().decode())
print(stderr.read().decode())

print("🔄 Restarting aquarium (Final Fix)...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
