import json, re, os
_cfg = json.load(open(os.path.join(os.path.dirname(__file__), "config.json")))

def _has(text, kw):
    return re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text) is not None

def tag_title(title):
    """First matching tag wins; specific tags are listed before 'Marketing'. '' = no match."""
    t = (title or "").lower()
    for tag, kws in _cfg["tags"].items():
        if any(_has(t, k) for k in kws):
            return tag
    return ""

def location_group(loc):
    l = (loc or "").lower()
    groups = []
    for g, kws in _cfg["locations"].items():
        if any(k in l for k in kws):
            groups.append(g)
    return ",".join(groups) if groups else "Other"
