"""Research LLVM workers with transferable, hash-checked job directories.

Coordinator: --input LINKED.bc --partitions 4 --jobs 4 --work DIR --report JSON
Worker only: --worker DIR --llvm /matching/llvm/bin

Input must already link program and runtime, with the desired target/layout and
pys_plain value. Partitioning BEFORE optimization changes optimization scope. This is an
experiment, not ThinLTO or a production replacement for the driver's backend.
Workers use only the standard library and input.bc + job.json. They can execute
on another compatible machine after transport, but this harness does no transport.
Tool hashes do not yet cover the complete target/sysroot/shared-library identity;
these jobs are not a sufficient key for a cross-host shared object cache.

Use --inherited-group only inside a controller that owns the entire process group,
propagates failures and cleans up descendants. Direct invocations own their group.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time


LATE = ["-force-remove-attribute=pys_new:noinline",
        "-force-remove-attribute=pys_new:optnone", "-force-attribute=pys_new:alwaysinline"]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def identity(llvm):
    names = ["clang", "opt"]
    if (llvm / "ld.lld").is_file():
        names.append("ld.lld")
    return {name: digest(llvm / name) for name in names}


# Transfer the lifecycle and process_worker_child.py with detached worker scripts. Loading
# by an explicit path also works with Python -I and without a repository install.
_support = Path(__file__).resolve().with_name("process_workers.py")
if not _support.is_file():
    _support = Path(__file__).resolve().parents[2] / "tools/process_workers.py"
_spec = importlib.util.spec_from_file_location("pystachy_process_workers", _support)
_support_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_support_module)
Commands = _support_module.Commands
Resources = _support_module.Resources
Budget = _support_module.Budget
Job = _support_module.Job
group_members = _support_module.group_members


def validate_result(directory, expected_job_sha256):
    result = json.loads((directory / "result.json").read_text())
    if (digest(directory / "job.json") != expected_job_sha256
            or result.get("job_sha256") != expected_job_sha256):
        raise RuntimeError("worker result/job identity mismatch")
    output = directory / "output.o"
    job = json.loads((directory / "job.json").read_text())
    if job.get("input_sha256") != digest(directory / "input.bc"):
        raise RuntimeError("worker input changed after submission")
    if (result.get("complete") is not True or not output.is_file()
            or result.get("output_sha256") != digest(output)
            or result.get("output_bytes") != output.stat().st_size):
        raise RuntimeError("incomplete or altered worker output")
    return result


def uncached_worker(work, llvm, tool_env=None):
    work, llvm = work.resolve(), llvm.resolve()
    # Retrying a directory must never expose an earlier successful output if
    # this attempt is rejected, interrupted or fails before its first step.
    for name in ("result.json", "output.o", "output.tmp.o"):
        (work / name).unlink(missing_ok=True)
    job = json.loads((work / "job.json").read_text())
    if job["version"] not in (1, 2) or job["input_sha256"] != digest(work / "input.bc"):
        raise RuntimeError("worker input/version mismatch")
    if (job["tool_sha256"] != identity(llvm) or job["opt"] not in (0, 1, 2, 3)
            or job["emit"] not in ("object", "bitcode")):
        raise RuntimeError("worker toolchain/options mismatch")
    # Version 2 binds the optimizer policy. Version 1 remains replayable only
    # without that field; old worker scripts must reject new policy-bearing jobs.
    inline_threshold = job.get("inline_threshold")
    if ((job["version"] == 1 and "inline_threshold" in job)
            or (job["version"] == 2 and "inline_threshold" not in job)
            or (inline_threshold is not None
                and (type(inline_threshold) is not int or not 0 <= inline_threshold <= 10000))):
        raise RuntimeError("worker inlining policy/version mismatch")
    inline_flags = [] if inline_threshold is None else ["-mllvm", "-inline-threshold=" + str(inline_threshold)]
    clang, opt, level = str(llvm / "clang"), str(llvm / "opt"), "-O" + str(job["opt"])
    config_flags = ["--no-default-config"] if tool_env is not None else []
    steps = [
        ("optimize", [clang, *config_flags, level, *inline_flags, "-c", "-emit-llvm", "input.bc", "-o", "optimized.bc"]),
        ("late_inline", [opt, "-passes=forceattrs,always-inline", *LATE, "optimized.bc", "-o", "late.bc"]),
    ]
    if job["emit"] == "object":
        steps.append(("codegen", [clang, *config_flags, level, "-c", "-Xclang", "-disable-llvm-passes", "late.bc", "-o", "output.tmp.o"]))
    report = {"job_sha256": digest(work / "job.json"), "steps": [], "complete": False}
    for name, command in steps:
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        with (work / f"{name}.stdout").open("wb") as out, (work / f"{name}.stderr").open("wb") as err:
            completed = subprocess.run(command, cwd=work, env=tool_env, stdout=out, stderr=err, check=False)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        report["steps"].append({"name": name, "command": command, "wall_s": time.monotonic() - start,
                                "cpu_s": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                                "exit_code": completed.returncode})
        write_json(work / "result.json", report)
        if completed.returncode:
            raise RuntimeError(f"worker {name} failed: {(work / (name + '.stderr')).read_text()[-2000:]}")
    if job["emit"] == "bitcode":
        shutil.copyfile(work / "late.bc", work / "output.tmp.o")
    (work / "output.tmp.o").replace(work / "output.o")
    report.update({"complete": True, "output_sha256": digest(work / "output.o"),
                   "output_bytes": (work / "output.o").stat().st_size})
    write_json(work / "result.json", report)


def artifact_module():
    path = Path(__file__).resolve().with_name("worker_artifacts.py")
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / "tools/worker_artifacts.py"
    spec = importlib.util.spec_from_file_location("pystachy_worker_artifacts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def cache_identity(llvm, env):
    """Conservative same-host cache; no remote/toolchain-closure claim.

    This path only consumes standalone LLVM bitcode, never a ThinLTO index or
    implicit imports. Clang configuration is disabled. Hash its resolved native
    shared libraries as well as executables and the semantic worker source.
    """
    if sys.platform != "linux":
        raise ValueError("prototype LLVM object cache is Linux-only")
    dependencies = {}
    for name in identity(llvm):
        path = (llvm / name).resolve()
        listing = subprocess.run(["/usr/bin/ldd", str(path)], env=env, capture_output=True,
                                 text=True, timeout=10)
        if listing.returncode or "not found" in listing.stdout:
            raise ValueError("cannot validate LLVM shared-library closure")
        for line in listing.stdout.splitlines():
            value = line.split("=>", 1)[-1].strip().split(" ", 1)[0]
            if value.startswith("/"):
                library = Path(value).resolve()
                dependencies[str(library)] = digest(library)
    return {"scope": "same-host-standalone-bitcode-v1", "host": list(platform.uname()),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "tools": identity(llvm), "shared_libraries": dependencies,
            "worker_sha256": digest(__file__), "environment": env,
            "clang_default_config": False}


def worker(work, llvm, cache_root=None):
    if cache_root is None:
        return uncached_worker(work, llvm)
    work, llvm = work.resolve(), llvm.resolve()
    # A rejected retry must never expose output left by an older attempt.
    for name in ("result.json", "output.o", "output.tmp.o"):
        (work / name).unlink(missing_ok=True)
    job = json.loads((work / "job.json").read_text())
    if (job.get("input_sha256") != digest(work / "input.bc")
            or job.get("tool_sha256") != identity(llvm)):
        raise RuntimeError("worker input/tool identity mismatch")
    env = {"PATH": str(llvm) + ":/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    artifacts, support_path = artifact_module()
    context = cache_identity(llvm, env)
    expected_job = digest(work / "job.json")
    support_digest = digest(support_path)
    key = artifacts.key_for({"job": job, "context": context, "cache_code": support_digest})
    cache = artifacts.ArtifactCache(cache_root)
    with cache.locked(key) as waited:
        found = cache.lookup(key)
        if found:
            artifact, entry = found
            artifacts.atomic_copy(artifact, work / "output.o")
            report = {"job_sha256": digest(work / "job.json"), "steps": [], "complete": True,
                      "output_sha256": entry["sha256"], "output_bytes": entry["bytes"]}
        else:
            uncached_worker(work, llvm, tool_env=env)
            report = validate_result(work, expected_job)
            if cache_identity(llvm, env) != context or digest(support_path) != support_digest:
                raise RuntimeError("worker execution identity changed before publication")
            cache.publish(key, work / "output.o")
        if (digest(work / "job.json") != expected_job
                or digest(work / "input.bc") != job["input_sha256"]
                or digest(work / "output.o") != report["output_sha256"]):
            raise RuntimeError("worker artifacts changed during cache use")
        report["cache"] = {"key": key, "hit": found is not None, "wait_s": waited,
                           "scope": context["scope"]}
        write_json(work / "result.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--object-cache", type=Path, help="opt-in same-host cache for standalone backend jobs")
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--partitions", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--cpu-budget", type=int, help="total CPU reservations; defaults to jobs")
    parser.add_argument("--memory-budget-mib", type=int, help="estimated in-flight memory; defaults to jobs * 512 MiB")
    parser.add_argument("--worker-memory-mib", type=int, default=512, help="estimated memory per LLVM worker")
    parser.add_argument("--input-budget-mib", type=int, default=256, help="maximum active input artifact bytes")
    parser.add_argument("--queued-input-mib", type=int, default=256, help="maximum bytes in one queued input descriptor")
    parser.add_argument("--lto-partitions", type=int, default=0)
    parser.add_argument("--opt", type=int, choices=(0, 1, 2, 3), default=2)
    parser.add_argument("--inline-threshold", type=int, help="research: optimizer inlining threshold (0..10000); default uses LLVM policy")
    parser.add_argument("--timeout", type=float, default=600, help="seconds per worker or tool command")
    parser.add_argument("--inherited-group", action="store_true",
                        help="run inside an outer controller's owned process group")
    parser.add_argument("--managed-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be a positive finite number")
    if args.inline_threshold is not None and not 0 <= args.inline_threshold <= 10000:
        parser.error("inlining threshold must be from 0 to 10000")
    if args.worker:
        if args.inline_threshold is not None:
            parser.error("worker replay takes its inlining policy from job.json")
        if args.managed_worker:
            worker(args.worker, args.llvm, args.object_cache)
        else:
            # A detached replay has the same cancellation ownership as the
            # coordinator, without importing anything from the repository.
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(args.worker),
                       "--llvm", str(args.llvm), "--managed-worker"]
            if args.object_cache is not None:
                command += ["--object-cache", str(args.object_cache.resolve())]
            with Commands(owns_group=not args.inherited_group) as scope:
                result = scope.execute(command, dict(os.environ), args.timeout)
                if result["exit_code"]:
                    raise RuntimeError(result["stderr"][-3000:])
        return 0
    if args.managed_worker:
        parser.error("managed-worker requires worker")
    if not args.input or not args.work or not args.report or not 1 <= args.jobs <= 8 or not 1 <= args.partitions <= 8:
        parser.error("coordinator needs input/work/report and jobs/partitions in 1..8")
    if args.lto_partitions and not (args.llvm / "ld.lld").is_file():
        parser.error("LTO partitioning requires matching ld.lld")
    if not 0 <= args.lto_partitions <= args.jobs or (args.lto_partitions and args.partitions != 1):
        parser.error("LTO needs one whole input and no more codegen partitions than jobs")
    cpu_budget = args.cpu_budget if args.cpu_budget is not None else args.jobs
    memory_budget = args.memory_budget_mib if args.memory_budget_mib is not None else args.jobs * 512
    if min(cpu_budget, memory_budget, args.worker_memory_mib, args.input_budget_mib, args.queued_input_mib) < 1:
        parser.error("resource budgets must be positive")
    if args.lto_partitions > cpu_budget:
        parser.error("LTO partitions exceed CPU budget")
    budget = Budget(cpu_budget, memory_budget * 1024 ** 2, args.input_budget_mib * 1024 ** 2,
                    args.queued_input_mib * 1024 ** 2)
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("measure", root / "bench/compiler_parallel/llvm_partitions.py")
    measure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(measure)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    llvm = args.llvm.resolve()
    source = args.input.resolve()
    env = dict(os.environ)
    start = time.monotonic()
    report = {"input_sha256": digest(source), "partitions": args.partitions, "jobs": args.jobs,
              "lto_partitions": args.lto_partitions, "opt": args.opt, "inline_threshold": args.inline_threshold,
              "timeout_s": args.timeout,
              "input_bytes": source.stat().st_size, "tool_sha256": identity(llvm),
              "worker_script_sha256": digest(__file__), "lifecycle_sha256": digest(_support),
              "supervisor_sha256": digest(_support_module.CHILD_SCRIPT),
              "resource_budget": budget.limit.as_dict(), "queued_input_bytes": budget.queued_bytes,
              "workers": [], "complete": False}
    write_json(args.report, report)
    scope = Commands(measure, owns_group=not args.inherited_group)
    code = 1
    try:
        with scope:
            if args.partitions == 1:
                parts = [source]
            else:
                result = scope.execute([str(llvm / "llvm-split"), str(source), "-j", str(args.partitions), "-o", str(work / "part-")], env, args.timeout)
                report["split"] = result
                measure.successful(result)
                parts = [work / f"part-{i}" for i in range(args.partitions)]
            jobs = []
            expected_jobs = {}
            for i, part in enumerate(parts):
                directory = work / f"worker-{i}"
                directory.mkdir()
                shutil.copyfile(part, directory / "input.bc")
                job = {"version": 2, "input_sha256": digest(part), "tool_sha256": report["tool_sha256"], "opt": args.opt,
                       "inline_threshold": args.inline_threshold, "emit": "bitcode" if args.lto_partitions else "object"}
                write_json(directory / "job.json", job)
                expected_jobs[directory] = digest(directory / "job.json")
                jobs.append(directory)
            report["transferred_input_bytes"] = sum((job / "input.bc").stat().st_size for job in jobs)
            write_json(args.report, report)
            commands = (Job(i, [sys.executable, str(Path(__file__).resolve()), "--worker", str(directory),
                              "--llvm", str(llvm), "--managed-worker",
                              *([] if args.object_cache is None else ["--object-cache", str(args.object_cache.resolve())])],
                            Resources(1, args.worker_memory_mib * 1024 ** 2,
                                      (directory / "input.bc").stat().st_size))
                        for i, directory in enumerate(jobs))
            for result in scope.run(commands, env, args.timeout, jobs=args.jobs, budget=budget):
                i = result.pop("key")
                directory = jobs[i]
                result["partition"] = i
                if (directory / "result.json").is_file():
                    result["worker"] = json.loads((directory / "result.json").read_text())
                report["workers"].append(result)
                write_json(args.report, report)
                measure.successful(result)
                result["worker"] = validate_result(directory, expected_jobs[directory])
            report["workers"].sort(key=lambda row: row["partition"])
            # Stable partition order matters for reproducibility and layout.
            command = [str(llvm / "clang"), *[str(job / "output.o") for job in jobs], "-o", str(work / "compiler"), "-lm"]
            if args.lto_partitions:
                command += ["-fuse-ld=" + str(llvm / "ld.lld"), "-flto=full", "-Wl,--lto-newpm-passes=verify",
                            "-Wl,--lto-CGO" + str(args.opt), "-Wl,--lto-partitions=" + str(args.lto_partitions),
                            "-Wl,--threads=" + str(min(args.jobs, cpu_budget))]
            report["link"] = scope.execute(command, env, args.timeout)
            measure.successful(report["link"])
            report.update({"complete": True, "compiler_sha256": digest(work / "compiler"),
                           "compiler_bytes": (work / "compiler").stat().st_size})
            code = 0
    except (OSError, RuntimeError, ValueError) as error:
        report["complete"] = False
        report["error"] = str(error)
        if scope.interrupted:
            code = 128 + scope.interrupted
    finally:
        report["wall_s"] = time.monotonic() - start
        report["commands"] = scope.results
        report["peak_reserved"] = scope.peak_reserved
        write_json(args.report, report)
        print(json.dumps({key: report[key] for key in ("wall_s", "complete")}), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
