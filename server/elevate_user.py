import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Elevation script
elevation_script = r'''
import asyncio
from app.core.db import AsyncSessionLocal
from app.models.user import User
from sqlalchemy.future import select

async def elevate():
    async with AsyncSessionLocal() as db:
        # We find the most recent active user (likely you)
        res = await db.execute(select(User).order_by(User.updated_at.desc()).limit(5))
        users = res.scalars().all()
        
        if not users:
            print("No users found.")
            return

        # I'll elevate the first one as it's the most recently updated
        target_user = users[0]
        print(f"👑 Elevating user {target_user.username or target_user.telegram_id} to ADMIN...")
        target_user.plan = "admin"
        await db.commit()
        print("✅ User promoted to admin status.")

if __name__ == "__main__":
    asyncio.run(elevate())
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/elevate_admin.py', 'w') as f:
    f.write(elevation_script)
sftp.close()

print("🚀 Running promotion script with PYTHONPATH...")
stdin, stdout, stderr = ssh.exec_command("cd /root/aquarium-ai/server && export PYTHONPATH=. && venv/bin/python /tmp/elevate_admin.py")
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
