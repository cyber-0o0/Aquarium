import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check postgres
print("Postgres status:")
stdin, stdout, stderr = ssh.exec_command("systemctl status postgresql --no-pager")
print(stdout.read().decode())

# Check port 5432
print("Port 5432 check:")
stdin, stdout, stderr = ssh.exec_command("ss -lntp | grep 5432")
print(stdout.read().decode())

ssh.close()
