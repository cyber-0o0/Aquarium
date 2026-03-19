import paramiko
import os

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

# Read local .env content
local_env_path = r"d:\programming\AiHubTon\server\.env"
with open(local_env_path, 'r', encoding='utf-8') as f:
    local_env_content = f.read()

# Filter out SQLALCHEMY_DATABASE_URI or other local paths if needed
# Actually, keeping it as-is is fine as long as we use corrected keys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Write to a temp file on server then move
print("📤 Uploading local .env to server...")
sftp = ssh.open_sftp()
with sftp.file('/root/aquarium-ai/server/.env', 'w') as f:
    f.write(local_env_content)
sftp.close()

# Double check
stdin, stdout, stderr = ssh.exec_command("grep -E 'API_KEY|TOKEN' /root/aquarium-ai/server/.env | wc -l")
print(f"Number of keys synced: {stdout.read().decode().strip()}")

# Restart service
print("🔄 Restarting aquarium to apply all keys...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
