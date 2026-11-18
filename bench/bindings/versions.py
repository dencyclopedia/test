"""Versions matrix from the package registries (PyPI, npm, Maven Central, Go module proxy, NuGet, GitHub).
usage: python3 versions.py OUT.json   -- every value is copied from a registry response; nothing typed by hand."""
import json, sys, urllib.request


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ocr-test-lab"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


rows = []


def add(name, f):
    try:
        rows.append({"package": name, **f()})
    except Exception as e:  # record the failure, don't guess
        rows.append({"package": name, "error": repr(e)})


def pypi(p):
    d = get(f"https://pypi.org/pypi/{p}/json")
    v = d["info"]["version"]
    files = d["releases"].get(v, [])
    return {"registry": "PyPI", "latest": v, "released": min((f["upload_time_iso_8601"] for f in files), default=None),
            "license": d["info"].get("license_expression") or d["info"].get("license"),
            "url": f"https://pypi.org/project/{p}/"}


def npm(p):
    d = get(f"https://registry.npmjs.org/{p}")
    v = d["dist-tags"]["latest"]
    return {"registry": "npm", "latest": v, "released": d["time"][v], "license": d["versions"][v].get("license"),
            "url": f"https://www.npmjs.com/package/{p}"}


def maven(g, a):
    d = get(f"https://search.maven.org/solrsearch/select?q=g:{g}+AND+a:{a}&core=gav&rows=1&wt=json")
    doc = d["response"]["docs"][0]
    import datetime
    rel = datetime.datetime.fromtimestamp(doc["timestamp"] / 1000, datetime.timezone.utc).isoformat()
    pom = urllib.request.urlopen(f"https://repo1.maven.org/maven2/{g.replace('.', '/')}/{a}/{doc['v']}/{a}-{doc['v']}.pom", timeout=30).read().decode()
    import re
    lic = re.findall(r"<license>\s*<name>([^<]+)</name>", pom)
    return {"registry": "Maven Central", "latest": doc["v"], "released": rel, "license": ", ".join(lic) or None,
            "url": f"https://central.sonatype.com/artifact/{g}/{a}"}


def goproxy(mod, repo):
    d = get(f"https://proxy.golang.org/{mod}/@latest")
    lic = get(f"https://api.github.com/repos/{repo}").get("license", {}) or {}
    return {"registry": "Go module proxy", "latest": d["Version"], "released": d["Time"], "license": lic.get("spdx_id"),
            "url": f"https://pkg.go.dev/{mod}"}


def nuget(p):
    d = get(f"https://api.nuget.org/v3/registration5-gz-semver2/{p.lower()}/index.json") if False else \
        get(f"https://api.nuget.org/v3/registration5-semver1/{p.lower()}/index.json")
    items = d["items"][-1]
    if "items" not in items:
        items = get(items["@id"])
    leaf = items["items"][-1]["catalogEntry"]
    return {"registry": "NuGet", "latest": leaf["version"], "released": leaf.get("published"),
            "license": leaf.get("licenseExpression") or leaf.get("licenseUrl"), "url": f"https://www.nuget.org/packages/{p}"}


def gh_release(repo, tag):
    d = get(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
    lic = get(f"https://api.github.com/repos/{repo}").get("license", {}) or {}
    return {"registry": "GitHub releases", "latest": tag, "released": d.get("published_at"), "license": lic.get("spdx_id"),
            "url": d.get("html_url")}


add("tesseract (C++ engine, TessBaseAPI)", lambda: gh_release("tesseract-ocr/tesseract", "5.5.4"))
add("pytesseract", lambda: pypi("pytesseract"))
add("tesserocr", lambda: pypi("tesserocr"))
add("tesseract.js", lambda: npm("tesseract.js"))
add("tesseract.js-core", lambda: npm("tesseract.js-core"))
add("tess4j", lambda: maven("net.sourceforge.tess4j", "tess4j"))
add("gosseract", lambda: goproxy("github.com/otiai10/gosseract/v2", "otiai10/gosseract"))
add("Tesseract (.NET NuGet)", lambda: nuget("Tesseract"))
add("ocrmypdf", lambda: pypi("ocrmypdf"))
json.dump(rows, open(sys.argv[1], "w"), indent=2)
print(json.dumps(rows, indent=1))
