"""Remotive official API. Pulls categories that match the target roles."""
from datetime import datetime, timezone
from scrapers._http import get_json, pause

CATS = ["marketing", "sales-business", "customer-support", "product"]

def _iso(s):
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat(timespec="seconds")
    except Exception:
        return None

def fetch():
    jobs, seen = [], set()
    for c in CATS:
        for j in get_json(f"https://remotive.com/api/remote-jobs?category={c}&limit=100").get("jobs", []):
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            jobs.append(dict(source="remotive", external_id=str(j["id"]), company=j.get("company_name") or "Unknown",
                             title=j.get("title", ""), location="Remote" + (f" ({j['candidate_required_location']})" if j.get("candidate_required_location") else ""),
                             url=j.get("url", ""), posted_at=_iso(j.get("publication_date") or "")))
        pause(1)
    return jobs
