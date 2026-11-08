"""Compare two CPython FFI twins with the same verified socket consumer.

The optional netio prototype supplies all workloads, binary validation, C bridge
and sample parsing. This measures CPython's bridge, not native Pystachy.
"""

import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import pstats
import sys
import tempfile
import time


def compare(args):
    root = args.netio_root.resolve()
    sys.path.insert(0, str(root / "examples/netio"))
    spec = importlib.util.spec_from_file_location("netio_benchmark", root / "examples/netio/benchmark.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    check, common = bench.check, bench.common
    twins = {name: path.resolve() / "tools/rt_cpython" for name, path in
             [("baseline", args.baseline), ("candidate", args.candidate)]}
    if platform.python_version() != (root / ".python-version").read_text().strip():
        raise ValueError("use the netio checkout's pinned CPython")
    if args.cpu is not None:
        if not hasattr(os, "sched_setaffinity") or args.cpu not in os.sched_getaffinity(0):
            raise ValueError("requested CPU is unavailable")
        os.sched_setaffinity(0, {args.cpu})
    before = bench.source_hashes()
    twin_hashes = {name: common.digest(path / "ffi.py") for name, path in twins.items()}
    report = {
        "scope": "CPython ctypes bridge only; native Pystachy and stdlib baseline are unchanged",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version, "platform": platform.platform(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                           if line.startswith("model name")), "unknown") if Path("/proc/cpuinfo").exists() else platform.processor(),
        "source_sha256": before, "ffi_sha256": twin_hashes,
        "controller_sha256": common.digest(Path(__file__)),
        "python_executable_sha256": common.digest(Path(sys.executable)),
        "netio_revision": check.run("git/revision", ["git", "rev-parse", "HEAD"], os.environ.copy(), root).stdout.decode().strip(),
        "rounds": args.rounds, "warmups": args.warmups, "samples": args.samples,
        "iterations": bench.CASES, "cases": {}, "measurement_order": [],
        "load_average_start": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
    }
    with tempfile.TemporaryDirectory(prefix="ffi-twin-bench-") as temporary:
        directory = Path(temporary)
        environment = check.environment(directory)
        library = check.build_bridge(directory, environment, check.c_compiler(args.cc, environment), 60)
        report["bridge_sha256"] = common.digest(library)
        modes = {name: dict(environment, PYTHONPATH=os.pathsep.join([str(path), str(check.HERE)]))
                 for name, path in twins.items()}
        for name, environment in modes.items():
            loaded = check.run(name + "/import", [sys.executable, "-c", "import ffi; print(ffi.__file__)"],
                               environment, directory).stdout.decode().strip()
            if Path(loaded).resolve() != twins[name] / "ffi.py":
                raise RuntimeError(f"{name}: unexpected FFI twin: {loaded}")
        driver = check.HERE / "bench_driver.py"
        for case, iterations in bench.CASES.items():
            records = {name: {"runs": []} for name in modes}
            for round_index in range(args.rounds):
                order = ["baseline", "candidate"] if round_index % 2 == 0 else ["candidate", "baseline"]
                for name in order:
                    command = [sys.executable, str(driver), case, str(iterations), str(args.warmups), str(args.samples)]
                    result, elapsed = bench.timed(name + "/" + case, command, modes[name], directory, 120)
                    if result.stderr:
                        raise ValueError(f"{name}/{case}: unexpected diagnostics: {result.stderr!r}")
                    sample = bench.validate_measurement(result.stdout, case, iterations, args.warmups, args.samples)
                    records[name]["runs"].append(dict(sample, process_wall_s=elapsed))
                    report["measurement_order"].append([case, round_index, name])
            for name, record in records.items():
                record.update(common.summary([v / iterations for run in record["runs"] for v in run["samples_s"]]))
            records["speedup"] = records["baseline"]["median_s"] / records["candidate"]["median_s"]
            report["cases"][case] = records
        report["profiles"] = {}
        for name, environment in modes.items():
            output = directory / (name + ".pstats")
            command = [sys.executable, "-m", "cProfile", "-o", str(output), str(driver), "sparse_64", "500", "1", "1"]
            result = check.run(name + "/profile", command, environment, directory, timeout=120)
            bench.validate_measurement(result.stdout, "sparse_64", 500, 1, 1)
            stream = io.StringIO()
            stats = pstats.Stats(str(output), stream=stream)
            binding_calls = sum(value[1] for (file, _, function), value in stats.stats.items()
                                if Path(file).name == "inspect.py" and function in ("bind", "apply_defaults"))
            stats.strip_dirs().sort_stats("cumulative").print_stats(20)
            report["profiles"][name] = {"total_calls": stats.total_calls,
                                        "signature_binding_calls": binding_calls, "summary": stream.getvalue()}
    if before != bench.source_hashes() or twin_hashes != {name: common.digest(path / "ffi.py") for name, path in twins.items()}:
        raise RuntimeError("consumed source changed during comparison")
    report["load_average_end"] = list(os.getloadavg()) if hasattr(os, "getloadavg") else None
    report["result"] = "pass"
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"result": report["result"], "speedups": {k: v["speedup"] for k, v in report["cases"].items()},
                      "binding_calls": {k: v["signature_binding_calls"] for k, v in report["profiles"].items()}}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--netio-root", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--samples", type=int, default=5)
    arguments = parser.parse_args()
    if min(arguments.rounds, arguments.samples) < 1 or arguments.warmups < 0:
        parser.error("rounds/samples must be positive and warmups nonnegative")
    compare(arguments)
