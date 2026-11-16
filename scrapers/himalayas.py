"""Himalayas public jobs API (newest first)."""
from datetime import datetime, timezone
from scrapers._http import get_json, pause

def _iso(v):
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            v = int(v); v = v / 1000 if v > 1e12 else v
            return datetime.fromtimestamp(v, tz=timezone.utc).isoformat(timespec="seconds")
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None

def fetch():
    jobs = []
    for off in (0, 20, 40, 60, 80):
        data = get_json(f"https://himalayas.app/jobs/api?limit=20&offset={off}")
        for j in data.get("jobs", []):
            locs = j.get("locationRestrictions") or []
            jobs.append(dict(source="himalayas", external_id=str(j.get("guid") or j.get("applicationLink") or j.get("title")),
                             company=j.get("companyName") or "Unknown", title=j.get("title", ""),
                             location="Remote" + (f" ({', '.join(locs[:3])})" if locs else ""),
                             url=j.get("applicationLink") or j.get("guid") or "", posted_at=_iso(j.get("pubDate"))))
        pause(0.8)
    return jobs
