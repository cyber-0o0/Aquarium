import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Start Nginx
print("🚀 Starting Nginx...")
stdin, stdout, stderr = ssh.exec_command("systemctl restart nginx")
print(stdout.read().decode())
print(stderr.read().decode())

# Check status again
stdin, stdout, stderr = ssh.exec_command("systemctl status nginx --no-pager")
print(stdout.read().decode())

ssh.close()
