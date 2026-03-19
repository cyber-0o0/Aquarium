import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Brutally clear port 80 if needed
commands = [
    "systemctl stop ezhik-ideas || true",
    "fuser -k 80/tcp || true",
    "systemctl restart aquarium"
]

for cmd in commands:
    print(f"🚀 {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())

ssh.close()
