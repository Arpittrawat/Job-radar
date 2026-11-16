"""YC jobs from public role/location pages on ycombinator.com (server-rendered, no login).
Each page shows only the ~30 newest jobs, so we read several pages."""
import re, html, time, urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://www.ycombinator.com"
# (path, tag_hint). Marketing pages: every job is a marketing job, so hint 'Marketing'.
PAGES = [
    ("/jobs/role/marketing", "Marketing"),
    ("/jobs/role/marketing/remote", "Marketing"),
    ("/jobs/role/marketing/india", "Marketing"),
    ("/jobs/role/software-engineer", ""),   # FDE, growth/solutions engineer
    ("/jobs/role/sales-manager", ""),       # solutions engineer, GTM
    ("/jobs/role/operations", ""),          # marketing ops, founder's office
    ("/jobs/location/india", ""),
]
UA = {"User-Agent": "Mozilla/5.0 (job-radar personal use)"}
JOB_A = re.compile(r'<a\b[^>]*href="(?:https://www\.ycombinator\.com)?(/companies/([^/"]+)/jobs/([A-Za-z0-9]+)-[^"]*)"[^>]*>(.*?)</a>', re.S)

def _text(fragment):
    t = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"[ \t\r\f\v]+", " ", t).strip()

def ago_to_dt(s, now):
    """'2 days ago', 'about 1 month ago', '1 day ago', 'about 5 hours ago' -> datetime (approx)."""
    m = re.search(r"(\d+|an?|one)\s+(minute|hour|day|week|month|year)s?\s+ago", s or "", re.I)
    if not m:
        return None
    n = 1 if m.group(1).lower() in ("a", "an", "one") else int(m.group(1))
    unit = {"minute": 1/1440, "hour": 1/24, "day": 1, "week": 7, "month": 30, "year": 365}[m.group(2).lower()]
    return now - timedelta(days=n * unit)

SALARY = re.compile(r"[$₹€£]|hourly|monthly|yearly|\d\s?[KM]\b|^\W*(full-time|part-time|contract|internship)\W*$", re.I)

def _company(slug, before, batch):
    """Company name: words just before the '(W21)' batch tag that spell the URL slug; fallback = slug in Title Case."""
    key = re.sub(r"[^a-z0-9]", "", re.sub(r"-\d+$", "", slug.lower()))
    for m in re.finditer(r"([^()\n]{1,120}?)\s*\(([WSFXP]\d{2})\)", before):
        words = m.group(1).split()
        for k in range(1, min(6, len(words)) + 1):
            cand = " ".join(words[-k:])
            if re.sub(r"[^a-z0-9]", "", cand.lower()) == key:
                return f"{cand} ({m.group(2)})"
    name = re.sub(r"-\d+$", "", slug).replace("-", " ").title()
    return f"{name} ({batch[-1].split('(')[-1]}" if batch else name

def parse_page(page_html, tag_hint="", now=None):
    now = now or datetime.now(timezone.utc)
    anchors = list(JOB_A.finditer(page_html))
    jobs = []
    for i, a in enumerate(anchors):
        path, slug, jid, title_html = a.group(1), a.group(2), a.group(3), a.group(4)
        title = _text(title_html)
        if not title:
            continue
        prev_end = anchors[i - 1].end() if i else max(0, a.start() - 1500)
        before = _text(page_html[prev_end:a.start()])
        before = before.rsplit("Apply", 1)[-1]                      # drop previous card's tail
        ago = re.findall(r"((?:about\s+|over\s+|almost\s+)?(?:\d+|an?|one)\s+(?:minute|hour|day|week|month|year)s?\s+ago)", before, re.I)
        batch = re.findall(r"([^\n•]{1,60}?\([WSFXP]\d{2}\))", before)
        company = _company(slug, before, batch)
        nxt = anchors[i + 1].start() if i + 1 < len(anchors) else a.end() + 1500
        after = _text(page_html[a.end():min(nxt, a.end() + 1500)]).split("Apply", 1)[0]
        parts = [p.strip() for p in after.split("•") if p.strip()]
        loc = ""
        if len(parts) >= 3 and not SALARY.search(parts[-1]):
            loc = parts[-1][:160]
        hint = "Marketing" if any(p.lower() == "marketing" for p in parts[:-1]) else ""
        dt = ago_to_dt(ago[-1], now) if ago else None
        jobs.append(dict(source="yc", external_id=jid, company=company, title=title, location=loc,
                         url=BASE + path, tag_hint=hint,
                         posted_at=dt.isoformat(timespec="seconds") if dt else None))
    return jobs

def fetch():
    out, seen, errors = [], set(), []
    for path, hint in PAGES:
        try:
            req = urllib.request.Request(BASE + path, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                page = r.read().decode("utf-8", "replace")
            got = parse_page(page, hint)
            if not got:
                errors.append(f"{path}: 0 jobs parsed (page layout may have changed)")
            for j in got:
                if j["external_id"] not in seen:
                    seen.add(j["external_id"]); out.append(j)
        except Exception as e:
            errors.append(f"{path}: {type(e).__name__}: {e}")
        time.sleep(1)
    for e in errors:
        print("   [yc] warning:", e)
    if not out:
        raise RuntimeError("no YC jobs parsed from any page: " + "; ".join(errors)[:300])
    return out
