import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# See current nginx sites
stdin, stdout, stderr = ssh.exec_command("ls /etc/nginx/sites-enabled/")
print("Enabled sites:")
print(stdout.read().decode())

ssh.close()
