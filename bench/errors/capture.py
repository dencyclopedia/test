"""Run one command and record exactly what it printed.

usage: python3 capture.py OUTDIR ID [--env K=V ...] [--path PATH] [--note TEXT] -- COMMAND...
Writes OUTDIR/ID.txt (verbatim transcript) and appends a record to OUTDIR/captures.jsonl.
COMMAND is run through bash -c so pipes work. Nothing is edited: stdout/stderr are stored byte-for-byte.
"""
import datetime, json, os, subprocess, sys


def main():
    argv = sys.argv[1:]
    out, cid = argv[0], argv[1]
    i = argv.index("--")
    opts, cmd = argv[2:i], " ".join(argv[i + 1:])
    env, note = dict(os.environ), ""
    j = 0
    while j < len(opts):
        if opts[j] == "--env":
            k, v = opts[j + 1].split("=", 1)
            if v == "":
                env.pop(k, None)
            else:
                env[k] = v
            j += 2
        elif opts[j] == "--path":
            env["PATH"] = opts[j + 1]; j += 2
        elif opts[j] == "--note":
            note = opts[j + 1]; j += 2
        else:
            raise SystemExit("bad option " + opts[j])
    os.makedirs(out, exist_ok=True)
    p = subprocess.run(["/bin/bash", "-c", cmd], env=env, capture_output=True)
    so, se = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    changed = {k: env.get(k) for k in ("PATH", "TESSDATA_PREFIX", "OMP_THREAD_LIMIT") if env.get(k) != os.environ.get(k)}
    with open(os.path.join(out, cid + ".txt"), "w") as f:
        f.write(f"$ {cmd}\n")
        for k, v in changed.items():
            f.write(f"# env {k}={v if v is not None else '(unset)'}\n")
        f.write(f"# exit code: {p.returncode}\n--- stdout ---\n{so}--- stderr ---\n{se}")
    rec = {"id": cid, "command": cmd, "env_changed": changed, "exit_code": p.returncode,
           "stdout": so[-4000:], "stderr": se[-4000:], "note": note,
           "captured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    with open(os.path.join(out, "captures.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[{cid}] rc={p.returncode}\n{se[-1500:]}{so[-500:]}")


if __name__ == "__main__":
    main()
