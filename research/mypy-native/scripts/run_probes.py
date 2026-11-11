"""Run each probe under CPython and Pystachy (JIT); classify PASS / MISMATCH / REJECT / CPY-FAIL."""
import json, os, re, subprocess, sys
probes, compiler, out = sys.argv[1], sys.argv[2], sys.argv[3]
res = {}
for f in sorted(os.listdir(probes)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(probes, f)
    c = subprocess.run([sys.executable, "-I", p], capture_output=True, text=True, timeout=60)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    try:
        n = subprocess.run([compiler, "run", p], capture_output=True, text=True, timeout=180, env=env)
        nout, nerr, nrc = n.stdout, n.stderr, n.returncode
    except subprocess.TimeoutExpired:
        nout, nerr, nrc = "", "TIMEOUT", -1
    if c.returncode != 0:
        status = "CPY-FAIL"; detail = c.stderr.strip().splitlines()[-1]
    elif nrc == 0 and nout == c.stdout:
        status = "PASS"; detail = c.stdout.strip()[:80]
    elif nrc == 0:
        status = "MISMATCH"; detail = f"cpython={c.stdout.strip()!r} pystachy={nout.strip()!r}"
    else:
        first = (nerr.strip().splitlines() or [""])[0]
        first = re.sub(r"^\S+?:(\d+): error: ", r"L\1: ", first)
        status = "REJECT" if (nerr.strip() and "error:" in nerr.strip().splitlines()[0]) else "RUNFAIL"
        detail = first[:230]
    res[f[:-3]] = {"status": status, "detail": detail}
    print(f"{f[:-3]:36s} {status:9s} {detail}")
json.dump(res, open(out, "w"), indent=1)
import collections
print(collections.Counter(v["status"] for v in res.values()))
