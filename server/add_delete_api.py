import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Script to inject DELETE endpoint into feed.py
print("🛠️ Injecting DELETE endpoint into feed.py and adding Admin checks...")

inject_script = r'''
import os
import re

path = '/root/aquarium-ai/server/app/api/v1/endpoints/feed.py'
with open(path, 'r') as f:
    content = f.read()

# 1. Add imports
if 'from app.api.deps import get_current_user' not in content:
    content = content.replace(
        'from app.services.social_service import SocialService',
        'from app.services.social_service import SocialService\nfrom app.api.deps import get_current_user\nfrom app.models.user import User'
    )

# 2. Add the DELETE endpoint at the end or before Reaction
delete_endpoint = r"""
@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    \"\"\"
    Удалить пост (только для Админов).
    \"\"\"
    if current_user.plan != "admin":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Admin access required to delete posts."
        )

    from sqlalchemy import delete
    # Find the post first to ensure it exists
    query = select(FeedPost).where(FeedPost.id == post_id)
    res = await db.execute(query)
    post = res.scalar_one_or_none()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    await db.delete(post)
    await db.commit()
    return {"status": "ok", "message": f"Post {post_id} deleted"}
"""

if '@router.delete("/{post_id}")' not in content:
    content += delete_endpoint

with open(path, 'w') as f:
    f.write(content)
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/inject_delete.py', 'w') as f:
    f.write(inject_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("/root/aquarium-ai/server/venv/bin/python /tmp/inject_delete.py")
print(stdout.read().decode())
print(stderr.read().decode())

print("🔄 Restarting aquarium...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
