import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Pull latest code
print("⬇️ Pulling from master...")
stdin, stdout, stderr = ssh.exec_command("cd /root/aquarium-ai && git pull origin master")
print(stdout.read().decode())
print(stderr.read().decode())

# 2. Restart service
print("🔄 Restarting aquarium...")
ssh.exec_command("systemctl restart aquarium")

# 3. Wait and check
import time
time.sleep(5)
print("🧐 Checking health...")
stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:80/api/v1/health || echo 'FAILED'")
print(stdout.read().decode())

ssh.close()
