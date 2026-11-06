"""Build this compiler through explicit cold-runtime/frontend/backend artifacts.

This self-build-only controller measures whole-runtime overlap. The tiny build
prepares runtime bitcode through the unchanged driver (and has its own measured
small overhead). It does not silently replace arbitrary-program driver behavior.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

from run import ROOT, atomic_json, bootstrap, measure, sha
from backend_workers import Commands


def same_file(first, second):
    if first.resolve() == second.resolve():
        return True
    try:
        return first.samefile(second)
    except OSError:
        return False


def validate_outputs(args, root, work, compiler):
    # Output publication must not replace a consumed input or another artifact.
    outputs = [p.resolve() for p in (args.output, args.emit_ir, args.report) if p is not None]
    protected = [Path(p) for p in compiler]
    for directory in ("src", "lib", "ryu", "mpz"):
        protected.extend(p for p in (root / directory).rglob("*") if p.is_file())
    protected.extend(root / p for p in ("pystachy.py", "runtime.py", "runtime.c"))
    for index, output in enumerate(outputs):
        if output.is_relative_to(work) or any(same_file(output, p) for p in protected + outputs[:index]):
            raise ValueError("published outputs must be distinct from inputs and the private work directory")


def publish(source, destination):
    # Unique adjacent staging preserves existing outputs until a complete copy.
    fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", suffix=".pending", dir=destination.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def wait_for_settled(paths):
    # The driver's cache deliberately refuses files changed within two seconds.
    # Honor that trust window before relying on its exported runtime artifact.
    started = time.monotonic()
    while True:
        latest = max(max(p.stat().st_mtime, p.stat().st_ctime) for p in paths)
        remaining = latest + 2.01 - time.time()
        if remaining <= 0:
            return time.monotonic() - started
        if time.monotonic() - started > 3:
            raise RuntimeError("compiler/tool inputs did not settle for runtime-cache publication")
        time.sleep(min(0.05, remaining))


def prepared_runtime(cache, prior, stderr):
    bitcode = sorted(cache.glob("runtime-py-*.bc"))
    fresh = [p for p in bitcode if p not in prior or sha(p) != prior[p]]
    if len(fresh) == 1:
        return fresh[0]
    rebuilt = any(marker in stderr for marker in (
        "pystachy-timing\truntime.frontend\t", "pystachy-timing\truntime.parallel\t"))
    if not fresh and len(bitcode) == 1 and not rebuilt:
        return bitcode[0]
    raise RuntimeError(f"cannot identify the prepared runtime artifact: fresh={fresh}, all={bitcode}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    producer = parser.add_mutually_exclusive_group(required=True)
    producer.add_argument("--compiler", type=Path)
    producer.add_argument("--hosted", action="store_true", help="use this Python interpreter as the first producer")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--overlap", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--partitions", type=int, default=1)
    parser.add_argument("--opt", type=int, choices=(0, 1, 2), default=2)
    parser.add_argument("--inline-threshold", type=int, help="research: backend optimizer inlining threshold (0..10000)")
    parser.add_argument("--cache", type=Path, help="private bootstrap cache shared with the next stage")
    parser.add_argument("--output", type=Path, help="publish the built executable here")
    parser.add_argument("--emit-ir", type=Path, help="publish the exact frontend witness here")
    parser.add_argument("--caller-witnesses", action="store_true", help="the full bootstrap controller supplies all six witnesses")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8 or not 1 <= args.partitions <= 8 or (args.overlap and args.jobs < 2):
        parser.error("jobs/partitions must be 1..8; overlap needs at least 2 jobs")
    if args.inline_threshold is not None and not 0 <= args.inline_threshold <= 10000:
        parser.error("inlining threshold must be from 0 to 10000")
    return run_pipeline(args)


def run_pipeline(args):
    work, root, llvm = args.work.resolve(), args.root.resolve(), args.llvm.resolve()
    compiler = [sys.executable, str(root / "pystachy.py")] if args.hosted else [str(args.compiler.resolve())]
    validate_outputs(args, root, work, compiler)
    work.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    cache = args.cache.resolve() if args.cache else work / "cache"
    env.update({"PYSTACHY_HOME": str(root), "PYSTACHY_CACHE": str(cache),
                "PYSTACHY_TIMING": "1", "PYSTACHY_BUILD_JOBS": "1", "PYSTACHY_RUNTIME_C_CACHE": "1",
                "PYSTACHY_LLVM": str(llvm), "PYTHONHASHSEED": "0"})
    (work / "tiny.py").write_text("print(0)\n")
    commands = {
        "frontend": compiler + ["ir", str(root / "pystachy.py"), "-o", str(work / "raw.ll")],
        "runtime_prewarm": compiler + ["build", str(work / "tiny.py"), "-o", str(work / "tiny")],
    }
    source = bootstrap.source_identity(root)
    report = {"source": source, "host": bootstrap.host_state(), "compiler": compiler,
              "harness_sha256": sha(Path(__file__)),
              "producer_sha256": {p: sha(p) for p in compiler},
              "llvm": bootstrap.tool_identity(sys.executable, str(llvm)), "overlap": args.overlap,
              "partitions": args.partitions, "jobs": args.jobs, "opt": args.opt, "inline_threshold": args.inline_threshold,
              "caller_witnesses": args.caller_witnesses, "complete": False, "stages": {}}
    runner = Commands(measure)
    try:
        with runner:
            start = time.monotonic()
            inputs = [root / p for p in source["files"]] + [Path(p) for p in compiler]
            inputs += [llvm / name for name in ("clang", "llvm-as", "llvm-link", "opt")]
            report["cache_trust_wait_s"] = wait_for_settled(inputs)
            prior_runtime = {p: sha(p) for p in cache.glob("runtime-py-*.bc")}

            for result in runner.run(list(commands.items()), env, 300, jobs=2 if args.overlap else 1):
                report["stages"][result["key"]] = result
                atomic_json(args.report, report)
                measure.successful(result)
            report["frontend_runtime_wall_s"] = time.monotonic() - start
            report["raw_ir_sha256"] = sha(work / "raw.ll")
            # A private bootstrap cache may also contain an earlier producer's
            # runtime. Select the artifact this prewarm actually published.
            runtime = prepared_runtime(cache, prior_runtime, report["stages"]["runtime_prewarm"]["stderr"])
            report["runtime_bc_path"] = str(runtime)
            report["runtime_bc_sha256"] = sha(runtime)
            # The compiler source does not opt into dynamic Any or promoting int.
            raw = (work / "raw.ll").read_bytes()
            if any(line.startswith(b"@pys_plain =") for line in raw.splitlines()):
                raise RuntimeError("unexpected pys_plain definition in raw compiler IR")
            (work / "program.ll").write_bytes(raw + b"@pys_plain = constant i64 1\n")
            linked = work / "linked.bc"
            result = runner.execute([str(llvm / "llvm-link"), "--only-needed", str(work / "program.ll"), str(runtime), "-o", str(linked)], env, 120)
            measure.successful(result)
            report["stages"]["link_ir"] = result
            backend_report = work / "backend.json"
            command = [sys.executable, str(ROOT / "bench/compiler_host/backend_workers.py"), "--input", str(linked),
                       "--llvm", str(llvm), "--partitions", str(args.partitions), "--jobs", str(args.jobs),
                       "--opt", str(args.opt), "--inherited-group", "--work", str(work / "backend"), "--report", str(backend_report)]
            if args.inline_threshold is not None:
                command += ["--inline-threshold", str(args.inline_threshold)]
            result = runner.execute(command, env, 600)
            report["stages"]["backend"] = result
            report["build_wall_s"] = time.monotonic() - start
            atomic_json(args.report, report)
            measure.successful(result)
            report["backend"] = json.loads(backend_report.read_text())
            built = work / "backend/compiler"
            report["witnesses"] = {}
            for mode, file in (() if args.caller_witnesses else (("ir", "pystachy.py"), ("rt", "runtime.py"))):
                output = work / f"built-{mode}.ll"
                result = runner.execute([str(built), mode, str(root / file), "-o", str(output)], env, 300)
                measure.successful(result)
                report["witnesses"][mode] = result
                if mode == "ir":
                    reference = work / "raw.ll"
                else:
                    reference = work / "seed-rt.ll"
                    reference_result = runner.execute(compiler + [mode, str(root / file), "-o", str(reference)], env, 300)
                    measure.successful(reference_result)
                    report["witnesses"]["rt_reference"] = reference_result
                result["output_sha256"] = sha(output)
                result["matches"] = sha(output) == sha(reference)
            report["source_unchanged"] = source == bootstrap.source_identity(root)
            report["producer_unchanged"] = report["producer_sha256"] == {p: sha(p) for p in compiler}
            report["complete"] = report["source_unchanged"] and report["producer_unchanged"] and (args.caller_witnesses or all(
                report["witnesses"][mode]["matches"] for mode in ("ir", "rt")))
            if report["complete"]:
                validate_outputs(args, root, work, compiler)
                for source_path, destination in ((built, args.output), (work / "raw.ll", args.emit_ir)):
                    if destination:
                        publish(source_path, destination.resolve())
            atomic_json(args.report, report)
            print(json.dumps({k: report[k] for k in ("build_wall_s", "frontend_runtime_wall_s", "complete")}), flush=True)
            return 0 if report["complete"] else 1
    except BaseException as exc:
        report["error"] = str(exc)
        report["complete"] = False
        raise
    finally:
        report["command_history"] = runner.results
        atomic_json(args.report, report)


if __name__ == "__main__":
    sys.exit(main())
