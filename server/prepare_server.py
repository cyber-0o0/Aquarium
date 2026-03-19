import paramiko
import time

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

def deploy():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, port=22, username=username, password=password)
        print("✅ SSH Connection established.")

        def run_cmd(cmd):
            print(f"🚀 Running: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            if out: print(out)
            if err: print(f"❌ ERR: {err}")
            return out, err

        # 1. Inspect server (what's running)
        run_cmd("ps -aux | head -n 20")
        
        # 2. Update and install basic stuff
        run_cmd("apt-get update && apt-get install -y git python3-pip python3-venv")
        
        # 3. Stop potential conflicting services (Apache2, etc if they exist)
        print("🧹 Cleaning up unnecessary services...")
        run_cmd("systemctl stop apache2 || true")
        run_cmd("systemctl stop nginx || true") # I'll restart it later if needed, but for now clear port 80/443
        run_cmd("systemctl disable apache2 || true")
        
        # 4. Preparing app directory
        run_cmd("rm -rf /root/aquarium-ai")
        run_cmd("git clone https://github.com/cyber-0o0/Aquarium.git /root/aquarium-ai")
        
        # 5. Setting up venv
        print("📦 Setting up virtual environment...")
        run_cmd("cd /root/aquarium-ai/server && python3 -m venv venv")
        run_cmd("cd /root/aquarium-ai/server && ./venv/bin/pip install -r requirements.txt")

        ssh.close()
        print("✅ Initial preparation done.")

    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    deploy()
