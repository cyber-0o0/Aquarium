import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

def run_cmd(cmd):
    print(f"🚀 Running: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    if err: print(f"❌ ERR: {err}")
    return out, err

# 1. Create SWAP (to handle heavy installation)
print("🛠 Creating swap space...")
run_cmd("fallocate -l 2G /swapfile")
run_cmd("chmod 600 /swapfile")
run_cmd("mkswap /swapfile")
run_cmd("swapon /swapfile")
run_cmd("echo '/swapfile none swap sw 0 0' >> /etc/fstab")

# 2. Check RAM
run_cmd("free -m")

# 3. Clean and Reinstall requirements
print("📦 Reinstalling requirements.txt...")
run_cmd("cd /root/aquarium-ai/server && ./venv/bin/python -m pip install --upgrade pip")
run_cmd("cd /root/aquarium-ai/server && ./venv/bin/pip install -r requirements.txt")

# 4. Final Restart
run_cmd("systemctl restart aquarium")

ssh.close()
print("✅ Server repaired and Aquarium restarted.")
