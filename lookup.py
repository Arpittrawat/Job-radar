"""Finds the real article behind a Google News link, and searches the web for a company's founders (LinkedIn) and website.
Best effort: every function returns empty results instead of raising."""
import re, json, html, time, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}

def _req(url, data=None, headers=None, timeout=20):
    h = dict(UA, **(headers or {}))
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), r.geturl()

# ---------- Google News -> real article URL ----------
def resolve_gnews(url):
    """news.google.com/rss/articles/<id> -> publisher URL (uses the same decode call the Google News page makes)."""
    if "news.google.com" not in url:
        return url
    try:
        m = re.search(r"/articles/([^?/]+)", url)
        if not m:
            return None
        gid = m.group(1)
        page, final = _req(f"https://news.google.com/rss/articles/{gid}")
        if "news.google.com" not in final:
            return final
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if not (sg and ts):
            return None
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], gid, int(ts.group(1)), sg.group(1)]
        payload = [[["Fbv4je", json.dumps(inner), None, "generic"]]]
        body = urllib.parse.urlencode({"f.req": json.dumps(payload)}).encode()
        txt, _ = _req("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
                      headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        for line in txt.split("\n"):
            if "garturlres" in line:
                arr = json.loads(json.loads(line)[0][2])
                return arr[1]
    except Exception:
        return None
    return None

# ---------- web search (DuckDuckGo HTML, Bing as backup) ----------
def search(query, n=8):
    """[(url, title, snippet)] from a web search."""
    out = []
    try:
        page, _ = _req("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query}))
        for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?:class="result__snippet"[^>]*>(.*?)</a>)?', page, re.S):
            href = html.unescape(m.group(1))
            u = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]
            out.append((u, _clean(m.group(2)), _clean(m.group(4) or "")))
    except Exception:
        pass
    if not out:
        try:
            page, _ = _req("https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "setlang": "en"}))
            for m in re.finditer(r'<li class="b_algo".*?<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?(?:<p[^>]*>(.*?)</p>)?', page, re.S):
                out.append((html.unescape(m.group(1)), _clean(m.group(2)), _clean(m.group(3) or "")))
        except Exception:
            pass
    time.sleep(1.2)
    return out[:n]

def _clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()

def _key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

SKIP_SITES = re.compile(r"(linkedin|crunchbase|wikipedia|facebook|twitter|x\.com|instagram|youtube|techcrunch|tracxn|pitchbook|"
                        r"bloomberg|reuters|forbes|zoominfo|glassdoor|indeed|apollo\.io|rocketreach|cbinsights|dealroom|entrackr|inc42|"
                        r"yourstory|economictimes|livemint|moneycontrol|medium|substack|github|ycombinator|wellfound|angel\.co|f6s|eu-startups|news\.google)", re.I)

def find_founders(company, max_n=3):
    """LinkedIn profiles of people whose LinkedIn title says founder/CEO at this company."""
    ck = _key(company)
    found = []
    for q in (f'"{company}" founder linkedin', f'{company} co-founder CEO site:linkedin.com/in'):
        for url, title, snip in search(q):
            if "linkedin.com/in/" not in url:
                continue
            # LinkedIn titles: "Jane Doe - Co-founder & CEO - Acme | LinkedIn"
            parts = [p.strip() for p in re.split(r"\s[-–|]\s", title) if p.strip()]
            name = parts[0] if parts else ""
            blob = (title + " " + snip).lower()
            if not name or len(name.split()) > 4 or not re.search(r"found|ceo|cto|coo", blob):
                continue
            if ck[:6] not in _key(title + " " + snip):
                continue
            role = next((p for p in parts[1:] if re.search(r"found|ceo|cto|coo", p, re.I)), "Founder")
            url = url.split("?")[0]
            if url not in [f["linkedin"] for f in found]:
                found.append(dict(name=name, title=role[:60], linkedin=url))
            if len(found) >= max_n:
                return found
        if found:
            break
    return found

def find_website(company):
    """Company homepage: first search result that isn't a news/social/directory site and looks like the company."""
    ck = _key(company)
    for url, title, snip in search(f"{company} official website"):
        host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
        if not host or SKIP_SITES.search(host):
            continue
        if ck[:6] in _key(host) or (ck and ck in _key(title)):
            return "https://" + host
    return None
