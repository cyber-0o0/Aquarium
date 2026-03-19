import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Grep for SOCIAL or Bot
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 500 --no-pager | grep -E 'SOCIAL|Bot|ERROR|Exception'")
print(stdout.read().decode())

ssh.close()
