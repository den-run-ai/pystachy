"""Compare one ordinary scoring program with compiler callback guards off/on.

Run on Linux with the repository's pinned CPython; --smoke checks correctness only.
Binaries, caches and raw IR are retained with --keep (alias --work-dir).
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXAMPLE = ROOT / "examples/guarded_score"
sys.path.insert(0, str(ROOT / "tools"))
from bench_extended import execute  # noqa: E402

VARIANTS = ("generic", "guarded")
OPTIONS = {"generic": "-callbacks", "guarded": ""}
CASES = ("square", "absolute", "skew99", "mixed", "miss", "change", "short", "stream")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    paths = [ROOT / name for name in ("pystachy.py", "runtime.py", "runtime.c", "VERSION",
                                      "tools/bench_extended.py")]
    for tree in ("src", "lib", "mpz", "ryu", "examples/guarded_score", "bench/guarded_callbacks"):
        paths.extend(p for p in (ROOT / tree).rglob("*") if p.suffix in (".py", ".c", ".h"))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))}


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    pending.replace(path)


def checked(command, env, timeout, elements, expected=None):
    record = execute(command, env, timeout)
    rows = record["stdout"].splitlines()
    if len(rows) != 2:
        raise ValueError(f"expected two output rows: {record['stdout']!r}")
    total, count = float(rows[0]), int(rows[1])
    if not math.isfinite(total) or count != elements or (expected is not None and total != expected):
        raise ValueError(f"incorrect result: {(total, count)}; expected {(expected, elements)}")
    metrics = {}
    for line in record["stderr"].splitlines():
        fields = line.split()
        if fields and fields[0] in ("kernel_wall_ns", "kernel_cpu_ns"):
            if len(fields) != 2 or fields[0] in metrics:
                raise ValueError(f"invalid/duplicate timing row: {line!r}")
            metrics[fields[0]] = int(fields[1])
    if set(metrics) != {"kernel_wall_ns", "kernel_cpu_ns"}:
        raise ValueError(f"missing kernel timing: {record['stderr']!r}")
    if any(not math.isfinite(v) or v <= 0 for v in (*metrics.values(), record["wall_s"])):
        raise ValueError("timings must be positive and finite")
    record.update(metrics, checksum=total, elements=count)
    return record


def summarize(pairs, metrics=("kernel_wall_ns", "kernel_cpu_ns", "wall_s")):
    result = {}
    for metric in metrics:
        ratios = [pair["generic"][metric] / pair["guarded"][metric] for pair in pairs]
        result[metric] = {"median_paired_speedup": statistics.median(ratios),
                          "min_paired_speedup": min(ratios), "max_paired_speedup": max(ratios),
                          "guarded_wins": sum(ratio > 1 for ratio in ratios), "pairs": len(ratios)}
    return result


def metadata(compiler, env, timeout, drivers):
    def info(command):
        return execute(command, env, timeout)["stdout"].strip()
    llvm = info([sys.executable, "-c", "from pystachy import llvm_dir; print(llvm_dir())"])
    tools = {}
    for name in ("clang", "opt", "lli", "llvm-link", "llvm-as"):
        path = str(ROOT / llvm / name) if llvm else shutil.which(name, path=env.get("PATH"))
        if path is None:
            raise ValueError(f"missing LLVM tool: {name}")
        binary = Path(path).resolve()
        tools[name] = {"path": str(binary), "version": info([str(binary), "--version"]),
                       "sha256": digest(binary)}
    sources = source_hashes()
    cpuinfo = Path("/proc/cpuinfo").read_text()
    return {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_revision": info(["git", "rev-parse", "HEAD"]),
            "git_status": info(["git", "status", "--porcelain=v1", "--untracked-files=all"]),
            "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "cpu_model": next((line.split(":", 1)[1].strip() for line in cpuinfo.splitlines()
                               if line.startswith("model name")), platform.processor()),
            "cpu_affinity": sorted(os.sched_getaffinity(0)), "load_average_start": os.getloadavg(),
            "python": {"version": sys.version, "executable": sys.executable,
                       "sha256": digest(Path(sys.executable)),
                       "repository_version": (ROOT / ".python-version").read_text().strip()},
            "compiler": {"path": str(compiler), "version": info([str(compiler), "--version"]),
                         "sha256": digest(compiler)}, "llvm": tools,
            "environment": {k: v for k, v in env.items() if k.startswith("PYSTACHY_") or
                            k in ("PYTHONPATH", "PYTHONHASHSEED", "LANG", "LC_ALL")},
            "source_sha256": sources,
            "source_tree_sha256": hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
            "driver_sha256": {p.name: digest(p) for p in drivers}}


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy", help="one native compiler executable")
    parser.add_argument("--keep", "--work-dir", dest="keep", type=Path, help="new, owned artifact/cache directory")
    parser.add_argument("--json", type=Path, default=ROOT / "build/guarded-callbacks.json")
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--samples", type=positive, default=7, help="paired process samples per case/mode")
    parser.add_argument("--size", type=positive, default=16384)
    parser.add_argument("--batches", type=positive, default=2000)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--cpu", type=int, help="default: lowest CPU in the current affinity")
    parser.add_argument("--timeout", type=float, default=60, help="seconds per command, including LLVM children")
    parser.add_argument("--jit", choices=("none", "selected", "all"), default="selected",
                        help="selected: square, miss, short and stream; process timings include compilation/startup")
    parser.add_argument("--smoke", action="store_true", help="tiny inputs, one pair/build; no speedup claims")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0 or not 0 <= args.seed <= 1000000:
        parser.error("timeout must be positive and finite; seed must be in 0..1000000")
    if args.size * args.batches > 2**63 - 1:
        parser.error("size * batches exceeds the signed-64-bit element count")
    if platform.python_implementation() != "CPython" or not hasattr(os, "sched_setaffinity"):
        parser.error("use CPython on Linux with CPU affinity support")
    affinity = os.sched_getaffinity(0)
    cpu = min(affinity) if args.cpu is None else args.cpu
    if cpu not in affinity:
        parser.error(f"CPU {cpu} is not in the current affinity")
    compiler, output = args.compiler.resolve(), args.json.resolve()
    samples, builds = (1, 1) if args.smoke else (args.samples, 3)
    directory = args.keep.resolve() if args.keep else Path(tempfile.mkdtemp(prefix="pystachy-guarded-callbacks-"))
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") or k == "PYSTACHY_LLVM"}
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_PATH=str(EXAMPLE),
               PYTHONPATH=str(EXAMPLE), PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    environments = {variant: dict(env, PYSTACHY_OPT=OPTIONS[variant],
                                  PYSTACHY_CACHE=str(directory / "cache" / variant))
                    for variant in VARIANTS}
    report = {"schema_version": 2, "status": "incomplete", "cases": [],
              "program": str(HERE / "workload.py"), "compiler_options": OPTIONS,
              "measurement_kind": "correctness_only" if args.smoke else "paired_performance",
              "settings": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              "work_dir": str(directory), "original_affinity": sorted(affinity),
              "scope": "Measured: schedule lookup and scoring; stream also constructs inputs. "
                       "Initial inputs and callback schedule are excluded. JIT wall_s includes compilation/startup."}
    try:
        if args.keep:
            directory.mkdir(parents=True, exist_ok=False)
        os.sched_setaffinity(0, {cpu})
        save(output, report)
        # Both variants compile the exact same file; only the compiler pass differs.
        drivers = {variant: HERE / "workload.py" for variant in VARIANTS}
        binaries = {variant: directory / f"{variant}.exe" for variant in VARIANTS}
        prime = directory / "prime.py"
        prime.write_text("pass\n")
        report["metadata"] = metadata(compiler, env, args.timeout, [*drivers.values(), prime])
        report["metadata"]["variant_environment"] = {
            variant: {key: environments[variant][key] for key in ("PYSTACHY_OPT", "PYSTACHY_CACHE")}
            for variant in VARIANTS}
        # Each compiler option gets its own cache, including on every JIT invocation.
        report["cold_runtime_prime"] = {
            variant: execute([str(compiler), "run", str(prime)], environments[variant], args.timeout)
            for variant in VARIANTS}
        report["artifacts"], report["build_warmups"], report["build_pairs"] = {}, {}, []
        for variant in VARIANTS:
            ir = directory / f"{variant}.ll"
            ir_run = execute([str(compiler), "ir", str(drivers[variant]), "-o", str(ir)],
                             environments[variant], args.timeout)
            report["artifacts"][variant] = {"raw_ir_bytes": ir.stat().st_size,
                                             "raw_ir_sha256": digest(ir), "ir_generation": ir_run}
            report["build_warmups"][variant] = execute(
                [str(compiler), "build", str(drivers[variant]), "-o", str(binaries[variant])],
                environments[variant], args.timeout)
        for repeat in range(builds):
            pair = {"order": list(VARIANTS[::1 if repeat % 2 == 0 else -1])}
            report["build_pairs"].append(pair)
            for variant in pair["order"]:
                pair[variant] = execute([str(compiler), "build", str(drivers[variant]),
                                         "-o", str(binaries[variant])], environments[variant], args.timeout)
                pair[variant]["binary_bytes"] = binaries[variant].stat().st_size
        for variant in VARIANTS:
            report["artifacts"][variant].update(binary_bytes=binaries[variant].stat().st_size,
                                                 binary_sha256=digest(binaries[variant]))
        if not args.smoke:
            report["build_summary"] = summarize(report["build_pairs"], ("wall_s",))
        save(output, report)
        for index, name in enumerate(args.cases):
            scenario = "square" if name == "short" else name
            size, batches = (1, 200000) if name == "short" else ((1024, 2000) if name == "stream"
                                                                 else (args.size, args.batches))
            if args.smoke:
                size, batches = (1 if name == "short" else 8), 100
            known = {"miss": 0, "skew99": batches - batches // 100, "change": batches // 2}.get(name, batches)
            case = {"name": name, "scenario": scenario, "size": size, "batches": batches,
                    "known_target_calls": known, "known_target_fraction": known / batches,
                    "oracle": {}, "warmups": {}, "pairs": {}, "summary": {}, "gc_probes": {}}
            report["cases"].append(case)
            runargs = [scenario, str(size), str(batches), str(args.seed)]
            expected = None
            for variant in VARIANTS:
                oracle = checked([sys.executable, str(drivers[variant]), *runargs], env,
                                 args.timeout, size * batches, expected)
                case["oracle"][variant], expected = oracle, oracle["checksum"]
            modes = ["aot"]
            if args.jit == "all" or (args.jit == "selected" and (args.smoke or name in ("square", "miss", "short", "stream"))):
                modes.append("jit")
            for mode in modes:
                commands = {v: ([str(binaries[v])] if mode == "aot" else
                                [str(compiler), "run", str(drivers[v])]) + runargs for v in VARIANTS}
                case["warmups"][mode] = {v: checked(commands[v], environments[v], args.timeout, size * batches, expected)
                                         for v in VARIANTS}
                pairs = case["pairs"][mode] = []
                for repeat in range(samples):
                    pair = {"order": list(VARIANTS[::1 if (repeat + index) % 2 == 0 else -1])}
                    pairs.append(pair)
                    for variant in pair["order"]:
                        pair[variant] = checked(commands[variant], environments[variant], args.timeout, size * batches, expected)
                if not args.smoke:
                    case["summary"][mode] = summarize(pairs)
            for variant in VARIANTS:
                probe = checked([str(binaries[variant]), *runargs], dict(environments[variant], PYSTACHY_GC="stats"),
                                args.timeout, size * batches, expected)
                probe["environment_overrides"] = {"PYSTACHY_GC": "stats"}
                case["gc_probes"][variant] = probe
            save(output, report)
            if args.smoke:
                print(f"{name}: correctness passed (smoke; timings are not performance evidence)", flush=True)
            else:
                speed = case["summary"]["aot"]["kernel_wall_ns"]
                print(f"{name}: AOT paired median {speed['median_paired_speedup']:.3f}x "
                      f"[{speed['min_paired_speedup']:.3f}, {speed['max_paired_speedup']:.3f}]", flush=True)
        if source_hashes() != report["metadata"]["source_sha256"] or digest(compiler) != report["metadata"]["compiler"]["sha256"]:
            raise ValueError("compiler or source inputs changed during measurement")
        if {p.name: digest(p) for p in [*drivers.values(), prime]} != report["metadata"]["driver_sha256"]:
            raise ValueError("input program changed during measurement")
        report["load_average_end"] = os.getloadavg()
        report["status"] = "complete"
    except (OSError, RuntimeError, ValueError, KeyboardInterrupt) as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(report["error"], file=sys.stderr)
    finally:
        save(output, report)
        os.sched_setaffinity(0, affinity)
        if not args.keep:
            shutil.rmtree(directory)
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
