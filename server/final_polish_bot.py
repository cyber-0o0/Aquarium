import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Final fix: Remove the extra slash space and improve logging
print("🛠️ Polishing telegram_bot.py and adding ultra-logs...")

remote_fix_script = r'''
import os
path = '/root/aquarium-ai/server/app/services/telegram_bot.py'
with open(path, 'r') as f:
    content = f.read()

# 1. Fix the syntax warning (extra space after backslash)
content = content.replace(r'\ Manage', 'Manage')

# 2. Add more explicit logging to _call (using sys.stderr to bypass buffering)
import sys
content = content.replace(
    'print(f"❌ Telegram [{method}] error: {data.get(\'description\')}")',
    'import sys; print(f"❌ ERROR: Telegram [{method}] failed: {data.get(\'description\')}", file=sys.stderr)'
)

with open(path, 'w') as f:
    f.write(content)
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/final_polish.py', 'w') as f:
    f.write(remote_fix_script)
sftp.close()

ssh.exec_command("/root/aquarium-ai/server/venv/bin/python /tmp/final_polish.py")

print("🔄 Restarting aquarium...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
