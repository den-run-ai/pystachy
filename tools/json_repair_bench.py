"""Interleave JSON-repair variants and retain checked timings and process memory.

The JSON config supplies variants (name, source, commands, optional env/identity)
and cases (name, probe, args). Commands are arrays, never shell strings. Probe
programs accept their normal arguments followed by BATCHES WARMUPS. Compilation
is a separate explicit step. See bench/json_repair/ACCUMULATOR.md.
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
import subprocess
import tempfile
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_identity(root):
    root = Path(root).resolve()
    files = set()
    for area in ("src", "lib", "ports/json_repair", "bench/json_repair"):
        files.update(path for path in (root / area).rglob("*.py") if path.is_file())
    for name in ("runtime.c", "runtime.py", "pystachy.py", "Makefile", ".python-version"):
        path = root / name
        if path.is_file():
            files.add(path)
    # Includes ignored/untracked Python sources in these consumed search roots.
    return {
        "root": str(root),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "status": subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, text=True
        ),
        "sha256": {str(path.relative_to(root)): digest(path) for path in sorted(files)},
    }


def command_identity(command):
    executable = shutil.which(command[0])
    if executable is None:
        raise ValueError(f"command not found: {command[0]}")
    files = {str(Path(executable).resolve())}
    files.update(str(Path(arg).resolve()) for arg in command[1:] if Path(arg).is_file())
    return {name: digest(name) for name in sorted(files)}


def parse_output(output, batches, warmups):
    measured = []
    warmed = []
    witness = []
    for line in output.splitlines():
        if line.startswith(("seconds ", "warmup_seconds ")):
            kind, value = line.split(" ", 1)
            value = float(value)
            if not math.isfinite(value) or value < 0:
                raise ValueError("non-finite or negative timing")
            (measured if kind == "seconds" else warmed).append(value)
        else:
            witness.append(line)
    if len(measured) != batches or len(warmed) != warmups:
        raise ValueError("missing or extra timing batches")
    if not witness or not any(line.startswith(("witness ", "outputs ")) for line in witness):
        raise ValueError("missing complete-result witness")
    return {"seconds": measured, "warmup_seconds": warmed, "witness": witness,
            "median_seconds": statistics.median(measured)}


def run_process(command, env, timeout):
    # wait4 gives this child's whole-process peak RSS; it includes startup/JIT,
    # input creation and validation, unlike the internal repair-loop timer.
    if not hasattr(os, "wait4"):
        raise RuntimeError("this memory-measurement runner requires POSIX wait4")
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        start = time.perf_counter()
        process = subprocess.Popen(command, env=env, stdout=output, stderr=errors)
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                process.returncode = os.waitstatus_to_exitcode(status)
                break
            if time.perf_counter() - start > timeout:
                process.kill()
                _, status, usage = os.wait4(process.pid, 0)
                process.returncode = os.waitstatus_to_exitcode(status)
                raise TimeoutError(f"benchmark timed out after {timeout}s: {command}")
            time.sleep(0.01)
        wall = time.perf_counter() - start
        output.seek(0)
        errors.seek(0)
        stdout = output.read().decode()
        stderr = errors.read().decode()
    if process.returncode:
        raise RuntimeError(f"benchmark exited {process.returncode}: {command}\n{stdout}\n{stderr}")
    # Linux reports KiB; macOS reports bytes.
    peak = usage.ru_maxrss * (1 if platform.system() == "Darwin" else 1024)
    return {"stdout": stdout, "stderr": stderr, "process_wall_seconds": wall,
            "whole_process_peak_rss_bytes": peak}


def validate_config(config):
    for group in ("variants", "cases"):
        rows = config.get(group)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"nonempty {group} required")
        names = [row.get("name") for row in rows]
        if not all(isinstance(name, str) and name for name in names) or len(set(names)) != len(names):
            raise ValueError(f"unique nonempty {group} names required")
    if len(config["variants"]) < 2:
        raise ValueError("at least two variants required")
    for variant in config["variants"]:
        if not Path(variant["source"]).is_dir():
            raise ValueError("variant source directory is missing")
        if not isinstance(variant.get("env", {}), dict):
            raise ValueError("variant env must be a mapping")
        for case in config["cases"]:
            command = variant["commands"][case["probe"]]
            if not isinstance(command, list) or not command or not all(isinstance(arg, str) for arg in command):
                raise ValueError("commands must be nonempty argument arrays")
    for case in config["cases"]:
        if not isinstance(case["args"], list) or not all(isinstance(arg, str) for arg in case["args"]):
            raise ValueError("case args must be string arrays")


def run_campaign(config, *, pairs, batches, warmups, cpu, timeout):
    validate_config(config)
    variants = config["variants"]
    clean_env = {key: value for key, value in os.environ.items()
                 if not key.startswith("PYSTACHY_") and key not in ("PYTHONPATH", "PYTHONHOME")}
    report = {
        "config": config, "pairs": pairs, "batches": batches, "warmups": warmups,
        "platform": platform.platform(), "runner_python": platform.python_version(), "cpu": cpu,
        "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                           if line.startswith("model name")), platform.processor()) if Path("/proc/cpuinfo").exists() else platform.processor(),
        "memory_scope": "whole child process peak RSS, including startup/JIT and input/validation; not retained heap",
        "timing_scope": "repair loops; input creation, full-result validation, startup and compilation excluded",
        "identities": {}, "samples": [], "summary": {},
    }
    for variant in variants:
        report["identities"][variant["name"]] = {
            "source": source_identity(variant["source"]),
            "commands": {name: command_identity(command) for name, command in variant["commands"].items()},
            "provided": variant.get("identity", {}),
        }
    witnesses = {}
    for pair in range(pairs):
        ordered = variants[pair % len(variants):] + variants[:pair % len(variants)]
        for case in config["cases"]:
            for variant in ordered:
                command = variant["commands"][case["probe"]] + case["args"] + [str(batches), str(warmups)]
                env = dict(clean_env, **variant.get("env", {}))
                sample = run_process(command, env, timeout)
                sample.update(parse_output(sample["stdout"], batches, warmups))
                if case["name"] in witnesses and sample["witness"] != witnesses[case["name"]]:
                    raise ValueError(f"complete-result witness mismatch: {case['name']} / {variant['name']}")
                witnesses[case["name"]] = sample["witness"]
                sample.update({"pair": pair, "case": case["name"], "variant": variant["name"], "command": command})
                report["samples"].append(sample)
                print(f"{pair + 1}/{pairs} {case['name']} {variant['name']}: {sample['median_seconds']:.6f}s", flush=True)
    for case in config["cases"]:
        report["summary"][case["name"]] = {}
        for variant in variants:
            samples = [sample for sample in report["samples"]
                       if sample["case"] == case["name"] and sample["variant"] == variant["name"]]
            report["summary"][case["name"]][variant["name"]] = {
                "median_seconds": statistics.median(sample["median_seconds"] for sample in samples),
                "process_medians_seconds": [sample["median_seconds"] for sample in samples],
                "peak_rss_bytes": [sample["whole_process_peak_rss_bytes"] for sample in samples],
            }
    # Fail if a source or executable changes during the campaign.
    for variant in variants:
        before = report["identities"][variant["name"]]
        if before["source"] != source_identity(variant["source"]):
            raise ValueError(f"source changed while timing: {variant['name']}")
        for name, command in variant["commands"].items():
            if before["commands"][name] != command_identity(command):
                raise ValueError(f"executable changed while timing: {variant['name']}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=5)
    parser.add_argument("--batches", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=6)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if args.pairs < 1 or args.batches < 1 or args.warmups < 0 or args.timeout <= 0:
        parser.error("pairs/batches/timeout must be positive; warmups nonnegative")
    affinity = os.sched_getaffinity(0)
    if args.cpu not in affinity:
        parser.error("cpu is outside the available affinity mask")
    try:
        os.sched_setaffinity(0, {args.cpu})
        report = run_campaign(json.loads(args.config.read_text()), pairs=args.pairs,
                              batches=args.batches, warmups=args.warmups, cpu=args.cpu, timeout=args.timeout)
    finally:
        os.sched_setaffinity(0, affinity)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
