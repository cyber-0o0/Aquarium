import asyncio
import asyncpg
import socket
from app.core.config import settings

def test_socket(host, port):
    print(f"Checking socket connectivity to {host}:{port}...")
    try:
        with socket.create_connection((host, port), timeout=1):
            print(f"[SUCCESS] Socket is OPEN on {host}:{port}")
            return True
    except Exception:
        print(f"[FAILED] Socket is CLOSED on {host}:{port}")
        return False

async def attempt_conn(host, port, user, password, db, ssl):
    desc = f"host={host}, port={port}, user={user}, db={db}, ssl={ssl}"
    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=db,
                ssl=ssl
            ),
            timeout=2.0
        )
        print(f"    [SUCCESS] Connected! ({desc})")
        await conn.close()
        return True
    except Exception:
        return False

async def diagnose_db():
    print("=== Deep Database Connection Diagnostics ===")
    
    ports = [5432, 5433]
    hosts = ["127.0.0.1", "localhost"]
    users = ["postgres"]
    passwords = ["postgres", "", "password"]
    ssl_modes = [None, "disable"]
    
    found_any = False
    
    for port in ports:
        if not test_socket("127.0.0.1", port):
            continue
            
        print(f"\n--- Testing Port {port} ---")
        for host in hosts:
            for user in users:
                for pwd in passwords:
                    for ssl in ssl_modes:
                        if await attempt_conn(host, port, user, pwd, "postgres", ssl):
                            print(f"    *** VALID CREDENTIALS FOUND: user={user}, port={port}, pwd='{pwd}' ***")
                            found_any = True
                            # Check if target DB exists there
                            try:
                                conn = await asyncpg.connect(user=user, password=pwd, host=host, port=port, database="postgres", ssl=ssl)
                                dbs = await conn.fetch("SELECT datname FROM pg_database")
                                db_names = [r['datname'] for r in dbs]
                                print(f"    Existing DBs on this instance: {db_names}")
                                if settings.POSTGRES_DB in db_names:
                                    print(f"    [FOUND] Target DB '{settings.POSTGRES_DB}' exists here!")
                                else:
                                    print(f"    [MISSING] Target DB '{settings.POSTGRES_DB}' not found here.")
                                await conn.close()
                            except:
                                pass

    if not found_any:
        print("\n!!! No successful connections found on ports 5432 or 5433 !!!")
        print("This might be due to 'pg_hba.conf' restrictions or incorrect passwords.")

if __name__ == "__main__":
    asyncio.run(diagnose_db())
