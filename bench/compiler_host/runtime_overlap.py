"""Compare serial and overlapping cold-runtime preparation plus self frontend.

Run with a successful self_pipeline.py work directory as --snapshot. Each sample
gets an empty private runtime cache. An unchanged-driver tiny build prepares the
whole runtime, including its small program/link overhead; no self-build backend
is timed here. Cold describes the runtime cache, not the OS page cache.

Aggregate RSS is sampled over this controller and its descendants while both
jobs run, rather than adding independent peaks. CPU is the sum of measured
child-process CPU and excludes the controller's sampling/reporting overhead.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import random
import statistics
import sys
from threading import Event, Thread
import time

from run import ROOT, atomic_json, bootstrap, measure, sha


class AggregateRss:
    """Sample our own tree using the existing namespace-aware /proc helpers."""

    def __init__(self):
        lines = Path("/proc/self/status").read_text().splitlines()
        self.pid = next(int(line.split()[1]) for line in lines if line.startswith("Pid:"))
        self.peak = 0
        self.processes = 0
        self.error = None
        self.stop = Event()
        self.thread = Thread(target=self.sample, name="runtime-overlap-rss")

    def sample(self):
        try:
            while not self.stop.is_set():
                rss, count = measure.process_tree_rss(self.pid)
                self.peak = max(self.peak, rss)
                self.processes = max(self.processes, count)
                self.stop.wait(measure.SAMPLE_INTERVAL)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"

    def start(self):
        self.thread.start()

    def finish(self):
        self.stop.set()
        self.thread.join()


def stage_times(result):
    return [{"stage": fields[1], "seconds": float(fields[2])}
            for line in result["stderr"].splitlines()
            if line.startswith("pystachy-timing\t")
            for fields in [line.split("\t")]]


def summarize(values):
    return {"median": statistics.median(values), "min": min(values), "max": max(values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True,
                        help="successful self_pipeline.py directory containing raw.ll")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    compiler, llvm = args.compiler.resolve(), args.llvm.resolve()
    work = args.work.resolve()
    reference = args.snapshot.resolve() / "raw.ll"
    if not compiler.is_file() or not reference.is_file():
        parser.error("compiler and snapshot/raw.ll must exist")
    work.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env.update({"PYSTACHY_HOME": str(ROOT), "PYSTACHY_TIMING": "1",
                "PYSTACHY_BUILD_JOBS": "1", "PYSTACHY_RUNTIME_C_CACHE": "1",
                "PYSTACHY_LLVM": str(llvm), "PYTHONHASHSEED": "0"})
    source = bootstrap.source_identity(ROOT)
    compiler_hash, reference_hash = sha(compiler), sha(reference)
    report = {
        "source": source, "host": bootstrap.host_state(),
        "compiler_sha256": compiler_hash, "reference_ir_sha256": reference_hash,
        "llvm": bootstrap.tool_identity(sys.executable, str(llvm)),
        "requested_samples": args.samples, "samples": [], "complete": False,
        "environment": {k: v for k, v in env.items()
                        if k.startswith("PYSTACHY_") or k in ("PYTHONHASHSEED", "LD_LIBRARY_PATH")},
        "notes": [
            "Every sample starts with an empty private runtime cache; OS caches are warm.",
            "Runtime preparation includes the unchanged driver's tiny-program compilation and link.",
            "The overlap case has two independent jobs, each with PYSTACHY_BUILD_JOBS=1; serial has one.",
            "No self-build LLVM optimization, code generation, or link is included.",
            "cpu_s sums child-process CPU and excludes this controller's overhead.",
            "Aggregate RSS includes this controller; shared pages count once per resident process.",
            "Tiny-executable correctness checks and file hashing are outside wall_s.",
        ],
    }
    atomic_json(args.report, report)
    rng = random.Random(20261105)
    try:
        for sample in range(args.samples):
            order = ["serial", "overlap"]
            rng.shuffle(order)
            for variant in order:
                directory = work / f"{variant}-{sample}"
                directory.mkdir()
                (directory / "tiny.py").write_text("print(0)\n")
                sample_env = env | {"PYSTACHY_CACHE": str(directory / "cache")}
                commands = {
                    "frontend": [str(compiler), "ir", str(ROOT / "pystachy.py"), "-o", str(directory / "raw.ll")],
                    "runtime_prewarm": [str(compiler), "build", str(directory / "tiny.py"), "-o", str(directory / "tiny")],
                }
                row = {"variant": variant, "sample": sample,
                       "jobs": 2 if variant == "overlap" else 1,
                       "cache": sample_env["PYSTACHY_CACHE"], "stages": {}, "complete": False}
                report["samples"].append(row)
                atomic_json(args.report, report)
                rss = AggregateRss()
                start = time.monotonic()
                rss.start()
                try:
                    with ThreadPoolExecutor(max_workers=row["jobs"]) as pool:
                        pending = {pool.submit(measure.execute, command, sample_env, 300): name
                                   for name, command in commands.items()}
                        for job in as_completed(pending):
                            name = pending[job]
                            result = job.result()
                            result["stages"] = stage_times(result)
                            row["stages"][name] = result
                            atomic_json(args.report, report)
                finally:
                    row["wall_s"] = time.monotonic() - start
                    rss.finish()
                    row["sampled_process_tree_peak_rss_kib"] = rss.peak
                    row["sampled_max_processes"] = rss.processes
                    row["cpu_s"] = sum(r["cpu_s"] for r in row["stages"].values())
                    row["rss_sampling_error"] = rss.error
                    atomic_json(args.report, report)
                if rss.error or rss.peak <= 0 or rss.processes < 2:
                    raise RuntimeError(f"aggregate process-tree RSS unavailable: {rss.error}")
                for result in row["stages"].values():
                    measure.successful(result)
                row["raw_ir_sha256"] = sha(directory / "raw.ll")
                row["matches_reference"] = row["raw_ir_sha256"] == reference_hash
                bitcode = sorted((directory / "cache").glob("runtime-py-*.bc"))
                row["runtime_bitcode_count"] = len(bitcode)
                if len(bitcode) != 1:
                    raise RuntimeError(f"expected exactly one runtime bitcode artifact, got {bitcode}")
                row["runtime_bc_sha256"] = sha(bitcode[0])
                row["runtime_bc_bytes"] = bitcode[0].stat().st_size
                row["tiny_witness"] = measure.execute([str(directory / "tiny")], sample_env, 30)
                atomic_json(args.report, report)
                measure.successful(row["tiny_witness"])
                row["tiny_matches"] = row["tiny_witness"]["stdout"] == "0\n"
                row["complete"] = row["matches_reference"] and row["tiny_matches"]
                atomic_json(args.report, report)
                if not row["complete"]:
                    raise RuntimeError(f"output mismatch for {variant} sample {sample}")
                print(json.dumps({"variant": variant, "sample": sample, "wall_s": row["wall_s"],
                                  "cpu_s": row["cpu_s"], "complete": row["complete"]}), flush=True)
        report["summary"] = []
        for variant in ("serial", "overlap"):
            rows = [r for r in report["samples"] if r["variant"] == variant]
            summary = {"variant": variant, "n": len(rows), "stages": {}}
            for key in ("wall_s", "cpu_s", "sampled_process_tree_peak_rss_kib"):
                summary[key] = summarize([r[key] for r in rows])
            for stage in ("frontend", "runtime_prewarm"):
                summary["stages"][stage] = {key: summarize([r["stages"][stage][key] for r in rows])
                                             for key in ("wall_s", "cpu_s", "wait4_max_process_rss_kib")}
            report["summary"].append(summary)
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["source_unchanged"] = source == bootstrap.source_identity(ROOT)
        report["compiler_unchanged"] = compiler.is_file() and compiler_hash == sha(compiler)
        report["reference_unchanged"] = reference.is_file() and reference_hash == sha(reference)
        report["complete"] = ("error" not in report and len(report["samples"]) == 2 * args.samples
                              and all(r["complete"] for r in report["samples"])
                              and report["source_unchanged"] and report["compiler_unchanged"]
                              and report["reference_unchanged"])
        atomic_json(args.report, report)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
