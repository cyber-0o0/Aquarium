import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Read User model to find admin field
print("🔍 Checking User model and FeedPost delete logic...")
stdin, stdout, stderr = ssh.exec_command("cat /root/aquarium-ai/server/app/models/user.py")
print(stdout.read().decode())

ssh.close()
