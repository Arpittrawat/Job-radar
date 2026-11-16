"""Writes docs/jobs.json from radar.db. The cloud dashboard (docs/index.html) reads this file."""
import json, os, re, urllib.parse
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
            if (_dt(r["first_seen_at"]) or cut) >= cut and not r["possible_dupe_of"]][:3000]
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
            # founders already known from YC job pages (real LinkedIn profiles), keyed by company
            yc_founders = {}
            for j in jobs:
                for p in (j.get("d") or {}).get("people", []):
                    if p.get("role") == "Founder" and p.get("linkedin"):
                        yc_founders.setdefault(_f.norm_company(re.sub(r"\s*\([A-Z]\d{2}\)$", "", j["company"])), []).append(
                            dict(name=p["name"], title=p.get("title", ""), linkedin=p["linkedin"]))
            seen, uniq = set(), []
            for r in funding:  # drop repeats of the same company and generic headlines stored by older versions
                r.pop("dedupe_key", None)
                r["company"] = _f.clean_name(r["company"]) or r["company"]
                try:
                    names = json.loads(r.get("founders") or "[]")
                except Exception:
                    names = []
                r["founders"] = yc_founders.get(_f.norm_company(r["company"])) or [
                    dict(name=n, title="Founder", linkedin="", search="https://www.linkedin.com/search/results/people/?"
                         + urllib.parse.urlencode({"keywords": f"{n} {r['company']}"})) for n in names]
                r["founders_search"] = "https://www.linkedin.com/search/results/people/?" + urllib.parse.urlencode({"keywords": f"{r['company']} founder"})
                k = _f.norm_company(r["company"])
                if k in seen or _f.GENERIC.search(r["company"]):
                    continue
                seen.add(k); uniq.append(r)
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
