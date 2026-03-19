import httpx
import os

def check_route(url):
    try:
        # Отключаем использование системных прокси для локального запроса
        with httpx.Client(proxies={}, timeout=5) as client:
            r = client.get(url)
            print(f"URL: {url} | Status: {r.status_code}")
            if r.status_code == 200:
                print(f"  Result: {r.text[:50]}...")
    except Exception as e:
        print(f"URL: {url} | ERROR: {e}")

if __name__ == "__main__":
    # Проверяем и 127.0.0.1, и localhost
    bases = ["http://127.0.0.1:8000", "http://localhost:8000"]
    routes = ["/health", "/api/v1/feed/"]
    
    print(f"ENV HTTP_PROXY: {os.environ.get('HTTP_PROXY')}")
    print(f"ENV HTTPS_PROXY: {os.environ.get('HTTPS_PROXY')}")
    
    for b in bases:
        for r in routes:
            check_route(b + r)
