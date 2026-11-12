"""Paired AOT comparison of two compilers: build time and execution time per benchmark.

usage: python3.13 -I perfab.py OUT.json BUILDREPS RUNREPS LABEL=CHECKOUT... [-- BENCH...]
Each checkout's ./pystachy builds every benchmark BUILDREPS times (PYSTACHY_PROGRAM_CACHE=0,
the runtime cache warm), builds rotated between compilers, pinned to CPU 3; then the executables
run RUNREPS times each, interleaved and rotated, pinned to CPU 3. Outputs must equal CPython's.
Ports report their 'seconds' line; other programs process wall time.
"""
import json, os, re, statistics, subprocess, sys, time
from pathlib import Path
S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
args = sys.argv[1:]
out, breps, rreps = args[0], int(args[1]), int(args[2])
rest = args[3:]
only = []
if "--" in rest:
    only = rest[rest.index("--") + 1:]
    rest = rest[:rest.index("--")]
comps = dict(a.split("=", 1) for a in rest)
specs = json.load(open(S / "sweep/perf_specs.json"))
base = Path(list(comps.values())[0])
extra = {
    "hello": {"src": str(S / "ab/hello.py"), "args": [], "kind": "micro"},
    "imports": {"src": str(S / "ab/imports.py"), "args": [], "kind": "micro"},
}
specs.update(extra)
names = only or list(specs)
env = dict(os.environ, PYSTACHY_PROGRAM_CACHE="0")
for k in ["PYSTACHY_TIMING", "PYSTACHY_CFLAGS", "PYSTACHY_CACHE"]:
    env.pop(k, None)
res = {}
exe_dir = S / "ab/exe"
exe_dir.mkdir(parents=True, exist_ok=True)
for b in names:
    spec = specs[b]
    src = spec["src"] if spec["src"].startswith("/") else str(base / spec["src"])
    argv = [a.replace(str(S / "sweep/perfroot"), str(base)) for a in spec["args"]]
    ref = subprocess.run(["/usr/local/bin/python3.13", "-I", src] + argv, cwd=base, capture_output=True, text=True)
    assert ref.returncode == 0, (b, ref.stderr[-300:])
    builds = {lab: [] for lab in comps}
    labs = list(comps)
    for r in range(breps):
        order = labs[r % len(labs):] + labs[:r % len(labs)]
        for lab in order:
            exe = exe_dir / f"{b}.{lab}"
            t0 = time.perf_counter()
            p = subprocess.run(["taskset", "-c", "3", str(Path(comps[lab]) / "pystachy"), "build", src, "-o", str(exe)],
                               cwd=comps[lab], capture_output=True, text=True, env=env)
            builds[lab].append(time.perf_counter() - t0)
            assert p.returncode == 0, (b, lab, p.stderr[-500:])
    runs = {lab: [] for lab in comps}
    for r in range(rreps):
        order = labs[r % len(labs):] + labs[:r % len(labs)]
        for lab in order:
            t0 = time.perf_counter()
            p = subprocess.run(["taskset", "-c", "3", str(exe_dir / f"{b}.{lab}")] + argv, cwd=base, capture_output=True, text=True)
            wall = time.perf_counter() - t0
            assert p.returncode == 0 and p.stdout == ref.stdout, (b, lab, p.stdout[-200:], p.stderr[-200:])
            found = re.findall(r"^seconds (\S+)$", p.stderr, re.M)
            runs[lab].append(float(found[0]) if len(found) == 1 else wall)
    sizes = {lab: (exe_dir / f"{b}.{lab}").stat().st_size for lab in labs}
    res[b] = {"kind": spec["kind"], "build_s": builds, "run_s": runs, "exe_bytes": sizes}
    line = f"{b:16s}"
    for lab in labs:
        line += f" | {lab}: build {statistics.median(builds[lab]):6.3f} s run {statistics.median(runs[lab]) * 1000:9.2f} ms ({min(runs[lab]) * 1000:.2f}-{max(runs[lab]) * 1000:.2f}) {sizes[lab]} B"
    print(line, flush=True)
    json.dump({"build_reps": breps, "run_reps": rreps, "cpu": 3, "compilers": comps, "results": res}, open(out, "w"), indent=1)
