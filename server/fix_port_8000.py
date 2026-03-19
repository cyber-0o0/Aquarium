import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Update systemd to use port 8000
new_service = """
[Unit]
Description=Aquarium AI Backend
After=network.target

[Service]
User=root
WorkingDirectory=/root/aquarium-ai/server
ExecStart=/root/aquarium-ai/server/venv/bin/python main.py
Restart=always
Environment=PORT=8000
Environment=DEBUG=false

[Install]
WantedBy=multi-user.target
"""
ssh.exec_command(f"echo '{new_service}' > /etc/systemd/system/aquarium.service")
ssh.exec_command("systemctl daemon-reload && systemctl restart aquarium")

ssh.close()
print("✅ Switched to port 8000. Restarting...")
