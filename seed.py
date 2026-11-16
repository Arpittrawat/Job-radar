"""Fake jobs so you can see the dashboard before any scraper exists. Safe to run twice."""
import db
from datetime import datetime, timedelta, timezone
db.init()
now = datetime.now(timezone.utc)
rows = [
 ("yc","Acme AI","Growth Marketing Associate","San Francisco, CA",2),
 ("yc","Loop Labs","GTM Engineer","Remote (US)",5),
 ("trueup","Nimbus","Forward Deployed Engineer","New York, NY",8),
 ("trueup","Pixelcraft","Technical Marketer","Remote",12),
 ("hn","Tilt","Founder's Office Associate","Bengaluru, India",20),
 ("hn","Orbit","Backend Engineer","Austin, TX",3),
 ("a16z","Vela","Marketing Operations Manager","Remote (US)",30),
 ("a16z","Acme AI","Growth Marketing Associate","San Francisco, CA",2),
 ("yc","Fable","Solutions Engineer","London, UK",26),
 ("trueup","Kite","Content Marketing Lead","Gurugram, India",7),
]
n = 0
for i,(s,co,t,loc,h) in enumerate(rows):
    n += db.upsert(dict(source=s, external_id=f"seed{i}", company=co, title=t, location=loc,
        url=f"https://example.com/{i}", posted_at=(now-timedelta(hours=h)).isoformat(timespec="seconds")))
print(f"seeded {n} new jobs")
