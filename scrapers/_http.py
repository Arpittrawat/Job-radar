"""Shared polite HTTP helper for every scraper, funding.py, enrich.py and lookup.py.

- Retries up to 3 attempts on 429, 5xx, timeouts and connection errors, waiting 1s, 3s, 9s
  (or the site's Retry-After, capped at 30s).
- Never retries 403 / 404 / other 4xx: those won't fix themselves.
- Keeps a minimum gap between requests to the same host (min_gap seconds).
"""
import json, time, socket, urllib.request, urllib.error, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json, text/html;q=0.9, */*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}

BACKOFF = (1, 3, 9)          # wait before attempt 2, 3 (and a 4th if ever raised)
ATTEMPTS = 3
RETRY_AFTER_CAP = 30
_last_hit = {}               # host -> time of last request
sleep = time.sleep           # patched in tests


def _retry_after(err):
    try:
        v = err.headers.get("Retry-After") if err.headers else None
        return min(RETRY_AFTER_CAP, max(0, int(float(v)))) if v else None
    except (TypeError, ValueError):
        return None


def _wait_for_host(url, min_gap):
    host = urllib.parse.urlparse(url).netloc
    gap = min_gap - (time.time() - _last_hit.get(host, 0))
    if gap > 0:
        sleep(gap)
    _last_hit[host] = time.time()


def fetch_full(url, data=None, headers=None, timeout=25, min_gap=0.0):
    """Returns (text, final_url). Raises the last error if every attempt fails."""
    h = dict(UA, **(headers or {}))
    last = None
    for attempt in range(ATTEMPTS):
        if attempt:
            sleep(wait)
        if min_gap:
            _wait_for_host(url, min_gap)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
                return r.read().decode("utf-8", "replace"), r.geturl()
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429 and e.code < 500:
                raise                                   # 403, 404, ... : no retry
            wait = _retry_after(e)
            wait = BACKOFF[attempt] if wait is None else wait
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            last = e
            wait = BACKOFF[attempt]
    raise last


def get(url, timeout=25, headers=None, min_gap=0.0):
    return fetch_full(url, headers=headers, timeout=timeout, min_gap=min_gap)[0]


def get_json(url, timeout=25, headers=None, min_gap=0.0):
    return json.loads(get(url, timeout, headers, min_gap))


def pause(s=0.6):
    time.sleep(s)
