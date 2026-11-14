# usage: optin_stdlib.py LIBDIR OUTDIR : copies LIBDIR's .py files, less the directories that
# tools/import_sweep.py skips, into OUTDIR with "# pystachy: dynamic-any" as each one's first line,
# so that 'tools/import_sweep.py COMPILER OUTDIR' sweeps the same modules with every one opted in
import os
import sys

SKIP = ("test", "tests", "idlelib", "tkinter", "turtledemo", "site-packages", "dist-packages", "lib2to3", "ensurepip", "venv", "__pycache__")
src, dst = sys.argv[1], sys.argv[2]
n = 0
for dp, dn, fn in os.walk(src):
    dn[:] = [d for d in dn if d not in SKIP and not d.startswith(".")]
    for f in fn:
        if f.endswith(".py"):
            rel = os.path.relpath(os.path.join(dp, f), src)
            os.makedirs(os.path.join(dst, os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(dp, f), "rb") as i, open(os.path.join(dst, rel), "wb") as o:
                o.write(b"# pystachy: dynamic-any\n" + i.read())
            n += 1
print(n, "files copied with the comment")
