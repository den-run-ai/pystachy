"""Run a checkout's compiler under CPython on its own source and log where each inference retry (Rejoin) starts.

usage: python3.13 -I rejoin_sites.py CHECKOUT
Patches pystachy_compiler.diagnostics.Rejoin.__init__ to record the innermost compiler frames at each raise
and the source line being compiled when the frames expose it. Compilation output goes to a temporary file.
"""
import os, runpy, sys, tempfile, traceback
wt = os.path.abspath(sys.argv[1])
sys.path.insert(0, wt)
os.chdir(wt)
import src.pystachy_compiler.diagnostics as diag  # noqa: E402
sites = []
orig = diag.Rejoin.__init__


def init(self, *a, **k):
    st = traceback.extract_stack()[:-1]
    inner = [f"{os.path.basename(f.filename)}:{f.lineno} {f.name}" for f in st if "pystachy_compiler" in f.filename][-6:]
    node = None
    fr = sys._getframe(1)
    for _ in range(40):
        if fr is None:
            break
        for v in ("node", "stmt", "expr", "n"):
            x = fr.f_locals.get(v)
            if hasattr(x, "lineno"):
                node = (type(x).__name__, getattr(x, "lineno", None))
                break
        if node:
            break
        fr = fr.f_back
    info = {}
    fr = sys._getframe(1)
    for _ in range(10):
        if fr is None:
            break
        if fr.f_code.co_name in ("gen_err", "gen_discover_program"):
            g = fr.f_locals.get("self")
            info["msg"] = str(fr.f_locals.get("msg"))[:300]
            hints = getattr(g, "newhints", {}) or {}
            info["newhints"] = [f"{k!s:.120} -> {v!s:.80}" for k, v in list(hints.items())[:6]]
            info["n_newhints"] = len(hints)
            cf = getattr(g, "curfn", None)
            info["curfn"] = str(getattr(cf, "name", cf))[:120]
            for attr in ("lineno", "line", "curline", "srcline", "loc"):
                if hasattr(g, attr):
                    info[attr] = str(getattr(g, attr))[:120]
            break
        fr = fr.f_back
    sites.append((inner, node, info))
    orig(self, *a, **k)


diag.Rejoin.__init__ = init
out = tempfile.mktemp(suffix=".ll")
sys.argv = ["pystachy.py", "ir", "pystachy.py", "-o", out]
try:
    runpy.run_path(os.path.join(wt, "pystachy.py"), run_name="__main__")
except SystemExit as e:
    print("exit", e.code)
finally:
    if os.path.exists(out):
        os.unlink(out)
print(len(sites), "Rejoin raised")
for inner, node, info in sites:
    print("  node", node)
    for k, v in info.items():
        print("    ", k, "=", v)
    for f in inner[-3:]:
        print("    ", f)
