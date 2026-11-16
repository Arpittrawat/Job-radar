"""Local dashboard. Run: python3 server.py  then open http://localhost:8765"""
import json, os, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import db

HERE = os.path.dirname(__file__)

def query(p):
    g = lambda k: (p.get(k) or [""])[0]
    where, args = [], []
    tab = g("tab") or "new"
    if tab == "new": where.append("status='new'")
    elif tab == "applied": where.append("status='applied'")
    if g("all") != "1": where.append("tag!=''")          # default view = title matches only
    if g("tag"): where.append("tag=?"); args.append(g("tag"))
    if g("loc"): where.append("(','||location_group||',') LIKE ?"); args.append(f"%,{g('loc')},%")
    if g("source"): where.append("source=?"); args.append(g("source"))
    if g("q"): where.append("(lower(title) LIKE ? OR lower(company) LIKE ?)"); args += [f"%{g('q').lower()}%"] * 2
    sql = "SELECT * FROM jobs" + (" WHERE " + " AND ".join(where) if where else "") + \
          " ORDER BY COALESCE(posted_at, first_seen_at) DESC LIMIT 500"
    with db.conn() as c:
        jobs = [dict(r) for r in c.execute(sql, args)]
        counts = {k: c.execute(q).fetchone()[0] for k, q in {
            "new": "SELECT COUNT(*) FROM jobs WHERE status='new' AND tag!=''",
            "applied": "SELECT COUNT(*) FROM jobs WHERE status='applied'",
            "all": "SELECT COUNT(*) FROM jobs"}.items()}
        sources = [r[0] for r in c.execute("SELECT DISTINCT source FROM jobs ORDER BY 1")]
        tags = [r[0] for r in c.execute("SELECT DISTINCT tag FROM jobs WHERE tag!='' ORDER BY 1")]
        health = [dict(r) for r in c.execute(
            "SELECT source, MAX(ran_at) ran_at, ok, error FROM runs GROUP BY source")]
    return dict(jobs=jobs, counts=counts, sources=sources, tags=tags, health=health)

class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json", code=200):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/": self._send(open(os.path.join(HERE, "dashboard.html"), "rb").read(), "text/html; charset=utf-8")
        elif u.path == "/api/jobs": self._send(json.dumps(query(parse_qs(u.query))))
        else: self._send("not found", "text/plain", 404)

    def do_POST(self):
        if urlparse(self.path).path == "/api/status":
            d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if d.get("status") in ("new", "applied"):
                with db.conn() as c: c.execute("UPDATE jobs SET status=? WHERE id=?", (d["status"], int(d["id"])))
                return self._send('{"ok":true}')
        self._send('{"ok":false}', code=400)

    def log_message(self, *a): pass

if __name__ == "__main__":
    db.init()
    srv = HTTPServer(("127.0.0.1", 8765), H)
    print("Dashboard: http://localhost:8765  (Ctrl+C to stop)")
    try: webbrowser.open("http://localhost:8765")
    except Exception: pass
    srv.serve_forever()
