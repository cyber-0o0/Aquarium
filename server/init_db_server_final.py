import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Run init_db.py on server
print("🏗️ Initializing database on server...")
cmd = "cd /root/aquarium-ai/server && source venv/bin/activate && python init_db.py"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())

# Restart service just in case
print("🔄 Restarting aquarium to pick up new DB...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
