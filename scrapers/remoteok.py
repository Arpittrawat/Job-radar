"""Remote OK official JSON feed (https://remoteok.com/api). First element is a legal notice."""
from datetime import datetime, timezone
from scrapers._http import get_json

def fetch():
    jobs = []
    for j in get_json("https://remoteok.com/api"):
        if not isinstance(j, dict) or not j.get("position"):
            continue
        ep = j.get("epoch")
        posted = datetime.fromtimestamp(int(ep), tz=timezone.utc).isoformat(timespec="seconds") if ep else j.get("date")
        jobs.append(dict(source="remoteok", external_id=str(j.get("id") or j.get("slug")), company=j.get("company") or "Unknown",
                         title=j["position"], location="Remote" + (f" ({j['location']})" if j.get("location") else ""),
                         url=j.get("url") or f"https://remoteok.com/remote-jobs/{j.get('id')}", posted_at=posted))
    return jobs
