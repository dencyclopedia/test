"""Write the Dockerfiles for the image-size matrix: base x languages x model.
usage: python3 gen_dockerfiles.py OUTDIR
'distro' = the distro's own language packages (Debian ships tessdata_fast files, Alpine ships tessdata standard — see results);
'fast'/'best' = tessdata_fast / tessdata_best files ADDed from GitHub at a pinned commit over the distro files."""
import os, sys

BEST = "e12c65a915945e4c28e237a9b52bc4a8f39a0cec"
FAST = "87416418657359cb625c412a48b6e1d6d41c29bd"
REPO = {"best": ("tessdata_best", BEST), "fast": ("tessdata_fast", FAST)}
BASES = {
    "python312-slim": dict(
        from_="python:3.12-slim", tessdir="/usr/share/tesseract-ocr/5/tessdata",
        install="apt-get update && apt-get install -y --no-install-recommends tesseract-ocr {pk} && rm -rf /var/lib/apt/lists/*",
        pk=lambda l: " ".join(f"tesseract-ocr-{x}" for x in l), pip="pip install --no-cache-dir -r requirements.txt",
        py="python"),
    "debian12": dict(
        from_="debian:12-slim", tessdir="/usr/share/tesseract-ocr/5/tessdata",
        install="apt-get update && apt-get install -y --no-install-recommends python3 python3-venv tesseract-ocr {pk} && rm -rf /var/lib/apt/lists/* && python3 -m venv /venv",
        pk=lambda l: " ".join(f"tesseract-ocr-{x}" for x in l),
        pip="/venv/bin/pip install --no-cache-dir -r requirements.txt", py="/venv/bin/python", path="/venv/bin"),
    "alpine322": dict(
        from_="alpine:3.22", tessdir="/usr/share/tessdata",
        install="apk add --no-cache python3 tesseract-ocr {pk} && python3 -m venv /venv",
        pk=lambda l: " ".join(f"tesseract-ocr-data-{x}" for x in l),
        pip="/venv/bin/pip install --no-cache-dir -r requirements.txt", py="/venv/bin/python", path="/venv/bin"),
}


def dockerfile(base, langs, model):
    b = BASES[base]
    run = "RUN " + b["install"].format(pk=b["pk"](langs))
    if model in REPO:  # drop the distro's copies in the same layer, so the image holds only the ADDed models
        run += " && rm -f " + " ".join(f"{b['tessdir']}/{l}.traineddata" for l in langs)
    lines = [f"FROM {b['from_']}", run]
    if model in REPO:
        repo, sha = REPO[model]
        for l in langs:
            lines.append(f"ADD https://raw.githubusercontent.com/tesseract-ocr/{repo}/{sha}/{l}.traineddata {b['tessdir']}/{l}.traineddata")
    if b.get("path"):
        lines.append(f"ENV PATH={b['path']}:$PATH")
    lines += ["ENV OMP_THREAD_LIMIT=1", f"ENV OCR_LANGS=\"{' '.join(langs)}\"", "WORKDIR /app",
              "COPY requirements.txt .", "RUN " + b["pip"], "COPY app.py .", "EXPOSE 8000",
              'CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]']
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    for base in BASES:
        for langs in (["eng"], ["eng", "deu"]):
            for model in ("distro", "fast", "best"):
                name = f"{base}-{'_'.join(langs)}-{model}"
                open(os.path.join(out, f"Dockerfile.{name}"), "w").write(dockerfile(base, langs, model))
                print(name)
