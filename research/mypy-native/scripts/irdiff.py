"""Compare `ir` output of two compilers over the irsame corpus, normalizing string constants
that embed a library path (REF's build/ref/lib vs lib). Prints programs whose IR still differs."""
import concurrent.futures, os, re, subprocess, sys
old, new = sys.argv[1], sys.argv[2]
files = [l.strip() for l in open(sys.argv[3])]
PATHC = re.compile(r'^(@s\.\d+) = .*c"[^"]*/lib/[^"]*".*$')
def norm(text):
    return "\n".join(PATHC.sub(r"\1 = <libpath>", l) for l in text.splitlines())
def run(comp, f, out):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    path = f[:-3] + ".path"
    if os.path.exists(path):
        env["PYSTACHY_PATH"] = open(path).read().strip()
    mode = "rt" if f == "runtime.py" or "/rtmode_" in f else "ir"
    r = subprocess.run([comp, mode, f, "-o", out], capture_output=True, text=True, env=env)
    text = open(out).read() if r.returncode == 0 and os.path.exists(out) else ""
    return r.returncode, r.stderr.replace("build/ref/lib/", "lib/").replace(os.getcwd() + "/", ""), text
def one(f):
    tag = f.replace("/", "_")
    a = run(old, f, f"/tmp/irdiff_old_{tag}.ll")
    b = run(new, f, f"/tmp/irdiff_new_{tag}.ll")
    for p in (f"/tmp/irdiff_old_{tag}.ll", f"/tmp/irdiff_new_{tag}.ll"):
        if os.path.exists(p): os.remove(p)
    if a[0] != b[0] or a[1] != b[1]:
        return f, "status/messages"
    if norm(a[2]) != norm(b[2]):
        return f, "ir"
    return f, ""
diffs = []
with concurrent.futures.ThreadPoolExecutor(4) as ex:
    for f, why in ex.map(one, files):
        if why:
            diffs.append((f, why))
            print("DIFF", why, f, flush=True)
print(len(diffs), "of", len(files), "differ after normalizing library-path constants")
