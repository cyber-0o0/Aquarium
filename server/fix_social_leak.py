import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# 1. Fix the code leak in agent_runtime.py
print("🛠️ Fixing the social feed leak in agent_runtime.py...")

fix_script = r'''
import os
import re
path = '/root/aquarium-ai/server/app/services/agent_runtime.py'
with open(path, 'r') as f:
    content = f.read()

# Add the check for is_social_active in _add_feed_post helper
# Or better: check it BEFORE calling the helper in stream_task
# We'll update _add_feed_post to be safer internal check

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
content = re.sub(pattern_helper, new_helper, content, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(content)
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/fix_feed_leak.py', 'w') as f:
    f.write(fix_script)
sftp.close()

ssh.exec_command("/root/aquarium-ai/server/venv/bin/python /tmp/fix_feed_leak.py")

# 2. Cleanup the database
print("🧹 Cleaning up existing leaked posts from the database...")
cleanup_db_script = r'''
import asyncio
from app.core.db import AsyncSessionLocal
from app.models.feed_post import FeedPost
from app.models.agent import Agent
from sqlalchemy.future import select
from sqlalchemy import delete

async def cleanup():
    async with AsyncSessionLocal() as db:
        # Find posts from agents that have is_social_active = False
        res = await db.execute(select(Agent.id).where(Agent.is_social_active == False))
        inactive_agent_ids = [r for r in res.scalars().all()]
        
        if inactive_agent_ids:
            q = delete(FeedPost).where(FeedPost.agent_id.in_(inactive_agent_ids))
            await db.execute(q)
            await db.commit()
            print(f"✅ Deleted leaked posts for {len(inactive_agent_ids)} inactive agents.")
        else:
            print("No inactive agents found to cleanup.")

if __name__ == "__main__":
    asyncio.run(cleanup())
'''

# We also need to delete posts that are NOT social cycles (if we want full reset)
# But the user specifically complained about private messages leaking.

with sftp.file('/tmp/cleanup_feed.py', 'w') as f:
    f.write(cleanup_db_script)

ssh.exec_command("cd /root/aquarium-ai/server && venv/bin/python /tmp/cleanup_feed.py")

print("🔄 Restarting aquarium...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
