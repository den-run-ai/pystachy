"""Executed instructions (callgrind) of the executables perfab.py built, per benchmark and compiler.

usage: python3.13 -I cgab.py OUT.json BASE_CHECKOUT LABEL... -- BENCH...
"""
import json, re, subprocess, sys
from pathlib import Path
S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
args = sys.argv[1:]
out, base = args[0], Path(args[1])
rest = args[2:]
labels = rest[:rest.index("--")] if "--" in rest else rest
specs = json.load(open(S / "sweep/perf_specs.json"))
specs.update({"hello": {"args": []}, "imports": {"args": []}})
names = rest[rest.index("--") + 1:] if "--" in rest else list(specs)
res = {}
for b in names:
    argv = [a.replace(str(S / "sweep/perfroot"), str(base)) for a in specs[b]["args"]]
    res[b] = {}
    for lab in labels:
        exe = S / "ab/exe" / f"{b}.{lab}"
        f = S / f"ab/cg/{b}.{lab}.out"
        p = subprocess.run(["valgrind", "--tool=callgrind", f"--callgrind-out-file={f}", str(exe)] + argv,
                           cwd=base, capture_output=True, text=True)
        m = re.search(r"Collected : (\d+)", p.stderr)
        res[b][lab] = int(m.group(1)) if m and p.returncode == 0 else None
        f.unlink(missing_ok=True)
    a, c = res[b].get(labels[0]), res[b].get(labels[-1])
    print(f"{b:16s} " + " ".join(f"{lab} {res[b][lab]}" for lab in labels) + (f"  {100 * (c - a) / a:+.2f}%" if a and c else ""), flush=True)
    json.dump(res, open(out, "w"), indent=1)
