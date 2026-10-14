"""Run the type-feedback census (tools/typeprofile.py) over a corpus of ordinary Python programs.

usage: python3 tools/typeprofile_corpus.py OUTDIR [--python PY] [--jobs N] [--only NAME,...]
                                           [--eligibility ADAPTIVE.py] [--report-only]

PY (default: this interpreter) must have the packages of tools/typeprofile-requirements.txt:
- pyperformance 1.14.0's benchmarks that need no service, compiler or network, plus the pure-Python
  applications it pins (docutils, html5lib, genshi, sqlglot, networkx, chameleon, sympy, tomli).
  Each runs once, in-process, through a stand-in for pyperf;
- the upstream releases of the libraries under ports/, running the ports' differential workloads
  (tests/port_*.py). A workload counts only if its output matches the CPython output recorded in
  tests/; the rest are listed as skipped;
- Pystachy's CPython-hosted compiler compiling tests/algorithms.py: code in the typed subset,
  a positive control whose types must all be stable and expressible.
Each program is recorded, then timed by cProfile in a second process. OUTDIR receives NAME.json,
NAME.time.json, NAME.log, corpus.json and summary.json; the report is printed. --report-only
reports an earlier run in OUTDIR again.
"""
import concurrent.futures
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "typeprofile.py")

# Benchmarks that are services, subprocesses, C-library drivers or startup timers are left out:
# their Python code is a thin layer over something else, or there is nothing to profile in-process.
BENCHMARKS = [
    "async_generators", "base64", "bpe_tokeniser", "chameleon", "chaos", "comprehensions", "coroutines",
    "crypto_pyaes", "deepcopy", "deltablue", "docutils", "fannkuch", "float", "generators", "genshi", "go",
    "hexiom", "html5lib", "json_dumps", "json_loads", "logging", "mdp", "meteor_contest", "nbody", "nqueens",
    "pathlib", "pidigits", "pprint", "pyflate", "raytrace", "regex_compile", "regex_dna", "regex_effbot",
    "regex_v8", "richards", "richards_super", "scimark", "spectral_norm", "sympy", "telco", "tomli_loads",
    "typing_runtime_protocols", "unpack_sequence", "xml_etree",
]
# Benchmarks whose script runs one of several workloads: pyperformance's extra_opts for each.
VARIANTS = {
    "argparse": [["many_optionals"], ["subparsers"]],
    "async_tree": [["none"]],
    "networkx": [["shortest_path"], ["connected_components"], ["k_core"]],
    "pickle": [["--pure-python", "pickle"], ["--pure-python", "unpickle"]],
    "sqlglot_v2": [["parse"], ["transpile"], ["optimize"], ["normalize"]],
}

SHIM = '''"""In-process stand-in for pyperf: each benchmark function runs once, with no worker processes."""
import argparse
import asyncio
import sys
import time

perf_counter = time.perf_counter


def python_implementation():
    return "cpython"


class Runner:
    def __init__(self, *args, add_cmdline_args=None, **kwargs):
        self.metadata = {}
        self.argparser = argparse.ArgumentParser()
        self._args = None

    @property
    def args(self):
        if self._args is None:
            self._args = self.argparser.parse_args(sys.argv[1:])
        return self._args

    def parse_args(self, args=None):
        self._args = self.argparser.parse_args(sys.argv[1:] if args is None else args)
        return self._args

    def bench_func(self, name, func, *args, inner_loops=None, metadata=None):
        func(*args)

    def bench_time_func(self, name, time_func, *args, inner_loops=None, metadata=None):
        time_func(1, *args)

    def bench_async_func(self, name, func, *args, inner_loops=None, metadata=None):
        asyncio.run(func(*args))

    def bench_command(self, name, command):
        pass
'''


def corpus(python):
    found = subprocess.run([python, "-c", "import pyperformance, os; print(os.path.dirname(pyperformance.__file__))"],
                           capture_output=True, text=True, check=True).stdout.strip()
    benchmarks = os.path.join(found, "data-files", "benchmarks")
    programs = [{"name": "control_compiler", "group": "control",
                 "argv": [os.path.join(ROOT, "pystachy.py"), "ir", os.path.join(ROOT, "tests", "algorithms.py"),
                          "-o", os.devnull]}]
    for name in BENCHMARKS + sorted(VARIANTS):
        script = os.path.join(benchmarks, "bm_" + name, "run_benchmark.py")
        for opts in VARIANTS.get(name, [[]]):
            label = "_".join(["bm", name] + [o.lstrip("-").replace("-", "_") for o in opts])
            if os.path.exists(script):
                programs.append({"name": label, "group": "pyperformance", "argv": [script] + opts})
    tests = os.path.join(ROOT, "tests")
    for f in sorted(os.listdir(tests)):
        if f.startswith("port_") and f.endswith(".py"):
            base = os.path.join(tests, f[:-3])
            programs.append({"name": f[:-3], "group": "upstream ports", "argv": [base + ".py", "a1", "a2"],
                             "expect": base + ".out", "stdin": base + ".in" if os.path.exists(base + ".in") else os.devnull})
    return programs


def run_one(program, outdir, python, eligibility, shim):
    env = dict(os.environ, PYTHONPATH=shim, PYTHONHASHSEED="0")
    log = os.path.join(outdir, program["name"] + ".log")
    result = {"name": program["name"], "group": program["group"]}
    for command in ("record", "time"):
        out = os.path.join(outdir, program["name"] + (".json" if command == "record" else ".time.json"))
        argv = [python, TOOL, command, out]
        if command == "record" and eligibility:
            argv += ["--eligibility", eligibility]
        start = time.perf_counter()
        with open(program.get("stdin", os.devnull)) as stdin:
            try:
                done = subprocess.run(argv + program["argv"], cwd=ROOT, env=env, stdin=stdin, capture_output=True,
                                      text=True, timeout=1800)
            except subprocess.TimeoutExpired:
                result["skipped"] = command + " timed out"
                return result
        result[command + "_s"] = round(time.perf_counter() - start, 1)
        with open(log, "a", encoding="utf-8") as stream:
            stream.write(f"$ {' '.join(argv + program['argv'])}\n{done.stdout[-4000:]}\n{done.stderr[-4000:]}\n")
        if not os.path.exists(out):
            result["skipped"] = f"{command} wrote no data (exit {done.returncode})"
            return result
        if "expect" in program and command == "record":
            with open(program["expect"], encoding="utf-8") as stream:
                expected = stream.read()
            if done.stdout + f"[exit {done.returncode}]\n" != expected:
                result["skipped"] = "output differs from the recorded CPython output"
                return result
        elif done.returncode and "expect" not in program:
            result["skipped"] = f"{command} exited {done.returncode}"
            return result
    return result


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)

    def option(name, default):
        if name in args:
            value = args[args.index(name) + 1]
            del args[args.index(name):args.index(name) + 2]
            return value
        return default
    python = option("--python", sys.executable)
    jobs = int(option("--jobs", "3"))
    only = option("--only", "")
    eligibility = option("--eligibility", "")
    outdir = args[0]
    if "--report-only" in args:
        with open(os.path.join(outdir, "corpus.json"), encoding="utf-8") as stream:
            results = json.load(stream)
        report(outdir, results)
        return
    os.makedirs(os.path.join(outdir, "shim"), exist_ok=True)
    shim = os.path.join(outdir, "shim")
    with open(os.path.join(shim, "pyperf.py"), "w", encoding="utf-8") as stream:
        stream.write(SHIM)
    programs = corpus(python)
    if only:
        programs = [p for p in programs if p["name"] in only.split(",")]
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(lambda p: run_one(p, outdir, python, eligibility, shim), programs))
    for r in results:
        print(f"{r['name']:40} {r.get('skipped', 'ok')}", file=sys.stderr)
    listing = os.path.join(outdir, "corpus.json")
    if only and os.path.exists(listing):  # a partial run replaces its programs' entries
        with open(listing, encoding="utf-8") as stream:
            earlier = [r for r in json.load(stream) if r["name"] not in {p["name"] for p in programs}]
        names = [p["name"] for p in corpus(python)]
        results = sorted(earlier + results, key=lambda r: names.index(r["name"]) if r["name"] in names else len(names))
    with open(listing, "w", encoding="utf-8") as stream:
        json.dump(results, stream, indent=1)
    report(outdir, results)


def report(outdir, results):
    recorded = [os.path.join(outdir, r["name"] + ".json") for r in results if "skipped" not in r]
    summary = os.path.join(outdir, "summary.json")
    with open(os.path.join(outdir, "report.md"), "w", encoding="utf-8") as stream:
        subprocess.run([sys.executable, TOOL, "report", *recorded, "--json", summary], check=True, stdout=stream)
    tables(results, summary)


MIN_CALLS = 1000  # fewer program calls: the work is in C, the standard library or one loop

SKEW = [  # call-weighted, as receiver-class studies count dynamic dispatches
    ("inline cache: one target and receiver class", lambda s: s["views"]["send site: target and receiver class"]["mono"]),
    ("... at most 4 (a PIC)", lambda s: s["views"]["send site: target and receiver class"]["mono"] +
     s["views"]["send site: target and receiver class"]["poly"]),
    ("function entry: one class tuple", lambda s: s["views"]["function: classes"]["mono"]),
    ("one Pystachy specialization per function", lambda s: s["views"]["function: Pystachy types"]["mono"]),
    ("... per call site", lambda s: s["views"]["function + call site: Pystachy types"]["mono"]),
    ("... per call string of 2", lambda s: s["views"]["function + call string of 2: Pystachy types"]["mono"]),
    ("... per caller's types", lambda s: s["views"]["function + caller's types: Pystachy types"]["mono"]),
]
BLOCKERS = [  # time-weighted where a timing run allows: where specialization would have to pay
    ("time in program Python code", lambda s: s.get("program_time_share")),
    ("one specialization per caller's types (time)",
     lambda s: (s.get("views_time") or {}).get("function + caller's types: Pystachy types", {}) and
     s["views_time"]["function + caller's types: Pystachy types"]["mono"]),
    ("arguments have Pystachy types (time)", lambda s: s.get("args_expressible_time")),
    ("returns fixed by argument types", lambda s: s["returns_determined_by_arg_types"]),
    ("fields keep one type", lambda s: s["fields_stable"]),
    ("arguments fit the ext ABI (time)", lambda s: s.get("ext_abi_args_time")),
    ("adaptive prototype could run natively (time)", lambda s: s.get("adaptive_eligible_time")),
]


def pct(x):
    if x is None or x == {}:
        return "–"
    return f"{x:.0%}" if x >= 0.995 or x < 0.005 or x >= 0.1 else f"{x:.1%}"


def table(title, columns, groups, rows):
    head = "| | workloads | calls | " + " | ".join(h for h, _ in columns) + " |"
    print(f"### {title}\n")
    print(head)
    print("|---|---:|---:|" + "---:|" * len(columns))
    for group, members in groups.items():
        cells = []
        for _, value in columns:
            values = sorted(v for v in (value(m) for m in members) if v not in (None, {}))
            cells.append(f"{pct(values[len(values) // 2])} ({pct(values[0])})" if values else "–")
        print(f"| {group} | {len(members)} | {sum(m['calls'] for m in members):,} | " + " | ".join(cells) + " |")
    print("\nMedian (minimum) over workloads, each weighted equally.\n")
    if rows:
        print("| workload | | calls | " + " | ".join(h for h, _ in columns) + " |")
        print("|---|---|---:|" + "---:|" * len(columns))
        for group, members in groups.items():
            for m in members:
                print(f"| {m['name']} | {group} | {m['calls']:,} | " + " | ".join(pct(value(m)) for _, value in columns) + " |")
        print()


def tables(results, summary_path, rows=True):
    """Program-code metrics by group and for each workload with at least MIN_CALLS calls."""
    with open(summary_path, encoding="utf-8") as stream:
        summaries = {s["name"]: s for s in json.load(stream) if s["scope"] == "program"}
    groups, few = {}, []
    for r in results:
        s = summaries.get(r["name"])
        if s is None:
            continue
        if s["calls"] < MIN_CALLS:
            few.append(f"{r['name']} ({s['calls']})")
        else:
            groups.setdefault(r["group"], []).append(s)
    table("Type skew: share of calls (program code)", SKEW, groups, rows)
    table("What Pystachy would need (program code)", BLOCKERS, groups, rows)
    if few:
        print(f"Fewer than {MIN_CALLS:,} calls into program code, left out: " + ", ".join(few) + "\n")
    skipped = [r for r in results if "skipped" in r]
    if skipped:
        print("Skipped: " + "; ".join(f"{r['name']} ({r['skipped']})" for r in skipped))


if __name__ == "__main__":
    main()
