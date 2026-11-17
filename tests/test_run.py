import run, pick_db, db


def test_too_many_failed():
    ok, bad = ("a", True, 1, 1, ""), ("b", False, 0, 0, "x")
    assert run.too_many_failed([bad, bad, ok]) is True
    assert run.too_many_failed([bad, ok]) is False          # exactly half is allowed
    assert run.too_many_failed([]) is False


def test_summary_written(tmp_path, monkeypatch):
    p = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(p))
    run.write_summary([("hn", True, 10, 2, ""), ("yc", False, 0, 0, "HTTPError: 500")], 2)
    t = p.read_text()
    assert "2 new matching jobs" in t and "hn" in t and "HTTPError" in t


def test_pick_db_keeps_newer(tmp_path, monkeypatch):
    def make(path, seen):
        monkeypatch.setattr(db, "PATH", str(path)); db.init()
        with db.conn() as c:
            c.execute("INSERT INTO jobs (dedupe_key, first_seen_at, company, title) VALUES ('k', ?, 'A', 'B')", (seen,))
    make(tmp_path / "backup.db", "2026-11-17T10:00:00+00:00")
    make(tmp_path / "cache.db", "2026-11-17T04:00:00+00:00")
    msg = pick_db.pick(str(tmp_path / "backup.db"), str(tmp_path / "cache.db"))
    assert "repo backup" in msg
    assert pick_db.last_seen(str(tmp_path / "cache.db")).startswith("2026-11-17T10")
    assert "cached" in pick_db.pick(str(tmp_path / "backup.db"), str(tmp_path / "cache.db"))
    assert "fresh" in pick_db.pick(str(tmp_path / "none.db"), str(tmp_path / "none2.db"))


def test_run_source_success_and_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", str(tmp_path / "t.db")); db.init()
    run.RESULTS.clear()
    jobs = [dict(source="fake", external_id=str(i), company="A", title="Growth Marketer", url="https://a.com") for i in range(3)]
    assert run.run_source("fake", lambda: jobs) is True
    def boom():
        raise RuntimeError("site down")
    assert run.run_source("broken", boom) is False
    assert [(r[0], r[1], r[3]) for r in run.RESULTS] == [("fake", True, 3), ("broken", False, 0)]
    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2
