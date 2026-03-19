import paramiko

hostname = '213.176.78.194'
username = 'root'
password = '6SsoaVyMahRk'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username=username, password=password)

# Add debug logging to _handle_command
print("🔧 Adding debug logs to telegram_bot.py...")
cmd = """sed -i '507i\\    print(f"DEBUG: Handling command {text} in thread {thread_id}")' /root/aquarium-ai/server/app/services/telegram_bot.py"""
ssh.exec_command(cmd)

print("🔄 Restarting aquarium...")
ssh.exec_command("systemctl restart aquarium")

ssh.close()
