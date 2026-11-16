"""Company career pages, read through the official public job-board APIs of Ashby, Greenhouse, Lever and Workable.
Watchlist = companies from the Funding tab + companies already seen in matching jobs + config.json "watch".
For each new company we try a few likely board names once (cached in radar.db table ats_map), then read its jobs every run."""
import re, json, os, urllib.error
from datetime import datetime, timezone, timedelta
from scrapers._http import get_json, pause
import db

PROBE_PER_RUN = 20          # new companies checked per run (each costs a few quick requests)
RECHECK_DAYS = 21           # companies with no board found are retried after this

def _iso(v):
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            v = int(v); v = v / 1000 if v > 1e12 else v
            return datetime.fromtimestamp(v, tz=timezone.utc).isoformat(timespec="seconds")
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None

def board_jobs(provider, token, company):
    out = []
    if provider == "ashby":
        for j in get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}").get("jobs", []):
            if j.get("isListed") is False:
                continue
            out.append(dict(external_id=f"ashby:{token}:{j.get('id')}", title=j.get("title", ""), location=j.get("location") or ("Remote" if j.get("isRemote") else ""),
                            url=j.get("jobUrl", ""), posted_at=_iso(j.get("publishedAt"))))
    elif provider == "greenhouse":
        for j in get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs").get("jobs", []):
            out.append(dict(external_id=f"gh:{token}:{j.get('id')}", title=j.get("title", ""), location=(j.get("location") or {}).get("name", ""),
                            url=j.get("absolute_url", ""), posted_at=_iso(j.get("first_published") or j.get("updated_at"))))
    elif provider == "lever":
        for j in get_json(f"https://api.lever.co/v0/postings/{token}?mode=json"):
            out.append(dict(external_id=f"lever:{token}:{j.get('id')}", title=j.get("text", ""), location=(j.get("categories") or {}).get("location", ""),
                            url=j.get("hostedUrl", ""), posted_at=_iso(j.get("createdAt"))))
    elif provider == "workable":
        for j in get_json(f"https://apply.workable.com/api/v1/widget/accounts/{token}").get("jobs", []):
            loc = ", ".join(x for x in [j.get("city"), j.get("country")] if x) or ("Remote" if j.get("telecommuting") else "")
            out.append(dict(external_id=f"workable:{token}:{j.get('shortcode')}", title=j.get("title", ""), location=loc,
                            url=j.get("url") or f"https://apply.workable.com/{token}/j/{j.get('shortcode')}/", posted_at=_iso(j.get("published_on"))))
    for j in out:
        j.update(source="ats", company=company)
    return out

def candidates(name, website=""):
    c = []
    if website:
        host = re.sub(r"^https?://(www\.)?", "", website).split("/")[0]
        c.append(host.split(".")[0])
    base = re.sub(r"\(.*?\)", "", name).strip().lower()
    c += [re.sub(r"[^a-z0-9]", "", base), re.sub(r"[^a-z0-9]+", "-", base).strip("-")]
    words = re.findall(r"[a-z0-9]+", base)
    if words and words[-1] in ("ai", "labs", "inc", "hq", "app"):
        c.append("".join(words[:-1]))
    return [x for x in dict.fromkeys(c) if len(x) >= 3][:3]

def probe(name, website):
    for tok in candidates(name, website):
        for prov in ("ashby", "greenhouse", "lever", "workable"):
            try:
                jobs = board_jobs(prov, tok, name)
                pause(0.25)
                if jobs:
                    return prov, tok
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError, TypeError):
                pause(0.25)
                continue
    return None, None

def watchlist():
    with db.conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS ats_map (key TEXT PRIMARY KEY, name TEXT, website TEXT, provider TEXT, token TEXT, checked_at TEXT)")
        names = {}
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='funding'").fetchone():
            since = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
            for r in c.execute("SELECT company, website FROM funding WHERE first_seen_at>=?", (since,)):
                names[r[0]] = r[1] or ""
        since = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        for r in c.execute("SELECT DISTINCT company FROM jobs WHERE tag!='' AND source IN ('yc','a16z','hn','vc') AND first_seen_at>=?", (since,)):
            names.setdefault(re.sub(r"\s*\([A-Z]\d{2}\)\s*$", "", r[0]), "")
    try:
        cfg = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")))
        for w in cfg.get("watch", []):
            names.setdefault(w, "")
    except Exception:
        pass
    return {n: w for n, w in names.items() if n and n not in ("See post", "Unknown", "Stealth")}

def fetch():
    wl = watchlist()
    now = datetime.now(timezone.utc)
    retry_before = (now - timedelta(days=RECHECK_DAYS)).isoformat()
    probed = 0
    with db.conn() as c:
        known = {r["key"]: dict(r) for r in c.execute("SELECT * FROM ats_map")}
    for name, site in wl.items():
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        k = known.get(key)
        if k and (k["provider"] or k["checked_at"] > retry_before):
            continue
        if probed >= PROBE_PER_RUN:
            break
        probed += 1
        prov, tok = probe(name, site)
        with db.conn() as c:
            c.execute("INSERT OR REPLACE INTO ats_map (key,name,website,provider,token,checked_at) VALUES (?,?,?,?,?,?)",
                      (key, name, site, prov, tok, now.isoformat(timespec="seconds")))
    jobs, errs = [], 0
    with db.conn() as c:
        boards = [dict(r) for r in c.execute("SELECT name, provider, token FROM ats_map WHERE provider IS NOT NULL")]
    for b in boards:
        try:
            jobs += board_jobs(b["provider"], b["token"], b["name"])
        except Exception:
            errs += 1
        pause(0.4)
    print(f"[ats] watching {len(boards)} company boards ({probed} new companies checked, {errs} board errors)")
    return jobs
