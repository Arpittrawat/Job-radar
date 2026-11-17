"""One scrape pass over all sources. Run: python3 run.py"""
import importlib, traceback, subprocess, sys, os
from datetime import datetime, timedelta, timezone
import db

SOURCES = ["hn", "yc", "a16z", "trueup", "vc", "remoteok", "remotive", "himalayas", "wwr"]

def baseline_cutoff():
    """First run only: jobs older than the start of yesterday (your local time) are stored as 'old', not 'new'."""
    d = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")

def stale_cutoff(days=7):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")

RESULTS = []   # (source, ok, found, added, error) for this run, used for the summary and the exit code

def run_source(name, fetch=None):
    """Scrape one source. Returns True on success. One DB transaction per source."""
    first = not db.has_run(name)
    cutoff = baseline_cutoff()
    stale = stale_cutoff()
    try:
        jobs = (fetch or importlib.import_module(f"scrapers.{name}").fetch)()
        added = 0
        with db.conn() as c:
            for j in jobs:
                pa = j.get("posted_at")
                # old = posted >7 days before we saw it, or (first run only) older than yesterday / date unknown
                old = (bool(pa) and ((first and pa < cutoff) or pa < stale)) or (first and not pa)
                added += db.upsert(j, "old" if old else "new", c)
        db.log_run(name, True, len(jobs), added)
        RESULTS.append((name, True, len(jobs), added, ""))
        print(f"[{name}] ok: {len(jobs)} found, {added} stored" + (" (first run: only yesterday+ shown as new)" if first else ""))
        return True
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        db.log_run(name, False, error=err)
        RESULTS.append((name, False, 0, 0, err))
        print(f"[{name}] FAILED: {e}")
        traceback.print_exc()
        return False

def too_many_failed(results, limit=0.5):
    """True if more than `limit` of the job sources failed this run."""
    return bool(results) and sum(not r[1] for r in results) / len(results) > limit

def write_summary(results, new_matches):
    """GitHub Actions run page summary (no-op outside Actions)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [f"## {new_matches} new matching job{'s' if new_matches != 1 else ''}", "",
             "| Source | Status | Found | New |", "|---|---|---|---|"]
    for name, ok, found, added, err in results:
        lines.append(f"| {name} | {'✅' if ok else '❌ ' + err[:80].replace('|', '/')} | {found} | {added} |")
    with open(path, "a") as f:
        f.write("\n".join(lines) + "\n")

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
    run_source("ats")   # company career pages; after funding so newly funded companies are watched right away
    try:
        import enrich
        enrich.run()
    except Exception as e:
        print(f"[details] FAILED: {e}")
    n = count_new_matches(before)
    print(f"{n} new matching jobs this run")
    write_summary(RESULTS, n)
    if not first_ever:                 # no notification for the very first baseline run
        notify(n)
    if too_many_failed(RESULTS):
        failed = [r[0] for r in RESULTS if not r[1]]
        print(f"ERROR: {len(failed)} of {len(RESULTS)} job sources failed: {', '.join(failed)}")
        sys.exit(1)
