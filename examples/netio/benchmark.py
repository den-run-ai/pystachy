"""Compare one verified socket consumer across runtimes; timings are advisory.

No dependencies beyond the prototype are needed for CPython and Pystachy.
PyPy, mypyc, Cython, pyperf export and profiling are explicit opt-ins.
"""

import argparse
import importlib.util
import io
import math
import os
from pathlib import Path
import platform
import pstats
import shutil
import sys
import tempfile
import time

import check

SPEC = importlib.util.spec_from_file_location("netio_bench_common", check.ROOT / "tools/bench_extended.py")
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)

CASES = {"pair_64": 2000, "fanin_4k": 400, "sparse_64": 2000, "bulk_64k": 250}
BYTES_PER_ITERATION = {"pair_64": 64, "fanin_4k": 16 * 4096, "sparse_64": 64, "bulk_64k": 4 * 65536}
SOURCES = ("bench_workload.py", "bench_driver.py", "benchmark.py")


def source_hashes():
    paths = [check.HERE / name for name in SOURCES]
    paths += [check.ROOT / "tools/bench_extended.py", check.ROOT / "tools/rt_cpython/ffi.py"]
    return check.hashes() | {str(path.relative_to(check.ROOT)): common.digest(path) for path in paths}


def compiler_hashes():
    paths = [check.ROOT / name for name in ("pystachy.py", "runtime.c", "runtime.py", "pystachy_toolchain.py")]
    paths += [path for name in ("src", "lib", "ryu", "mpz") for path in (check.ROOT / name).rglob("*")
              if path.suffix in {".py", ".c", ".h"}]
    return {str(path.relative_to(check.ROOT)): common.digest(path) for path in sorted(paths)}


def timed(label, command, env, directory, timeout):
    start = time.perf_counter()
    result = check.run(label, command, env, directory, timeout=timeout)
    return result, time.perf_counter() - start


def extension(kind, python, directory, env, timeout):
    """Compile only the identical consumer; imports keep using unmodified stdlib APIs."""
    target = directory / kind
    target.mkdir()
    shutil.copy2(check.HERE / "bench_workload.py", target)
    # The serial parser also works in PID namespaces where optional psutil cannot
    # inspect the build process. This changes compiler setup, not generated code.
    (target / "mypy.ini").write_text("[mypy]\nfollow_imports = skip\nignore_missing_imports = True\n"
                                   "native_parser = False\n")
    if kind == "mypyc":
        build = ("from mypyc.build import mypycify\n"
                 "ext = mypycify(['bench_workload.py', '--config-file', 'mypy.ini'], "
                 "opt_level='3', debug_level='0')\n")
    else:
        build = ("from Cython.Build import cythonize\n"
                 "ext = cythonize(['bench_workload.py'], compiler_directives="
                 "{'language_level': 3})\n")
    (target / "setup.py").write_text("from setuptools import setup\n" + build +
                                   "setup(name='netio-consumer', ext_modules=ext)\n")
    result, elapsed = timed(kind + "/build", [python, "setup.py", "build_ext", "--inplace"],
                            env, target, timeout)
    runtime_env = dict(env, PYTHONPATH=os.pathsep.join([str(target), str(check.HERE / "oracle")]))
    verify = check.run(kind + "/import", [python, "-c", "import bench_workload; print(bench_workload.__file__)"],
                       runtime_env, target, timeout=timeout)
    loaded = Path(verify.stdout.decode().strip())
    if loaded.parent != target or loaded.suffix not in {".so", ".pyd"}:
        raise ValueError(f"{kind}: consumer extension was not loaded: {loaded}")
    # Keep the driver outside target: its script directory must not shadow the extension.
    return [python, str(directory / "driver.py")], runtime_env, {
        "wall_s": elapsed, "binary_sha256": common.digest(loaded),
        "build_stdout": result.stdout.decode(errors="replace"),
        "build_stderr": result.stderr.decode(errors="replace"),
    }


def validate_measurement(stdout, case, iterations, warmups, samples):
    return common.parse_output(stdout.decode(), warmups, samples,
                               BYTES_PER_ITERATION[case] * iterations)


def profile_run(modes, directory, args, report):
    """Profile wrapper work and native syscall counts independently of benchmark samples."""
    case = "sparse_64"
    parameters = [case, "500", "1", "1"]
    records = {}
    for name in ("cpython_stdlib", "cpython_bridge"):
        command, env = modes[name]
        output = directory / (name + ".pstats")
        profile_command = [command[0], "-m", "cProfile", "-o", str(output)] + command[1:] + parameters
        result = check.run(name + "/profile", profile_command, env, directory, timeout=args.timeout)
        validate_measurement(result.stdout, case, 500, 1, 1)
        stream = io.StringIO()
        stats = pstats.Stats(str(output), stream=stream)
        stats.strip_dirs().sort_stats("cumulative").print_stats(22)
        records[name] = {"kind": "cProfile", "summary": stream.getvalue(),
                         "total_calls": stats.total_calls, "primitive_calls": stats.prim_calls}
    tracer = shutil.which("strace")
    if tracer and "pystachy_aot" in modes:
        command, env = modes["pystachy_aot"]
        output = directory / "native-strace.txt"
        try:
            check.run("strace/availability", [tracer, "-o", str(output), sys.executable, "-c", "pass"],
                      env, directory, timeout=args.timeout)
        except RuntimeError as error:
            message = str(error).lower()
            if "ptrace" not in message or not any(word in message for word in ("operation not permitted", "permission denied")):
                raise
            records["pystachy_aot"] = {"kind": "strace -c", "status": "unavailable", "error": str(error)}
        else:
            result = check.run("aot/syscalls", [tracer, "-c", "-o", str(output)] + command + parameters,
                               env, directory, timeout=args.timeout)
            validate_measurement(result.stdout, case, 500, 1, 1)
            records["pystachy_aot"] = {"kind": "strace -c (includes startup/setup/teardown)",
                                        "summary": output.read_text()}
    report["profiles"] = records


def export_pyperf(path, report):
    """Export already-validated in-process samples, normalized per iteration."""
    import pyperf

    benchmarks = []
    for case, results in report["cases"].items():
        for mode, entry in results.items():
            iterations = report["iterations"][case]
            runs = [pyperf.Run([value / iterations for value in run["samples_s"]],
                              metadata={"name": case + "/" + mode, "unit": "second", "loops": iterations,
                                        "netio_iterations": iterations, "netio_mode": mode},
                              collect_metadata=False) for run in entry["runs"]]
            benchmarks.append(pyperf.Benchmark(runs))
    path.parent.mkdir(parents=True, exist_ok=True)
    pyperf.BenchmarkSuite(benchmarks).dump(str(path), replace=True)


def benchmark(args, report):
    if platform.python_version() != (check.ROOT / ".python-version").read_text().strip():
        raise RuntimeError("run the controller with the repository's pinned CPython")
    before = source_hashes()
    compiler_before = compiler_hashes()
    compiler = check.compiler_command(args.compiler)
    iterations = {name: 3 if args.smoke else count for name, count in CASES.items()}
    samples, warmups, rounds = (2, 1, 1) if args.smoke else (args.samples, args.warmups, args.rounds)
    report.update(created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  source_sha256=before, compiler_source_sha256=compiler_before,
                  compiler_executable_sha256=common.digest(Path(compiler[0])) if Path(compiler[0]).is_file() else None,
                  iterations=iterations, samples=samples, warmups=warmups,
                  rounds=rounds, platform=platform.platform(), python=sys.version, compiler=compiler,
                  git_revision=check.run("git/revision", ["git", "rev-parse", "HEAD"], os.environ.copy(),
                                         check.ROOT).stdout.decode().strip(),
                  git_status=check.run("git/status", ["git", "status", "--porcelain"], os.environ.copy(),
                                       check.ROOT).stdout.decode(),
                  load_average_start=list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
                  cpu_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                  cpu_model=next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                                  if line.startswith("model name")), "unknown") if Path("/proc/cpuinfo").exists() else platform.processor(),
                  builds={}, runtimes={}, cases={}, measurement_order=[],
                  scope="Local socket pairs, binary payload validation, persistent selector; no WAN/TCP throughput claim",
                  timing_scope="First and sampled transfer times exclude socket/selector setup and process startup. "
                               "process_wall_s includes import/launch and all iterations. JIT process time includes "
                               "compilation with the private runtime cache populated by the earlier AOT build.")
    with tempfile.TemporaryDirectory(prefix="pystachy-netio-bench-") as temporary:
        directory = Path(temporary)
        source_dir = directory / "source"
        source_dir.mkdir()
        for name in ("bench_workload.py", "bench_driver.py"):
            shutil.copy2(check.HERE / name, source_dir)
        driver = source_dir / "bench_driver.py"
        shutil.copy2(driver, directory / "driver.py")
        env = check.environment(directory)
        env["PYSTACHY_PATH"] = os.pathsep.join([str(source_dir), str(check.HERE)])
        env["PYTHONPATH"] = os.pathsep.join([str(source_dir), env["PYTHONPATH"]])
        oracle_env = check.environment(directory, oracle=True)
        oracle_env["PYTHONPATH"] = os.pathsep.join([str(source_dir), oracle_env["PYTHONPATH"]])
        start = time.perf_counter()
        bridge = check.build_bridge(directory, env, check.c_compiler(args.cc, env), args.build_timeout)
        report["builds"]["bridge"] = {"wall_s": time.perf_counter() - start, "sha256": common.digest(bridge)}
        report["builds"]["bridge"]["compiler"] = check.run("cc/version", check.c_compiler(args.cc, env) + ["--version"],
                                                            env, directory).stdout.decode().strip()
        report["builds"]["bridge"]["flags"] = "-std=c11 -O2 -g -fPIC -shared (dynamiclib on macOS)"
        modes = {"cpython_stdlib": ([sys.executable, str(driver)], oracle_env),
                 "cpython_bridge": ([sys.executable, str(driver)], env)}
        if not args.cpython_only:
            executable = directory / "consumer"
            result, elapsed = timed("aot/build", compiler + ["build", str(driver), "-o", str(executable)],
                                    env, check.ROOT, args.build_timeout)
            check.quiet("aot/build", result)
            report["builds"]["pystachy_aot"] = {"wall_s": elapsed, "sha256": common.digest(executable)}
            modes["pystachy_aot"] = ([str(executable)], env)
            modes["pystachy_jit"] = (compiler + ["run", str(driver)], env)
        if args.pypy:
            modes["pypy_stdlib"] = ([str(Path(args.pypy).absolute()), str(driver)], oracle_env)
        if args.extension_python:
            python = str(Path(args.extension_python).absolute())
            versions = check.run("extensions/version", [python, "-c", "import importlib.metadata as m; "
                                 "print('mypy', m.version('mypy')); print('Cython', m.version('Cython'))"],
                                 oracle_env, directory).stdout.decode().strip()
            report["extension_versions"] = versions
            for kind in ("mypyc", "cython"):
                command, runtime_env, build = extension(kind, python, directory, oracle_env, args.build_timeout)
                modes[kind + "_stdlib"] = (command, runtime_env)
                report["builds"][kind] = build
        for name, (command, child_env) in modes.items():
            if name.startswith("pystachy"):
                version = check.run(name + "/version", compiler + ["--version"], child_env, check.ROOT).stdout.decode()
                scope = "consumer and netio wrapper compiled by Pystachy; native C bridge"
            else:
                version = check.run(name + "/version", [command[0], "-c", "import sys; print(sys.version)"],
                                    child_env, directory).stdout.decode()
                scope = "consumer plus unmodified stdlib socket/selectors"
                if name == "cpython_bridge":
                    scope = "Python consumer and wrapper through the existing ctypes FFI twin"
                elif name.startswith(("mypyc", "cython")):
                    scope = "compiled consumer; unmodified CPython stdlib socket/selectors"
            report["runtimes"][name] = {"version": version.strip(), "scope": scope}
        original_affinity = os.sched_getaffinity(0) if hasattr(os, "sched_getaffinity") else None
        try:
            if args.cpu is not None:
                if original_affinity is None or args.cpu not in original_affinity:
                    raise ValueError("--cpu must be in this process's available affinity mask")
                os.sched_setaffinity(0, {args.cpu})
            report["measurement_affinity"] = sorted(os.sched_getaffinity(0)) if original_affinity else None
            names = list(modes)
            for case, count in iterations.items():
                report["cases"][case] = {name: {"runs": []} for name in modes}
                for round_index in range(rounds):
                    order = names[round_index % len(names):] + names[:round_index % len(names)]
                    for name in order:
                        command, child_env = modes[name]
                        result, elapsed = timed(name + "/" + case, command + [case, str(count), str(warmups), str(samples)],
                                                child_env, directory, args.timeout)
                        if result.stderr:
                            raise ValueError(f"{name}/{case}: unexpected stderr: {result.stderr!r}")
                        record = validate_measurement(result.stdout, case, count, warmups, samples)
                        record["process_wall_s"] = elapsed
                        record["round"] = round_index
                        report["cases"][case][name]["runs"].append(record)
                        report["measurement_order"].append([case, round_index, name])
                        check.write_report(args.json, report)
                for name, entry in report["cases"][case].items():
                    values = [value for run in entry["runs"] for value in run["samples_s"]]
                    entry["summary"] = common.summary(values)
                    entry["ns_per_iteration"] = entry["summary"]["median_s"] * 1e9 / count
                    baseline = common.summary([value for run in report["cases"][case]["cpython_stdlib"]["runs"]
                                               for value in run["samples_s"]])["median_s"]
                    entry["speedup_vs_cpython_stdlib"] = baseline / entry["summary"]["median_s"]
                    print(f"{case:12} {name:17} {entry['ns_per_iteration']:10.0f} ns/iteration "
                          f"{entry['speedup_vs_cpython_stdlib']:.3f}x CPython stdlib", flush=True)
            if args.smoke and not args.cpython_only:
                for name in ("pystachy_jit", "pystachy_aot"):
                    command, child_env = modes[name]
                    setting = "PYSTACHY_GC_STRESS_PROGRAM" if name.endswith("jit") else "PYSTACHY_GC_STRESS"
                    for case, count in iterations.items():
                        result = check.run(name + "/gc/" + case, command + [case, str(count), "1", "2"],
                                           child_env | {setting: "1"}, directory, timeout=args.timeout)
                        validate_measurement(result.stdout, case, count, 1, 2)
                report["gc_modes"] = ["jit_gc", "aot_gc"]
            if args.profile:
                profile_run(modes, directory, args, report)
        finally:
            if original_affinity is not None:
                os.sched_setaffinity(0, original_affinity)
        if source_hashes() != before or compiler_hashes() != compiler_before:
            raise RuntimeError("consumed source changed during measurement; rerun on the final tree")
        report["load_average_end"] = list(os.getloadavg()) if hasattr(os, "getloadavg") else None
    report["result"] = "pass"
    if args.pyperf_json:
        export_pyperf(args.pyperf_json, report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(check.ROOT / "pystachy"))
    parser.add_argument("--cc")
    parser.add_argument("--cpython-only", action="store_true")
    parser.add_argument("--pypy", help="optional PyPy executable")
    parser.add_argument("--extension-python", help="optional CPython with mypyc, Cython and setuptools")
    parser.add_argument("--smoke", action="store_true", help="tiny correctness inputs, including native GC stress")
    parser.add_argument("--cpu", type=int, help="pin measured subprocesses to an available logical CPU")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--build-timeout", type=float, default=240)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--json", type=Path, default=check.ROOT / "build/netio-benchmark.json")
    parser.add_argument("--pyperf-json", type=Path, help="optional pyperf format (requires pyperf in controller)")
    args = parser.parse_args(argv)
    if min(args.rounds, args.samples) <= 0 or args.warmups < 0:
        parser.error("rounds/samples must be positive; warmups must be nonnegative")
    if any(not math.isfinite(value) or value <= 0 for value in (args.timeout, args.build_timeout)):
        parser.error("timeouts must be positive and finite")
    report = {"schema": 1, "result": "running"}
    check.write_report(args.json, report)
    try:
        benchmark(args, report)
    except Exception as error:
        report.update(result="fail", error=str(error))
        check.write_report(args.json, report)
        print(str(error), file=sys.stderr)
        return 1
    check.write_report(args.json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
