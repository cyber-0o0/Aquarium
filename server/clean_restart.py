import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Kill all potential duplicate python processes
print("🧹 Cleaning up old processes...")
ssh.exec_command("pkill -9 python")

# 2. Restart the main service
print("🚀 Restarting aquarium service CLEAN...")
ssh.exec_command("systemctl restart aquarium")

# 3. Wait a bit and check logs for bot startup
import time
time.sleep(5)
print("📜 Fresh logs after clean restart:")
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 30 --no-pager")
print(stdout.read().decode())

ssh.close()
