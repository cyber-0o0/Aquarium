import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check dependencies for auth
print("🔍 Checking auth dependencies in deps.py...")
stdin, stdout, stderr = ssh.exec_command("cat /root/aquarium-ai/server/app/api/deps.py")
print(stdout.read().decode())

ssh.close()
