from scrapers.hn import parse_comment


def test_pipe_format():
    j = parse_comment({"id": 42, "created_at_i": 1763000000,
                       "text": "Acme AI | Growth Marketer | Remote (US) | Full-time<p>We are hiring..."})
    assert j["company"] == "Acme AI"
    assert "Growth Marketer" in j["title"]
    assert "Remote" in j["location"]
    assert j["url"] == "https://news.ycombinator.com/item?id=42"
    assert j["external_id"] == "42" and j["source"] == "hn"


def test_free_text_and_empty():
    j = parse_comment({"id": 7, "created_at_i": 1763000000, "text": "We are hiring a founding marketer in London"})
    assert j["company"] == "See post"
    assert parse_comment({"id": 8, "created_at_i": 1763000000, "text": ""}) is None
    assert parse_comment({"id": 9, "created_at_i": 1763000000}) is None
