"""
Algeo Verify - End-to-End Test
================================
Login -> Verify Address -> Check DB result

Run from backend/ folder:
    python test_e2e.py

Requires the server to be running:
    uvicorn app.main:app --reload
"""

import sys
import os
import json
import sqlite3
import urllib.request
import urllib.error
import urllib.parse

# ── Config ────────────────────────────────────────────────────────────
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
DB_PATH  = os.path.join(os.path.dirname(__file__), "algeo_verify.db")

AGENT_EMAIL    = "agent@algeo.dz"
AGENT_PASSWORD = "agent1234"

# A realistic Algerian address for the verification test
TEST_ADDRESS = "Rue Didouche Mourad, Constantine 25000"

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

# ── Helpers ───────────────────────────────────────────────────────────

def api(method: str, path: str, body: dict = None, token: str = None) -> dict:
    """Simple HTTP helper — no external dependencies."""
    url = f"{BASE_URL}{path}"

    if method == "GET" and body:
        url += "?" + urllib.parse.urlencode(body)
        data = None
    else:
        data = json.dumps(body).encode() if body else None

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return {
                "status": resp.status,
                "body": json.loads(resp.read().decode()),
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "body": json.loads(e.read().decode()) if e.fp else {},
        }


def query_db(sql: str, params: tuple = ()) -> list:
    """Run a raw SQL query against the SQLite database file."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def separator(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ── Tests ─────────────────────────────────────────────────────────────

def test_server_health() -> bool:
    separator("Step 0: Server Health Check")
    r = api("GET", "/")
    if r["status"] == 200:
        print(f"  {PASS} Server is running: {r['body']}")
        return True
    else:
        print(f"  {FAIL} Server not reachable (status={r['status']})")
        return False


def test_login() -> str | None:
    separator("Step 1: Login as Delivery Agent")

    # The auth endpoint uses query params (email, password)
    r = api(
        "POST",
        f"/auth/login?email={urllib.parse.quote(AGENT_EMAIL)}&password={urllib.parse.quote(AGENT_PASSWORD)}",
    )

    if r["status"] == 200 and "access_token" in r["body"]:
        token = r["body"]["access_token"]
        print(f"  {PASS} Login successful")
        print(f"  {INFO} Token: {token[:40]}...")
        return token
    else:
        print(f"  {FAIL} Login failed (status={r['status']})")
        print(f"  {INFO} Response: {r['body']}")
        return None


def test_auth_me(token: str) -> bool:
    separator("Step 2: Verify Token (/auth/me)")
    r = api("GET", "/auth/me", token=token)

    if r["status"] == 200:
        user = r["body"]
        print(f"  {PASS} Authenticated as: {user.get('name')} ({user.get('email')})")
        print(f"  {INFO} Role: {user.get('role')}, ID: {user.get('id')}")
        return True
    else:
        print(f"  {FAIL} /auth/me failed (status={r['status']})")
        print(f"  {INFO} Response: {r['body']}")
        return False


def test_list_deliveries(token: str) -> int | None:
    separator("Step 3: List Deliveries")
    r = api("GET", "/deliveries/", token=token)

    if r["status"] == 200:
        deliveries = r["body"]
        print(f"  {PASS} Found {len(deliveries)} deliveries")
        if deliveries:
            d = deliveries[0]
            print(f"  {INFO} First delivery: id={d.get('id')}, status={d.get('status')}")
            return d["id"]
        else:
            print(f"  {INFO} No deliveries found - will use /verify endpoint instead")
            return None
    else:
        print(f"  {FAIL} List deliveries failed (status={r['status']})")
        print(f"  {INFO} Response: {r['body']}")
        return None


def test_verify_standalone(token: str) -> dict | None:
    separator("Step 4a: Verify Address (standalone /verify)")
    r = api("POST", "/verify", body={"raw_address": TEST_ADDRESS})

    if r["status"] == 200:
        result = r["body"]
        print(f"  {PASS} Verification successful")
        print(f"  {INFO} Confidence Score: {result.get('confidenceScore')}")
        print(f"  {INFO} Normalized:       {result.get('normalizedAddress')}")
        print(f"  {INFO} Match Details:    {result.get('matchDetails')}")
        entities = result.get("detectedEntities", {})
        print(f"  {INFO} Detected Entities:")
        print(f"         Wilaya:      {entities.get('wilaya')}")
        print(f"         Commune:     {entities.get('commune')}")
        print(f"         Postal Code: {entities.get('postalCode')}")
        print(f"         Street:      {entities.get('street')}")
        flags = result.get("riskFlags", [])
        if flags:
            print(f"  {INFO} Risk Flags:")
            for f in flags:
                print(f"         - [{f.get('severity')}] {f.get('label')}: {f.get('description')}")
        return result
    else:
        print(f"  {FAIL} Verification failed (status={r['status']})")
        print(f"  {INFO} Response: {r['body']}")
        return None


def test_verify_delivery(delivery_id: int, token: str) -> dict | None:
    separator(f"Step 4b: Verify Delivery #{delivery_id}")
    r = api("POST", f"/deliveries/{delivery_id}/verify", token=token)

    if r["status"] == 200:
        result = r["body"]
        print(f"  {PASS} Delivery verification successful")
        print(f"  {INFO} Confidence: {result.get('confidenceScore')}")
        print(f"  {INFO} Risk:       {result.get('risk')}")
        print(f"  {INFO} Normalized: {result.get('normalizedAddress')}")
        return result
    else:
        print(f"  {FAIL} Delivery verification failed (status={r['status']})")
        print(f"  {INFO} Response: {r['body']}")
        return None


def test_db_verification_saved(verification_id: int = None) -> bool:
    separator("Step 5: Check Result Saved in DB")

    if not os.path.exists(DB_PATH):
        print(f"  {FAIL} Database file not found at: {DB_PATH}")
        return False

    # Query for the most recent verification record
    rows = query_db(
        "SELECT * FROM address_verification ORDER BY id DESC LIMIT 1"
    )

    if not rows:
        print(f"  {FAIL} No address_verification records found in DB")
        return False

    row = rows[0]
    print(f"  {PASS} Verification record found in DB")
    print(f"  {INFO} id:                 {row.get('id')}")
    print(f"  {INFO} raw_address:        {row.get('raw_address')}")
    print(f"  {INFO} normalized_address: {row.get('normalized_address')}")
    print(f"  {INFO} confidence_score:   {row.get('confidence_score')}")
    print(f"  {INFO} match_details:      {row.get('match_details')}")
    print(f"  {INFO} created_at:         {row.get('created_at')}")

    # Validate the record matches our test
    # Verify the most recent record has a valid confidence score
    score = row.get("confidence_score")
    if score is None:
        print(f"  {FAIL} Verification record has no confidence_score")
        return False

    # Count total verification records
    count = query_db("SELECT COUNT(*) as cnt FROM address_verification")[0]["cnt"]
    print(f"  {INFO} Total verification records in DB: {count}")

    return True


def test_no_token_rejected() -> bool:
    separator("Step 6: Auth Guard (no token -> 401/403)")
    r = api("GET", "/deliveries/")
    if r["status"] in (401, 403):
        print(f"  {PASS} Unauthenticated request correctly rejected ({r['status']})")
        return True
    else:
        print(f"  {FAIL} Expected 401 or 403, got {r['status']}")
        return False


# ── Main ──────────────────────────────────────────────────────────────

def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    print()
    print("  Algeo Verify - End-to-End Test Suite")
    print("  " + "=" * 40)
    print(f"  Server:   {BASE_URL}")
    print(f"  Database: {DB_PATH}")
    print(f"  Address:  {TEST_ADDRESS}")

    results = {}

    # 0. Health check
    if not test_server_health():
        print(f"\n  {FAIL} Server is not running. Start it with:")
        print(f"        uvicorn app.main:app --reload")
        sys.exit(1)

    # 1. Login
    token = test_login()
    results["login"] = token is not None

    if not token:
        print(f"\n  {FAIL} Cannot continue without a valid token.")
        sys.exit(1)

    # 2. Verify token
    results["auth_me"] = test_auth_me(token)

    # 3. List deliveries
    delivery_id = test_list_deliveries(token)
    results["list_deliveries"] = delivery_id is not None

    # 4a. Standalone verify
    verify_result = test_verify_standalone(token)
    results["verify_standalone"] = verify_result is not None

    # 4b. Delivery-specific verify (if we have deliveries)
    if delivery_id:
        delivery_verify = test_verify_delivery(delivery_id, token)
        results["verify_delivery"] = delivery_verify is not None

    # 5. Check DB
    verification_id = verify_result.get("id") if verify_result else None
    results["db_saved"] = test_db_verification_saved(verification_id)

    # 6. Auth guard
    results["auth_guard"] = test_no_token_rejected()

    # ── Summary ───────────────────────────────────────────────────────
    separator("Test Summary")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  {status} {name}")

    print(f"\n  {passed}/{total} passed, {failed} failed")

    if failed:
        sys.exit(1)
    else:
        print(f"\n  All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
