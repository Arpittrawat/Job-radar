"""Funding radar: recent startup funding news from RSS feeds.
Each item: company, amount, round, region, headline, news link, source, date, company website (best effort).
Stored in radar.db table `funding`; exported to docs/jobs.json under "funding"."""
import re, html, time, hashlib, json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import db

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def gnews(q):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:3d", "hl": "en-US", "gl": "US", "ceid": "US:en"})

# (name shown in dashboard, feed url, region hint or None)
FEEDS = [
    ("TechCrunch", "https://techcrunch.com/category/venture/feed/", None),
    ("Crunchbase News", "https://news.crunchbase.com/feed/", None),
    ("Entrackr", "https://entrackr.com/feed/", "India"),
    ("Inc42", "https://inc42.com/feed/", "India"),
    ("YourStory", "https://yourstory.com/feed", "India"),
    ("Google News", gnews('startup raises "seed round" OR "Series A" OR "pre-seed"'), None),
    ("Google News", gnews('Indian startup raises funding Series OR seed'), "India"),
]

VERB = r"(?:raises?|raised|secures?|secured|bags?|bagged|lands?|landed|closes?|closed|nets?|netted|picks up|picked up|snags?|grabs?|gets|receives|scores?)"
FUND_WORDS = re.compile(r"\b(raise[sd]?|funding|secures?|bags?|series [a-h]\b|seed|pre-seed|round)\b", re.I)
AMOUNT = re.compile(
    r"(?P<cur>\$|US\$|USD\s?|₹|Rs\.?\s?|INR\s?|€|£)\s?(?P<num>\d+(?:[.,]\d+)?)\s?(?P<unit>billion|bn|b\b|million|mn|mln|m\b|crore|cr\b|lakh|k\b)?", re.I)
ROUND = re.compile(r"\b(pre[- ]seed|seed|angel|pre[- ]series [a-h]|series [a-h]\d?|bridge|growth|debt|venture debt|ipo)\b", re.I)
INDIA = re.compile(r"\b(india|indian|bengaluru|bangalore|mumbai|delhi|gurugram|gurgaon|noida|pune|hyderabad|chennai)\b|₹|crore|\bRs\b", re.I)
MEDIA_NAMES = {"techcrunch","crunchbase","entrackr","inc42","yourstory","google","googleapis","gstatic","twitter","facebook","linkedin","instagram",
    "youtube","wordpress","gravatar","feedburner","apple","medium","amazon","amazonaws","cloudflare","doubleclick","substack","tiktok","reddit",
    "github","w3","schema","gmpg","ogp","pitchbook","sec","forbes","bloomberg","reuters","wsj","cnbc","businessinsider","axios","economictimes",
    "indiatimes","livemint","moneycontrol","vccircle","thehindu","ndtv","indianexpress","timesofindia","news18","whatsapp","telegram","spotify","jsdelivr","fonts"}
MEDIA_DOMAINS = {"x.com","t.co","bit.ly","wp.com","lnkd.in","goo.gl","ow.ly","buff.ly"}
def _is_media(domain):
    return domain in MEDIA_DOMAINS or any(p in MEDIA_NAMES for p in domain.split(".")[:-1])

def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def _date(s):
    try:
        d = parsedate_to_datetime(s)
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None

def parse_feed(xml_text):
    """Return list of dict(title, link, date, summary, source) from RSS 2.0 or Atom."""
    out = []
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    for it in root.iter("item"):
        src = it.find("source")
        out.append(dict(title=_text(it.findtext("title")), link=(it.findtext("link") or "").strip(),
                        date=_date(it.findtext("pubDate") or ""), summary=_text(it.findtext("description"))[:600],
                        source=_text(src.text) if src is not None and src.text else None))
    ns = "{http://www.w3.org/2005/Atom}"
    for e in root.iter(ns + "entry"):
        l = e.find(ns + "link")
        out.append(dict(title=_text(e.findtext(ns + "title")), link=l.get("href") if l is not None else "",
                        date=(e.findtext(ns + "updated") or e.findtext(ns + "published")),
                        summary=_text(e.findtext(ns + "summary"))[:600], source=None))
    return out

def _usd(cur, num, unit):
    """Rough USD value, only for sorting/display hints."""
    try:
        n = float(num.replace(",", ""))
    except ValueError:
        return None
    u = (unit or "").lower()
    mult = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mn": 1e6, "mln": 1e6, "m": 1e6,
            "crore": 1e7, "cr": 1e7, "lakh": 1e5, "k": 1e3}.get(u, 1)
    v = n * mult
    c = cur.strip().lower()
    if c in ("₹", "rs.", "rs", "inr"):
        v /= 84
    elif c == "€":
        v *= 1.08
    elif c == "£":
        v *= 1.27
    return v

def _amount_text(m):
    cur, num, unit = m.group("cur").strip(), m.group("num"), (m.group("unit") or "")
    cur = {"US$": "$", "USD": "$", "Rs.": "₹", "Rs": "₹", "INR": "₹"}.get(cur, cur)
    u = unit.lower()
    u = {"million": "M", "mn": "M", "mln": "M", "m": "M", "billion": "B", "bn": "B", "b": "B", "crore": " Cr", "cr": " Cr", "lakh": " Lakh", "k": "K"}.get(u, unit)
    return f"{cur}{num}{u}"

def extract(title, summary=""):
    """Pull company / amount / round from a funding headline. Returns None if it isn't a funding story."""
    t = re.sub(r"^\[?(exclusive|breaking|funding alert|funding news|funding roundup)\]?\s*[:|\-–]?\s*", "", title, flags=re.I).strip()
    if not FUND_WORDS.search(t):
        return None
    m = re.search(r"^(?P<pre>.+?)\s+" + VERB + r"\b", t, re.I)
    if not m:
        return None
    pre = m.group("pre").strip(" ,:-‘’'\"")
    # "Fintech startup Acme" / "Bengaluru-based Acme" / "AI agent maker Acme" -> "Acme"
    pre = re.split(r"\b(?:startup|start-up|platform|maker|company|firm|provider|developer|unicorn|player|brand|app|based)\s+", pre, flags=re.I)[-1]
    pre = re.sub(r"^(?:ai|fintech|healthtech|edtech|d2c|saas|b2b|stealth)\s+", "", pre, flags=re.I).strip()
    pre = re.sub(r"[’']s$", "", pre).strip(" ,")
    if not pre or len(pre) > 50 or len(pre.split()) > 6:
        return None
    blob = t + " " + (summary or "")
    am = AMOUNT.search(t) or AMOUNT.search(summary or "")
    rd = ROUND.search(t) or ROUND.search(summary or "")
    if not am and not rd:
        return None
    rnd = rd.group(1).title().replace("Pre Seed", "Pre-Seed").replace("Ipo", "IPO") if rd else ""
    return dict(company=pre, amount=_amount_text(am) if am else "", amount_usd=_usd(am.group("cur"), am.group("num"), am.group("unit")) if am else None,
                round=rnd, india=bool(INDIA.search(blob)))

def find_website(article_url, company):
    """Best effort: first outbound link in the article whose domain looks like the company's."""
    try:
        page = _get(article_url, timeout=15)
    except Exception:
        return None
    key = re.sub(r"[^a-z0-9]", "", company.lower())[:12]
    links = re.findall(r'href="(https?://[^"#?]+)', page)
    domains = []
    for l in links:
        d = urllib.parse.urlparse(l).netloc.lower().removeprefix("www.")
        if d and not _is_media(d) and d not in domains:
            domains.append(d)
    for d in domains:
        if key and key[:6] in re.sub(r"[^a-z0-9]", "", d):
            return "https://" + d
    return None

def init():
    with db.conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS funding (
            id INTEGER PRIMARY KEY AUTOINCREMENT, dedupe_key TEXT UNIQUE,
            company TEXT, amount TEXT, amount_usd REAL, round TEXT, region TEXT,
            headline TEXT, url TEXT, source TEXT, published_at TEXT, first_seen_at TEXT, website TEXT)""")

def _key(company, rnd):
    return hashlib.sha1((re.sub(r"[^a-z0-9]", "", company.lower()) + "|" + (rnd or "").lower()).encode()).hexdigest()

def store(item):
    """Insert if new. Same company+round within 30 days counts as a duplicate."""
    key = _key(item["company"], item["round"])
    with db.conn() as c:
        row = c.execute("SELECT first_seen_at FROM funding WHERE dedupe_key=?", (key,)).fetchone()
        if row:
            return False
        c.execute("""INSERT INTO funding (dedupe_key,company,amount,amount_usd,round,region,headline,url,source,published_at,first_seen_at,website)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (key, item["company"], item["amount"], item["amount_usd"], item["round"], item["region"], item["headline"],
                   item["url"], item["source"], item["published_at"], datetime.now(timezone.utc).isoformat(timespec="seconds"), item.get("website")))
        return True

def run(max_age_days=7, website_lookups=25):
    init()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat(timespec="seconds")
    lookups = 0
    for name, url, region_hint in FEEDS:
        tag = "f:" + name
        try:
            items = parse_feed(_get(url))
            added = 0
            for it in items:
                if it["date"] and it["date"] < cutoff:
                    continue
                title, source = it["title"], name
                if name == "Google News":
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2:
                        title, source = parts[0], parts[1]
                    if it.get("source"):
                        source = it["source"]
                x = extract(title, it["summary"])
                if not x:
                    continue
                with db.conn() as c:
                    if c.execute("SELECT 1 FROM funding WHERE dedupe_key=?", (_key(x["company"], x["round"]),)).fetchone():
                        continue
                site = None
                if name != "Google News" and lookups < website_lookups:
                    lookups += 1
                    site = find_website(it["link"], x["company"])
                    time.sleep(0.5)
                region = "India" if (region_hint == "India" or x["india"]) else "Global"
                added += store(dict(company=x["company"], amount=x["amount"], amount_usd=x["amount_usd"], round=x["round"],
                                    region=region, headline=title, url=it["link"], source=source,
                                    published_at=it["date"], website=site))
            db.log_run(tag, True, len(items), added)
            print(f"[{tag}] ok: {len(items)} items, {added} new funding stories")
        except Exception as e:
            db.log_run(tag, False, error=f"{type(e).__name__}: {e}")
            print(f"[{tag}] FAILED: {e}")
        time.sleep(1)
