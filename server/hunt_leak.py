import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Read agent_runtime.py to find where feed posts are created
print("🔍 Reading agent_runtime.py to find the leak...")
stdin, stdout, stderr = ssh.exec_command("cat /root/aquarium-ai/server/app/services/agent_runtime.py")
print(stdout.read().decode())

ssh.close()
