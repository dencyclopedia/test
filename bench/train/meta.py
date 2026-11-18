"""Write results/meta.json for a bench run (LAB.md). Shared by the bench-* workflows.
usage: python3 bench/train/meta.py OUT.json [key=value ...]  (values may be JSON)"""
import json, os, platform, subprocess, sys, datetime

def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:  # noqa
        return f"error: {e}"

def main():
    out = sys.argv[1]
    tess = os.environ.get("TESSERACT", "/opt/tess554/bin/tesseract")
    cpu = sh("lscpu | sed -n 's/^Model name:[ ]*//p' | head -1")
    meta = {
        "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "runner": "github-actions" if os.environ.get("GITHUB_ACTIONS") else "dev-container (timings not publishable)",
        "runner_image": os.environ.get("ImageOS", "") + " " + os.environ.get("ImageVersion", ""),
        "os": sh("lsb_release -ds") or platform.platform(),
        "kernel": platform.release(),
        "cpu_model": cpu,
        "cpu_cores_logical": os.cpu_count(),
        "mem_total": sh("free -h | awk '/Mem:/{print $2}'"),
        "engine": sh(f"{tess} --version 2>&1 | head -2").replace("\n", " | "),
        "engine_path": tess,
        "models": {
            "tessdata_fast": "87416418657359cb625c412a48b6e1d6d41c29bd",
            "tessdata": "ced78752cc61322fb554c280d13360b35b8684e4",
            "tessdata_best": "e12c65a915945e4c28e237a9b52bc4a8f39a0cec",
        },
        "git_sha": os.environ.get("GITHUB_SHA") or sh("git rev-parse HEAD"),
        "run_url": (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                    if os.environ.get("GITHUB_RUN_ID") else None),
        "python": platform.python_version(),
    }
    for kv in sys.argv[2:]:
        k, v = kv.split("=", 1)
        try:
            meta[k] = json.loads(v)
        except ValueError:
            meta[k] = v
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))

if __name__ == "__main__":
    main()
