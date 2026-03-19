import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Unified script for FIX + CLEANUP + RESTART
unified_script = r'''
import os
import re
import asyncio
from app.core.db import AsyncSessionLocal
from app.models.feed_post import FeedPost
from app.models.agent import Agent
from sqlalchemy.future import select
from sqlalchemy import delete

# 1. FIX THE CODE
path = '/root/aquarium-ai/server/app/services/agent_runtime.py'
with open(path, 'r') as f:
    content = f.read()

new_helper = r"""async def _add_feed_post(agent_id: str, content: str):
    from app.core.db import SessionLocal
    from app.models.agent import Agent
    from sqlalchemy.future import select
    async with SessionLocal() as db:
        try:
            res = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = res.scalar_one_or_none()
            if not agent or not agent.is_social_active:
                return
            
            new_post = FeedPost(
                agent_id=agent_id,
                content=content,
                post_type="insight"
            )
            db.add(new_post)
            await db.commit()
        except Exception as e:
            print(f"❌ Failed to auto-post to feed: {e}")"""

pattern_helper = r'async def _add_feed_post\(agent_id: str, content: str\):.*?await db\.commit\(\).*?except Exception as e:.*?print\(f"❌ Failed to auto-post to feed: \{e\}"\)'
if "_add_feed_post" in content:
    content = re.sub(pattern_helper, new_helper, content, flags=re.DOTALL)
    with open(path, 'w') as f:
        f.write(content)
    print("✅ Logic fix applied to agent_runtime.py")

# 2. CLEANUP DB
async def cleanup():
    async with AsyncSessionLocal() as db:
        # Delete posts from agents that have is_social_active = False
        res = await db.execute(select(Agent.id).where(Agent.is_social_active == False))
        inactive_ids = [str(r) for r in res.scalars().all()]
        if inactive_ids:
            q = delete(FeedPost).where(FeedPost.agent_id.in_(inactive_ids))
            await db.execute(q)
            await db.commit()
            print(f"🧹 Deleted leaked posts for {len(inactive_ids)} inactive agents.")
        else:
            print("No leaked posts found to cleanup.")

if __name__ == "__main__":
    asyncio.run(cleanup())
'''

print("📤 Uploading unified fix-and-cleanup script...")
sftp = ssh.open_sftp()
with sftp.file('/tmp/unified_feed_fix.py', 'w') as f:
    f.write(unified_script)
sftp.close()

print("🚀 Executing unified fix...")
stdin, stdout, stderr = ssh.exec_command("cd /root/aquarium-ai/server && venv/bin/python /tmp/unified_feed_fix.py")
print(stdout.read().decode())
print(stderr.read().decode())

print("🔄 Restarting aquarium (Clean Slate)...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
