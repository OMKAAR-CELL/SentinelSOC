import os, sqlite3

DB = os.path.join(os.path.dirname(__file__), "..", "data", "logs.db")
BLOCKLIST = os.path.join(os.path.dirname(__file__), "..", "data", "blocklist.txt")

def _q(sql, params=()):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows

def find_failed_login_spikes(min_count: int = 10) -> list:
    """Find IP and username pairs with many failed logins. Use this first to spot brute-force attacks."""
    return _q("""SELECT ip, user, COUNT(*) AS failed, MIN(ts) AS first_seen, MAX(ts) AS last_seen
                 FROM events WHERE event='login' AND status='failed'
                 GROUP BY ip, user HAVING failed >= ? ORDER BY failed DESC""", (min_count,))

def search_logs(ip: str = "", user: str = "", source: str = "", status: str = "",
                start: str = "", end: str = "", limit: int = 25) -> list:
    """Search log events. Filters are optional. source is auth, web or db. start and end are ISO times like 2026-10-12T02:00:00. Returns at most limit rows."""
    sql, p = "SELECT id, ts, source, user, ip, event, status, detail FROM events WHERE 1=1", []
    for col, val in (("ip", ip), ("user", user), ("source", source), ("status", status)):
        if val:
            sql += f" AND {col}=?"; p.append(val)
    if start:
        sql += " AND ts>=?"; p.append(start)
    if end:
        sql += " AND ts<=?"; p.append(end)
    sql += " ORDER BY ts LIMIT ?"; p.append(min(int(limit), 50))
    return _q(sql, tuple(p))

def get_user_timeline(user: str, start: str = "", end: str = "") -> list:
    """Get a user's important events: logins, db queries and exports, in time order (max 40)."""
    sql, p = "SELECT id, ts, source, ip, event, status, detail FROM events WHERE user=? AND (event!='GET' OR detail LIKE '/admin%')", [user]
    if start:
        sql += " AND ts>=?"; p.append(start)
    if end:
        sql += " AND ts<=?"; p.append(end)
    sql += " AND NOT (event='login' AND status='failed') ORDER BY ts LIMIT 40"
    return _q(sql, tuple(p))

REPUTATION = {
    "185.220.101.45": {"reputation": "malicious", "note": "Known Tor exit node, reported for brute force"},
}

def check_ip_reputation(ip: str) -> dict:
    """Check whether an IP address is known to be malicious."""
    return REPUTATION.get(ip, {"reputation": "unknown", "note": "No reports found"})

def block_ip(ip: str) -> dict:
    """Blocks an IP. Called only after human approval, never by the agent."""
    with open(BLOCKLIST, "a") as f:
        f.write(ip + "\n")
    return {"blocked": ip}