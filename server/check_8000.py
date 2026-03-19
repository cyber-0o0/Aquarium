import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Check who is on 8000
stdin, stdout, stderr = ssh.exec_command("lsof -i :8000")
print("--- PORT 8000 ---")
print(stdout.read().decode())

# 2. Check complete process list for aquarium
stdin, stdout, stderr = ssh.exec_command("ps -aux | grep main.py")
print("--- PROCESS ---")
print(stdout.read().decode())

# 3. Check logs AGAIN carefully
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 100 --no-pager")
print("--- LOGS ---")
print(stdout.read().decode())

ssh.close()
