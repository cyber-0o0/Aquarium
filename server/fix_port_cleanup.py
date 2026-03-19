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
print("CURRENT service content:")
print(content)

# 2. Complete cleaning of any port 80 or PORT=80
new_content = content.replace("Environment=PORT=80", "Environment=PORT=8080")
if "--port 80" in new_content:
    new_content = new_content.replace("--port 80", "--port 8080")

# 3. Write new content back
sftp = ssh.open_sftp()
with sftp.open("/etc/systemd/system/aquarium.service", "w") as f:
    f.write(new_content)
sftp.close()

# 4. Daemon-reload and restart
print("🔄 Force reloading and restarting...")
ssh.exec_command("systemctl daemon-reload && systemctl restart aquarium")

# 5. Check port 8080 and 80
import time
time.sleep(5)
stdin, stdout, stderr = ssh.exec_command("ss -lntp | grep 8080")
print("Listening ports (8080):")
print(stdout.read().decode())

ssh.close()
