"""One scrape pass over all sources. Run: python3 run.py"""
import importlib, traceback, subprocess, sys
from datetime import datetime, timedelta, timezone
import db

SOURCES = ["hn", "yc", "a16z", "trueup"]

def baseline_cutoff():
    """First run only: jobs older than the start of yesterday (your local time) are stored as 'old', not 'new'."""
    d = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")

def stale_cutoff(days=7):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")

def run_source(name, fetch=None):
    first = not db.has_run(name)
    cutoff = baseline_cutoff()
    stale = stale_cutoff()
    try:
        jobs = (fetch or importlib.import_module(f"scrapers.{name}").fetch)()
        added = 0
        for j in jobs:
            pa = j.get("posted_at")
            # old = posted >7 days before we saw it, or (first run only) older than yesterday / date unknown
            old = (bool(pa) and ((first and pa < cutoff) or pa < stale)) or (first and not pa)

            added += db.upsert(j, "old" if old else "new")
        db.log_run(name, True, len(jobs), added)
        print(f"[{name}] ok: {len(jobs)} found, {added} stored" + (" (first run: only yesterday+ shown as new)" if first else ""))
    except Exception as e:
        db.log_run(name, False, error=f"{type(e).__name__}: {e}")
        print(f"[{name}] FAILED: {e}")
        traceback.print_exc()

def notify(n):
    """macOS notification: 'N new matches'. Silent on other systems or if it fails."""
    if n <= 0 or sys.platform != "darwin":
        return
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{n} new job match{"es" if n != 1 else ""}. Open the dashboard." with title "Job Radar"'],
                       timeout=10, check=False)
    except Exception:
        pass

def count_new_matches(after_id):
    with db.conn() as c:
        return c.execute("SELECT COUNT(*) FROM jobs WHERE id>? AND status='new' AND tag!=''", (after_id,)).fetchone()[0]

if __name__ == "__main__":
    db.init()
    with db.conn() as c:
        before = c.execute("SELECT COALESCE(MAX(id),0) FROM jobs").fetchone()[0]
    first_ever = before == 0
    for s in SOURCES:
        run_source(s)
    try:
        import funding
        funding.run()
    except Exception as e:
        print(f"[funding] FAILED: {e}")
    n = count_new_matches(before)
    print(f"{n} new matching jobs this run")
    if not first_ever:                 # no notification for the very first baseline run
        notify(n)
