"""Hacker News 'Ask HN: Who is hiring?' (monthly thread). Uses the free Algolia HN API."""
import json, re, html, urllib.request, urllib.parse
from datetime import datetime, timezone
import tagger

API = "https://hn.algolia.com/api/v1"
PLACES = re.compile(r"onsite|on-site|hybrid|remote|london|\\buk\\b|europe|berlin|paris|toronto|canada|singapore|dubai|amsterdam|dublin|sydney|lisbon|barcelona|zurich|tel aviv", re.I)
UA = {"User-Agent": "job-radar/1.0 (personal use)"}

def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)

def latest_thread_id():
    q = urllib.parse.urlencode({"tags": "story,author_whoishiring", "query": "who is hiring", "hitsPerPage": 10})
    for h in _get(f"{API}/search_by_date?{q}")["hits"]:
        if "who is hiring" in (h.get("title") or "").lower():
            return h["objectID"]
    raise RuntimeError("could not find the latest 'Who is hiring' thread")

def parse_comment(c):
    """Top-level comment -> job dict, or None. Posts usually start: Company | Role | Location | Remote"""
    raw = c.get("text")
    if not raw:
        return None
    first = re.split(r"<p>|\n", raw, maxsplit=1)[0]
    line = html.unescape(re.sub(r"<[^>]+>", " ", first))
    line = re.sub(r"\s+", " ", line).strip()
    if not line:
        return None
    parts = [p.strip() for p in line.split("|") if p.strip()]
    if len(parts) == 1:                      # free-text post with no "|" format
        parts = ["See post", line]
    company = parts[0][:80]
    rest = parts[1:]
    locs = [p for p in rest if len(p) <= 45 and (tagger.location_group(p) != "Other" or PLACES.search(p))]
    return dict(
        source="hn", external_id=str(c["id"]), company=company,
        title=(" | ".join(rest) if rest else line)[:200],
        location=" / ".join(locs)[:120],
        url=f"https://news.ycombinator.com/item?id={c['id']}",
        posted_at=datetime.fromtimestamp(c["created_at_i"], tz=timezone.utc).isoformat(timespec="seconds"),
    )

def fetch():
    thread = _get(f"{API}/items/{latest_thread_id()}")
    jobs = [parse_comment(c) for c in thread.get("children", [])]
    return [j for j in jobs if j]
