import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check ffmpeg on server
print("Checking ffmpeg on server...")
stdin, stdout, stderr = ssh.exec_command("ffmpeg -version || echo 'NOT_FOUND'")
print(stdout.read().decode())

ssh.close()
