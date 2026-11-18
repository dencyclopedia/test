#!/usr/bin/env python3
"""Run a command under a pseudo-terminal and record its output as an asciicast v2 file
(https://docs.asciinema.org/manual/asciicast/v2/): a JSON header line, then one
[seconds_since_start, "o", text] event per chunk of output. Also writes a plain .log copy.

usage: castrec.py OUT.cast TITLE -- command args...
The exit code of the command is passed through and stored in the header as "x_exit_code";
the wall-clock duration as "x_duration_s".
"""
import json, os, pty, select, subprocess, sys, time

def main():
    out, title = sys.argv[1], sys.argv[2]
    cmd = sys.argv[sys.argv.index('--') + 1:]
    cols, rows = 120, 36
    master, slave = pty.openpty()
    import fcntl, struct, termios
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
    env = dict(os.environ, TERM='xterm-256color', COLUMNS=str(cols), LINES=str(rows))
    t0 = time.time()
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    events, raw = [], bytearray()
    while True:
        r, _, _ = select.select([master], [], [], 0.5)
        if master in r:
            try:
                data = os.read(master, 65536)
            except OSError:
                data = b''
            if not data:
                break
            raw += data
            events.append([round(time.time() - t0, 6), 'o', data.decode('utf-8', 'replace')])
        elif p.poll() is not None:
            # drain
            try:
                while True:
                    r, _, _ = select.select([master], [], [], 0.2)
                    if not r: break
                    data = os.read(master, 65536)
                    if not data: break
                    raw += data
                    events.append([round(time.time() - t0, 6), 'o', data.decode('utf-8', 'replace')])
            except OSError:
                pass
            break
    rc = p.wait()
    dur = round(time.time() - t0, 3)
    header = {"version": 2, "width": cols, "height": rows, "timestamp": int(t0), "title": title,
              "env": {"TERM": "xterm-256color", "SHELL": "/bin/bash"},
              "x_command": cmd, "x_exit_code": rc, "x_duration_s": dur}
    with open(out, 'w', encoding='utf-8') as f:
        f.write(json.dumps(header) + '\n')
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    with open(os.path.splitext(out)[0] + '.log', 'w', encoding='utf-8') as f:
        f.write(raw.decode('utf-8', 'replace').replace('\r\n', '\n'))
    print(f"[castrec] {title}: exit={rc} duration={dur}s events={len(events)} -> {out}", file=sys.stderr)
    sys.exit(rc)

if __name__ == '__main__':
    main()
