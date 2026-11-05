"""Build this compiler through explicit cold-runtime/frontend/backend artifacts.

This self-build-only controller measures whole-runtime overlap. The tiny build
prepares runtime bitcode through the unchanged driver (and has its own measured
small overhead). It does not silently replace arbitrary-program driver behavior.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time

from run import ROOT, atomic_json, bootstrap, measure, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--overlap", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--partitions", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8 or not 1 <= args.partitions <= 8 or (args.overlap and args.jobs < 2):
        parser.error("jobs/partitions must be 1..8; overlap needs at least 2 jobs")
    work, compiler, llvm = args.work.resolve(), args.compiler.resolve(), args.llvm.resolve()
    work.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env.update({"PYSTACHY_HOME": str(ROOT), "PYSTACHY_CACHE": str(work / "cache"),
                "PYSTACHY_TIMING": "1", "PYSTACHY_BUILD_JOBS": "1", "PYSTACHY_RUNTIME_C_CACHE": "1",
                "PYSTACHY_LLVM": str(llvm), "PYTHONHASHSEED": "0"})
    (work / "tiny.py").write_text("print(0)\n")
    commands = {
        "frontend": [str(compiler), "ir", str(ROOT / "pystachy.py"), "-o", str(work / "raw.ll")],
        "runtime_prewarm": [str(compiler), "build", str(work / "tiny.py"), "-o", str(work / "tiny")],
    }
    source = bootstrap.source_identity(ROOT)
    report = {"source": source, "host": bootstrap.host_state(), "compiler_sha256": sha(compiler),
              "llvm": bootstrap.tool_identity(sys.executable, str(llvm)), "overlap": args.overlap,
              "partitions": args.partitions, "jobs": args.jobs, "complete": False, "stages": {}}
    start = time.monotonic()

    def execute(name):
        result = measure.execute(commands[name], env, 300)
        measure.successful(result)
        return result

    if args.overlap:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = {name: pool.submit(execute, name) for name in commands}
            report["stages"].update({name: job.result() for name, job in pending.items()})
    else:
        report["stages"].update({name: execute(name) for name in commands})
    report["frontend_runtime_wall_s"] = time.monotonic() - start
    report["raw_ir_sha256"] = sha(work / "raw.ll")
    bitcode = sorted((work / "cache").glob("runtime-py-*.bc"))
    if len(bitcode) != 1:
        raise RuntimeError(f"expected exactly one runtime bitcode artifact, got {bitcode}")
    report["runtime_bc_sha256"] = sha(bitcode[0])
    # The compiler source does not opt into dynamic Any or promoting int.
    raw = (work / "raw.ll").read_bytes()
    if any(line.startswith(b"@pys_plain =") for line in raw.splitlines()):
        raise RuntimeError("unexpected pys_plain definition in raw compiler IR")
    (work / "program.ll").write_bytes(raw + b"@pys_plain = constant i64 1\n")
    linked = work / "linked.bc"
    result = measure.execute([str(llvm / "llvm-link"), "--only-needed", str(work / "program.ll"), str(bitcode[0]), "-o", str(linked)], env, 120)
    measure.successful(result)
    report["stages"]["link_ir"] = result
    backend_report = work / "backend.json"
    command = [sys.executable, str(ROOT / "bench/compiler_host/backend_workers.py"), "--input", str(linked),
               "--llvm", str(llvm), "--partitions", str(args.partitions), "--jobs", str(args.jobs),
               "--work", str(work / "backend"), "--report", str(backend_report)]
    result = measure.execute(command, env, 600)
    report["stages"]["backend"] = result
    report["build_wall_s"] = time.monotonic() - start
    atomic_json(args.report, report)
    measure.successful(result)
    report["backend"] = json.loads(backend_report.read_text())
    built = work / "backend/compiler"
    report["witnesses"] = {}
    for mode, file in (("ir", "pystachy.py"), ("rt", "runtime.py")):
        output = work / f"built-{mode}.ll"
        result = measure.execute([str(built), mode, str(ROOT / file), "-o", str(output)], env, 300)
        measure.successful(result)
        report["witnesses"][mode] = result
        if mode == "ir":
            reference = work / "raw.ll"
        else:
            reference = work / "seed-rt.ll"
            reference_result = measure.execute([str(compiler), mode, str(ROOT / file), "-o", str(reference)], env, 300)
            measure.successful(reference_result)
            report["witnesses"]["rt_reference"] = reference_result
        result["output_sha256"] = sha(output)
        result["matches"] = sha(output) == sha(reference)
    report["source_unchanged"] = source == bootstrap.source_identity(ROOT)
    report["complete"] = report["source_unchanged"] and all(report["witnesses"][mode]["matches"] for mode in ("ir", "rt"))
    atomic_json(args.report, report)
    print(json.dumps({k: report[k] for k in ("build_wall_s", "frontend_runtime_wall_s", "complete")}), flush=True)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
