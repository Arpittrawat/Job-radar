"""Writes docs/jobs.json from radar.db. The cloud dashboard (docs/index.html) reads this file."""
import json, os, re, urllib.parse
from datetime import datetime, timezone, timedelta
import db

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "jobs.json")
HERE = os.path.dirname(os.path.abspath(__file__))
# Dashboard shows only jobs first seen on/after this moment. Older jobs stay in radar.db
# (so they never come back as "new") but are hidden.
# config.json "show_from" is the one place to change this; the default below is only used if it's missing.
DEFAULT_SHOW_FROM = "2026-11-14T00:00:00+05:30"

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

MAX_TAGGED = 5000   # safety cap; matching jobs are never pushed out by other titles
MAX_OTHER = 1000    # jobs that don't match your roles ("Show other titles")

def select_jobs(rows):
    """rows newest first. All matching jobs first, then up to MAX_OTHER others; result stays newest first."""
    tagged = [r for r in rows if r["tag"]][:MAX_TAGGED]
    other = [r for r in rows if not r["tag"]][:MAX_OTHER]
    keep = {id(r) for r in tagged + other}
    for r in rows:
        r["url"] = db.safe_url(r.get("url"))
    return [r for r in rows if id(r) in keep]

def main():
    db.init()
    with db.conn() as c:
        cut = show_from()
        rows = [{k: r[k] for k in FIELDS} for r in c.execute(
            "SELECT * FROM jobs ORDER BY COALESCE(posted_at, first_seen_at) DESC")
            if (_dt(r["first_seen_at"]) or cut) >= cut and not r["possible_dupe_of"]]
        jobs = select_jobs(rows)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='details'").fetchone():
            det = {r["job_id"]: r["data"] for r in c.execute("SELECT job_id, data FROM details")}
            for j in jobs:
                if j["id"] in det:
                    try:
                        j["d"] = json.loads(det[j["id"]])
                    except Exception:
                        pass
        allh = [dict(r) for r in c.execute(
            "SELECT source, MAX(ran_at) ran_at, ok, error FROM runs GROUP BY source")]
        health = [h for h in allh if not h["source"].startswith("f:")]
        fhealth = [dict(h, source=h["source"][2:]) for h in allh if h["source"].startswith("f:")]
        funding = []
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='funding'").fetchone():
            since = (datetime.now(timezone.utc) - timedelta(days=21)).isoformat(timespec="seconds")
            funding = [dict(r) for r in c.execute(
                """SELECT * FROM funding WHERE COALESCE(published_at, first_seen_at) >= ?
                   ORDER BY COALESCE(published_at, first_seen_at) DESC LIMIT 400""", (since,))]
            import funding as _f
            seen, uniq, seen_amt = set(), [], []
            for r in funding:  # drop repeats of the same company and generic headlines stored by older versions
                for col in ("dedupe_key", "enriched_at", "website"):
                    r.pop(col, None)
                try:
                    r["founders"] = [n if isinstance(n, str) else n.get("name", "") for n in json.loads(r.get("founders") or "[]")]
                    r["founders"] = [n for n in r["founders"] if n][:4]
                except Exception:
                    r["founders"] = []
                r["url"] = db.safe_url(r.get("url"))
                r["company"] = _f.clean_name(r["company"]) or r["company"]
                k = _f.norm_company(r["company"])
                # same company written two ways (e.g. "Morgan" / "Morgan Health") with the same amount = same story
                near = any((k.startswith(s) or s.startswith(k)) and min(len(k), len(s)) >= 4 and amt == (r["amount"] or "")
                           for s, amt in seen_amt)
                if k in seen or near or _f.GENERIC.search(r["company"]):
                    continue
                seen.add(k); seen_amt.append((k, r["amount"] or "")); uniq.append(r)
            funding = uniq
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "show_from": cut.isoformat(timespec="seconds"),
                   "jobs": jobs, "health": health, "funding": funding, "funding_health": fhealth}, f, separators=(",", ":"))
    print(f"exported {len(funding)} funding stories")
    print(f"exported {len(jobs)} jobs (first seen since {cut.isoformat()}) -> docs/jobs.json")

if __name__ == "__main__":
    main()
