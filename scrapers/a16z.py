"""a16z portfolio jobs (jobs.a16z.com). Pages are server-rendered <article> cards, 25 per page, with exact ISO timestamps.
/jobs is newest-first, so its 25 cards cover roughly the last 1-2 days. Search pages add role-specific coverage."""
import re, html, time, urllib.request, urllib.parse

BASE = "https://jobs.a16z.com"
QUERIES = ["", "marketing", "growth", "gtm", "forward deployed", "solutions engineer", "founder's office", "marketing operations"]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
ART = re.compile(r"<article\b.*?</article>", re.S)

def _text(s):
    s = re.sub(r"<svg.*?</svg>", "", s, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def parse_page(page, tag_hint=""):
    jobs = []
    for a in ART.findall(page):
        m = re.search(r'<h2.*?<a[^>]*href="(/jobs/([^/"]+)/([^"]+?))--[^"]*"[^>]*>(.*?)</a>', a, re.S)
        if not m:
            continue
        path_full = re.search(r'<h2.*?<a[^>]*href="([^"]+)"', a, re.S).group(1)
        slug, title = m.group(2), _text(m.group(4))
        ext_id = path_full.rsplit('/', 1)[-1]
        co = re.search(r'href="/jobs/%s"[^>]*>(.*?)</a>' % re.escape(slug), a, re.S)
        company = _text(co.group(1)) if co else slug.replace("-", " ").title()
        t = re.search(r'<time[^>]*dateTime="([^"]+)"', a)
        posted = t.group(1).replace(".000Z", "Z") if t else None
        if posted and "." in posted:
            posted = posted.split(".")[0] + "Z"
        # meta line: [salary ·] location · Posted X ago
        meta = re.search(r"</h2>(.*?)<time", a, re.S)
        parts = [p.strip() for p in _text(meta.group(1)).split("·")] if meta else []
        parts = [p for p in parts if p and not re.search(r"[$€£₹]|\d\s?[KM]\b", p)]
        location = parts[-1][:160] if parts else ""
        apply = re.search(r'href="(https?://[^"]+)"[^>]*>[^<]*(?:<svg.*?</svg>)?\s*Apply', a, re.S)
        jobs.append(dict(source="a16z", external_id=ext_id, company=company, title=title, location=location,
                         url=BASE + path_full, tag_hint=tag_hint, posted_at=posted))
    return jobs

def fetch():
    out, seen, errors = [], set(), []
    for q in QUERIES:
        url = BASE + "/jobs" + ("?" + urllib.parse.urlencode({"q": q}) if q else "")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                page = r.read().decode("utf-8", "replace")
            got = parse_page(page)
            if not got:
                errors.append(f"{url}: 0 jobs parsed (page layout may have changed)")
            for j in got:
                if j["external_id"] not in seen:
                    seen.add(j["external_id"]); out.append(j)
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")
        time.sleep(1)
    for e in errors:
        print("   [a16z] warning:", e)
    if not out:
        raise RuntimeError("no a16z jobs parsed: " + "; ".join(errors)[:300])
    return out
