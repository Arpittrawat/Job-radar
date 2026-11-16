"""Job details for the dashboard: description, founders / hiring manager / HR, LinkedIn links, emails in the post,
and two estimates per person: how much an email would help ("need") and how likely an email can be found ("exists").
Runs after scraping, only for new matching jobs. Stored in radar.db table `details`; exported to docs/d/<job id>.json."""
import re, json, html, time, urllib.request, urllib.parse
from datetime import datetime, timezone
import db

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD_EMAIL = re.compile(r"(example\.com|sentry|wixpress|\.png|\.jpg|noreply|no-reply)", re.I)

def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), r.geturl()

def html_to_text(s, limit=6000):
    if not s:
        return ""
    s = html.unescape(s) if "&lt;" in s else s
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n• ", s)
    s = re.sub(r"(?i)<(br|/p|/div|/h\d|/ul|/ol|p|h\d)[^>]*>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return "\n".join(l.strip() for l in s.split("\n")).strip()[:limit]

def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)

def _json_blobs(page):
    """Embedded JSON on the page: Inertia data-page, Next.js __NEXT_DATA__, JSON-LD."""
    out = []
    for m in re.finditer(r'data-page="([^"]+)"', page):
        try: out.append(json.loads(html.unescape(m.group(1))))
        except Exception: pass
    for m in re.finditer(r'<script[^>]*(?:id="__NEXT_DATA__"|type="application/(?:ld\+)?json")[^>]*>(.*?)</script>', page, re.S):
        try: out.append(json.loads(m.group(1)))
        except Exception: pass
    return out

def parse_yc(page):
    """YC company or job page -> founders, company facts, description."""
    founders, company, desc = [], {}, ""
    for blob in _json_blobs(page):
        for d in _walk(blob):
            is_person = "team_size" not in d and "batch_name" not in d and (
                "full_name" in d or "founder_bio" in d or "/in/" in str(d.get("linkedin_url") or ""))
            name = d.get("full_name") or d.get("name") if is_person else None
            if name and isinstance(name, str) and len(name) < 60:
                f = dict(name=name.strip(), title=(d.get("title") or "Founder"), linkedin=d.get("linkedin_url") or "",
                         twitter=d.get("twitter_url") or "")
                if f["name"] not in [x["name"] for x in founders]:
                    founders.append(f)
            if "team_size" in d and not company.get("team_size"):
                company.update(team_size=d.get("team_size"), website=d.get("website") or d.get("url") or "",
                               batch=d.get("batch_name") or d.get("batch") or "", name=d.get("name") or "",
                               linkedin=d.get("linkedin_url") or "")
            for k in ("description", "job_description", "descriptionHtml"):
                v = d.get(k)
                if isinstance(v, str) and len(v) > len(desc) and len(v) > 200:
                    desc = v
    if not founders:  # HTML fallback: LinkedIn profile links on the page
        for m in re.finditer(r'href="(https?://(?:www\.)?linkedin\.com/in/[^"?#]+)"', page):
            founders.append(dict(name="", title="Founder", linkedin=m.group(1), twitter=""))
            if len(founders) >= 4:
                break
    if not desc:
        m = re.search(r'<div[^>]+class="[^"]*prose[^"]*"[^>]*>(.*?)</div>\s*</div>', page, re.S)
        desc = m.group(1) if m else ""
    try:
        company["team_size"] = int(company.get("team_size")) if company.get("team_size") not in (None, "") else None
    except (TypeError, ValueError):
        company["team_size"] = None
    return founders, company, html_to_text(desc)

def parse_generic(page):
    """Any job page (ATS like Greenhouse / Lever / Ashby): JSON-LD JobPosting, else meta description."""
    desc, site = "", ""
    for blob in _json_blobs(page):
        for d in _walk(blob):
            if d.get("@type") == "JobPosting" or ("description" in d and "hiringOrganization" in d):
                desc = d.get("description") or desc
                org = d.get("hiringOrganization") or {}
                if isinstance(org, dict):
                    site = org.get("sameAs") or org.get("url") or site
    if not desc:
        m = re.search(r'<meta[^>]+(?:name|property)="(?:og:)?description"[^>]+content="([^"]+)"', page)
        desc = m.group(1) if m else ""
    return html_to_text(desc), site if isinstance(site, str) else ""

def hn_text(item_id):
    raw, _ = _get(f"https://hn.algolia.com/api/v1/items/{item_id}")
    return html_to_text(json.loads(raw).get("text") or "")

# ---------- people + estimates ----------
MANAGER_QUERY = {"marketing": "head of marketing", "gtm engineer": "head of growth", "growth engineer": "head of growth",
                 "growth associate": "head of growth", "founder's office": "chief of staff", "marketing ops": "marketing operations",
                 "technical marketer": "product marketing", "solutions engineer": "head of solutions", "fde": "head of engineering"}

def li_search(company, words):
    return "https://www.linkedin.com/search/results/people/?" + urllib.parse.urlencode({"keywords": f"{company} {words}"})

def score(job, company, emails_in_post):
    """Overall: how much a direct email raises the odds versus only applying. Returns (pct, reasons)."""
    t, pct, why = company.get("team_size"), 55, []
    if t:
        if t <= 10: pct += 30; why.append(f"Tiny team ({t} people): founders read every email")
        elif t <= 25: pct += 20; why.append(f"Small team ({t} people): founders still hire directly")
        elif t <= 60: pct += 8; why.append(f"Growing team ({t} people)")
        elif t <= 200: pct -= 5; why.append(f"Mid-size team ({t} people): a hiring manager owns this role")
        else: pct -= 25; why.append(f"Large company ({t} people): recruiters screen first")
    if job["source"] == "hn": pct += 15; why.append("Posted by the team on Hacker News: replies go to real people")
    elif job["source"] == "yc": pct += 8; why.append("Early-stage YC company")
    if emails_in_post: pct += 10; why.append("The post itself asks you to email")
    try:
        days = (datetime.now(timezone.utc) - datetime.fromisoformat(job["posted_at"])).days if job.get("posted_at") else 0
    except Exception:
        days = 0
    if days >= 4: pct += 8; why.append(f"Posted {days} days ago: the applicant pile is growing")
    return max(5, min(95, pct)), why

def build_people(job, founders, company, emails_in_post, need):
    t, site, name = company.get("team_size"), company.get("website"), job["company"]
    people = []
    for e in emails_in_post[:3]:
        people.append(dict(role="From the post", name=e, title="Email listed in the job post", email=e,
                           need=min(95, need + 5), exists=100, linkedin="", search=""))
    for f in founders[:4]:
        ex = 85 if (f.get("linkedin") and site) else 70 if site else 45
        people.append(dict(role="Founder", name=f.get("name") or "Founder", title=f.get("title") or "Founder",
                           linkedin=f.get("linkedin", ""), twitter=f.get("twitter", ""), email="",
                           need=max(5, need - (20 if (t or 0) > 200 else 0)), exists=ex, search=""))
    if not founders:
        people.append(dict(role="Founder", name="Founders", title=f"Search {name} founders on LinkedIn", linkedin="",
                           search=li_search(name, "founder"), email="", need=need, exists=65 if site else 40))
    if t is None or t > 25:
        q = MANAGER_QUERY.get((job.get("tag") or "").lower(), "head of")
        people.append(dict(role="Hiring manager", name="Hiring manager", title=f"Likely the {q} at {name}", linkedin="",
                           search=li_search(name, q), email="", need=max(5, need - 5), exists=60 if site else 35))
    if t is None or t > 50 or job["source"] in ("a16z", "trueup"):
        people.append(dict(role="HR", name="Recruiter", title=f"Recruiter or talent team at {name}", linkedin="",
                           search=li_search(name, "recruiter talent"), email="", need=max(5, need - 30), exists=55 if site else 30))
    return people

def enrich_job(job):
    founders, company, desc, site = [], {}, "", ""
    if job["source"] == "yc":
        page, _ = _get(job["url"])
        founders, company, desc = parse_yc(page)
        if not founders or not company:
            m = re.search(r"(https://www\.ycombinator\.com/companies/[^/]+)", job["url"])
            if m:
                time.sleep(0.7)
                cp, _ = _get(m.group(1))
                f2, c2, d2 = parse_yc(cp)
                founders = founders or f2
                company = {**c2, **{k: v for k, v in company.items() if v}}
                company["yc_url"] = m.group(1)
    elif job["source"] == "hn":
        desc = hn_text(job["external_id"])
    elif job["source"] != "trueup":
        page, final = _get(job["url"])
        desc, site = parse_generic(page)
        company["website"] = site
    company.setdefault("website", site)
    company.setdefault("team_size", None)
    emails = [e for e in dict.fromkeys(EMAIL.findall(desc)) if not BAD_EMAIL.search(e)]
    need, why = score(job, company, emails)
    people = build_people(job, founders, company, emails, need)
    return dict(description=desc, company=company, people=people, need=need, why=why,
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))

def init():
    with db.conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS details (job_id INTEGER PRIMARY KEY, data TEXT, ok INTEGER, error TEXT, fetched_at TEXT)")

def run(limit=40):
    """Enrich new matching jobs that have no details yet (newest first)."""
    init()
    with db.conn() as c:
        rows = [dict(r) for r in c.execute(
            """SELECT j.* FROM jobs j LEFT JOIN details d ON d.job_id=j.id
               WHERE d.job_id IS NULL AND j.status='new' AND j.tag!=''
               ORDER BY COALESCE(j.posted_at, j.first_seen_at) DESC LIMIT ?""", (limit,))]
    ok = bad = 0
    for j in rows:
        try:
            data = enrich_job(j); ok += 1; err = ""
        except Exception as e:
            data = dict(description="", company={}, people=[], need=None, why=[], error=f"{type(e).__name__}: {e}"); bad += 1; err = data["error"]
        with db.conn() as c:
            c.execute("INSERT OR REPLACE INTO details (job_id,data,ok,error,fetched_at) VALUES (?,?,?,?,?)",
                      (j["id"], json.dumps(data), int(not err), err[:300], datetime.now(timezone.utc).isoformat(timespec="seconds")))
        time.sleep(0.8)
    print(f"[details] {ok} enriched, {bad} failed")
