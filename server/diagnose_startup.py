import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Inspect stderr logs for aquarium service
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 100 --no-pager")
print("--- FULL LOGS ---")
print(stdout.read().decode())

# 2. Check installed packages on server to see if anything is missing
stdin, stdout, stderr = ssh.exec_command("cd /root/aquarium-ai/server && ./venv/bin/pip list | grep langchain")
print("--- LANGCHAIN PACKAGES ---")
print(stdout.read().decode())

ssh.close()
