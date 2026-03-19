import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check all listening ports
stdin, stdout, stderr = ssh.exec_command("ss -lntp")
print("ALL PORTS:")
print(stdout.read().decode())

# Check for .env file on server
stdin, stdout, stderr = ssh.exec_command("cat /root/aquarium-ai/server/.env")
print("SERVER .ENV:")
print(stdout.read().decode())

ssh.close()
