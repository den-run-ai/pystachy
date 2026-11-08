"""Build this compiler through explicit cold-runtime/frontend/backend artifacts.

This self-build-only controller measures whole-runtime overlap. The tiny build
prepares runtime bitcode through the unchanged driver (and has its own measured
small overhead). It does not silently replace arbitrary-program driver behavior.
--backend ordinary keeps the driver's whole-module AOT pass order; --backend
thinlto uses the bounded summaries-only LLVM 18 experiment at O2. Isolated
workers remain the default. Full bootstraps use
--caller-witnesses only when their parent validates all six IR witnesses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import time

from run import ROOT, atomic_json, bootstrap, measure, sha
from backend_workers import Commands, LATE
import partition_import

sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.lower_module import uses_new_allocator


def ordinary_backend(args, runner, env, linked, raw):
    """Keep whole-module optimization and the driver's late-allocator contract."""
    directory = linked.parent / "backend"
    directory.mkdir()
    clang, opt = str(args.llvm.resolve() / "clang"), str(args.llvm.resolve() / "opt")
    level = "-O" + str(args.opt)
    inline = [] if args.inline_threshold is None else ["-mllvm", "-inline-threshold=" + str(args.inline_threshold)]
    allocator = uses_new_allocator(raw.decode("utf-8", errors="surrogateescape"))
    ready = linked
    steps = []
    if allocator:
        optimized, ready = directory / "optimized.bc", directory / "late.bc"
        steps += [("optimize", [clang, level, *inline, "-c", "-emit-llvm", str(linked), "-o", str(optimized)]),
                  ("late_inline", [opt, "-passes=forceattrs,always-inline", *LATE, str(optimized), "-o", str(ready)])]
    object_file, built = directory / "program.o", directory / "compiler"
    steps += [("codegen" if allocator else "optimize_codegen",
               [clang, level, "-c", *(["-Xclang", "-disable-llvm-passes"] if allocator else inline),
                str(ready), "-o", str(object_file), "-Wno-unused-command-line-argument"]),
              ("link", [clang, str(object_file), "-o", str(built), "-lm"])]
    report = {"complete": False, "allocator": allocator, "steps": []}
    for name, command in steps:
        result = runner.execute(command, env, 600)
        result["name"] = name
        report["steps"].append(result)
        atomic_json(linked.parent / "backend.json", report)
        measure.successful(result)
    report.update(complete=True, compiler_sha256=sha(built), compiler_bytes=built.stat().st_size,
                  object_sha256=sha(object_file))
    atomic_json(linked.parent / "backend.json", report)
    return report


def same_file(first, second):
    if first.resolve() == second.resolve():
        return True
    try:
        return first.samefile(second)
    except OSError:
        return False


def validate_outputs(args, root, work, compiler):
    # Output publication must not replace a consumed input or another artifact.
    manifest = getattr(args, "publish_manifest", None)
    producer_manifest = getattr(args, "compiler_manifest", None)
    outputs = [p.resolve() for p in (args.output, args.emit_ir, args.report, manifest) if p is not None]
    protected = [Path(p) for p in compiler]
    if producer_manifest:
        protected += [producer_manifest, Path(compiler[0]).parent / "raw.ll"]
    for directory in ("src", "lib", "ryu", "mpz"):
        protected.extend(p for p in (root / directory).rglob("*") if p.is_file())
    protected.extend(root / p for p in ("pystachy.py", "runtime.py", "runtime.c"))
    for index, output in enumerate(outputs):
        if output.is_relative_to(work) or any(same_file(output, p) for p in protected + outputs[:index]):
            raise ValueError("published outputs must be distinct from inputs and the private work directory")
    for pointer in (manifest, producer_manifest):
        if pointer is not None:
            store = pointer.parent.resolve() / (pointer.name + ".generations")
            if any(output.is_relative_to(store) for output in outputs):
                raise ValueError("published outputs must not modify immutable build generations")


def publish(source, destination):
    # Unique adjacent staging preserves existing outputs until a complete copy.
    fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", suffix=".pending", dir=destination.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


PUBLICATION_FILES = {"compiler": "compiler", "raw_ir": "raw.ll"}


def publication_path(path):
    # Resolve the parent, not a final symlink that could name another output.
    return path.parent.resolve() / path.name


def resolve_publication_data(destination, payload, require_witnesses=False):
    """Resolve one pointer snapshot, never rereading a concurrently replaced one.

    Generations are private copies and never modified by this publisher. Hashes
    detect accidental edits; this is trusted local storage, not a sandbox for
    another account that can mutate the files while they are being consumed.
    """
    record = json.loads(payload)
    if (not isinstance(record, dict)
            or set(record) != {"version", "complete", "generation", "source_sha256", "validation", "artifacts"}
            or type(record["version"]) is not int or record["version"] != 1 or record["complete"] is not True
            or not isinstance(record["generation"], str)
            or not re.fullmatch(r"generation-[a-zA-Z0-9_-]{8,64}", record["generation"])
            or not isinstance(record["source_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", record["source_sha256"])
            or record["validation"] not in ("local-witnesses", "caller-witnesses")
            or not isinstance(record["artifacts"], dict)
            or set(record["artifacts"]) != set(PUBLICATION_FILES)):
        raise ValueError("invalid build publication manifest")
    if require_witnesses and record["validation"] != "local-witnesses":
        raise ValueError("build publication still requires the caller's IR witnesses")
    store = destination.parent / (destination.name + ".generations")
    generation = store / record["generation"]
    if any(path.is_symlink() or not path.is_dir() for path in (store, generation)):
        raise ValueError("build publication generation is missing or symlinked")
    resolved = {"manifest": record, "manifest_sha256": hashlib.sha256(payload).hexdigest()}
    for name, filename in PUBLICATION_FILES.items():
        artifact = record["artifacts"][name]
        if (not isinstance(artifact, dict) or set(artifact) != {"sha256", "bytes"}
                or type(artifact["bytes"]) is not int or artifact["bytes"] < 0
                or not isinstance(artifact["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"])):
            raise ValueError("invalid build publication artifact description")
        path = generation / filename
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_size != artifact["bytes"]
                or (name == "compiler" and not info.st_mode & 0o111)
                or sha(path) != artifact["sha256"]):
            raise ValueError("build publication artifact is missing, altered or symlinked")
        resolved[name] = path
    return resolved


def resolve_publication(path, require_witnesses=False):
    """Return validated compiler/raw_ir paths pinned to one immutable generation."""
    destination = publication_path(path)
    if destination.is_symlink() or not destination.is_file():
        raise ValueError("build publication manifest is missing or symlinked")
    return resolve_publication_data(destination, destination.read_bytes(), require_witnesses)


def publish_generation(compiler, raw_ir, destination, *, expected, source_sha256, validation):
    """Copy and validate both artifacts, then atomically publish one manifest.

    Once replacement is attempted, keep the complete generation even on an
    interrupted/ambiguous result: a reader may already have observed it. Old
    generations also remain available to readers holding an earlier snapshot.
    """
    destination = publication_path(destination)
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise ValueError("build publication manifest must be a regular file")
    store = destination.parent / (destination.name + ".generations")
    if store.is_symlink():
        raise ValueError("build publication store must not be a symlink")
    store.mkdir(exist_ok=True)
    generation = Path(tempfile.mkdtemp(prefix="generation-", dir=store))
    temporary = None
    keep_generation = False
    try:
        artifacts = {}
        for name, source in (("compiler", compiler), ("raw_ir", raw_ir)):
            artifact = generation / PUBLICATION_FILES[name]
            shutil.copy2(source, artifact)
            artifact.chmod(0o555 if name == "compiler" else 0o444)
            if sha(artifact) != expected[name]:
                raise ValueError("build artifact changed before publication")
            artifacts[name] = {"sha256": expected[name], "bytes": artifact.stat().st_size}
        record = {"version": 1, "complete": True, "generation": generation.name,
                  "source_sha256": source_sha256, "validation": validation, "artifacts": artifacts}
        payload = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()
        resolved = resolve_publication_data(destination, payload)
        fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", suffix=".pending", dir=destination.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # This is the only visibility commit. No fallible artifact operation
        # follows it; a signal between replace and return cannot remove the data.
        keep_generation = True
        os.replace(temporary, destination)
        return resolved
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
        if not keep_generation:
            shutil.rmtree(generation, ignore_errors=True)


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
    producer.add_argument("--compiler-manifest", type=Path, help="consume one validated immutable compiler generation")
    producer.add_argument("--hosted", action="store_true", help="use this Python interpreter as the first producer")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--overlap", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--partitions", type=int, default=1)
    parser.add_argument("--backend", choices=("workers", "thinlto", "ordinary"), default="workers")
    parser.add_argument("--opt", type=int, choices=(0, 1, 2), default=2)
    parser.add_argument("--inline-threshold", type=int, help="research: backend optimizer inlining threshold (0..10000)")
    parser.add_argument("--cache", type=Path, help="private bootstrap cache shared with the next stage")
    parser.add_argument("--output", type=Path, help="publish the built executable here")
    parser.add_argument("--emit-ir", type=Path, help="publish the exact frontend witness here")
    parser.add_argument("--publish-manifest", type=Path,
                        help="atomically publish compiler and retained IR through an immutable generation")
    parser.add_argument("--caller-witnesses", action="store_true", help="the full bootstrap controller supplies all six witnesses")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8 or not 1 <= args.partitions <= 8 or (args.overlap and args.jobs < 2):
        parser.error("jobs/partitions must be 1..8; overlap needs at least 2 jobs")
    if args.inline_threshold is not None and not 0 <= args.inline_threshold <= 10000:
        parser.error("inlining threshold must be from 0 to 10000")
    if args.backend == "thinlto" and (args.opt != 2 or args.inline_threshold is not None):
        parser.error("ThinLTO self-builds require O2 and the default LLVM inlining policy")
    if args.backend == "ordinary" and args.partitions != 1:
        parser.error("ordinary self-builds keep one whole module")
    return run_pipeline(args)


def run_pipeline(args):
    work, root, llvm = args.work.resolve(), args.root.resolve(), args.llvm.resolve()
    producer_publication = resolve_publication(args.compiler_manifest) if args.compiler_manifest else None
    compiler = ([str(producer_publication["compiler"])] if producer_publication else
                [sys.executable, str(root / "pystachy.py")] if args.hosted else [str(args.compiler.resolve())])
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
              "backend_policy": args.backend,
              "caller_witnesses": args.caller_witnesses, "complete": False, "stages": {}}
    if producer_publication:
        report["producer_publication"] = {
            "path": str(publication_path(args.compiler_manifest)),
            "manifest_sha256": producer_publication["manifest_sha256"],
            "generation": producer_publication["manifest"]["generation"],
            "validation": producer_publication["manifest"]["validation"]}
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
            if args.backend == "thinlto":
                job_path = partition_import.prepare_backend_job(linked, llvm, work / "backend",
                                                               args.partitions, args.jobs)
                expected_job_sha256 = sha(job_path)
                report["expected_job_sha256"] = expected_job_sha256
                report["thinlto_job"] = json.loads(job_path.read_text())
                command = partition_import.backend_command(job_path, inherited_group=True)
                backend_report = job_path.parent / "build.json"
            elif args.backend == "workers":
                command = [sys.executable, str(ROOT / "bench/compiler_host/backend_workers.py"), "--input", str(linked),
                           "--llvm", str(llvm), "--partitions", str(args.partitions), "--jobs", str(args.jobs),
                           "--opt", str(args.opt), "--inherited-group", "--work", str(work / "backend"), "--report", str(backend_report)]
                if args.inline_threshold is not None:
                    command += ["--inline-threshold", str(args.inline_threshold)]
            if args.backend == "ordinary":
                report["backend"] = ordinary_backend(args, runner, env, linked, raw)
            else:
                result = runner.execute(command, env, 600)
                report["stages"]["backend"] = result
                if backend_report.exists():
                    report["backend"] = json.loads(backend_report.read_text())
                measure.successful(result)
            report["build_wall_s"] = time.monotonic() - start
            atomic_json(args.report, report)
            built = work / "backend/compiler"
            if args.backend == "thinlto":
                built = partition_import.validate_backend_result(job_path, report["backend"], expected_job_sha256)
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
            if args.backend == "thinlto":
                partition_import.validate_backend_result(job_path, report["backend"], expected_job_sha256)
            report["complete"] = report["source_unchanged"] and report["producer_unchanged"] and (args.caller_witnesses or all(
                report["witnesses"][mode]["matches"] for mode in ("ir", "rt")))
            if report["complete"]:
                validate_outputs(args, root, work, compiler)
                for source_path, destination in ((built, args.output), (work / "raw.ll", args.emit_ir)):
                    if destination:
                        publish(source_path, destination.resolve())
                if args.publish_manifest:
                    publication = publish_generation(
                        built, work / "raw.ll", args.publish_manifest,
                        expected={"compiler": report["backend"]["compiler_sha256"], "raw_ir": report["raw_ir_sha256"]},
                        source_sha256=source["sha256"],
                        validation="caller-witnesses" if args.caller_witnesses else "local-witnesses")
                    report["publication"] = {"path": str(publication_path(args.publish_manifest)),
                                             "manifest_sha256": publication["manifest_sha256"],
                                             "generation": publication["manifest"]["generation"]}
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
