import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check why it's failing
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 100 --no-pager")
full_log = stdout.read().decode()
print("--- LOGS ---")
print(full_log)

# Check if anything is still on port 80
stdin, stdout, stderr = ssh.exec_command("lsof -i :80")
print("--- PORT 80 ---")
print(stdout.read().decode())

ssh.close()
