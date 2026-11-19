"""Compose bench/results/jit-host-cpu-2026-11-19.json from variants2.py's outputs."""
import json
import statistics
import sys

SP = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad"


def summarize(path, keys):
    d = json.load(open(path))
    runs, rounds = d["runs"], d["rounds"]
    out = {}
    for name in runs:
        out[name] = {}
        for k in keys:
            med = statistics.median(row[k] for row in runs[name])
            paired = statistics.median(runs[name][j][k] / runs["generic"][j][k] for j in range(rounds))
            out[name][k] = {"median": round(med, 4), "paired": round(paired, 3)}
    return d["rounds"], out


result = {
    "notes": ("The JIT tier compiling for the host's CPU (this branch's default, PYSTACHY_JIT_CPU=native: opt "
              "-mcpu=native names it and its features on each function) against the module target's default CPU "
              "(PYSTACHY_JIT_CPU=generic, x86-64's SSE2), on this branch (claude/dreamy-shannon-bb3cu1-jit-host-cpu, "
              "stacked on #1571 and #1540, main 8259611e). variants.py: interleaved rounds, rotating order, each run "
              "pinned to CPU 1 with taskset, PYSTACHY_PROGRAM_CACHE=0, PYSTACHY_TIMING=1; every run's stdout is the "
              "first variant's. run: wall seconds less the driver's preparation and the runner's code generation; "
              "jit_optimize and jit_codegen: the driver's stage records. saxpy and scale run listguard's copy of "
              "y[i] = a * x[i] + y[i] and y[i] = x[i] * 3.0 over 1,000 items (in L1) 400,000 times. x86-64 (Intel "
              "Xeon @ 2.10GHz, AVX-512, which LLVM calls sapphirerapids and tunes to 256-bit vectors; 4 CPUs, shared "
              "host), LLVM 18.1.3."),
    "kernels": {}, "programs": {},
}
for k in ("saxpy", "scale"):
    rounds, s = summarize(f"{SP}/meas/var-cpu-{k}.json", ("run", "wall", "jit_optimize", "jit_codegen"))
    result["kernels"][k] = {"rounds": rounds, "args": [f"k/{k}.py", "1000", "400000"], "variants": s}
for p in ("scimark", "nbody", "spectral_norm", "raytrace", "json_loads", "chaos"):
    rounds, s = summarize(f"{SP}/meas/var-cpu-pp-{p}{'11' if p == 'scimark' else ''}.json", ("wall", "run", "jit_optimize", "jit_codegen"))
    result["programs"][f"bench/pyperformance/{p}.py"] = {"rounds": rounds, "variants": s}
result["sources"] = {k: open(f"{SP}/simd/k/{k}.py").read() for k in ("saxpy", "scale")}
json.dump(result, open(sys.argv[1], "w"), indent=1)
print(json.dumps({k: {n: v["run"]["paired"] for n, v in r["variants"].items()} for k, r in result["kernels"].items()}))
print(json.dumps({k: {n: (v["wall"]["paired"], v["jit_codegen"]["paired"]) for n, v in r["variants"].items()} for k, r in result["programs"].items()}))
