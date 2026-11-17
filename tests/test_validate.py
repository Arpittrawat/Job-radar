import validate


def data(n, show="2026-11-14T00:00:00+00:00"):
    return {"jobs": [{}] * n, "funding": [], "health": [], "show_from": show}


def test_ok_and_first_run():
    assert validate.check(data(100), data(90)) == []
    assert validate.check(data(0), None) == []                 # first run: nothing to compare


def test_broken_shape():
    assert validate.check([], None)
    assert validate.check({"jobs": "x", "funding": [], "health": []}, None)


def test_big_drop_fails_but_show_from_change_is_allowed():
    assert validate.check(data(10), data(100))                 # 90% drop
    assert validate.check(data(25), data(100)) == []           # 75% drop is fine
    assert validate.check(data(0), data(100, show="2026-12-01T00:00:00+00:00")) == []
    assert validate.check(data(1), data(10)) == []             # tiny previous file: ignored
