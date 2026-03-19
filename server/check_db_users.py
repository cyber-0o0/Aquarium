import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Check if any users exist in SQLite
print("👥 Checking users in DB...")
cmd = "cd /root/aquarium-ai/server && sqlite3 sql_app.db 'SELECT * FROM users;'"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

ssh.close()
