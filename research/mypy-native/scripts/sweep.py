"""Compile 'import M' per module with Pystachy; record the first diagnostic. Probe only: IR emission, not execution."""
import concurrent.futures, collections, json, os, re, subprocess, sys, tempfile

compiler, out, paths, roots = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
SKIP = {"test", "typeshed", "test-data", "lib-rt", "doc", "external", "__pycache__"}

def modules(base, pkg):
    res = []
    for dp, dn, fn in os.walk(os.path.join(base, pkg)):
        dn[:] = sorted(d for d in dn if d not in SKIP)
        for f in sorted(fn):
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(dp, f), base)[:-3].replace(os.sep, ".")
                if rel.endswith(".__init__"):
                    rel = rel[:-9]
                if not rel.endswith("__main__"):
                    res.append(rel)
    return res

def one(m):
    with tempfile.TemporaryDirectory() as d:
        prog = os.path.join(d, "prog.py")
        open(prog, "w").write(f"import {m}\n")
        env = dict(os.environ, PYSTACHY_PATH=paths)
        try:
            p = subprocess.run([compiler, "ir", prog, "-o", os.path.join(d, "p.ll")], env=env, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return m, "TIMEOUT"
        if p.returncode == 0:
            return m, "OK"
        return m, (p.stderr.strip() or p.stdout.strip() or f"exit {p.returncode}")[-1500:]

mods = []
for r in roots:
    base, pkg = os.path.split(r.rstrip("/"))
    mods += modules(base, pkg)
with concurrent.futures.ThreadPoolExecutor(3) as ex:
    res = dict(ex.map(one, mods))
json.dump(res, open(out, "w"), indent=1, sort_keys=True)

def norm(e):
    e = e.splitlines()[0] if e else e
    e = re.sub(r"^\S+?:\d+: error: ", "", e)
    e = re.sub(r"module '([\w.]+)' is not supported: it is not a builtin module.*", r"missing module \1", e)
    return e[:150]

ok = [m for m, v in res.items() if v == "OK"]
print(f"{len(ok)} of {len(res)} modules import")
c = collections.Counter(norm(v) for v in res.values() if v != "OK")
for k, v in c.most_common(60):
    print(f"{v:5d}  {k}")
