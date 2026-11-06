#!/usr/bin/env python3
"""Count complete-process instructions for existing, hash-verified native builds.

Callgrind is a separate untimed experiment. It includes startup, data preparation,
validation, the first batch and one measured batch; no wall-clock result is used.
Run under the same exclusive lock as run.py. VALGRIND_LIB may be set for an unpacked
Valgrind distribution; a normally installed Valgrind needs no such setting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from run import ROOT, witness


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--valgrind", default="valgrind")
    args = parser.parse_args()
    measured = json.loads(args.results.read_text())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    builds = args.results.resolve().parent
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYTHONPATH"] = str(ROOT / "ports")
    os.sched_setaffinity(0, set(measured["cpu_affinity"]))
    if digest(builds / "libtextkernels.so") != measured["dependency"]["adapter_sha256"]:
        raise ValueError("adapter bytes changed since measured builds")
    sources = {"json": ROOT / "bench/extended/json_scan.py", "numeric": ROOT / "bench/text_kernels/numeric_load.py"}
    for source in sources.values():
        if digest(source) != measured["source_hashes"][str(source.relative_to(ROOT))]:
            raise ValueError(f"workload source changed: {source}")
    result = {
        "valgrind": subprocess.check_output([args.valgrind, "--version"], env=env, text=True).strip(),
        "method": "Callgrind Ir for entire native process; warmups=0, samples=1; clocks ignored",
        "cpu_affinity": measured["cpu_affinity"], "native_results_sha256": digest(args.results),
        "counter_script_sha256": digest(Path(__file__)), "rows": [],
    }
    cases = [
        ("json-direct-short", "json", ["direct", "short", "8", "10000", "0", "1"]),
        ("json-direct-long", "json", ["direct", "long", "8192", "1000", "0", "1"]),
        ("json-direct-unicode", "json", ["direct", "unicode", "4096", "150", "0", "1"]),
        ("numeric-plain", "numeric", ["plain", "200", "0", "1"]),
        ("numeric-long", "numeric", ["long", "100", "0", "1"]),
        ("numeric-underscores", "numeric", ["underscores", "100", "0", "1"]),
    ]
    for label, kind, argv in cases:
        oracle = subprocess.run([sys.executable, str(sources[kind]), *argv], env=env,
                                capture_output=True, text=True, check=True)
        if oracle.stderr:
            raise ValueError(f"unexpected CPython diagnostics: {label}")
        for name, variant in measured["variants"].items():
            exe = builds / name / kind
            exe_hash = digest(exe)
            if exe_hash != variant["builds"][kind]["sha256"]:
                raise ValueError(f"native executable changed: {exe}")
            prefix = output / (label + "-" + name)
            command = [args.valgrind, "--tool=callgrind", "--error-exitcode=97",
                       f"--callgrind-out-file={prefix}.callgrind", f"--log-file={prefix}.log", str(exe), *argv]
            run = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
            if run.stderr or witness(run.stdout) != witness(oracle.stdout):
                raise ValueError(f"native output mismatch: {label} {name}")
            Path(str(prefix) + ".out").write_text(run.stdout)
            profile = Path(str(prefix) + ".callgrind").read_text()
            events = [line for line in profile.splitlines() if line.startswith("events:")]
            totals = [line for line in profile.splitlines() if line.startswith("summary:")]
            if events != ["events: Ir"] or len(totals) != 1:
                raise ValueError(f"unexpected Callgrind counters: {prefix}")
            instructions = int(totals[0].split()[1])
            result["rows"].append({"case": label, "variant": name, "instructions": instructions,
                                   "executable_sha256": exe_hash, "command": command, "witness": witness(run.stdout)})
            (output / "instructions.json").write_text(json.dumps(result, indent=2) + "\n")
            print(label, name, instructions, flush=True)


if __name__ == "__main__":
    main()
