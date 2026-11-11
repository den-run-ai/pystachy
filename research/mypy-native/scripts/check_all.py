import collections, os, subprocess, sys, concurrent.futures, re, time
compiler, root, ext = sys.argv[1], sys.argv[2], sys.argv[3]
files = []
for dp, dn, fn in os.walk(root):
    dn[:] = sorted(d for d in dn if d not in ("__pycache__", "test-data", "lib-rt"))
    files += [os.path.join(dp, f) for f in sorted(fn) if f.endswith(ext)]
def one(f):
    src = f
    if ext == ".pyi":
        return f, None
    p = subprocess.run([compiler, "check", f], capture_output=True, text=True, timeout=120)
    return f, None if p.returncode == 0 else (p.stderr.strip().splitlines() or ["?"])[0]
t = time.time()
with concurrent.futures.ThreadPoolExecutor(3) as ex:
    res = list(ex.map(one, files))
bad = [(f, e) for f, e in res if e]
print(f"{len(res) - len(bad)} of {len(res)} {ext} files pass 'pystachy check' in {time.time() - t:.1f}s")
c = collections.Counter(re.sub(r"^\S+?:\d+: error: ", "", e)[:110] for f, e in bad)
for k, v in c.most_common(12): print(f"{v:4d}  {k}")
for f, e in bad[:6]: print("   ", os.path.relpath(f, root), "|", e[-160:])
