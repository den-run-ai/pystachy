"""Try to compile 'import M' for every module of a Python standard library with Pystachy.

usage: python3 tools/import_sweep.py [COMPILER] [LIBDIR] [OUT.json]
       (defaults: ./pystachy, the running CPython's stdlib directory, build/import-sweep.json)
Each module is compiled (pystachy ir) in a program of its own, with LIBDIR on PYSTACHY_PATH; the
JSON maps each module to "OK" or the compiler's error, and a summary groups the errors.
"""
import collections
import json
import os
import subprocess
import sys
import sysconfig
import tempfile

SKIP = ("test", "tests", "idlelib", "tkinter", "turtledemo", "site-packages", "dist-packages", "lib2to3", "ensurepip", "venv", "__pycache__")


def modules(lib):
    out = []
    for dp, dn, fn in os.walk(lib):
        dn[:] = sorted(d for d in dn if d not in SKIP and not d.startswith("."))
        for f in sorted(fn):
            if not f.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dp, f), lib)[:-3].replace(os.sep, ".")
            if rel.endswith(".__init__"):
                rel = rel[:-9]
            if rel.endswith("__main__") or rel.startswith("__") or "-" in rel:
                continue
            out.append(rel)
    return out


def main():
    pys = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "./pystachy")
    lib = sys.argv[2] if len(sys.argv) > 2 else sysconfig.get_paths()["stdlib"]
    out = sys.argv[3] if len(sys.argv) > 3 else "build/import-sweep.json"
    env = dict(os.environ, PYSTACHY_PATH=lib)
    res = {}
    with tempfile.TemporaryDirectory() as d:
        prog = os.path.join(d, "prog.py")
        for m in modules(lib):
            with open(prog, "w") as f:
                f.write(f"import {m}\n")
            p = subprocess.run([pys, "ir", prog, "-o", os.devnull], capture_output=True, text=True, env=env, timeout=120)
            err = p.stderr.strip().splitlines()
            res[m] = "OK" if p.returncode == 0 else (err[-1].replace(d + "/", "") if err else f"exit {p.returncode}")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    ok = sorted(m for m, v in res.items() if v == "OK")
    print(f"{len(ok)} of {len(res)} modules import: {' '.join(ok)}\n")
    why = collections.Counter()
    for m, v in res.items():
        if v != "OK":
            msg = v.split("error: ", 1)[-1]
            if "is not supported: it is not a builtin module" in msg:
                msg = "imports the missing module " + msg.split("'")[1]
            why[msg[:100]] += 1
    for k, n in why.most_common(30):
        print(f"{n:5}  {k}")


main()
