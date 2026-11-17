import json
import db, export


def test_export_shape_and_tagged_first(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(export, "OUT", str(tmp_path / "jobs.json"))
    monkeypatch.setattr(export, "MAX_OTHER", 3)
    db.init()
    with db.conn() as c:
        for i in range(10):
            db.upsert(dict(source="yc", external_id=f"o{i}", company=f"Co{i}", title="Backend Engineer",
                           location="Remote", url=f"https://x.com/{i}"), "new", c)
        for i in range(4):
            db.upsert(dict(source="yc", external_id=f"m{i}", company=f"M{i}", title="Product Marketing Manager",
                           location="India", url="javascript:alert(1)"), "new", c)
    export.main()
    out = json.load(open(export.OUT))
    assert {"generated_at", "show_from", "jobs", "health", "funding", "funding_health"} <= set(out)
    tagged = [j for j in out["jobs"] if j["tag"]]
    other = [j for j in out["jobs"] if not j["tag"]]
    assert len(tagged) == 4 and len(other) == 3          # all matches kept, others capped
    assert all(j["url"] == "" for j in tagged)             # unsafe links removed on export too
