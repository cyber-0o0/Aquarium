import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check nginx
print("Nginx status:")
stdin, stdout, stderr = ssh.exec_command("systemctl status nginx --no-pager")
print(stdout.read().decode())

# Check ports
print("Ports (Listen):")
stdin, stdout, stderr = ssh.exec_command("ss -lntp")
print(stdout.read().decode())

# Check firewall
print("UFW status:")
stdin, stdout, stderr = ssh.exec_command("ufw status")
print(stdout.read().decode())

ssh.close()
