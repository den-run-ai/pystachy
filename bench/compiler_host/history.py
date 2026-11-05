"""Compare historical/current native frontends on the same frozen source trees.

Old-compiler preparation and hosted/native parity checks are excluded from timed
samples. Cross-version LLVM IR may differ; each compiler/input pair must remain
deterministic. A stable old-compiler rejection of newer source is a capability
gap, never a compilation-speed result. This does not time complete native builds.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import random
import statistics
import sys

from run import ROOT, atomic_json, bootstrap, measure, sha


def source_sizes(home):
    files = [home / "pystachy.py", *sorted((home / "src").rglob("*.py"))]
    return {
        "compiler_files": len(files),
        "compiler_bytes": sum(p.stat().st_size for p in files),
        "compiler_lines": sum(p.read_bytes().count(b"\n") for p in files),
        "runtime_c_bytes": (home / "runtime.c").stat().st_size,
        "runtime_py_bytes": (home / "runtime.py").stat().st_size,
    }


def emitted(result, path):
    result["output_sha256"] = sha(path) if path.is_file() else None
    result["output_bytes"] = path.stat().st_size if path.is_file() else None
    return result


def signature(result):
    return tuple(result[key] for key in (
        "exit_code", "timed_out", "stdout_sha256", "stderr_sha256",
        "output_sha256", "output_bytes",
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-home", type=Path, required=True)
    parser.add_argument("--old-compiler", type=Path, help="reuse a binary, still verify its own-source IR")
    parser.add_argument("--compiler", type=Path, required=True, help="current native compiler")
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--cpu", type=int, help="one allowed core for timed frontend processes")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    if args.cpu is not None and args.cpu not in os.sched_getaffinity(0):
        parser.error("cpu is outside the process affinity")
    homes = {"old": args.old_home.resolve(), "current": ROOT}
    llvm, work = args.llvm.resolve(), args.work.resolve()
    compilers = {"old": args.old_compiler.resolve() if args.old_compiler else work / "old-compiler",
                 "current": args.compiler.resolve()}
    for home in homes.values():
        if not all((home / name).is_file() for name in ("pystachy.py", "runtime.py", "runtime.c")):
            parser.error(f"incomplete source checkout: {home}")
    if any(homes["old"].joinpath("src").rglob("*.so")):
        parser.error("old checkout contains compiled Python modules; need plain hosted source")
    if not compilers["current"].is_file() or (args.old_compiler and not compilers["old"].is_file()):
        parser.error("compiler binary is missing")
    work.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH"):
        env.pop(key, None)
    env.update(PYSTACHY_LLVM=str(llvm), PYTHONHASHSEED="0", PYTHONNOUSERSITE="1",
               PYTHONDONTWRITEBYTECODE="1")
    sources = {name: bootstrap.source_identity(home) for name, home in homes.items()}
    tools = bootstrap.tool_identity(sys.executable, str(llvm))
    report = {
        "scope": "fresh-process frontend IR emission; preparation and verification excluded",
        "homes": {name: str(home) for name, home in homes.items()},
        "sources_before": sources, "source_sizes": {name: source_sizes(home) for name, home in homes.items()},
        "host_state": bootstrap.host_state(), "toolchain": tools, "python_version": sys.version,
        "requested_samples": args.samples, "cpu": args.cpu,
        "environment": {k: env[k] for k in ("PYSTACHY_LLVM", "PYTHONHASHSEED", "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE")},
        "preparation": None, "oracles": {}, "samples": [], "llvm_verification": {},
        "complete": False,
    }
    atomic_json(args.report, report)

    def input_env(name):
        return env | {"PYSTACHY_HOME": str(homes[name]), "PYSTACHY_CACHE": str(work / (name + "-cache"))}

    try:
        old_env = input_env("old")
        if not args.old_compiler:
            result = measure.execute([sys.executable, str(homes["old"] / "pystachy.py"),
                                      "build", str(homes["old"] / "pystachy.py"),
                                      "-o", str(compilers["old"])], old_env, 900)
            report["preparation"] = result
            atomic_json(args.report, report)
            measure.successful(result)
        report["compiler_sha256"] = {name: sha(path) for name, path in compilers.items()}
        report["compiler_paths"] = {name: str(path) for name, path in compilers.items()}
        for mode, source in (("ir", "pystachy.py"), ("rt", "runtime.py")):
            pair = {}
            report["oracles"][mode] = pair
            for host, command in (("hosted", [sys.executable, str(homes["old"] / "pystachy.py")]),
                                  ("native", [str(compilers["old"])])):
                output = work / f"old-oracle-{host}-{mode}.ll"
                result = emitted(measure.execute(command + [mode, str(homes["old"] / source),
                                 "-o", str(output)], old_env, 300), output)
                pair[host] = result
                atomic_json(args.report, report)
                measure.successful(result)
                if result["output_sha256"] is None:
                    raise RuntimeError(f"old {host} {mode} oracle produced no output")
            pair["matches"] = pair["hosted"]["output_sha256"] == pair["native"]["output_sha256"]
            atomic_json(args.report, report)
            if not pair["matches"]:
                raise RuntimeError(f"old native/hosted {mode} oracle differs")

        combinations = [(host, item) for host in compilers for item in homes]
        first = {}
        rng = random.Random(20261105)
        for sample in range(args.samples):
            order = combinations.copy()
            rng.shuffle(order)
            for host, item in order:
                output = work / f"{host}-on-{item}-{sample}.ll"
                source = homes[item] / "pystachy.py"
                command = [str(compilers[host]), "ir", str(source), "-o", str(output)]
                if args.cpu is not None:
                    command = ["taskset", "-c", str(args.cpu)] + command
                result = emitted(measure.execute(command, input_env(item), 300), output)
                result.update(host=host, input=item, sample=sample, input_sha256=sha(source))
                compiled = (result["exit_code"] == 0 and not result["timed_out"]
                            and result["output_sha256"] is not None)
                gap = (host == "old" and item == "current" and result["exit_code"] == 1
                       and not result["timed_out"] and result["output_sha256"] is None
                       and ": error:" in result["stderr"])
                result["status"] = "compiled" if compiled else "capability_gap" if gap else "failed"
                key = host + "-on-" + item
                previous = first.setdefault(key, signature(result))
                result["stable"] = previous == signature(result)
                report["samples"].append(result)
                atomic_json(args.report, report)
                if result["status"] == "failed" or not result["stable"]:
                    raise RuntimeError(f"failed or nondeterministic frontend: {key} sample {sample}")
                if compiled and key not in report["llvm_verification"]:
                    verified = measure.execute([str(llvm / "opt"), "-passes=verify", "-disable-output", str(output)], env, 120)
                    report["llvm_verification"][key] = verified
                    atomic_json(args.report, report)
                    measure.successful(verified)
                print(f"{key} {sample}: {result['wall_s']:.4f}s {result['status']} stable={result['stable']}", flush=True)
        report["summary"] = []
        for host, item in combinations:
            rows = [r for r in report["samples"] if r["host"] == host and r["input"] == item]
            summary = {"host": host, "input": item, "n": len(rows), "status": rows[0]["status"],
                       "stable": all(r["stable"] for r in rows), "output_sha256": rows[0]["output_sha256"],
                       "output_bytes": rows[0]["output_bytes"]}
            if summary["status"] == "compiled":
                for key in ("wall_s", "cpu_s", "wait4_max_process_rss_kib", "sampled_process_tree_peak_rss_kib"):
                    values = [r[key] for r in rows if r[key] is not None]
                    summary[key] = {"median": statistics.median(values), "min": min(values), "max": max(values)} if values else None
            report["summary"].append(summary)
        report["sources_after"] = {name: bootstrap.source_identity(home) for name, home in homes.items()}
        report["sources_unchanged"] = sources == report["sources_after"]
        report["compilers_unchanged"] = report["compiler_sha256"] == {name: sha(path) for name, path in compilers.items()}
        report["toolchain_unchanged"] = tools == bootstrap.tool_identity(sys.executable, str(llvm))
        report["complete"] = (report["sources_unchanged"] and report["compilers_unchanged"] and report["toolchain_unchanged"]
                              and len(report["samples"]) == args.samples * len(combinations))
        atomic_json(args.report, report)
        return 0 if report["complete"] else 1
    except Exception as error:
        report["error"] = str(error)
        atomic_json(args.report, report)
        raise


if __name__ == "__main__":
    sys.exit(main())
