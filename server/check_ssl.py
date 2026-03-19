import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check if certbot is installed
print("Checking certbot...")
stdin, stdout, stderr = ssh.exec_command("certbot --version || echo 'NOT_INSTALLED'")
print(stdout.read().decode())
print(stderr.read().decode())

# Check port 443
print("Checking port 443...")
stdin, stdout, stderr = ssh.exec_command("lsof -i :443")
print(stdout.read().decode())

ssh.close()
