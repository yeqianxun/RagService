from urllib.request import Request, urlopen
import json
import urllib.parse

BASE = "http://localhost:8000/api/v1"

# 1. Login
data = urllib.parse.urlencode({
    "grant_type": "password",
    "username": "admin@example.com",
    "password": "Admin@123456",
}).encode()
req = Request(f"{BASE}/auth/token", data=data, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
r = urlopen(req)
token_data = json.loads(r.read())
token = token_data.get("access_token", "")
print("=== Login ===")
print(f"Status: {r.status}")
print(f"Token: {token[:50]}...")

# 2. Get permissions
req2 = Request(f"{BASE}/permissions")
req2.add_header("Authorization", f"Bearer {token}")
r2 = urlopen(req2)
perms = json.loads(r2.read())
print()
print("=== Permissions List ===")
print(f"Status: {r2.status}")
for p in perms["data"]:
    print(f'  [{p["module"]}] {p["code"]} -> {p["name"]}')

# 3. Get current user
req3 = Request(f"{BASE}/auth/me")
req3.add_header("Authorization", f"Bearer {token}")
r3 = urlopen(req3)
me = json.loads(r3.read())
print()
print("=== Current User ===")
u = me["data"]
print(f'Email: {u["email"]}')
print(f'Role: {u["role"]["name"]}')
perms_list = ", ".join(p["code"] for p in u["role"]["permissions"])
print(f"Permissions: {perms_list}")
