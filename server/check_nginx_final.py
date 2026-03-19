import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Read nginx config carefully
stdin, stdout, stderr = ssh.exec_command("cat /etc/nginx/sites-enabled/ezhikfish.fun")
print(stdout.read().decode())

ssh.close()
