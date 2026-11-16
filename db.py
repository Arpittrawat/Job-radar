import sqlite3, hashlib, re, os
from datetime import datetime, timezone
from tagger import tag_title, location_group

PATH = os.path.join(os.path.dirname(__file__), "radar.db")

def conn():
    c = sqlite3.connect(PATH)
    c.row_factory = sqlite3.Row
    return c

def init():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dedupe_key TEXT UNIQUE, source TEXT, external_id TEXT,
            company TEXT, title TEXT, location TEXT, url TEXT,
            posted_at TEXT, first_seen_at TEXT,
            tag TEXT, location_group TEXT,
            status TEXT DEFAULT 'new', possible_dupe_of INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT,
            ran_at TEXT, ok INTEGER, found INTEGER, added INTEGER, error TEXT)""")

def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def upsert(job, status="new"):
    """job: dict(source, external_id, company, title, location, url, posted_at ISO or None).
    Returns True if new."""
    key = f"{job['source']}:{job['external_id']}" if job.get("external_id") else \
        "h:" + hashlib.sha1(f"{_norm(job['company'])}|{_norm(job['title'])}|{job.get('url','')}".encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with conn() as c:
        if c.execute("SELECT 1 FROM jobs WHERE dedupe_key=?", (key,)).fetchone():
            return False
        dupe = c.execute("SELECT id FROM jobs WHERE source!=? AND lower(company)=lower(?) AND lower(title)=lower(?)",
                         (job["source"], job["company"], job["title"])).fetchone()
        c.execute("""INSERT INTO jobs (dedupe_key,source,external_id,company,title,location,url,
                     posted_at,first_seen_at,tag,location_group,possible_dupe_of,status)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (key, job["source"], job.get("external_id"), job["company"], job["title"],
                   job.get("location", ""), job.get("url", ""), job.get("posted_at"), now,
                   (tag_title(job["title"]) or job.get("tag_hint", "")), location_group(job.get("location", "")),
                   dupe["id"] if dupe else None, status))
        return True

def has_run(source):
    with conn() as c:
        return c.execute("SELECT 1 FROM runs WHERE source=? AND ok=1", (source,)).fetchone() is not None

def log_run(source, ok, found=0, added=0, error=""):
    with conn() as c:
        c.execute("INSERT INTO runs (source,ran_at,ok,found,added,error) VALUES (?,?,?,?,?,?)",
                  (source, datetime.now(timezone.utc).isoformat(timespec="seconds"), int(ok), found, added, error[:500]))
