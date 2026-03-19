import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Fix the broken line and move it AFTER 'text' is defined
print("🛠️ Repairing telegram_bot.py syntax...")
# Remove the broken line
ssh.exec_command("sed -i '507d' /root/aquarium-ai/server/app/services/telegram_bot.py")

# Add it back properly at line 509 (after text is defined)
cmd = """sed -i '509i\\    print(f"DEBUG: Handling command {text} in thread {thread_id}")' /root/aquarium-ai/server/app/services/telegram_bot.py"""
ssh.exec_command(cmd)

print("🔄 Restarting aquarium (Reanimation)...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
