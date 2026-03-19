import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check logs 
stdin, stdout, stderr = ssh.exec_command("journalctl -u aquarium -n 100 --no-pager")
print("--- STDOUT ---")
print(stdout.read().decode())
print("--- STDERR ---")
print(stderr.read().decode())

# Check listening ports
stdin, stdout, stderr = ssh.exec_command("ss -lptn | grep 80")
print("--- PORTS ---")
print(stdout.read().decode())

ssh.close()
