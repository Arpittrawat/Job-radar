"""Finds the real article behind a Google News link. Best effort: returns None instead of raising."""
import re, json, html, time, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}

from scrapers._http import fetch_full

def _req(url, data=None, headers=None, timeout=20):
    return fetch_full(url, data=data, headers=dict(UA, **(headers or {})), timeout=timeout, min_gap=0.5)

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

