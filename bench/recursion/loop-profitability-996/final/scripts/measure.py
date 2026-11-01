"""Bounded, serial measurements for the PR 996 scalar-depth prototype."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import re
import resource
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
PY = ROOT / "toolchain/venv/bin/python"
LLVM = Path("/usr/lib/llvm-18/bin")
SOURCES = ROOT / "pystachy-baseline"
ROLES = {"main": ROOT / "pystachy-main", "baseline": SOURCES,
         "value": ROOT / "pystachy-value", "policy": ROOT / "pystachy-policy",
         "policy_final": ROOT / "pystachy-policy-final"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment(role):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYSTACHY_") and k != "PYTHONPATH"}
    env.update(PYSTACHY_LLVM=str(LLVM), PYSTACHY_HOME=str(ROLES[role]),
               PYSTACHY_CACHE=str(OUT / ("cache-" + role)), PYTHONHASHSEED="0")
    return env


def execute(command, role, timeout=180):
    cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    result = subprocess.run([str(x) for x in command], cwd=ROLES[role],
                            env=environment(role), capture_output=True,
                            text=True, timeout=timeout)
    cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    record = {"command": [str(x) for x in command], "cwd": str(ROLES[role]),
              "wall_s": time.perf_counter() - start, "returncode": result.returncode,
              "cpu_s": cpu_after.ru_utime + cpu_after.ru_stime - cpu_before.ru_utime - cpu_before.ru_stime,
              "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode:
        raise RuntimeError(json.dumps(record))
    return record


def manifest(role):
    directory = ROLES[role]
    paths = [directory / "pystachy.py", directory / "runtime.py", directory / "runtime.c",
             directory / "pyembed.c", directory / "pyext.c"]
    for sub in ("src", "lib", "ryu", "mpz"):
        paths.extend(p for p in (directory / sub).rglob("*")
                     if p.is_file() and p.suffix in (".py", ".c", ".h"))
    return {str(p.relative_to(directory)): digest(p) for p in sorted(set(paths))}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.replace(path)


def oracle(mode, n):
    return execute([PY, SOURCES / "bench/smoke/text.py", mode, str(n)], "baseline", 180)["stdout"]


def run_text(role, mode, n, expected, profile=False):
    exe = OUT / role / "text"
    command = [exe, mode, str(n)]
    if profile:
        command = ["valgrind", "--tool=callgrind", "--compress-strings=no",
                   "--compress-pos=no", "--dump-instr=yes",
                   "--callgrind-out-file=" + str(OUT / role / (mode + ".callgrind")),
                   *command]
    record = execute(command, role, 600 if profile else 180)
    if record["stdout"] != expected:
        raise ValueError((role, record["stdout"], expected))
    match = re.search(r"^seconds ([0-9.eE+-]+)$", record["stderr"], re.M)
    if not match:
        raise ValueError(record["stderr"])
    record["loop_s"] = float(match.group(1))
    if record["loop_s"] <= 0:
        raise ValueError("nonpositive timing")
    record["binary_sha256"] = digest(exe)
    return record


def prepare(role):
    directory = OUT / role
    directory.mkdir(parents=True, exist_ok=True)
    before = manifest(role)
    records = []
    for kind in ("ir", "build"):
        target = directory / ("text.ll" if kind == "ir" else "text")
        records.append(execute([PY, ROLES[role] / "pystachy.py", kind,
                                SOURCES / "bench/smoke/text.py", "-o", target], role))
    records.append(run_text(role, "fnmatch", 1000, oracle("fnmatch", 1000)))
    if before != manifest(role):
        raise ValueError("source changed during preparation")
    result = {"role": role, "inputs": before, "records": records,
              "input_source": str(SOURCES / "bench/smoke/text.py"),
              "source_sha256": digest(SOURCES / "bench/smoke/text.py"),
              "binary_sha256": digest(directory / "text"),
              "llvm_sha256": digest(directory / "text.ll"),
              "llvm_lines": len((directory / "text.ll").read_text().splitlines()),
              "binary_bytes": (directory / "text").stat().st_size}
    save(directory / "prepare.json", result)
    print(role, "prepared", result["llvm_lines"], "LLVM lines", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "profile", "time"))
    parser.add_argument("roles", nargs="+", choices=ROLES)
    parser.add_argument("--mode", default="fnmatch", choices=("fnmatch", "json", "repair_scan"))
    parser.add_argument("--n", type=int, default=10000)
    args = parser.parse_args()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    if args.action == "prepare":
        for role in args.roles:
            prepare(role)
        return
    expected = oracle(args.mode, args.n)
    before = {role: digest(OUT / role / "text") for role in args.roles}
    result = {"action": args.action, "mode": args.mode, "n": args.n,
              "controller_sha256": digest(Path(__file__)),
              "python": sys.version, "platform": platform.platform(),
              "affinity": sorted(os.sched_getaffinity(0)), "oracle": expected,
              "binary_sha256": before, "observations": []}
    filename = OUT / (args.action + "-" + args.mode + "-" + str(args.n) + "-" + "-".join(args.roles) + ".json")
    if args.action == "profile":
        orders = [tuple(args.roles)]
    else:
        for role in args.roles:
            run_text(role, args.mode, args.n, expected)
        orders = list(itertools.permutations(args.roles))
        if len(orders) == 2:
            orders *= 3
    for order in orders:
        round_result = {}
        for role in order:
            record = run_text(role, args.mode, args.n, expected, args.action == "profile")
            round_result[role] = record
            print(args.action, args.mode, role, record["loop_s"], flush=True)
        result["observations"].append(round_result)
        save(filename, result)
    if before != {role: digest(OUT / role / "text") for role in args.roles}:
        raise ValueError("binary changed during observations")
    result["medians"] = {role: statistics.median(r[role]["loop_s"] for r in result["observations"])
                         for role in args.roles}
    result["complete"] = True
    save(filename, result)
    print(json.dumps(result["medians"]), flush=True)


if __name__ == "__main__":
    main()
