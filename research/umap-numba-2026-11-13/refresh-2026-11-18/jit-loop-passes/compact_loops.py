"""Compact final.sh's jit_variants.py outputs (and bench_loops.py's UMAP run) into one bench/results file.

usage: compact_loops.py CHECKOUT RESULTS_DIR UMAP.json CALLGRIND.tsv OUT.json
"""
import hashlib
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

checkout, results, umap, cg, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
WORK = Path("/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/jitopt-meas/work")
ORDER = ["tiny", "padded", "imports", "router", "nbody", "spectral", "mandel", "sieve", "fib", "dictcount", "words",
         "pp_chaos", "pp_float", "pp_nbody", "pp_raytrace", "pp_scimark", "pp_spectral_norm", "pp_fannkuch", "pp_nqueens",
         "pp_regex_v8", "pp_richards", "pp_go", "pp_hexiom", "pp_json_loads", "pp_json_dumps", "pp_generators",
         "long_richards", "long_regex_effbot", "long_go", "long_json_loads", "long_chaos", "long_raytrace", "long_scimark",
         "long_nbody", "long_generators"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display(arg: str) -> str:
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


inputs = {path.name: sha(path) for path in sorted(WORK.iterdir()) if path.name != "umap_core.py"}
for name in ["examples/route/route.py"] + sorted(str(p.relative_to(checkout)) for p in (checkout / "bench").glob("*.py")) + \
        sorted(str(p.relative_to(checkout)) for p in (checkout / "bench/pyperformance").glob("*.py")):
    inputs[name] = sha(checkout / name)
uncached = []
for name in ORDER:
    data = json.loads((results / f"{name}.json").read_text())
    c = [slim(r) for r in data["runs"]["cleanup"]]
    d = [slim(r) for r in data["runs"]["default"]]
    keys = [k for k in c[0] if k != "peak_rss_mib"]
    uncached.append({
        "workload": name, "command": ["pystachy", "run", *[display(a) for a in data["program"]]], "rounds": data["rounds"],
        "median": {"cleanup": {k: round(statistics.median(r[k] for r in c), 4) for k in c[0]},
                   "default": {k: round(statistics.median(r[k] for r in d), 4) for k in d[0]}},
        "paired_ratio_default_to_cleanup": {k: ratio(c, d, k) for k in keys},
        "runs": {"cleanup": c, "default": d}})
u = json.loads(umap.read_text())
stack = {"rounds": u["rounds"], "args": u["args"],
         "median": {v: {k: round(statistics.median(r[k] for r in rows), 4) for k in rows[0] if isinstance(rows[0][k], float)}
                    for v, rows in u["runs"].items()},
         "paired_ratio_loops_to_cleanup": {k: round(statistics.median(b[k] / a[k] for a, b in zip(u["runs"]["stack-jit"], u["runs"]["stack-jit-loops"])), 3)
                                           for k in ("knn", "layout")},
         "runs": u["runs"]}
counts: dict[str, dict[str, int]] = {}
for line in cg.read_text().splitlines():
    name, variant, ir = line.split("\t")
    counts.setdefault(name, {})[variant] = int(ir)
CG_ARGS = {"json_loads": "200", "chaos": "10", "richards": "20", "nbody": "10", "raytrace": "4", "go": "4", "scimark": "2",
           "hexiom": "20", "generators": "10", "float": "10", "fannkuch": "2", "nqueens": "10", "spectral_norm": "10",
           "json_dumps": "20", "regex_v8": "2"}
callgrind = [{"workload": n, "command": ["pystachy", "run", f"bench/pyperformance/{n}.py", CG_ARGS[n]],
              "instructions": c, "ratio_default_to_cleanup": round(c["default"] / c["cleanup"], 4)} for n, c in counts.items()]
cpu = next((line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo") if line.startswith("model name")), "")
llvm = subprocess.run(["/usr/lib/llvm-18/bin/opt", "--version"], capture_output=True, text=True).stdout
commit = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
report = {
    "schema_version": 1,
    "measurement": ("pystachy run with the JIT's cleanup alone (PYSTACHY_JIT_OPT=0) against the default, which follows "
                    "it with loop passes for a program within the inlining budget (PYSTACHY_JIT_OPT unset). The program "
                    "cache off (PYSTACHY_PROGRAM_CACHE=0), so every run compiles; rounds interleaved in rotating order, "
                    "each run pinned to one CPU (taskset -c 1), PYSTACHY_TIMING=1. Every run printed CPython 3.13's "
                    "output."),
    "fields": {"wall_s": "the launch's wall time, start to exit", "jit_optimize_s": "PYSTACHY_TIMING program.jit_optimize (opt)",
               "compile_s": "driver.prepare_run (frontend, typed-IR passes, opt) + program.jit_load + program.jit_codegen",
               "peak_rss_mib": "wait4's ru_maxrss: the largest process (driver, opt or the JIT runner)",
               "loop_s": "a pyperformance port's timed loop (execution only)"},
    "measured_commit": commit, "base_commit": "ed0c46e06896ab74178281cec5633ef51ddbca5f",
    "native_compiler_sha256": sha(checkout / "pystachy"),
    "platform": platform.platform(), "cpu": cpu, "python": platform.python_version(),
    "llvm": next(line.strip() for line in llvm.splitlines() if "LLVM version" in line),
    "inputs_sha256": inputs,
    "input_notes": "tiny.py, padded.py, imports.py, rules.txt and events.txt are tools/program_cache_probe.py's benchmark() workloads",
    "uncached": uncached,
    "callgrind": {"notes": ("Instructions executed (callgrind's Ir) by the program cache's executable of each program, built from "
                            "the module the JIT tier runs, in a private cache per variant; every run printed CPython's output. "
                            "regex_v8's module is over the inlining budget, so the loop passes do not run on it."),
                  "rows": callgrind},
    "draft_stack_umap": {
        "notes": ("The UMAP probe (research/umap-numba-2026-11-13/umap_core.py of branch claude/dreamy-shannon-bb3cu1, run as "
                  "10000 16 10 15 200 7) on a local merge of main 3cf23d20 with drafts #1437, #1449, #1456, #1455, #1450, "
                  "#1468, #1477, #1442 and #1436 (d0aa2934): stack-jit is its JIT cleanup, stack-jit-loops the same with this "
                  "change's passes spliced in by a wrapper of opt, stack-jit-O2 PYSTACHY_JIT_OPT=2, stack-aot its AOT "
                  "executable; Numba 0.68.1 (strict IEEE order, NUMBA_NUM_THREADS=1, warm call). knn and layout are the "
                  "probe's stage timers in seconds; every Pystachy run printed the recorded output."),
        **stack},
}
out.write_text(json.dumps(report, indent=1) + "\n")
print(f"{out}: {out.stat().st_size} bytes, {len(uncached)} uncached workloads")
