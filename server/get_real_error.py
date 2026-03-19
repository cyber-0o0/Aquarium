import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Run it manually and capture EVERYTHING
stdin, stdout, stderr = ssh.exec_command("cd /root/aquarium-ai/server && ./venv/bin/python main.py")
print("--- STDOUT ---")
print(stdout.read().decode())
print("--- STDERR ---")
print(stderr.read().decode())

ssh.close()
