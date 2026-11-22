"""Native frontend time (`pystachy ir`) per release, and a compiler-by-source crossover, on the idle machine.

usage: python3.13 -I frontend_series.py OUT.json
Series: each commit's compiler on its own source, v0.6.0-alpha.1 to v0.7.0-alpha.2, two interleaved runs.
Crossover: v0.6.0-alpha.1's and v0.7.0-alpha.2's compilers on each other's source (three runs each), to tell a
slower compiler from a source that costs more to compile.
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
LABS = ["1117-1034_3cf23d20", "1117-2325_e2b97bb4", "1118-1050_8259611e", "1118-2319_d35417c9", "1119-1826_299d12ad",
        "1119-2044_817c9cd9", "1119-2352_37512410", "1120-1407_41dffd36", "1121-1151_4998521d"]
env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
env["PYSTACHY_PROGRAM_CACHE"] = "0"
tmp = Path(tempfile.mkdtemp(prefix="fe.", dir=S))


def run(compiler_lab, source_lab):
    t0 = time.perf_counter()
    p = subprocess.run([str(S / "wt" / compiler_lab / "pystachy"), "ir", "pystachy.py", "-o", str(tmp / "o.ll")],
                       cwd=S / "wt" / source_lab, env=env, capture_output=True)
    return {"ok": p.returncode == 0, "wall_s": round(time.perf_counter() - t0, 2),
            **({} if p.returncode == 0 else {"error": p.stderr.decode(errors="replace")[-300:]})}


out = {"series": {l: [] for l in LABS}, "cross": {}}
for order in (LABS, LABS[::-1]):
    for l in order:
        out["series"][l].append(run(l, l))
        print(l, out["series"][l][-1], flush=True)
P, H = LABS[0], LABS[-1]
for c, s in ((P, P), (H, H), (H, P), (P, H)) * 3:
    out["cross"].setdefault(f"{c} on {s}", []).append(run(c, s))
json.dump(out, open(sys.argv[1], "w"), indent=1)
for k, v in out["cross"].items():
    print(k, [(x["wall_s"], x["ok"]) for x in v], v[0].get("error", "")[:200])
for f in tmp.iterdir():
    f.unlink()
tmp.rmdir()
