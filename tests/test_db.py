import db


def job(**kw):
    base = dict(source="yc", external_id="1", company="Acme", title="Growth Marketer",
                location="Remote", url="https://acme.com/jobs/1", posted_at=None)
    base.update(kw)
    return base


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", str(tmp_path / "t.db"))
    db.init()


def rows():
    with db.conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM jobs ORDER BY id")]


def test_dedupe_same_key(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    assert db.upsert(job()) is True
    assert db.upsert(job()) is False
    assert len(rows()) == 1


def test_cross_board_duplicate_is_flagged(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    db.upsert(job())
    db.upsert(job(source="hn", external_id="99"))
    r = rows()
    assert r[1]["possible_dupe_of"] == r[0]["id"]


def test_shared_connection(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    with db.conn() as c:
        for i in range(5):
            db.upsert(job(external_id=str(i)), "new", c)
    assert len(rows()) == 5


def test_unsafe_urls_are_dropped(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    db.upsert(job(external_id="a", url="javascript:alert(1)"))
    db.upsert(job(external_id="b", url="data:text/html,hi"))
    db.upsert(job(external_id="c", url="HTTPS://ok.com"))
    assert [r["url"] for r in rows()] == ["", "", "HTTPS://ok.com"]
    assert db.safe_url(None) == ""
