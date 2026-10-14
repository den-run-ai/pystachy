"""Compare ordinary regex tuple consumers with same-body fixed-shape controls.

This measures specialization headroom without feedback or guarded clones.
End-to-end static controls construct captures differently; only consumer-only
comparisons isolate the tuple consumer representation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench" / "regex_capture_tuples.py"


def command(args: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def source_hashes() -> dict[str, str]:
    paths = [ROOT / "pystachy.py", ROOT / "runtime.c", ROOT / "runtime.py"]
    paths += sorted((ROOT / "src" / "pystachy_compiler").glob("*.py"))
    paths += sorted((ROOT / "lib" / "re").glob("*.py"))
    paths += sorted((ROOT / "ryu").glob("*.c")) + sorted((ROOT / "ryu").glob("*.h"))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def metadata(compiler: list[str], env: dict[str, str], hashes: dict[str, str]) -> dict[str, object]:
    host = platform.uname()
    cpu_model = "not recorded"
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    llvm_home = env.get("PYSTACHY_LLVM", "")
    clang = str(Path(llvm_home) / "clang") if llvm_home else "clang"
    try:
        clang_version = command([clang, "--version"], env)
    except (OSError, RuntimeError):
        clang_version = "not recorded"
    git_base = command(["git", "rev-parse", "HEAD"], env)
    changed_sources: list[str] = []
    for name, digest in hashes.items():
        committed = subprocess.run(["git", "show", f"{git_base}:{name}"], cwd=ROOT, env=env, capture_output=True, check=False)
        if committed.returncode != 0 or hashlib.sha256(committed.stdout).hexdigest() != digest:
            changed_sources.append(name)
    return {"started_utc": datetime.now(timezone.utc).isoformat(),
            "compiler_command": compiler, "python_version": sys.version,
            "git_base_commit": git_base,
            "build_source_changes_from_git_base": changed_sources,
            "source_provenance": "Working-tree sources; exact build-source hashes recorded, including changes from the committed base.",
            "compiler_runtime_and_regex_sources_sha256": hashes,
            "combined_build_sources_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            "clang_version": clang_version,
            "build_environment": {key: env.get(key, "unset") for key in ["PYSTACHY_LLVM", "PYSTACHY_CFLAGS", "PYSTACHY_OPT", "PYSTACHY_NOOPT", "PYSTACHY_VARIADIC_TUPLES", "PYSTACHY_GC_STRESS"]},
            "host": {"system": host.system, "release": host.release, "version": host.version,
                     "machine": host.machine, "cpu_model": cpu_model,
                     "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else "not recorded",
                     "cpu_frequency": "not recorded", "other_host_workload": "not recorded"},
            "timing": "Native time.process_time; mode order reversed on alternate samples; no CPU pinning requested."}


def timing(binary: Path, mode: str, repeats: int, records: int, env: dict[str, str]) -> tuple[int, float]:
    output = command([str(binary), mode, str(repeats), str(records)], env)
    fields = output.split()
    if len(fields) != 3 or fields[0] != mode:
        raise RuntimeError(f"unexpected benchmark output: {output}")
    return int(fields[1]), float(fields[2])


def measure(binary: Path, samples: int, repeats: int, consumer_repeats: int, records: int, env: dict[str, str]) -> dict[str, object]:
    times: dict[str, list[float]] = {mode: [] for mode in ["endtoend", "static", "consumer", "concrete", "render", "render-static"]}
    checksums: dict[str, int] = {}
    for sample in range(samples):
        modes = list(times) if sample % 2 == 0 else list(reversed(times))
        for mode in modes:
            count = consumer_repeats if mode in ["consumer", "concrete", "render", "render-static"] else repeats
            checksum, elapsed = timing(binary, mode, count, records, env)
            if mode in checksums and checksums[mode] != checksum:
                raise RuntimeError(f"unstable checksum for {mode}")
            checksums[mode] = checksum
            times[mode].append(elapsed)
    if checksums["endtoend"] != checksums["static"] or checksums["consumer"] != checksums["concrete"] or checksums["render"] != checksums["render-static"]:
        raise RuntimeError(f"generic/fixed checksum mismatch: {checksums}")
    medians = {mode: statistics.median(values) for mode, values in times.items()}
    paired = {name: [a / b for a, b in zip(times[generic], times[fixed], strict=True)]
              for name, generic, fixed in [("signature", "consumer", "concrete"), ("render", "render", "render-static"), ("endtoend", "endtoend", "static")]}
    return {"cpu_seconds": times, "median_cpu_seconds": medians, "checksums": checksums,
            "consumer_fixed_speedup": medians["consumer"] / medians["concrete"],
            "render_fixed_speedup": medians["render"] / medians["render-static"],
            "endtoend_fixed_speedup": medians["endtoend"] / medians["static"],
            "paired_fixed_speedups": paired,
            "median_paired_fixed_speedup": {name: statistics.median(values) for name, values in paired.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, help="Self-hosted compiler; defaults to this Python -m pystachy")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=1000)
    parser.add_argument("--consumer-repeats", type=int, default=20000)
    parser.add_argument("--records", type=int, default=64)
    parser.add_argument("--json", type=Path, help="Write the complete measurement report")
    args = parser.parse_args()
    if min(args.samples, args.repeats, args.consumer_repeats, args.records) <= 0:
        parser.error("sample, repetition, and record counts must be positive")
    compiler = [str(args.compiler.resolve())] if args.compiler else [sys.executable, "-m", "pystachy"]
    env = dict(os.environ)
    for key in ["PYSTACHY_SKEW_PROFILE", "PYSTACHY_SKEW_STATS"]:
        env.pop(key, None)
    env["PYSTACHY_VARIADIC_TUPLES"] = "1"
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    build_hashes = source_hashes()
    report: dict[str, object] = {"source_sha256": digest, "samples": args.samples, "records": args.records,
                                "repeats": args.repeats, "consumer_repeats": args.consumer_repeats,
                                "source_path": str(SOURCE.relative_to(ROOT)),
                                "metadata": metadata(compiler, env, build_hashes),
                                "scope": "Original regex matching and Match.groups(); consumer-only times exclude producer costs."}
    with tempfile.TemporaryDirectory(prefix="pystachy-regex-groups-") as folder:
        work = Path(folder)
        baseline = work / "baseline"
        command(compiler + ["build", str(SOURCE), "-o", str(baseline)], env)
        report["heldout_check"] = command([str(baseline), "check"], env)
        baseline_report = measure(baseline, args.samples, args.repeats, args.consumer_repeats, args.records, env)
        report["baseline"] = baseline_report
        print("Baseline: " + json.dumps(baseline_report, sort_keys=True))
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != digest:
        raise RuntimeError("benchmark source changed during measurements")
    report["build_sources_unchanged_during_measurement"] = source_hashes() == build_hashes
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
