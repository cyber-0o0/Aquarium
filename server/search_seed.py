import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check for seed_db.py or similar
print("🔍 Searching for seeding scripts...")
stdin, stdout, stderr = ssh.exec_command("ls /root/aquarium-ai/server/*.py | grep -E 'seed|init'")
print(stdout.read().decode())

ssh.close()
