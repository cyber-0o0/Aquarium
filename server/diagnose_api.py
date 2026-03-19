import httpx

def check_route(url):
    try:
        r = httpx.get(url, timeout=5)
        print(f"URL: {url} | Status: {r.status_code}")
        if r.status_code == 200:
            print(f"  Result: {r.text[:100]}...")
    except Exception as e:
        print(f"URL: {url} | ERROR: {e}")

if __name__ == "__main__":
    base = "http://127.0.0.1:8000"
    routes = [
        "/",
        "/health",
        "/api/v1/feed",
        "/api/v1/feed/",
        "/api/v1/users/me"
    ]
    for r in routes:
        check_route(base + r)
