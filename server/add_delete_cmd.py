import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Final Polish: Add /delete command to the bot for admins
print("🛠️ Adding /delete command to telegram_bot.py for Admins...")

inject_cmd_script = r'''
import os
import re

path = '/root/aquarium-ai/server/app/services/telegram_bot.py'
with open(path, 'r') as f:
    content = f.read()

delete_cmd_logic = r"""
    elif text.startswith("/delete "):
        from sqlalchemy.future import select
        from app.models.feed_post import FeedPost
        from app.models.user import User as UserModel
        
        # Check if user is admin
        res = await db.execute(select(UserModel).where(UserModel.telegram_id == tg_user_id))
        u = res.scalar_one_or_none()
        if not u or u.plan != "admin":
            await send_to_topic(thread_id, "🚫 Access Denied: Admins only.", reply_to_message_id=message_id, chat_id=chat_id)
            return
            
        try:
            post_id = int(text.split(" ")[1])
            q = select(FeedPost).where(FeedPost.id == post_id)
            res = await db.execute(q)
            post = res.scalar_one_or_none()
            if not post:
                await send_to_topic(thread_id, f"❌ Post {post_id} not found.", reply_to_message_id=message_id, chat_id=chat_id)
            else:
                await db.delete(post)
                await db.commit()
                await send_to_topic(thread_id, f"✅ Post {post_id} deleted successfully!", reply_to_message_id=message_id, chat_id=chat_id)
                import sys; print(f"👑 Admin deleted post {post_id}", file=sys.stderr)
        except Exception as e:
            await send_to_topic(thread_id, f"❌ Error: {e}", reply_to_message_id=message_id, chat_id=chat_id)
        return
"""

# Insert before recreation or after tasks
if 'elif text.startswith("/delete "):' not in content:
    content = content.replace(
        'elif text == "/recreate":',
        delete_cmd_logic + '\n    elif text == "/recreate":'
    )

with open(path, 'w') as f:
    f.write(content)
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/inject_delete_cmd.py', 'w') as f:
    f.write(inject_cmd_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("/root/aquarium-ai/server/venv/bin/python /tmp/inject_delete_cmd.py")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
