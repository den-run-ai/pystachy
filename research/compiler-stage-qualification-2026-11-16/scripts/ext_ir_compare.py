"""Compare extension-mode (`pystachy ext`) LLVM between two hosted compiler roots.

usage: python3 -I ext_ir_compare.py OLD_ROOT NEW_ROOT OUTDIR FILE...

Each FILE is compiled by each root's own driver.compile_program with ext=<stem>, the
directories the driver's main() computes (program directory, PYSTACHY_PATH, root/lib),
and a clean PYSTACHY_* environment. stdout (IR), the last diagnostic line with the
root's library prefix normalized, and the exit status must match byte for byte.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

WORKER = r'''
import os, sys
root, path = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
from src.pystachy_compiler import diagnostics, driver
sys.setrecursionlimit(diagnostics.MAXNEST * 40)
diagnostics.SRC = path
s = path.rfind("/")
d = path[:s] if s > 0 else "."
real = os.path.realpath(path)
if os.path.realpath(d).rstrip("/") + "/" + path[s + 1:] != real:
    d = real[: real.rfind("/")]
dirs = [d] + [x for x in os.getenv("PYSTACHY_PATH", "").split(":") if x] + [root + "/lib"]
src = open(path, "r", encoding=diagnostics.RAW).read()
ext = path[path.rfind("/") + 1:-3]
ir = driver.compile_program(path, src, dirs, ext)
sys.stdout.write(ir)
'''


def run(root, path, cwd):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = root
    r = subprocess.run([sys.executable, "-I", "-c", WORKER, root, path], cwd=cwd, env=env,
                       capture_output=True, text=True, encoding="latin-1", timeout=600)
    err = r.stderr.replace(root + "/lib/", "lib/").replace(root + "/", "")
    return r.returncode, r.stdout, err


def main():
    old, new, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    files = sys.argv[4:]
    out.mkdir(parents=True, exist_ok=True)
    cwd = os.getcwd()

    def one(f):
        a = run(old, f, cwd)
        b = run(new, f, cwd)
        same = a == b
        if not same:
            stem = f.replace("/", "_")
            (out / (stem + ".old.ll")).write_text(a[1], encoding="latin-1")
            (out / (stem + ".new.ll")).write_text(b[1], encoding="latin-1")
            (out / (stem + ".old.err")).write_text(a[2], encoding="latin-1")
            (out / (stem + ".new.err")).write_text(b[2], encoding="latin-1")
        return {"file": f, "same": same, "exit": [a[0], b[0]],
                "ir_lines": a[1].count("\n"), "ir_sha256": hashlib.sha256(b[1].encode("latin-1")).hexdigest(),
                "stderr_last": (b[2].strip().splitlines() or [""])[-1][:200]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.getenv("JOBS", "3"))) as pool:
        results = list(pool.map(one, files))
    (out / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    differ = [r for r in results if not r["same"]]
    for r in results:
        print(("SAME " if r["same"] else "DIFF ") + f"exit={r['exit']} lines={r['ir_lines']} {r['file']} {r['stderr_last'] if r['exit'][1] else ''}")
    print(f"{len(results)} programs, {len(differ)} differ, "
          f"{sum(1 for r in results if r['exit'] == [0, 0])} compiled by both, "
          f"{sum(1 for r in results if r['exit'][0] != 0 and r['exit'][1] != 0)} rejected by both")
    return 1 if differ else 0


if __name__ == "__main__":
    raise SystemExit(main())
