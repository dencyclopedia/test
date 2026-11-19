#!/usr/bin/env python3
"""Per-site summary of the Playwright capture: cookies and requests by registrable domain."""
import json, csv, sys, collections, os
from urllib.parse import urlparse
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
def site(h):
    h = h.lstrip(".").split(":")[0]; p = h.split(".")
    return ".".join(p[-3:]) if len(p) > 2 and p[-2] in ("co", "com") and len(p[-1]) == 2 else ".".join(p[-2:])
for pas in ("no-consent", "accept"):
    req = json.load(open(f"{R}/{pas}-requests.json")); ck = json.load(open(f"{R}/{pas}-cookies.json"))
    rq = collections.Counter(site(urlparse(r["url"]).hostname or "") for r in req if r["url"].startswith("http"))
    cc = collections.Counter(site(c["domain"]) for c in ck)
    names = collections.defaultdict(set)
    for c in ck: names[site(c["domain"])].add(c["name"])
    rows = sorted(set(rq) | set(cc), key=lambda s: (-(rq[s] + cc[s])))
    with open(f"{R}/{pas}-by-site.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["site", "requests", "cookies", "example_cookie_names"])
        for s in rows: w.writerow([s, rq[s], cc[s], " ".join(sorted(names[s])[:6])])
    print(pas, "requests", sum(rq.values()), "cookies", len(ck), "sites", len(rows))
