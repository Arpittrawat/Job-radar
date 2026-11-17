import io, urllib.error
import pytest
from scrapers import _http


class Resp(io.BytesIO):
    def geturl(self):
        return "https://final.example/"
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def err(code, retry_after=None):
    h = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("https://x", code, "x", h, None)


def run(monkeypatch, outcomes):
    calls, waits = [], []
    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        o = outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return Resp(o.encode())
    monkeypatch.setattr(_http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(_http, "sleep", waits.append)
    return calls, waits


def test_retries_429_then_succeeds(monkeypatch):
    calls, waits = run(monkeypatch, [err(429), err(503), "ok"])
    assert _http.get("https://x") == "ok"
    assert len(calls) == 3 and waits == [1, 3]


def test_respects_retry_after(monkeypatch):
    calls, waits = run(monkeypatch, [err(429, "5"), "ok"])
    assert _http.get("https://x") == "ok" and waits == [5]


def test_no_retry_on_403_404(monkeypatch):
    for code in (403, 404):
        calls, waits = run(monkeypatch, [err(code), "never"])
        with pytest.raises(urllib.error.HTTPError):
            _http.get("https://x")
        assert len(calls) == 1 and waits == []


def test_gives_up_after_three(monkeypatch):
    calls, waits = run(monkeypatch, [err(500), err(500), err(500), "never"])
    with pytest.raises(urllib.error.HTTPError):
        _http.get("https://x")
    assert len(calls) == 3


def test_retries_timeouts(monkeypatch):
    calls, waits = run(monkeypatch, [TimeoutError("slow"), "ok"])
    assert _http.fetch_full("https://x") == ("ok", "https://final.example/")
