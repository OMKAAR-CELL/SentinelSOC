import random, sqlite3, os
from datetime import datetime, timedelta
from faker import Faker

random.seed(7)
fake = Faker()
Faker.seed(7)

DB = os.path.join(os.path.dirname(__file__), "logs.db")
DAY = datetime(2026, 10, 12)

USERS = [fake.user_name() for _ in range(40)] + ["admin"]
USER_IPS = {u: fake.ipv4_private() for u in USERS}   # each user has a home IP
ATTACKER_IP = "185.220.101.45"
PAGES = ["/home", "/login", "/courses", "/results", "/profile", "/library"]

rows = []

def add(ts, source, user, ip, event, status, detail=""):
    rows.append((ts.isoformat(timespec="seconds"), source, user, ip, event, status, detail))

# ---- normal traffic (6am to 11pm) ----
for _ in range(6000):
    ts = DAY + timedelta(seconds=random.randint(6 * 3600, 23 * 3600))
    u = random.choice(USERS)
    ip = USER_IPS[u]
    kind = random.choices(["login", "web", "db"], weights=[25, 60, 15])[0]
    if kind == "login":
        ok = random.random() > 0.04            # a few normal typos
        add(ts, "auth", u, ip, "login", "success" if ok else "failed")
    elif kind == "web":
        add(ts, "web", u, ip, "GET", "200", random.choice(PAGES))
    else:
        add(ts, "db", u, ip, "query", "ok",
            f"SELECT * FROM {random.choice(['courses', 'results', 'books'])} LIMIT 20")

# a harmless noisy IP so the agent has a distraction
noisy = fake.ipv4_public()
for i in range(15):
    add(DAY + timedelta(hours=11, seconds=i * 20), "auth", "student07", noisy, "login", "failed")

# ---- planted attack ----
t0 = DAY + timedelta(hours=2, minutes=3)
for i in range(200):                            # 2:03 AM brute force
    add(t0 + timedelta(seconds=i * 1.5), "auth", "admin", ATTACKER_IP, "login", "failed")
add(DAY + timedelta(hours=2, minutes=9), "auth", "admin", ATTACKER_IP, "login", "success")       # 2:09 login works
add(DAY + timedelta(hours=2, minutes=11), "web", "admin", ATTACKER_IP, "GET", "200", "/admin/export")
add(DAY + timedelta(hours=2, minutes=14), "db", "admin", ATTACKER_IP, "query", "ok",
    "SELECT * FROM customers  -- 48213 rows exported")                                            # 2:14 data theft

rows.sort(key=lambda r: r[0])

if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
con.execute("""CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, source TEXT, user TEXT, ip TEXT, event TEXT, status TEXT, detail TEXT)""")
con.executemany(
    "INSERT INTO events (ts,source,user,ip,event,status,detail) VALUES (?,?,?,?,?,?,?)", rows)
con.commit()
print(f"Wrote {len(rows)} events to {DB}")
con.close()