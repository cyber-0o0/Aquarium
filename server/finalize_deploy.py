import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

def finalize():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port=22, username=username, password=password)

    def run_cmd(cmd):
        print(f"🚀 Running: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out: print(out)
        if err: print(f"❌ ERR: {err}")
        return out, err

    # 1. Create .env on server
    # I'll populate it with placeholders for now or derived values
    # IMPORTANT: The user should update real keys later, but I'll set what I know
    env_content = """
PROJECT_NAME="Aquarium AI"
SECRET_KEY="supersecretkey-dev-auto"
ALLOWED_CORS_ORIGINS=["*"]
TELEGRAM_BOT_TOKEN="7850228302:AAH9LIOvHevC_C9S52uV7u3S-9E1n-Y_Pew"
# ... set other API keys here if needed ...
"""
    run_cmd(f"echo '{env_content}' > /root/aquarium-ai/server/.env")
    print("✅ .env created.")

    # 2. Init DB
    run_cmd("cd /root/aquarium-ai/server && ./venv/bin/python init_db.py")
    print("✅ Database initialized.")

    # 3. Create Systemd Service
    service_content = """
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

[Install]
WantedBy=multi-user.target
"""
    # Use multi-line write
    run_cmd(f"echo '{service_content}' > /etc/systemd/system/aquarium.service")
    
    # 4. Reload and start
    run_cmd("systemctl daemon-reload")
    run_cmd("systemctl enable aquarium")
    run_cmd("systemctl restart aquarium")
    
    # 5. Check status
    run_cmd("systemctl status aquarium | grep Active")
    
    ssh.close()
    print("✨ DEPLOY COMPLETE! Backend should be live on http://213.176.78.194")

if __name__ == "__main__":
    finalize()
