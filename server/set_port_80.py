import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Update systemd once more to port 80
final_service = """
[Unit]
Description=Aquarium AI Backend
After=network.target

[Service]
User=root
WorkingDirectory=/root/aquarium-ai/server
ExecStart=/root/aquarium-ai/server/venv/bin/python main.py
Restart=always
Environment=PORT=80
Environment=DEBUG=false
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
ssh.exec_command(f"echo '{final_service}' > /etc/systemd/system/aquarium.service")
ssh.exec_command("systemctl daemon-reload && systemctl restart aquarium")

# 2. Wait 5 seconds and check if it's REALLY listening
print("⏳ Waiting for startup...")
import time
time.sleep(5)

stdin, stdout, stderr = ssh.exec_command("lsof -i :80")
print("--- Check Port 80 ---")
print(stdout.read().decode())

ssh.close()
