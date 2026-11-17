"""Used by the workflow: keep whichever radar.db is newer (cache vs the repo's daily backup).
Run: python3 pick_db.py BACKUP_PATH CURRENT_PATH   (CURRENT_PATH is what the cache restored, if anything)"""
import os, shutil, sqlite3, sys


def last_seen(path):
    """Latest first_seen_at in the jobs table, or '' if the file is missing/empty/broken."""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return ""
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return c.execute("SELECT COALESCE(MAX(first_seen_at), '') FROM jobs").fetchone()[0] or ""
        finally:
            c.close()
    except Exception:
        return ""


def pick(backup, current):
    b, cur = last_seen(backup), last_seen(current)
    if b > cur:
        shutil.copyfile(backup, current)
        return f"Using the repo backup (newer: {b} vs cache {cur or 'none'})"
    return f"Using the cached radar.db (latest job seen {cur})" if cur else "No radar.db yet: starting fresh"


if __name__ == "__main__":
    print(pick(sys.argv[1], sys.argv[2]))
