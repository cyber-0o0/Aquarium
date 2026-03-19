import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Script to update the WebApp URL in telegram_bot.py
print("🛠️ Updating WebApp URL to include mode=fullscreen in telegram_bot.py...")

update_url_script = r'''
import os
path = '/root/aquarium-ai/server/app/services/telegram_bot.py'
with open(path, 'r') as f:
    content = f.read()

# Update the Vercel URL to include the fullscreen mode
old_url = 'https://aquarium-8ux8.vercel.app/'
new_url = 'https://aquarium-8ux8.vercel.app/?mode=fullscreen'

if old_url in content and new_url not in content:
    content = content.replace(old_url, new_url)
    with open(path, 'w') as f:
        f.write(content)
    print("✅ WebApp URL updated with mode=fullscreen")
else:
    print("URL already updated or not found.")
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/update_webapp_url.py', 'w') as f:
    f.write(update_url_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("/root/aquarium-ai/server/venv/bin/python /tmp/update_webapp_url.py")
print(stdout.read().decode())

print("🔄 Restarting aquarium...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
