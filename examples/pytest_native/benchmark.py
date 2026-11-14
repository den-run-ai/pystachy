"""Measure one small pytest-style suite, with compilation reported separately.

The original pytest run and generated CPython/AOT runs must agree on every case
and setup/call/teardown outcome before any timing is accepted. This is an
illustrative suite, not an overall pytest benchmark or a test of CPython internals.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import pytest_native as runner  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(command: list[str], env: dict[str, str], timeout: float) -> dict:
    start = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                            text=True, timeout=timeout)
    seconds = time.perf_counter() - start
    if result.returncode != 0:
        raise ValueError(f"exit {result.returncode}: {shlex.join(command)}\n"
                         f"{result.stdout}\n{result.stderr}")
    return {"seconds": seconds, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def read_oracle(path: Path, exit_code: int) -> dict:
    records = [json.loads(line) for line in path.read_text().splitlines()]
    if not records or records[-1] != {"complete": True, "exit_code": exit_code}:
        raise ValueError("incomplete timed pytest report")
    collections = [record["collection"] for record in records if "collection" in record]
    if len(collections) != 1:
        raise ValueError("timed pytest report requires exactly one collection record")
    return {"cases": collections[0], "events": [item for item in records if "nodeid" in item],
            "exit_code": exit_code}


def source_hashes(source: Path, suite: Path) -> dict[str, str]:
    # Hash a conservative superset of native compiler/runtime/library inputs,
    # including untracked implementation files and generated source.
    files = {source, Path(__file__).resolve(), ROOT / "pystachy.py", ROOT / "runtime.py",
             ROOT / "runtime.c", ROOT / "pyext.c", ROOT / "pyembed.c", ROOT / "lljit.c",
             ROOT / "VERSION"}
    for name in ("pytest_native.py", "pytest_native_codegen.py", "pytest_native_support.py",
                 "pytest_native_fixtures.py", "pytest_native_logging.py", "pytest_native_capture.py"):
        files.add(ROOT / "tools" / name)
    for directory, suffixes in (("src", {".py"}), ("lib", {".py"}),
                                ("ryu", {".c", ".h"}), ("mpz", {".c", ".h"})):
        files.update(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and path.suffix in suffixes)
    result = {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(files)}
    result.update({"generated/" + path.name: digest(path) for path in sorted(suite.glob("*.py"))})
    return result


def benchmark(args: argparse.Namespace) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    source = ROOT / "examples" / "pytest_native" / "test_compute.py"
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    affinity_before = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    selected_cpu = args.cpu if args.cpu is not None else affinity_before[0] if affinity_before else None
    if selected_cpu is not None:
        if not hasattr(os, "sched_setaffinity") or selected_cpu not in affinity_before:
            raise ValueError("requested CPU is not in this process's allowed affinity")
        os.sched_setaffinity(0, {selected_cpu})
    # Keep caches private, and never time assertions disabled by a caller's -O setting.
    os.environ["PYSTACHY_CACHE"] = str(work / "native-cache")
    os.environ.pop("PYTHONOPTIMIZE", None)
    # Resolving a venv's executable symlink would bypass its installed pytest.
    python = str(Path(args.python).absolute()) if os.path.sep in args.python else args.python
    compiler = shlex.split(args.compiler) if args.compiler else [python, str(ROOT / "pystachy.py")]
    paths = runner.discover([source], ROOT)
    reference = runner.oracle(paths, ROOT, work / "oracle", python, args.timeout)
    if "error" in reference or reference.get("exit_code") != 0:
        raise ValueError("original pytest suite did not pass: " + json.dumps(reference))
    results = runner.run_suite(paths, ROOT, work / "generated", "aot", compiler, python, args.timeout)
    differences = runner.compare(results, reference)
    if differences:
        raise ValueError("AOT preflight differs from pytest: " + "; ".join(differences)
                         + "\n" + "\n".join(result.error + result.stderr for result in results))
    result = results[0]
    suite = work / "generated" / hashlib.sha256(result.path.encode()).hexdigest()[:16]
    executable = suite / "_pyn_suite"
    report = suite / "events-0.jsonl"
    oracle_report = work / "oracle" / "oracle.jsonl"
    native_env = runner.environment([suite, source.parent, ROOT])
    oracle_env = runner.environment([work / "oracle", ROOT])
    oracle_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    oracle_env["PYSTACHY_PYTEST_ORACLE_REPORT"] = str(oracle_report)
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        oracle_env.pop(key, None)
    commands = {
        "pytest": [python, "-m", "pytest", "-q", "-p", "_pyn_oracle", "-p", "no:cacheprovider",
                   "--noconftest", "--rootdir", str(ROOT),
                   "-c", str(work / "oracle" / "empty.ini"), str(source)],
        "generated_cpython": [python, str(suite / "_pyn_suite.py")],
        "aot": [str(executable)],
    }
    samples = []
    modes = list(commands)
    load_before = list(os.getloadavg()) if hasattr(os, "getloadavg") else []
    # Rotate execution order; each mode still launches a fresh process per sample.
    for index in range(args.samples):
        order = modes[index % len(modes):] + modes[:index % len(modes)]
        for position, mode in enumerate(order):
            (oracle_report if mode == "pytest" else report).unlink(missing_ok=True)
            measured = capture(commands[mode], oracle_env if mode == "pytest" else native_env, args.timeout)
            if mode == "pytest":
                timed_reference = read_oracle(oracle_report, measured["exit_code"])
                differences = runner.compare(results, timed_reference)
            else:
                events = runner.read_report(report, result.cases, measured["exit_code"])
                candidate = replace(result, events=events, exit_code=measured["exit_code"], state="passed")
                differences = runner.compare([candidate], reference)
                if measured["stdout"] != result.stdout:
                    differences.append("generated program stdout differs from AOT preflight")
            if differences:
                raise ValueError(f"{mode} sample {index + 1}: " + "; ".join(differences))
            samples.append({"round": index + 1, "position": position, "mode": mode,
                            "cases": len(result.cases), "phase_outcomes_match": True, **measured})
    medians = {mode: statistics.median(sample["seconds"] for sample in samples if sample["mode"] == mode)
               for mode in modes}
    versions = subprocess.check_output(
        [python, "-c", "import json,sys,pytest,pluggy,textwrap,hashlib; "
         "print(json.dumps({'python':sys.version,'pytest':pytest.__version__,'pluggy':pluggy.__version__,"
         "'textwrap_file':textwrap.__file__,'textwrap_sha256':hashlib.sha256(open(textwrap.__file__,'rb').read()).hexdigest()}))"],
        text=True, env=native_env, timeout=args.timeout)
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    clang = str(Path(llvm) / "clang") if llvm else "clang"
    llvm_version = subprocess.check_output([clang, "--version"], text=True, timeout=10).strip()
    cpu = platform.processor()
    if Path("/proc/cpuinfo").exists():
        cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")), cpu)
    return {
        "started_at_utc": started_at,
        "scope": "Five-case original illustrative suite; not general pytest or CPython interpreter performance",
        "notes": ["Each execution timing includes a fresh process and outcome report I/O, excluding build and validation parsing.",
                  "pytest includes its reporting plugin, collection and assertion rewriting; generated modes use static collection.",
                  "Native textwrap uses Pystachy's maintained port; CPython uses its own standard library.",
                  "Arithmetic loops may be optimized heavily; the suite also performs repeated text wrapping.",
                  "Compilation is not amortized in the reported process-execution ratios."],
        "source": source.relative_to(ROOT).as_posix(), "cases": result.cases,
        "repository_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10).strip(),
        "aot_executable_sha256": digest(executable),
        "versions": {**json.loads(versions), "llvm": llvm_version},
        "host": {"platform": platform.platform(), "machine": platform.machine(), "cpu": cpu,
                 "affinity_before": affinity_before, "selected_cpu": selected_cpu,
                 "load_before": load_before, "load_after": list(os.getloadavg()) if hasattr(os, "getloadavg") else []},
        "compiler_command": compiler, "commands": commands,
        "settings": {key: os.environ[key] for key in (
            "PYSTACHY_LLVM", "PYSTACHY_CACHE", "PYSTACHY_PATH", "PYSTACHY_AOT_OPT",
            "PYSTACHY_OPT", "PYSTACHY_CFLAGS", "PYSTACHY_IRCHECK", "PYSTACHY_GC_STRESS",
            "PYSTACHY_GC_STRESS_PROGRAM", "PYSTACHY_PROGRAM_CACHE",
        ) if key in os.environ},
        "aot_build_seconds": result.build_seconds, "aot_preflight_seconds": result.run_seconds,
        "original_pytest_preflight_seconds": reference["seconds"], "samples": samples,
        "median_process_seconds": medians,
        "execution_ratios": {"pytest_over_aot": medians["pytest"] / medians["aot"],
                             "generated_cpython_over_aot": medians["generated_cpython"] / medians["aot"]},
        "estimated_runs_to_amortize_build": {
            mode: math.ceil(result.build_seconds / (medians[mode] - medians["aot"]))
            if medians[mode] > medians["aot"] else None
            for mode in ("pytest", "generated_cpython")
        },
        "source_sha256": source_hashes(source, suite),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--compiler", help="compiler command; defaults to hosted compiler with --python")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build" / "pytest-native-benchmark")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--cpu", type=int, help="CPU affinity; Linux default is first allowed CPU")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1 or args.timeout <= 0:
        parser.error("samples and timeout must be positive")
    try:
        with runner.lock_work_directory(args.work_dir.resolve()):
            result = benchmark(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"benchmark failed: {error}", file=sys.stderr)
        return 1
    runner.write_changed(args.json.resolve(), json.dumps(result, indent=2) + "\n")
    print(json.dumps({"aot_build_seconds": result["aot_build_seconds"],
                      "median_process_seconds": result["median_process_seconds"],
                      "execution_ratios": result["execution_ratios"],
                      "estimated_runs_to_amortize_build": result["estimated_runs_to_amortize_build"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
