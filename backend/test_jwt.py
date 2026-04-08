"""
JWT Protection Audit — tests every protected endpoint with:
  1. No token (missing Authorization header)
  2. Expired token
  3. Invalid/garbage token
  4. Valid token
"""
import requests
from jose import jwt
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8000"
SECRET_KEY = "supersecret"
ALGORITHM = "HS256"

# ── Generate tokens ──
expired_token = jwt.encode(
    {"sub": "1", "exp": datetime.utcnow() - timedelta(hours=1)},
    SECRET_KEY, algorithm=ALGORITHM
)
valid_token = jwt.encode(
    {"sub": "1", "exp": datetime.utcnow() + timedelta(hours=24)},
    SECRET_KEY, algorithm=ALGORITHM
)
garbage_token = "not.a.valid.jwt.token"

# ── All protected endpoints to test ──
ENDPOINTS = [
    # Auth
    ("GET",  "/auth/me"),
    # Deliveries (agent routes)
    ("GET",  "/deliveries/"),
    ("POST", "/deliveries/"),
    ("GET",  "/deliveries/1"),
    ("PATCH","/deliveries/1/status"),
    ("POST", "/deliveries/1/verify"),
    ("POST", "/deliveries/1/feedback"),
    ("GET",  "/deliveries/1/history"),
    # Admin
    ("GET",  "/api/admin/statistics"),
    ("GET",  "/api/admin/monthly-trends"),
    ("GET",  "/api/admin/delivery-status-distribution"),
    ("GET",  "/api/admin/verifications-by-wilaya"),
    ("GET",  "/api/admin/verifications"),
    ("GET",  "/api/admin/verifications/1"),
    ("GET",  "/api/admin/deliveries"),
    ("GET",  "/api/admin/deliveries/1"),
    ("GET",  "/api/admin/agents"),
    ("GET",  "/api/admin/agents/1"),
    ("GET",  "/api/admin/analytics/score-distribution"),
    ("GET",  "/api/admin/logs"),
    ("GET",  "/api/admin/logs/requests-per-endpoint"),
    ("GET",  "/api/admin/logs/error-rate"),
]

# ── Unprotected endpoints (should work WITHOUT token) ──
PUBLIC_ENDPOINTS = [
    ("GET",  "/"),
    ("POST", "/verify"),
    ("POST", "/auth/login"),
]

def req(method, path, token=None, json_body=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    fn = getattr(requests, method.lower())
    kwargs = {"headers": headers, "timeout": 5}
    if json_body:
        kwargs["json"] = json_body
    return fn(f"{BASE}{path}", **kwargs)

def status_icon(code, expected):
    return "✅" if code == expected else "❌"

# ═══════════════════════════════════════════════════════
print("=" * 72)
print("  JWT PROTECTION AUDIT")
print("=" * 72)

# ── Test 1: No token ──
print("\n── TEST 1: No Token (missing Authorization header) ──")
print(f"{'Method':<6} {'Endpoint':<45} {'Status':<8} {'OK?'}")
print("-" * 72)
all_pass = True
for method, path in ENDPOINTS:
    r = req(method, path)
    ok = r.status_code == 403  # HTTPBearer returns 403 when no header
    icon = "✅" if ok else "❌"
    if not ok:
        all_pass = False
    print(f"{method:<6} {path:<45} {r.status_code:<8} {icon}")
print(f"\nResult: {'ALL BLOCKED ✅' if all_pass else 'SOME UNPROTECTED ❌'}")

# ── Test 2: Expired token ──
print("\n── TEST 2: Expired Token ──")
print(f"{'Method':<6} {'Endpoint':<45} {'Status':<8} {'OK?'}")
print("-" * 72)
all_pass = True
for method, path in ENDPOINTS:
    r = req(method, path, token=expired_token)
    ok = r.status_code == 401
    icon = "✅" if ok else "❌"
    if not ok:
        all_pass = False
    print(f"{method:<6} {path:<45} {r.status_code:<8} {icon}")
print(f"\nResult: {'ALL REJECTED ✅' if all_pass else 'SOME LEAKED ❌'}")

# ── Test 3: Garbage token ──
print("\n── TEST 3: Invalid/Garbage Token ──")
print(f"{'Method':<6} {'Endpoint':<45} {'Status':<8} {'OK?'}")
print("-" * 72)
all_pass = True
for method, path in ENDPOINTS:
    r = req(method, path, token=garbage_token)
    ok = r.status_code == 401
    icon = "✅" if ok else "❌"
    if not ok:
        all_pass = False
    print(f"{method:<6} {path:<45} {r.status_code:<8} {icon}")
print(f"\nResult: {'ALL REJECTED ✅' if all_pass else 'SOME LEAKED ❌'}")

# ── Test 4: Valid token ──
print("\n── TEST 4: Valid Token (should succeed or return business errors) ──")
print(f"{'Method':<6} {'Endpoint':<45} {'Status':<8} {'OK?'}")
print("-" * 72)
all_pass = True
for method, path in ENDPOINTS:
    body = None
    if method == "POST" and path == "/deliveries/":
        body = {"status": "pending", "scheduled_date": "2026-04-10T09:00:00Z"}
    elif method == "PATCH" and "status" in path:
        body = {"status": "in_progress"}
    elif method == "POST" and "feedback" in path:
        body = {"outcome": "success", "notes": "test"}
    r = req(method, path, token=valid_token, json_body=body)
    # Valid token should NOT return 401 or 403
    ok = r.status_code not in (401, 403)
    icon = "✅" if ok else "❌"
    if not ok:
        all_pass = False
    print(f"{method:<6} {path:<45} {r.status_code:<8} {icon}")
print(f"\nResult: {'ALL AUTHENTICATED ✅' if all_pass else 'AUTH ISSUES ❌'}")

# ── Test 5: Public endpoints (should work without token) ──
print("\n── TEST 5: Public Endpoints (should work WITHOUT token) ──")
print(f"{'Method':<6} {'Endpoint':<45} {'Status':<8} {'OK?'}")
print("-" * 72)
all_pass = True
for method, path in PUBLIC_ENDPOINTS:
    body = None
    if path == "/verify":
        body = {"raw_address": "Constantine 25000"}
    elif path == "/auth/login":
        r = requests.post(f"{BASE}/auth/login?email=test@test.com&password=test123", timeout=5)
    else:
        r = req(method, path, json_body=body)
        
    if path != "/auth/login":
        r = req(method, path, json_body=body)
    ok = r.status_code < 400
    icon = "✅" if ok else "❌"
    if not ok:
        all_pass = False
    print(f"{method:<6} {path:<45} {r.status_code:<8} {icon}")
print(f"\nResult: {'ALL ACCESSIBLE ✅' if all_pass else 'SOME BLOCKED ❌'}")

print("\n" + "=" * 72)
print("  AUDIT COMPLETE")
print("=" * 72)
