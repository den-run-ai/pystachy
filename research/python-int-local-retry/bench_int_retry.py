#!/usr/bin/env python3
"""Temporary, serial native-front-end benchmark for the local int retry prototype.

Prepare without invoking either compiler:
  python bench_int_retry.py --prepare-only

After both builds are finished and other heavy jobs stop:
  python bench_int_retry.py --check-native-output

Each reported sample is a fresh native `pystachy ir` process. No LLVM invocation,
native-code build, JIT startup, or program execution is included in those samples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = HERE / "pystachy-int-base" / "pystachy"
DEFAULT_PROTOTYPE = HERE / "pystachy-int-retry" / "pystachy"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def plain_helpers(count: int, prefix: str = "sibling") -> str:
    return "\n".join(
        f"def {prefix}{index}(n: int) -> int:\n"
        f"    return n * {index + 2} + {index + 7}\n"
        for index in range(count)
    )


def prepare(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    scalar = plain_helpers(64) + "\n" + (
        "def accumulate(count: int) -> int:\n"
        "    total = 0\n"
        "    for i in range(count):\n"
        "        total += i\n"
        "    return total\n\n"
    )
    scalar += "\n".join(f"print(sibling{i}({i + 1}))" for i in range(64))
    scalar += "\nprint(accumulate(2000))\n"
    write(directory / "scalar" / "main.py", "# pystachy: python-int\n" + scalar)
    write(directory / "default_control" / "main.py", scalar)

    mixed = directory / "mixed_callable"
    write(mixed / "worker.py", (
        "from typing import Callable\n\n"
        "def square(n: int) -> int:\n"
        "    return n * n\n\n"
        "function: Callable[[int], int] = square\n\n"
        "def accumulate(count: int):\n"
        "    total = 0\n"
        "    for i in range(count):\n"
        "        total += function(i)\n"
        "    return total\n"
    ))
    main = "# pystachy: python-int\nfrom worker import accumulate\n"
    for group in range(4):
        write(mixed / f"group{group}.py", plain_helpers(16))
        main += f"import group{group}\n"
    for group in range(4):
        for index in range(16):
            main += f"print(group{group}.sibling{index}({group * 16 + index + 1}))\n"
    main += "print(accumulate(2000))\n"
    write(mixed / "main.py", main)

    manifest = {"python": sys.version, "cases": {}}
    for case in ["scalar", "mixed_callable", "default_control"]:
        path = directory / case / "main.py"
        result = subprocess.run([sys.executable, str(path)], capture_output=True, check=True)
        if result.stderr:
            raise RuntimeError(f"CPython emitted stderr for {case}: {result.stderr!r}")
        (directory / case / "expected.out").write_bytes(result.stdout)
        manifest["cases"][case] = {
            "entry": str(path),
            "sources": {p.name: digest(p.read_bytes()) for p in sorted(path.parent.glob("*.py"))},
            "expected_stdout_sha256": digest(result.stdout),
            "expected_stdout_lines": len(result.stdout.splitlines()),
        }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def checked(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    completed = subprocess.run(command, capture_output=True, check=False, timeout=300, **kwargs)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {command!r}\n"
                           f"{completed.stderr.decode(errors='replace')}")
    return completed


def compiler_environment(binary: Path, output: Path) -> dict[str, str]:
    # Preserve the selected matching toolchain for optional untimed run checks.
    # `ir` returns before locating or executing LLVM.
    env = {name: value for name, value in os.environ.items()
           if not name.startswith("PYSTACHY_")}
    if "PYSTACHY_LLVM" in os.environ:
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    env["PYSTACHY_HOME"] = str(binary.parent)
    env["XDG_CACHE_HOME"] = str(output / "runtime_cache" / binary.parent.name)
    return env


def compiler_identity(binary: Path) -> dict:
    repo = binary.parent
    files = [repo / "pystachy.py", *repo.glob("src/**/*.py"), *repo.glob("lib/**/*.py")]
    hashes = {str(p.relative_to(repo)): digest(p.read_bytes()) for p in sorted(files)}
    return {
        "binary": str(binary),
        "binary_sha256": digest(binary.read_bytes()),
        "git_head": checked(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.decode().strip(),
        "git_status": checked(["git", "-C", str(repo), "status", "--short"]).stdout.decode(),
        "compiler_and_lib_sources_sha256": digest(json.dumps(hashes, sort_keys=True).encode()),
    }


def measure(command: list[str], env: dict[str, str]) -> dict:
    start_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    completed = checked(command, env=env)
    wall_ns = time.perf_counter_ns() - start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    if completed.stdout or completed.stderr:
        raise RuntimeError(f"unexpected compiler output: {completed.stdout!r} {completed.stderr!r}")
    return {
        "wall_seconds": wall_ns / 1e9,
        "cpu_seconds": ((usage.ru_utime - start_usage.ru_utime)
                        + (usage.ru_stime - start_usage.ru_stime)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--prototype", type=Path, default=DEFAULT_PROTOTYPE)
    parser.add_argument("--output", type=Path, default=HERE / "int_retry_benchmark")
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--check-native-output", action="store_true")
    args = parser.parse_args()
    if args.samples < 1 or args.warmups < 0:
        parser.error("samples must be positive; warmups must be nonnegative")
    output = args.output.resolve()
    manifest = prepare(output / "cases")
    if args.prepare_only:
        print(f"Prepared {len(manifest['cases'])} cases and CPython outputs in {output / 'cases'}")
        return 0

    binaries = {"base": args.base.resolve(), "prototype": args.prototype.resolve()}
    identities = {name: compiler_identity(binary) for name, binary in binaries.items()}
    envs = {name: compiler_environment(binary, output) for name, binary in binaries.items()}
    case_names = list(manifest["cases"])
    commands = {}
    verified = {}
    for case in case_names:
        source = Path(manifest["cases"][case]["entry"])
        irs = {}
        for label, binary in binaries.items():
            ir = output / f"{case}-{label}.ll"
            command = [str(binary), "ir", str(source), "-o", str(ir)]
            commands[(case, label)] = command
            result = checked(command, env=envs[label])
            if result.stdout or result.stderr:
                raise RuntimeError(f"unexpected compiler output for {case}/{label}")
            irs[label] = ir.read_bytes()
        if irs["base"] != irs["prototype"]:
            raise RuntimeError(f"IR differs for {case}; inspect the two .ll files before timing")
        verified[case] = {"ir_sha256": digest(irs["base"]), "ir_bytes": len(irs["base"]),
                          "native_output_checked": False}
        if args.check_native_output:
            expected = (source.parent / "expected.out").read_bytes()
            for label, binary in binaries.items():
                result = checked([str(binary), "run", str(source)], env=envs[label])
                if result.stdout != expected or result.stderr:
                    raise RuntimeError(f"native output differs for {case}/{label}: "
                                       f"{result.stdout!r} {result.stderr!r}")
            verified[case]["native_output_checked"] = True

    allowed = os.sched_getaffinity(0)
    cpu = max(allowed) if args.cpu is None else args.cpu
    if cpu not in allowed:
        parser.error(f"CPU {cpu} not available: {sorted(allowed)}")
    samples = {case: {label: [] for label in binaries} for case in case_names}
    if not args.verify_only:
        os.sched_setaffinity(0, {cpu})
        try:
            for warmup in range(args.warmups):
                for case in case_names:
                    for label in (list(binaries) if warmup % 2 == 0 else list(reversed(binaries))):
                        checked(commands[(case, label)], env=envs[label])
            for index in range(args.samples):
                # Alternate pair order and rotate cases to avoid a one-sided time trend.
                ordered_cases = case_names[index % len(case_names):] + case_names[:index % len(case_names)]
                for case in ordered_cases:
                    labels = list(binaries) if index % 2 == 0 else list(reversed(binaries))
                    for label in labels:
                        sample = measure(commands[(case, label)], envs[label])
                        sample.update(pair=index, order=labels.index(label))
                        samples[case][label].append(sample)
                        ir = Path(commands[(case, label)][-1]).read_bytes()
                        if digest(ir) != verified[case]["ir_sha256"]:
                            raise RuntimeError(f"IR changed during timings: {case}/{label}")
        finally:
            os.sched_setaffinity(0, allowed)

    final_identities = {name: compiler_identity(binary) for name, binary in binaries.items()}
    for name in binaries:
        for field in ("binary_sha256", "compiler_and_lib_sources_sha256"):
            if identities[name][field] != final_identities[name][field]:
                raise RuntimeError(f"{name} changed during benchmark: {field}")
    summary = {}
    if not args.verify_only:
        for case in case_names:
            summary[case] = {}
            for metric in ("cpu_seconds", "wall_seconds"):
                medians = {label: statistics.median(s[metric] for s in samples[case][label])
                           for label in binaries}
                summary[case][metric] = {
                    "medians": medians,
                    "prototype_over_base": medians["prototype"] / medians["base"],
                    "paired_ratio_median": statistics.median(
                        samples[case]["prototype"][i][metric] / samples[case]["base"][i][metric]
                        for i in range(args.samples)),
                }

    result = {
        "scope": "fresh native front-end process: pystachy ir; no LLVM backend or native execution timed",
        "warning": "shared host; CPU/wall measurements are advisory, not executed instruction counts",
        "method": "15 interleaved paired samples by default; alternating binary order; rotating cases; inherited single-CPU affinity",
        "python": sys.version, "platform": platform.platform(), "cpu": cpu,
        "sample_pairs_per_case": 0 if args.verify_only else args.samples,
        "warmups_per_binary_case": 0 if args.verify_only else args.warmups,
        "compilers": identities, "inputs": manifest, "verified": verified,
        "samples": samples, "summary": summary,
    }
    report = output / "results.json"
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(f"IR identical for all {len(case_names)} cases; results: {report}")
    for case, row in summary.items():
        cpu_row = row["cpu_seconds"]
        wall_row = row["wall_seconds"]
        print(f"{case}: CPU {cpu_row['medians']['base'] * 1000:.3f} -> "
              f"{cpu_row['medians']['prototype'] * 1000:.3f} ms "
              f"({cpu_row['prototype_over_base']:.3f}x); "
              f"wall {wall_row['medians']['base'] * 1000:.3f} -> "
              f"{wall_row['medians']['prototype'] * 1000:.3f} ms "
              f"({wall_row['prototype_over_base']:.3f}x)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
