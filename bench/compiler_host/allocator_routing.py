"""Compare the old false allocator route with ordinary codegen on frozen self IR."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import random
import statistics
import sys
import time

from backend_workers import Commands, LATE
from run import atomic_json, bootstrap, measure, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=1)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    work, snapshot, llvm = args.work.resolve(), args.snapshot.resolve(), args.llvm.resolve()
    work.mkdir(parents=True, exist_ok=False)
    raw = (snapshot / "raw.ll").read_text()
    declaration = "declare ptr @pys_new(i64)\n"
    if "@pys_new(" not in raw or raw.startswith(declaration) or "\n" + declaration in raw:
        raise RuntimeError("snapshot is not the embedded-string false-positive case")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    report = {"input_sha256": sha(snapshot / "linked.bc"), "raw_ir_sha256": sha(snapshot / "raw.ll"),
              "raw_string_matches": raw.count("@pys_new("), "host": bootstrap.host_state(),
              "tools": bootstrap.tool_identity(sys.executable, str(llvm)),
              "harness_sha256": sha(Path(__file__)), "runs": [], "complete": False}
    rng = random.Random(20261106)
    runner = Commands(measure)
    try:
        with runner:
            for sample in range(args.samples):
                routes = ["staged", "ordinary"]
                rng.shuffle(routes)
                for route in routes:
                    directory = work / f"{route}-{sample}"
                    directory.mkdir()
                    commands = []
                    if route == "staged":
                        commands += [
                            [str(llvm / "clang"), "-O2", "-c", "-emit-llvm", str(snapshot / "linked.bc"),
                             "-o", str(directory / "optimized.bc")],
                            [str(llvm / "opt"), "-passes=forceattrs,always-inline", *LATE,
                             str(directory / "optimized.bc"), "-o", str(directory / "late.bc")],
                            [str(llvm / "clang"), "-O2", "-c", "-Xclang", "-disable-llvm-passes",
                             str(directory / "late.bc"), "-o", str(directory / "output.o")],
                        ]
                    else:
                        commands.append([str(llvm / "clang"), "-O2", "-c", str(snapshot / "linked.bc"),
                                         "-o", str(directory / "output.o")])
                    commands.append([str(llvm / "clang"), str(directory / "output.o"),
                                     "-o", str(directory / "compiler"), "-lm"])
                    start = time.monotonic()
                    record = {"route": route, "sample": sample, "steps": []}
                    report["runs"].append(record)
                    for command in commands:
                        result = runner.execute(command, env, 300)
                        record["steps"].append(result)
                        atomic_json(args.report, report)
                        measure.successful(result)
                    record.update(wall_s=time.monotonic() - start,
                                  cpu_s=sum(s["cpu_s"] for s in record["steps"]),
                                  object_sha256=sha(directory / "output.o"),
                                  compiler_sha256=sha(directory / "compiler"))
                    print(f"{route} {sample}: {record['wall_s']:.3f}s", flush=True)
            report["objects_identical"] = len({r["object_sha256"] for r in report["runs"]}) == 1
            report["compilers_identical"] = len({r["compiler_sha256"] for r in report["runs"]}) == 1
            report["input_unchanged"] = report["input_sha256"] == sha(snapshot / "linked.bc")
            report["raw_ir_unchanged"] = report["raw_ir_sha256"] == sha(snapshot / "raw.ll")
            report["summary"] = [{"route": route, "n": args.samples,
                                  "wall_s": statistics.median(r["wall_s"] for r in report["runs"] if r["route"] == route),
                                  "cpu_s": statistics.median(r["cpu_s"] for r in report["runs"] if r["route"] == route)}
                                 for route in ("staged", "ordinary")]
            report["complete"] = all(report[k] for k in
                                     ("objects_identical", "compilers_identical", "input_unchanged", "raw_ir_unchanged"))
    except BaseException as exc:
        report["error"] = str(exc)
        raise
    finally:
        if "error" in report:
            report["commands"] = runner.results
        atomic_json(args.report, report)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
