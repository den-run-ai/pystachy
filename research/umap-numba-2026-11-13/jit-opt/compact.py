"""Compact jit_variants.py and cache_hits.py outputs into one results file for bench/results/.

usage: compact.py CHECKOUT RESULTS_DIR HITS_DIR OUT.json
"""

import hashlib
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

checkout, results, hits, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
WORK = Path("/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/jitopt-meas/work")
ORDER = ["tiny", "padded", "imports", "router", "umap", "nbody", "spectral", "mandel", "sieve", "fib", "dictcount",
         "words", "pp_chaos", "pp_float", "pp_nbody", "pp_raytrace", "pp_scimark", "pp_spectral_norm", "pp_fannkuch",
         "pp_nqueens", "pp_regex_dna", "pp_regex_effbot", "pp_regex_v8", "pp_richards", "pp_go", "pp_hexiom",
         "pp_json_loads", "pp_json_dumps", "pp_generators", "long_richards", "long_regex_effbot", "long_regex_v8",
         "long_go", "long_json_loads", "long_chaos", "long_raytrace", "long_scimark", "long_nbody", "long_generators"]
HITS = ["richards", "regex_effbot", "regex_v8", "generators", "nbody", "raytrace", "imports", "umap"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display(arg: str) -> str:
    # (the measurement's scratch inputs by name: their contents are hashed below)
    return arg.replace(str(WORK) + "/", "")


def compile_s(r: dict) -> float:
    return r.get("driver.prepare_run", 0.0) + r.get("program.jit_load", 0.0) + r.get("program.jit_codegen", 0.0)


def slim(r: dict) -> dict:
    row = {"wall_s": round(r["wall"], 4), "jit_optimize_s": round(r.get("program.jit_optimize", 0.0), 4),
           "compile_s": round(compile_s(r), 4), "peak_rss_mib": round(r["peak_rss_mib"], 1)}
    for k, v in r.items():
        if k.startswith("timer."):
            row[k.removeprefix("timer.") + "_s"] = round(v, 4)
    return row


def ratio(a: list[dict], b: list[dict], key: str) -> float:
    return round(statistics.median(y[key] / x[key] for x, y in zip(a, b, strict=True) if x[key] > 0), 3)


inputs = {}
for path in sorted(WORK.iterdir()):
    inputs[path.name] = sha(path)
for name in ["examples/route/route.py"] + sorted(str(p.relative_to(checkout)) for p in (checkout / "bench").glob("*.py")) + \
        sorted(str(p.relative_to(checkout)) for p in (checkout / "bench/pyperformance").glob("*.py")):
    inputs[name] = sha(checkout / name)
uncached = []
for name in ORDER:
    data = json.loads((results / f"{name}.json").read_text())
    d = [slim(r) for r in data["runs"]["default"]]
    o = [slim(r) for r in data["runs"]["opt2"]]
    keys = [k for k in d[0] if k not in ("peak_rss_mib",)]
    uncached.append({
        "workload": name, "command": ["pystachy", "run", *[display(a) for a in data["program"]]], "rounds": data["rounds"],
        "median": {"default": {k: round(statistics.median(r[k] for r in d), 4) for k in d[0]},
                   "opt2": {k: round(statistics.median(r[k] for r in o), 4) for k in o[0]}},
        "paired_ratio_opt2_to_default": {k: ratio(d, o, k) for k in keys},
        "runs": {"default": d, "opt2": o}})
cached = []
for name in HITS:
    data = json.loads((hits / f"{name}.json").read_text())
    hd = [{k.removeprefix("timer.") + ("_s" if k != "wall" else "_s"): round(v, 4) for k, v in r.items()} for r in data["hits"]["default"]]
    ho = [{k.removeprefix("timer.") + ("_s" if k != "wall" else "_s"): round(v, 4) for k, v in r.items()} for r in data["hits"]["opt2"]]
    cached.append({
        "workload": name, "command": ["pystachy", "run", *[display(a) for a in data["program"]]], "rounds": data["rounds"],
        "hit_median": {"default": {k: round(statistics.median(r[k] for r in hd), 4) for k in hd[0]},
                       "opt2": {k: round(statistics.median(r[k] for r in ho), 4) for k in ho[0]}},
        "hit_paired_ratio_opt2_to_default": {k: ratio(hd, ho, k) for k in hd[0]},
        "hits": {"default": hd, "opt2": ho}})
cpu = next((line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo") if line.startswith("model name")), "")
llvm = subprocess.run(["/usr/lib/llvm-18/bin/opt", "--version"], capture_output=True, text=True).stdout
commit = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
report = {
    "schema_version": 1,
    "measurement": ("pystachy run with the JIT's cleanup (PYSTACHY_JIT_OPT unset) against LLVM's -O2 pipeline "
                    "(PYSTACHY_JIT_OPT=2). Uncached: the program cache off (PYSTACHY_PROGRAM_CACHE=0), so every run "
                    "compiles; rounds interleaved in rotating order, each run pinned to one CPU (taskset -c 1), "
                    "PYSTACHY_TIMING=1. Hits: the program cache on, in a private cache seeded with the runtime "
                    "artifacts, one traced miss per variant (not reported: a private cache's first miss also builds "
                    "the runtime's shared artifacts), then interleaved traced hits. Every run printed CPython "
                    "3.13's output."),
    "fields": {"wall_s": "the launch's wall time, start to exit", "jit_optimize_s": "PYSTACHY_TIMING program.jit_optimize (opt)",
               "compile_s": "driver.prepare_run (frontend, typed-IR passes, opt) + program.jit_load + program.jit_codegen",
               "peak_rss_mib": "wait4's ru_maxrss: the largest process (driver, opt or the JIT runner)",
               "knn_s, layout_s": "the UMAP probe's own stage timers (execution only)",
               "loop_s": "a pyperformance port's timed loop (execution only)"},
    "measured_commit": commit, "base_commit": "5f81cc2563d231501952104e991d858e670325ac",
    "native_compiler_sha256": sha(checkout / "pystachy"),
    "platform": platform.platform(), "cpu": cpu, "python": platform.python_version(),
    "llvm": next(line.strip() for line in llvm.splitlines() if "LLVM version" in line),
    "inputs_sha256": inputs,
    "input_notes": ("tiny.py, padded.py, imports.py, rules.txt and events.txt are tools/program_cache_probe.py's "
                    "benchmark() workloads; umap_core.py is research/umap-numba-2026-11-13/umap_core.py of "
                    "branch claude/dreamy-shannon-bb3cu1 at bc2df5cd, run as 10000 16 10 15 200 7"),
    "uncached": uncached, "cache_hits": cached,
}
out.write_text(json.dumps(report, indent=1) + "\n")
print(f"{out}: {out.stat().st_size} bytes, {len(uncached)} uncached workloads, {len(cached)} cached")
