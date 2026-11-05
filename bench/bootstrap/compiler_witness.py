"""Compare rebuilt compilers on identical self-IR work, alternating order."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sys.path.insert(0, str(ROOT / "tools"))
    from bootstrap_pipeline import host_state, source_identity

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    compilers = {name: path.resolve() for name, path in
                 (("baseline", args.baseline), ("candidate", args.candidate))}
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    report = {"status": "failed", "samples": args.samples, "results": [],
              "harness_sha256": digest(Path(__file__)),
              "compiler_sha256": {k: digest(v) for k, v in compilers.items()},
              "source": source_identity(ROOT), "host_before": host_state(),
              "cpu_affinity": affinity[:1], "workload": "ir pystachy.py"}
    # The benchmark is sequential; pin it and inherited children when available.
    if affinity:
        os.sched_setaffinity(0, {affinity[0]})
    expected = None
    try:
        with tempfile.TemporaryDirectory(prefix="pystachy-compiler-witness-") as temporary:
            output = Path(temporary) / "compiler.ll"
            for sample in range(args.samples):
                order = ("baseline", "candidate") if sample % 2 == 0 else ("candidate", "baseline")
                for label in order:
                    output.unlink(missing_ok=True)
                    command = [str(compilers[label]), "ir", "pystachy.py", "-o", str(output)]
                    before = resource.getrusage(resource.RUSAGE_CHILDREN)
                    start = time.monotonic()
                    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=120)
                    elapsed = time.monotonic() - start
                    after = resource.getrusage(resource.RUSAGE_CHILDREN)
                    if result.returncode or result.stdout or result.stderr:
                        raise RuntimeError(f"{label} emitted an error: {result.returncode}, {result.stderr!r}")
                    if not output.is_file() or output.stat().st_size == 0:
                        raise RuntimeError(f"{label} did not produce a nonempty IR witness")
                    actual = digest(output)
                    if expected is not None and actual != expected:
                        raise RuntimeError("compiler IR changed")
                    expected = actual
                    report["results"].append({"label": label, "sample": sample, "command": command,
                                              "wall_seconds": elapsed,
                                              "cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                                              "ir_sha256": actual})
        if {k: digest(v) for k, v in compilers.items()} != report["compiler_sha256"]:
            raise RuntimeError("compiler executable changed")
        if source_identity(ROOT) != report["source"]:
            raise RuntimeError("compiler source changed")
        report["status"] = "passed"
    finally:
        if affinity:
            os.sched_setaffinity(0, affinity)
        report["host_after"] = host_state()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
