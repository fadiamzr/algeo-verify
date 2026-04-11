import sqlite3
conn = sqlite3.connect("algeo_verify.db")
c = conn.cursor()

print("=== Users ===")
for row in c.execute("SELECT id, email, role FROM user"):
    print(f"  {row}")

print("\n=== Delivery Agents ===")
for row in c.execute("SELECT * FROM delivery_agent"):
    print(f"  {row}")

print("\n=== Deliveries ===")
for row in c.execute("SELECT id, address, latitude, longitude, status, geocoding_status FROM delivery"):
    print(f"  {row}")

print("\n=== Table row counts ===")
for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    count = c.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
    print(f"  {t[0]}: {count} rows")

conn.close()
