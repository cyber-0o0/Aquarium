import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Grep for AUTH or login errors in aquarium logs
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 100 --no-pager | grep -iE 'auth|telegram|401|403|ERROR'")
print(stdout.read().decode())

ssh.close()
