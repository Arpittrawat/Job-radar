"""Checks docs/jobs.json before the workflow commits it. Exit code 1 = don't commit (GitHub emails you).

Fails if:
- the file is missing, not valid JSON, or has no "jobs" / "funding" lists
- the job count dropped by more than 80% compared with the last committed version
  (skipped on the first run, when there's no previous version, and when show_from was changed on purpose)
Run: python3 validate.py            (compares with `git show HEAD:docs/jobs.json`)
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "docs", "jobs.json")
MAX_DROP = 0.8          # fail if more than 80% of jobs disappear
MIN_PREVIOUS = 20       # ignore the drop check when the previous file was tiny


def check(new, prev=None):
    """new / prev: parsed jobs.json dicts (prev may be None). Returns a list of problems ('' list = OK)."""
    problems = []
    if not isinstance(new, dict):
        return ["jobs.json is not a JSON object"]
    for key in ("jobs", "funding", "health"):
        if not isinstance(new.get(key), list):
            problems.append(f'"{key}" is missing or not a list')
    if problems or not isinstance(prev, dict) or not isinstance(prev.get("jobs"), list):
        return problems                          # first run: nothing to compare with
    if new.get("show_from") != prev.get("show_from"):
        return problems                          # show_from changed on purpose: big drops are expected
    before, after = len(prev["jobs"]), len(new["jobs"])
    if before >= MIN_PREVIOUS and after < before * (1 - MAX_DROP):
        problems.append(f"job count dropped from {before} to {after} (more than {int(MAX_DROP * 100)}%)")
    return problems


def previous():
    try:
        out = subprocess.run(["git", "show", "HEAD:docs/jobs.json"], cwd=HERE, capture_output=True, timeout=30)
        return json.loads(out.stdout) if out.returncode == 0 else None
    except Exception:
        return None


def main():
    try:
        new = json.load(open(PATH))
    except Exception as e:
        print(f"INVALID: docs/jobs.json could not be read: {e}")
        return 1
    prev = previous()
    problems = check(new, prev)
    if problems:
        for p in problems:
            print("INVALID:", p)
        return 1
    print(f"OK: {len(new['jobs'])} jobs, {len(new['funding'])} funding stories"
          + (f" (previous: {len(prev['jobs'])} jobs)" if prev and isinstance(prev.get('jobs'), list) else " (first run, no previous file)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
