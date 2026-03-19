import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check nginx
print("Checking nginx...")
stdin, stdout, stderr = ssh.exec_command("nginx -v || echo 'NGINX_NOT_FOUND'")
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
