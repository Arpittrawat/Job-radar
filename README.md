# Job Radar

Finds new marketing, GTM, growth, founder's office and FDE jobs (0–1 years) as early as possible, plus fresh startup
funding news to pitch. Runs by itself on GitHub every 6 hours; the dashboard is a static page anyone can open.

**Dashboard:** https://arpittrawat.github.io/Job-radar/

## How it works

```
scrapers/*.py ─┐
funding.py ────┼─► radar.db (SQLite) ─► export.py ─► docs/jobs.json ─► docs/index.html (GitHub Pages)
enrich.py ─────┘          ▲
                          └── kept between runs in GitHub's cache; backed up to the repo once a day
```

1. `run.py` scrapes every source (one failing source never stops the others), stores new jobs in `radar.db`,
   collects funding news (`funding.py`) and job details / people (`enrich.py`).
2. `export.py` writes `docs/jobs.json`: every matching job, plus up to 1,000 other titles.
3. `validate.py` blocks the save if `jobs.json` is broken or suddenly lost more than 80% of its jobs.
4. The workflow commits `docs/jobs.json`; GitHub Pages serves `docs/`.

## Schedule

`.github/workflows/radar.yml` runs at 09:07, 15:07, 21:07 and 03:07 India time (GitHub may start it up to ~30 min late),
or any time from **Actions → Job Radar → Run workflow**.

- Green tick = data updated. The run page shows "N new matching jobs" and a per-source table.
- Red ✗ = more than half the job sources failed, or the data check failed. Nothing bad is saved; GitHub emails you.
- `.github/workflows/ci.yml` runs the tests on every upload. A red ✗ there means an uploaded file is broken.

## Sources

Jobs: Hacker News "Who is hiring", YC Work at a Startup, a16z portfolio, TrueUp, VC job boards (Sequoia, Accel,
Lightspeed, Peak XV, Blume and more), Remote OK, Remotive, Himalayas, We Work Remotely, and company career pages
(Ashby / Greenhouse / Lever / Workable) for recently funded startups.

Funding: TechCrunch, Crunchbase News, Entrackr, Inc42, YourStory, Google News.

## Settings (`config.json`)

- `show_from`: the dashboard only shows jobs first seen after this time (older ones stay hidden but remembered).
- `tags`: title keywords for each role. `locations`: keywords for India / Remote / US.

## Run locally

```
python3 run.py && python3 export.py      # scrape + build docs/jobs.json
python3 server.py                        # older local dashboard on http://localhost:8765
python3 -m pytest -q                     # tests (pip install pytest)
```

No third-party Python packages are needed to run the radar itself.

## Add a source

Create `scrapers/<name>.py` with a `fetch()` that returns a list of
`dict(source, external_id, company, title, location, url, posted_at)`, using `scrapers/_http.py` for requests
(it retries 429 / 5xx / timeouts and spaces out requests). Add `<name>` to `SOURCES` in `run.py`.

## Known limits

- "Applied", tailored CVs and pasted job descriptions are saved in that browser only (not synced between devices).
- Some sites block automated reads (for example Himalayas job pages); those jobs show "Open Job" without details.
- The repo is public: the job list **and the CV inside `docs/index.html` (name, phone, email) are public on purpose.**

## License

MIT
