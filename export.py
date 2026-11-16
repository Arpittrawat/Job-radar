"""Writes docs/jobs.json from radar.db. The cloud dashboard (docs/index.html) reads this file."""
import json, os
from datetime import datetime, timezone
import db

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "jobs.json")
FIELDS = ["id", "source", "company", "title", "location", "url", "posted_at",
          "first_seen_at", "tag", "location_group", "status", "possible_dupe_of"]

def main():
    db.init()
    with db.conn() as c:
        jobs = [{k: r[k] for k in FIELDS} for r in c.execute(
            "SELECT * FROM jobs ORDER BY COALESCE(posted_at, first_seen_at) DESC LIMIT 3000")]
        health = [dict(r) for r in c.execute(
            "SELECT source, MAX(ran_at) ran_at, ok, error FROM runs GROUP BY source")]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "jobs": jobs, "health": health}, f, separators=(",", ":"))
    print(f"exported {len(jobs)} jobs -> docs/jobs.json")

if __name__ == "__main__":
    main()
