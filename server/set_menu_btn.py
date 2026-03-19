import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Script to set the Menu Button for the bot
menu_script = r'''
import asyncio
from app.services.telegram_bot import _call
from app.core.db import AsyncSessionLocal

async def set_menu():
    app_url = "https://aquarium-8ux8.vercel.app/"
    print(f"📡 Setting Chat Menu Button to: {app_url}")
    res = await _call("setChatMenuButton", menu_button={
        "type": "web_app",
        "text": "Open aquarium",
        "web_app": {"url": app_url}
    })
    print(f"✅ Result: {res}")

if __name__ == "__main__":
    asyncio.run(set_menu())
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/set_menu_button.py', 'w') as f:
    f.write(menu_script)
sftp.close()

print("🛠️ Setting Menu Button via server...")
# We use absolute path to PROJECT root so it can import app...
stdin, stdout, stderr = ssh.exec_command("cd /root/aquarium-ai/server && venv/bin/python /tmp/set_menu_button.py")
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
