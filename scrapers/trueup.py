"""Lenny's Jobs board (lenny.trueup.io, data by TrueUp). Each category page embeds its first 15 jobs as JSON (__NEXT_DATA__).
Covers the Growth and FDE categories. Only 15 per page: best-effort, not a full feed.
Job links go to the company's TrueUp jobs list (the page data has no direct job URL)."""
import re, json, time, urllib.request

BASE = "https://lenny.trueup.io"
PAGES = [("/jobs/growth", "Marketing"), ("/jobs/fde", "FDE")]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def _find_hits(o):
    """Find the first list of job dicts (have job_id + title) anywhere in the page JSON."""
    if isinstance(o, list):
        if o and isinstance(o[0], dict) and "job_id" in o[0] and "title" in o[0]:
            return o
        for x in o:
            r = _find_hits(x)
            if r: return r
    elif isinstance(o, dict):
        for v in o.values():
            r = _find_hits(v)
            if r: return r
    return []

def parse_page(page, tag_hint=""):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    hits = _find_hits(json.loads(m.group(1)))
    jobs = []
    for h in hits:
        if not h.get("job_id") or not h.get("title"):
            continue
        jobs.append(dict(source="trueup", external_id=str(h["job_id"]), company=h.get("company_name") or "",
                         title=h["title"], location=h.get("location") or "",
                         url=f"https://www.trueup.io/co/{h.get('company_id')}/jobs",
                         tag_hint=tag_hint, posted_at=(h.get("updated_at") or "").split(".")[0] + "Z" if h.get("updated_at") else None))
    return jobs

def fetch():
    out, seen, errors = [], set(), []
    for path, hint in PAGES:
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=UA), timeout=30) as r:
                page = r.read().decode("utf-8", "replace")
            got = parse_page(page, hint)
            if not got:
                errors.append(f"{path}: 0 jobs parsed (page layout may have changed or request blocked)")
            for j in got:
                if j["external_id"] not in seen:
                    seen.add(j["external_id"]); out.append(j)
        except Exception as e:
            errors.append(f"{path}: {type(e).__name__}: {e}")
        time.sleep(1)
    for e in errors:
        print("   [trueup] warning:", e)
    if not out:
        raise RuntimeError("no TrueUp jobs parsed: " + "; ".join(errors)[:300])
    return out
