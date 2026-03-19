import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check status
print("Service status:")
stdin, stdout, stderr = ssh.exec_command("systemctl status aquarium --no-pager")
print(stdout.read().decode())

# Check port 8080
print("Port 8080 check:")
stdin, stdout, stderr = ssh.exec_command("lsof -i :8080")
print(stdout.read().decode())

# Check HTTPS
print("HTTPS Health Check at ezhikfish.fun:")
stdin, stdout, stderr = ssh.exec_command("curl -s -v https://ezhikfish.fun/health || echo 'FAILED'")
print(stdout.read().decode())

ssh.close()
