import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Read existing service config
stdin, stdout, stderr = ssh.exec_command("cat /etc/systemd/system/aquarium.service")
content = stdout.read().decode()
print("Original service content:")
print(content)

# 2. Replace port to 8080 (matching Nginx config)
new_content = content.replace("--port 80", "--port 8080").replace("--port 8000", "--port 8080")

# 3. Write new content back
sftp = ssh.open_sftp()
with sftp.open("/etc/systemd/system/aquarium.service", "w") as f:
    f.write(new_content)
sftp.close()

# 4. Daemon-reload and restart
print("🔄 Reloading systemd and restarting aquarium on 8080...")
ssh.exec_command("systemctl daemon-reload && systemctl restart aquarium")

# 5. Check if it's listening on 8080
import time
time.sleep(5)
stdin, stdout, stderr = ssh.exec_command("lsof -i :8080")
print("Port 8080 status:")
print(stdout.read().decode())

ssh.close()
