#!/usr/bin/env python3
"""Separate instrumented CPU attribution; never combine these times with timings."""
import argparse
import json
import os
from pathlib import Path
import pstats
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--valgrind", default=shutil.which("valgrind"))
    parser.add_argument("--valgrind-lib", default=os.environ.get("VALGRIND_LIB", ""))
    parser.add_argument("--cpu", type=int, default=min(os.sched_getaffinity(0)))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    variants = {row["name"]: row for row in manifest["runtimes"]}
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=True)
    base = dict(os.environ)
    for key in list(base):
        if key.startswith("PYSTACHY_"):
            del base[key]
    base.update(manifest.get("env", {}))
    base.update(LD_LIBRARY_PATH=manifest["adapters"]["stub"], PYTHONHASHSEED="0")
    if args.valgrind_lib:
        base["VALGRIND_LIB"] = args.valgrind_lib
    summary = {"source": str(args.manifest), "commands": [], "profiles": {}}

    def execute(name, command, extra=None):
        env = base | variants[name].get("env", {}) | (extra or {})
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                text=True, check=True,
                                preexec_fn=lambda: os.sched_setaffinity(0, {args.cpu}))
        summary["commands"].append({"runtime": name, "argv": command, "extra_env": extra})
        return result

    for name in ("cpython_twin", "cpython_native"):
        path = target / (name + ".pstats")
        code = ("import cProfile; from benchmark_workload import run; "
                "p=cProfile.Profile(); p.runcall(run,'frame',150,1000,30); "
                "p.dump_stats(" + repr(str(path)) + ")")
        result = execute(name, [variants[name]["command"][0], "-c", code])
        (target / (name + ".log")).write_text(result.stdout + result.stderr)
        stats = pstats.Stats(str(path))
        rows = []
        for (filename, line, function), (primitive, calls, own, cumulative, _) in stats.stats.items():
            rows.append(dict(file=filename, line=line, function=function,
                             primitive_calls=primitive, calls=calls,
                             self_seconds=own, cumulative_seconds=cumulative))
        rows.sort(key=lambda row: row["cumulative_seconds"], reverse=True)
        summary["profiles"][name] = {"total_seconds": stats.total_tt, "top_functions": rows[:30]}
        with (target / (name + "-profile.txt")).open("w") as output:
            pstats.Stats(str(path), stream=output).strip_dirs().sort_stats("cumtime").print_stats(25)
        print(name, "cProfile complete", flush=True)

    result = execute("pystachy_aot", variants["pystachy_aot"]["command"]
                     + ["frame", "150", "50000", "30"], {"PYSTACHY_GC": "stats"})
    (target / "pystachy-gc.log").write_text(result.stdout + result.stderr)
    summary["gc"] = {"stdout": result.stdout, "stderr": result.stderr}
    if args.valgrind:
        annotate = str(Path(args.valgrind).parent / "callgrind_annotate")
        for name, symbol in [("pystachy_aot", "f.benchmark_workload$loop"),
                             ("cython_typed_noexcept", "__pyx_f_18benchmark_workload_loop")]:
            output = target / (name + ".callgrind")
            command = [args.valgrind, "--tool=callgrind", "--collect-atstart=no",
                       "--toggle-collect=" + symbol, "--callgrind-out-file=" + str(output)]
            command += variants[name]["command"] + ["frame", "150", "5000", "0"]
            result = execute(name, command)
            (target / (name + "-callgrind.log")).write_text(result.stdout + result.stderr)
            raw = output.read_text()
            total = re.search(r"^summary: (\d+)", raw, re.MULTILINE)
            if not total or int(total[1]) <= 0:
                raise RuntimeError("Callgrind did not collect the requested loop: " + name)
            report = subprocess.run([annotate, "--inclusive=no", "--threshold=95", "--auto=no",
                                     str(output)], capture_output=True, text=True, check=True)
            (target / (name + "-instructions.txt")).write_text(report.stdout)
            summary["profiles"][name] = {"instructions": int(total[1]), "frames": 5000,
                                         "symbol": symbol}
            print(name, "Callgrind complete", flush=True)
    (target / "profiles.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
