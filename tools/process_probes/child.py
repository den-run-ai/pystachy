"""Small allocating/pipe/descendant children for the native process tests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def write_all(fd, data):
    while data:
        data = data[os.write(fd, data):]


mode = sys.argv[1]
if mode == "duplex":
    write_all(1, b"o" * 131072)
    write_all(2, b"e" * 131072)
    data = sys.stdin.buffer.read()
    write_all(1, data)
    write_all(2, data[::-1])
elif mode == "arguments":
    write_all(1, "|".join(sys.argv[2:]).encode())
elif mode == "json":
    records = json.loads(sys.stdin.buffer.read())
    result = [{"name": row["name"].upper(), "total": sum(row["values"])} for row in records]
    write_all(1, json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode())
elif mode == "fd-check":
    Path(sys.argv[3]).write_text("executed")
    try:
        os.fstat(int(sys.argv[2]))
    except OSError:
        print("closed")
    else:
        print("leaked")
elif mode == "outputs":
    write_all(1, b"out")
    write_all(2, b"err")
    sys.exit(7)
elif mode == "descendant":
    child = subprocess.Popen(["/bin/sleep", "30"])
    print(child.pid, flush=True)
    # A process worker's descendants are required to end with their leader.
elif mode == "flood":
    while True:
        write_all(1, b"x" * 4096)
elif mode == "closed":
    os.close(0)
    time.sleep(0.05)
elif mode == "ir":
    kind, marker = Path(sys.argv[2]).read_text().split(":", 1)
    if kind == "block":
        Path(marker).write_text(str(os.getpid()))
        time.sleep(30)
    else:
        deadline = time.monotonic() + 3.0
        while not Path(marker).exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        print("injected compiler failure", file=sys.stderr)
        sys.exit(7)
