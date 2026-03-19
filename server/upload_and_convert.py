import paramiko
import os

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Create data dir
ssh.exec_command("mkdir -p /root/aquarium-ai/server/data")

# 2. Upload file
sftp = ssh.open_sftp()
local_path = r'd:\programming\AiHubTon\demo.mp4'
remote_path = '/root/aquarium-ai/server/data/demo.mp4'

print(f"Uploading {local_path} to {remote_path}...")
sftp.put(local_path, remote_path)
sftp.close()

# 3. Convert to GIF (optimized) 
# We use a palette to get better colors in GIF
print("🎬 Converting to GIF...")
conv_cmd = (
    "ffmpeg -i /root/aquarium-ai/server/data/demo.mp4 "
    "-vf \"fps=10,scale=320:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse\" "
    "-y /root/aquarium-ai/server/data/demo.gif"
)
stdin, stdout, stderr = ssh.exec_command(conv_cmd)
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
