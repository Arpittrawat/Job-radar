"""We Work Remotely RSS feeds. Item titles look like 'Company: Job title'."""
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import timezone
from scrapers._http import get, pause

FEEDS = ["https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
         "https://weworkremotely.com/categories/all-other-remote-jobs.rss"]

def fetch():
    jobs = []
    for f in FEEDS:
        root = ET.fromstring(get(f).encode("utf-8"))
        for it in root.iter("item"):
            t = (it.findtext("title") or "").strip()
            company, _, title = t.partition(": ")
            if not title:
                company, title = "Unknown", t
            try:
                d = parsedate_to_datetime(it.findtext("pubDate") or "")
                posted = d.astimezone(timezone.utc).isoformat(timespec="seconds")
            except Exception:
                posted = None
            link = (it.findtext("link") or "").strip()
            region = (it.findtext("region") or "").strip()
            jobs.append(dict(source="wwr", external_id=link.rsplit("/", 1)[-1] or t, company=company.strip(), title=title.strip(),
                             location="Remote" + (f" ({region})" if region else ""), url=link, posted_at=posted))
        pause(1)
    return jobs
