import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Check nginx config
stdin, stdout, stderr = ssh.exec_command("ls -la /etc/nginx/sites-enabled/")
print("--- NGINX SITES ---")
print(stdout.read().decode())

# 2. Check if nginx is running
stdin, stdout, stderr = ssh.exec_command("systemctl is-active nginx")
print("--- NGINX ACTIVE ---")
print(stdout.read().decode())

# 3. Check what's listening on ANY port
stdin, stdout, stderr = ssh.exec_command("ss -lptn")
print("--- ALL PORTS ---")
print(stdout.read().decode())

ssh.close()
