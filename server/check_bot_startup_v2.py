import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Get 50 log lines, no pager
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 50 --no-pager")
lines = stdout.readlines()
for l in lines:
    print(l.strip())

ssh.close()
