"""VC portfolio job boards. Most run on Consider (same layout as jobs.a16z.com) or Getro (Next.js JSON).
One dashboard source ("vc"); boards that fail are listed in the error but don't stop the others."""
import re, json, html
from datetime import datetime, timezone
from scrapers._http import get, pause
from scrapers import a16z

BOARDS = {
    "Sequoia": "https://jobs.sequoiacap.com", "Accel": "https://jobs.accel.com", "Lightspeed": "https://jobs.lsvp.com",
    "Greylock": "https://jobs.greylock.com", "Khosla": "https://jobs.khoslaventures.com", "First Round": "https://jobs.firstround.com",
    "GV": "https://jobs.gv.com", "Insight": "https://jobs.insightpartners.com", "Menlo": "https://jobs.menlovc.com",
    "Battery": "https://jobs.battery.com", "NEA": "https://careers.nea.com", "Techstars": "https://jobs.techstars.com",
    "Peak XV": "https://careers.peakxv.com", "Blume": "https://jobs.blume.vc",
}

def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)

def _iso(v):
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            v = int(v); v = v / 1000 if v > 1e12 else v
            return datetime.fromtimestamp(v, tz=timezone.utc).isoformat(timespec="seconds")
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None

def parse_getro(page, base, vc):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    data, jobs, seen = json.loads(m.group(1)), [], set()
    for d in _walk(data):
        org = d.get("organization")
        if isinstance(org, dict) and d.get("title") and (d.get("url") or d.get("slug")):
            jid = str(d.get("id") or d.get("slug") or d.get("url"))
            if jid in seen:
                continue
            seen.add(jid)
            locs = d.get("locations") or d.get("searchableLocations") or []
            loc = ", ".join(l if isinstance(l, str) else (l.get("name") or "") for l in locs[:3]) if isinstance(locs, list) else str(locs)
            url = d.get("url") or f"{base}/companies/{org.get('slug','')}/jobs/{d.get('slug')}"
            jobs.append(dict(source="vc", external_id=f"{vc}:{jid}", company=org.get("name") or "Unknown", title=d["title"],
                             location=loc, url=url, posted_at=_iso(d.get("createdAt") or d.get("created_at") or d.get("postedAt")),
                             tag_hint=""))
    return jobs

def fetch():
    jobs, errors, ok = [], [], 0
    for vc, base in BOARDS.items():
        try:
            page = get(base + "/jobs")
            found = parse_getro(page, base, vc)
            if not found:  # Consider layout (same as a16z)
                found = [dict(j, source="vc", external_id=f"{vc}:{j['external_id']}",
                              url=j["url"].replace(a16z.BASE, base)) for j in a16z.parse_page(page)]
            if not found:
                errors.append(f"{vc}: 0 jobs parsed")
            else:
                ok += 1
            jobs += found
        except Exception as e:
            errors.append(f"{vc}: {type(e).__name__}")
        pause(1)
    if ok == 0:
        raise RuntimeError("; ".join(errors) or "no boards worked")
    if errors:
        print("[vc] partial:", "; ".join(errors))
    return jobs
