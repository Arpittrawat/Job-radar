"""Writes docs/jobs.json from radar.db. The cloud dashboard (docs/index.html) reads this file."""
import json, os
from datetime import datetime, timezone, timedelta
import db

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "jobs.json")
HERE = os.path.dirname(os.path.abspath(__file__))
# Dashboard shows only jobs first seen on/after this moment. Older jobs stay in radar.db
# (so they never come back as "new") but are hidden. Override with "show_from" in config.json.
DEFAULT_SHOW_FROM = "2026-11-17T00:00:00+05:30"

def show_from():
    try:
        v = json.load(open(os.path.join(HERE, "config.json"))).get("show_from") or DEFAULT_SHOW_FROM
    except Exception:
        v = DEFAULT_SHOW_FROM
    return datetime.fromisoformat(v).astimezone(timezone.utc)

def _dt(s):
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None

FIELDS = ["id", "source", "company", "title", "location", "url", "posted_at",
          "first_seen_at", "tag", "location_group", "status", "possible_dupe_of"]

def main():
    db.init()
    with db.conn() as c:
        cut = show_from()
        jobs = [{k: r[k] for k in FIELDS} for r in c.execute(
            "SELECT * FROM jobs ORDER BY COALESCE(posted_at, first_seen_at) DESC")
            if (_dt(r["first_seen_at"]) or cut) >= cut][:3000]
        allh = [dict(r) for r in c.execute(
            "SELECT source, MAX(ran_at) ran_at, ok, error FROM runs GROUP BY source")]
        health = [h for h in allh if not h["source"].startswith("f:")]
        fhealth = [dict(h, source=h["source"][2:]) for h in allh if h["source"].startswith("f:")]
        funding = []
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='funding'").fetchone():
            since = (datetime.now(timezone.utc) - timedelta(days=21)).isoformat(timespec="seconds")
            funding = [dict(r) for r in c.execute(
                """SELECT id, company, amount, amount_usd, round, region, headline, url, source, published_at, first_seen_at, website
                   FROM funding WHERE COALESCE(published_at, first_seen_at) >= ?
                   ORDER BY COALESCE(published_at, first_seen_at) DESC LIMIT 400""", (since,))]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "show_from": cut.isoformat(timespec="seconds"),
                   "jobs": jobs, "health": health, "funding": funding, "funding_health": fhealth}, f, separators=(",", ":"))
    print(f"exported {len(funding)} funding stories")
    print(f"exported {len(jobs)} jobs (first seen since {cut.isoformat()}) -> docs/jobs.json")

if __name__ == "__main__":
    main()
