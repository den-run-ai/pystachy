"""Compare bounded compiler-source TCP echoes with stdlib sockets and owned libuv.

This is a loopback source-transfer workload, not a distributed compiler or an
upstream pyperformance result. The same source bytes, peer and request protocol
are used by every mode; every response is checked before its timing is accepted.
"""

import argparse
import ctypes
import hashlib
import math
import os
from pathlib import Path
import platform
import pstats
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

from check import HERE, ROOT, Peer, run, write_report


DEFAULT_SOURCE = ROOT / "src" / "pystachy_compiler" / "lexer.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(source):
    paths = [HERE / name for name in ("bridge.c", "bridge.h", "uvio.py", "check.py",
                                      "source_exchange.py", "socket_exchange.py", "dogfood.py")]
    paths += [ROOT / "tools" / "rt_cpython" / "ffi.py", ROOT / ".python-version", source]
    return {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): digest(path)
            for path in paths}


def compiler_hashes():
    paths = [ROOT / name for name in ("pystachy.py", "runtime.py", "runtime.c")]
    paths += sorted(ROOT.glob("*.h"))
    paths += sorted((ROOT / "src").rglob("*.py"))
    paths += sorted((ROOT / "lib").rglob("*.py"))
    for directory in ("ryu", "mpz"):
        for pattern in ("*.c", "*.h"):
            paths += sorted((ROOT / directory).rglob(pattern))
    return {str(path.relative_to(ROOT)): digest(path) for path in paths}


def parse_sample(output, source_size, chunk_size, rounds):
    values = output.decode().split()
    if len(values) != 4:
        raise AssertionError("consumer must report time, bytes, requests and loop turns")
    seconds = float(values[0])
    count, requests, steps = map(int, values[1:])
    expected_requests = max(1, (source_size + chunk_size - 1) // chunk_size) * rounds
    if not math.isfinite(seconds) or seconds <= 0:
        raise AssertionError("consumer reported invalid timing")
    if count != source_size * rounds or requests != expected_requests or steps < 1:
        raise AssertionError("consumer did not complete the expected source transfers")
    return {"seconds": seconds, "received_bytes": count,
            "exchanges": requests, "loop_turns": steps}


def command_words(value):
    command = shlex.split(value)
    if not command:
        raise ValueError("empty command")
    # check.run has a stable ROOT cwd; normalize existing relative scripts too.
    return [str((ROOT / word).resolve())
            if (not index or command[index - 1] not in ("-m", "-c"))
            and not word.startswith("-") and (ROOT / word).is_file()
            else word for index, word in enumerate(command)]


def profile_summary(path, limit=12):
    stats = pstats.Stats(str(path))
    rows = []
    for (filename, line, function), (primitive, calls, own, cumulative, _) in stats.stats.items():
        rows.append({"function": f"{Path(filename).name}:{line}:{function}", "calls": calls,
                     "primitive_calls": primitive, "self_seconds": own,
                     "cumulative_seconds": cumulative})
    return sorted(rows, key=lambda item: item["cumulative_seconds"], reverse=True)[:limit]


def benchmark(args, report):
    required = (ROOT / ".python-version").read_text().strip()
    if platform.python_implementation() != "CPython" or platform.python_version() != required:
        raise RuntimeError(f"controller requires CPython {required}; use --interpreter for additional runtimes")
    report["required_cpython"] = required
    affinity = None
    if args.cpu is not None:
        if not hasattr(os, "sched_setaffinity") or not hasattr(os, "sched_getaffinity"):
            raise ValueError("CPU affinity is unavailable on this platform")
        affinity = os.sched_getaffinity(0)
        if args.cpu not in affinity:
            raise ValueError("requested CPU is outside the allowed affinity")
        os.sched_setaffinity(0, {args.cpu})
    try:
        _benchmark(args, report)
    finally:
        if affinity is not None:
            os.sched_setaffinity(0, affinity)


def _benchmark(args, report):
    if not 1 <= args.samples <= 31 or not 1 <= args.rounds <= 1000:
        raise ValueError("samples must be 1..31 and rounds 1..1000")
    if not args.chunks or any(not 1 <= value <= 65535 for value in args.chunks):
        raise ValueError("chunk sizes must be 1..65535")
    if not args.concurrency or any(not 1 <= value <= 64 for value in args.concurrency):
        raise ValueError("concurrency must be 1..64")
    source = args.source.resolve()
    if not source.is_file():
        raise ValueError("source input must be a regular file")
    source_size = source.stat().st_size
    if source_size > 1048576:
        raise ValueError("source input exceeds the 1 MiB dogfood bound")
    before = source_hashes(source)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYSTACHY_") and key not in
           {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONINSPECT", "PYTHONSTARTUP"}}
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_PATH=str(HERE),
               PYSTACHY_PROGRAM_CACHE="0", PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONUTF8="1", PYTHONHASHSEED="0",
               PYTHONPATH=os.pathsep.join([str(ROOT / "tools" / "rt_cpython"), str(HERE)]))
    if "PYSTACHY_LLVM" in os.environ:
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    compiler = command_words(args.compiler)
    if not args.cpython_only:
        report["compiler_sources_before"] = compiler_hashes()
        binaries = [Path(shutil.which(compiler[0]) or compiler[0])]
        binaries += [Path(word) for word in compiler[1:] if Path(word).is_file()]
        report["compiler_files"] = {str(path): digest(path) for path in binaries}
    interpreters = {"cpython": [sys.executable]}
    for entry in args.interpreter:
        name, separator, value = entry.partition("=")
        if not separator or not name or name in interpreters or name in {"jit", "aot"}:
            raise ValueError("--interpreter requires a unique NAME=COMMAND")
        interpreters[name] = command_words(value)
    report.update({
        "platform": platform.platform(), "machine": platform.machine(), "python": sys.version,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "source_sha256": digest(source), "source_bytes": source_size, "sources_before": before,
        "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "loadavg_before": os.getloadavg() if hasattr(os, "getloadavg") else None,
        "timed_scope": "warm loop creation/close, fresh TCP connections, transfer, exact-byte checks; excludes process launch, source loading and compilation",
        "peer": "check.Peer: CPython socket, eight service threads, 2048-byte reply fragments",
        "samples": args.samples, "rounds": args.rounds, "warmup_rounds": 1, "results": [], "validation": {},
        "interpreters": {name: run(command + ["-c", "import sys; print(sys.version)"], env).decode().strip()
                         for name, command in interpreters.items()},
    })
    if args.libuv_prefix:
        prefix = args.libuv_prefix.resolve()
        cflags = ["-I" + str(prefix / "include")]
        libraries = ["-L" + str(prefix / "lib"), "-Wl,-rpath," + str(prefix / "lib"), "-luv"]
        report["libuv_library_sha256"] = digest(prefix / "lib" / "libuv.so")
    else:
        cflags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "libuv"], text=True))
        libraries = shlex.split(subprocess.check_output(["pkg-config", "--libs", "libuv"], text=True))
    with tempfile.TemporaryDirectory(prefix="pystachy-uvio-dogfood-") as temporary:
        build = Path(temporary)
        env["PYSTACHY_CACHE"] = str(build / "cache")
        report["environment"] = {key: env[key] for key in
                                 ("PYSTACHY_CACHE", "PYSTACHY_PROGRAM_CACHE", "PYTHONNOUSERSITE",
                                  "PYTHONDONTWRITEBYTECODE", "PYTHONUTF8", "PYTHONHASHSEED")}
        library = build / "libpystachy_uvio.so"
        cc = shlex.split(args.cc)
        report["cc"] = run(cc + ["--version"], env).decode().splitlines()[0]
        flags = ["-std=c11", "-D_GNU_SOURCE", "-Wall", "-Wextra", "-Werror", "-O2", "-shared", "-fPIC"] + cflags
        report["cc_flags"] = cc[1:] + flags
        report["cc_link_flags"] = libraries
        build_start = time.perf_counter()
        run(cc + flags + [str(HERE / "bridge.c")] + libraries + ["-o", str(library)], env)
        report["bridge_build_seconds"] = time.perf_counter() - build_start
        report["bridge_sha256"] = digest(library)
        native = ctypes.CDLL(str(library))
        native.uvio_version.restype = ctypes.c_char_p
        report["libuv"] = native.uvio_version().decode()
        env["LD_LIBRARY_PATH"] = str(build) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        modes = {}
        for name, command in interpreters.items():
            modes[name + "_stdlib"] = command + [str(HERE / "socket_exchange.py")]
            modes[name + "_uvio"] = command + [str(HERE / "source_exchange.py")]
        if not args.cpython_only:
            executable = build / "source-exchange"
            build_start = time.perf_counter()
            run(compiler + ["build", str(HERE / "source_exchange.py"), "-o", str(executable)], env)
            report["aot_build_seconds"] = time.perf_counter() - build_start
            report["aot_sha256"] = digest(executable)
            report["compiler_command"] = compiler
            modes["pystachy_aot"] = [str(executable)]
            for label, command, extra in [
                ("jit", compiler + ["run", str(HERE / "source_exchange.py")], {}),
                ("jit_gc", compiler + ["run", str(HERE / "source_exchange.py")], {"PYSTACHY_GC_STRESS_PROGRAM": "1"}),
                ("aot_gc", [str(executable)], {"PYSTACHY_GC_STRESS": "1"}),
            ]:
                with Peer() as peer:
                    command_args = [str(source), str(peer.port), "4096", "2", "1"]
                    started = time.perf_counter()
                    output = run(command + command_args, env | extra)
                    report["validation"][label] = parse_sample(output, source_size, 4096, 1)
                    report["validation"][label]["process_seconds"] = time.perf_counter() - started
        for chunk in args.chunks:
            for concurrency in args.concurrency:
                measurements = {name: [] for name in modes}
                for repetition in range(args.samples):
                    order = list(modes) if repetition % 2 == 0 else list(reversed(modes))
                    for name in order:
                        with Peer() as peer:
                            command_args = [str(source), str(peer.port), str(chunk), str(concurrency), str(args.rounds)]
                            started = time.perf_counter()
                            output = run(modes[name] + command_args, env, timeout=180)
                            process_seconds = time.perf_counter() - started
                        sample = parse_sample(output, source_size, chunk, args.rounds)
                        sample["process_seconds"] = process_seconds
                        measurements[name].append(sample)
                for name, samples in measurements.items():
                    seconds = [sample["seconds"] for sample in samples]
                    result = {"mode": name, "chunk_bytes": chunk, "concurrency": concurrency,
                              "samples": samples, "median_seconds": statistics.median(seconds),
                              "min_seconds": min(seconds), "max_seconds": max(seconds),
                              "median_process_seconds": statistics.median(sample["process_seconds"] for sample in samples)}
                    result["received_mib_per_second"] = source_size * args.rounds / (1024 * 1024) / result["median_seconds"]
                    report["results"].append(result)
                    print(f"{name} chunk={chunk} concurrency={concurrency}: {result['median_seconds']:.6f}s")
        if args.profile:
            args.profile = args.profile.resolve()
            args.profile.mkdir(parents=True, exist_ok=True)
            report["profiles"] = {}
            report["profile_validation"] = {}
            for name, script in [("cpython_uvio", "source_exchange.py"), ("cpython_stdlib", "socket_exchange.py")]:
                path = args.profile / (name + ".pstats")
                with Peer() as peer:
                    output = run([sys.executable, "-m", "cProfile", "-o", str(path), str(HERE / script),
                                 str(source), str(peer.port), "4096", "8", str(args.rounds)], env)
                report["profile_validation"][name] = parse_sample(output, source_size, 4096, args.rounds)
                report["profiles"][name] = profile_summary(path)
    report["sources_after"] = source_hashes(source)
    if report["sources_after"] != before:
        raise RuntimeError("consumed sources changed; rerun from a fixed tree")
    if not args.cpython_only:
        report["compiler_sources_after"] = compiler_hashes()
        if report["compiler_sources_after"] != report["compiler_sources_before"]:
            raise RuntimeError("compiler/runtime sources changed; rerun from a fixed tree")
        if any(digest(Path(path)) != checksum for path, checksum in report["compiler_files"].items()):
            raise RuntimeError("compiler command files changed; rerun from a fixed tree")
    report["loadavg_after"] = os.getloadavg() if hasattr(os, "getloadavg") else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--cpython-only", action="store_true", help="skip native Pystachy; additional interpreters still run")
    parser.add_argument("--interpreter", action="append", default=[], metavar="NAME=COMMAND")
    parser.add_argument("--libuv-prefix", type=Path)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=64)
    parser.add_argument("--chunks", type=int, nargs="+", default=[256, 4096, 32768])
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 8])
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--profile", type=Path, help="write separate, untimed CPython cProfile records")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = {"result": "running"}
    write_report(args.json, report)
    try:
        benchmark(args, report)
    except Exception as error:
        report.update(result="fail", error=str(error))
        write_report(args.json, report)
        print(f"uvio dogfood failed: {error}", file=sys.stderr)
        return 1
    report["result"] = "pass"
    write_report(args.json, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
