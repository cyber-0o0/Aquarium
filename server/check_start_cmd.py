import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check if the GIF file exists
print("📂 Checking for demo.gif...")
stdin, stdout, stderr = ssh.exec_command("ls -l /root/aquarium-ai/server/data/demo.gif")
print(stdout.read().decode())
print(stderr.read().decode())

# Check for recent errors related to sendAnimation
print("\n🕵️‍♂️ Checking for sendAnimation errors in logs...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 50 --no-pager | grep -i 'error'")
print(stdout.read().decode())

ssh.close()
