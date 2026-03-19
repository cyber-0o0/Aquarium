import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# The updated robust _call function code
updated_call_func = r'''async def _call(method: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skip: %s", method)
        return None
    
    file_fields = ['animation', 'photo', 'document', 'video', 'voice', 'audio', 'sticker']
    files = {}
    payload = {}
    
    for k, v in kwargs.items():
        if v is None: continue
        if k in file_fields and isinstance(v, str) and v.startswith("/") and os.path.exists(v):
            # Pass (filename, file_object, mimetype) to httpx
            from os.path import basename
            files[k] = (basename(v), open(v, 'rb'), "image/gif" if v.endswith(".gif") else "application/octet-stream")
        else:
            payload[k] = v
            
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            if files:
                resp = await c.post(_api(method), data=payload, files=files)
            else:
                resp = await c.post(_api(method), json=payload)
        
        for f_tuple in files.values():
            if isinstance(f_tuple, tuple): f_tuple[1].close()
        
        data = resp.json()
        if not data.get("ok"):
            print(f"❌ Telegram [{method}] error: {data.get('description')}")
            logger.error("Telegram [%s] error: %s", method, data.get("description"))
            return None
        return data.get("result")
    except Exception as e:
        for f_tuple in files.values():
            if isinstance(f_tuple, tuple): f_tuple[1].close()
        logger.exception("Telegram [%s] exception: %s", method, e)
        return None'''

# Define a safer update script that doesn't use regex for the whole block
# We replace a known marker line (the start of the old _call)

remote_update_script = r'''
import os
path = '/root/aquarium-ai/server/app/services/telegram_bot.py'
with open(path, 'r') as f:
    content = f.read()

# I'll define the replacement block as a raw string to avoid escaping hell
new_func = r"""''' + updated_call_func + r'''"""

# Match the old _call block specifically 
import re
pattern = r'async def _call\(method: str, \*\*kwargs: Any\) -> Optional\[Dict\[str, Any\]\]:.*?return None'
new_content = re.sub(pattern, new_func, content, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(new_content)
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/update_bot_call_v2.py', 'w') as f:
    f.write(remote_update_script)
sftp.close()

print("🛠️ Applying the fix using absolute path to python...")
stdin, stdout, stderr = ssh.exec_command("/root/aquarium-ai/server/venv/bin/python /tmp/update_bot_call_v2.py")
print(stdout.read().decode())
print(stderr.read().decode())

print("🔄 Restarting aquarium...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
