# Job Radar - step 7 (cloud)

Runs on GitHub every day at ~09:07 and ~21:07 India time. Mac can be off.
Dashboard = a web page (GitHub Pages). Open it from any device.

## One-time setup
1. github.com -> sign up / log in -> New repository. Name: job-radar. Choose PUBLIC. Create.
2. On the repo page: "uploading an existing file" link. Drag in EVERYTHING from this folder
   (the folders docs and scrapers, plus all files). Commit.
   Do not upload radar.db or radar.log (they do not exist yet).
3. Add file -> Create new file. Name it exactly:  .github/workflows/radar.yml
   (typing the slashes creates the folders). Paste the full text of github-workflow-radar.yml. Commit.
4. Tab "Actions" -> "Job Radar" -> Run workflow. Wait ~1-2 min until green tick.
5. Settings -> Pages -> Source: "Deploy from a branch" -> Branch main, folder /docs -> Save.
6. After ~1 min your link appears there: https://<username>.github.io/job-radar/
   Bookmark it. Open on phone too.

## Notes
- "Mark applied" is saved in that browser only (not synced between phone and laptop).
- Repo is public, so the job list is public. It has no personal data.
- GitHub may delay runs up to ~30 min. If it ever pauses the schedule, Actions tab -> Enable.
- Local mode still works: python3 run.py, python3 server.py
