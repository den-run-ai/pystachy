"""Research LLVM workers with transferable, hash-checked job directories.

Coordinator: --input LINKED.bc --partitions 4 --jobs 4 --work DIR --report JSON
Worker only: --worker DIR --llvm /matching/llvm/bin

Input must already link program and runtime, with the desired target/layout and
pys_plain value. Partitioning BEFORE O2 changes optimization scope. This is an
experiment, not ThinLTO or a production replacement for the driver's backend.
Workers use only the standard library and input.bc + job.json. They can execute
on another compatible machine after transport, but this harness does no transport.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
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
    return {name: digest(llvm / name) for name in ("clang", "opt", "ld.lld")}


def validate_result(directory, expected_job_sha256):
    result = json.loads((directory / "result.json").read_text())
    if (digest(directory / "job.json") != expected_job_sha256
            or result.get("job_sha256") != expected_job_sha256):
        raise RuntimeError("worker result/job identity mismatch")
    output = directory / "output.o"
    if (not result.get("complete") or not output.is_file()
            or result.get("output_sha256") != digest(output)
            or result.get("output_bytes") != output.stat().st_size):
        raise RuntimeError("incomplete or altered worker output")
    return result


def worker(work, llvm):
    work, llvm = work.resolve(), llvm.resolve()
    job = json.loads((work / "job.json").read_text())
    if job["version"] != 1 or job["input_sha256"] != digest(work / "input.bc"):
        raise RuntimeError("worker input/version mismatch")
    if (job["tool_sha256"] != identity(llvm) or job["opt"] not in (0, 1, 2, 3)
            or job["emit"] not in ("object", "bitcode")):
        raise RuntimeError("worker toolchain/options mismatch")
    clang, opt, level = str(llvm / "clang"), str(llvm / "opt"), "-O" + str(job["opt"])
    steps = [
        ("optimize", [clang, level, "-c", "-emit-llvm", "input.bc", "-o", "optimized.bc"]),
        ("late_inline", [opt, "-passes=forceattrs,always-inline", *LATE, "optimized.bc", "-o", "late.bc"]),
    ]
    if job["emit"] == "object":
        steps.append(("codegen", [clang, level, "-c", "-Xclang", "-disable-llvm-passes", "late.bc", "-o", "output.tmp.o"]))
    report = {"job_sha256": digest(work / "job.json"), "steps": [], "complete": False}
    for name, command in steps:
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        with (work / f"{name}.stdout").open("wb") as out, (work / f"{name}.stderr").open("wb") as err:
            completed = subprocess.run(command, cwd=work, stdout=out, stderr=err, check=False)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--partitions", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--lto-partitions", type=int, default=0)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.llvm)
        return
    if not args.input or not args.work or not args.report or not 1 <= args.jobs <= 8 or not 1 <= args.partitions <= 8:
        parser.error("coordinator needs input/work/report and jobs/partitions in 1..8")
    if not 0 <= args.lto_partitions <= args.jobs or (args.lto_partitions and args.partitions != 1):
        parser.error("LTO needs one whole input and no more codegen partitions than jobs")
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
              "lto_partitions": args.lto_partitions,
              "input_bytes": source.stat().st_size, "tool_sha256": identity(llvm),
              "worker_script_sha256": digest(__file__), "workers": [], "complete": False}
    if args.partitions == 1:
        parts = [source]
    else:
        result = measure.execute([str(llvm / "llvm-split"), str(source), "-j", str(args.partitions), "-o", str(work / "part-")], env, 120)
        measure.successful(result)
        report["split"] = result
        parts = [work / f"part-{i}" for i in range(args.partitions)]
    jobs = []
    expected_jobs = {}
    for i, part in enumerate(parts):
        directory = work / f"worker-{i}"
        directory.mkdir()
        shutil.copyfile(part, directory / "input.bc")
        job = {"version": 1, "input_sha256": digest(part), "tool_sha256": report["tool_sha256"], "opt": 2,
               "emit": "bitcode" if args.lto_partitions else "object"}
        write_json(directory / "job.json", job)
        expected_jobs[directory] = digest(directory / "job.json")
        jobs.append(directory)
    report["transferred_input_bytes"] = sum((job / "input.bc").stat().st_size for job in jobs)
    write_json(args.report, report)

    def run(directory):
        result = measure.execute([sys.executable, str(Path(__file__).resolve()), "--worker", str(directory), "--llvm", str(llvm)], env, 600)
        result["partition"] = int(directory.name.split("-")[1])
        if (directory / "result.json").is_file():
            result["worker"] = json.loads((directory / "result.json").read_text())
        measure.successful(result)
        result["worker"] = validate_result(directory, expected_jobs[directory])
        return result

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run, directory) for directory in jobs]
        for future in as_completed(futures):
            report["workers"].append(future.result())
            write_json(args.report, report)
    report["workers"].sort(key=lambda row: row["partition"])
    # Stable partition order matters for reproducibility and layout.
    command = [str(llvm / "clang"), *[str(job / "output.o") for job in jobs], "-o", str(work / "compiler"), "-lm"]
    if args.lto_partitions:
        command += ["-fuse-ld=" + str(llvm / "ld.lld"), "-flto=full", "-Wl,--lto-newpm-passes=verify",
                    "-Wl,--lto-CGO2", "-Wl,--lto-partitions=" + str(args.lto_partitions),
                    "-Wl,--threads=" + str(args.jobs)]
    report["link"] = measure.execute(command, env, 120)
    measure.successful(report["link"])
    report.update({"wall_s": time.monotonic() - start, "complete": True,
                   "compiler_sha256": digest(work / "compiler"),
                   "compiler_bytes": (work / "compiler").stat().st_size})
    write_json(args.report, report)
    print(json.dumps({k: report[k] for k in ("wall_s", "compiler_bytes", "complete")}), flush=True)


if __name__ == "__main__":
    main()
