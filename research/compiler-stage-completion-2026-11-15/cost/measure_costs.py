#!/usr/bin/env python3
"""Bounded, sequential compiler cost measurements with output equivalence checks.

Run only after builds/tests finish and the source and both binaries are frozen.
This records advisory measurements on a shared host; it makes no speed claim.
No command executes a compiled test program or invokes LLVM code generation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

STAGES = ["prepare", "discover", "analyze", "optimize", "finalize", "lower"]
METRICS = ("wall_seconds", "user_seconds", "system_seconds", "cpu_seconds", "peak_rss_kib")
GC = re.compile(
    r"gc: (\d+) collections, ([0-9.]+) ms; heap peak ([0-9.]+) MiB; "
    r"live ([0-9.]+) MiB at the last"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def file_identity(path):
    path = Path(path)
    return {"path": str(path), "resolved": str(path.resolve()),
            "bytes": path.stat().st_size, "sha256": digest(path)}


def same_bytes(left, right):
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as one, right.open("rb") as two:
        while True:
            first = one.read(1 << 20)
            if first != two.read(1 << 20):
                return False
            if not first:
                return True


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def source_manifest(root, workloads):
    # Include actual importable files, including untracked Python source. Build
    # outputs and bytecode are excluded. Neither git HEAD nor a clean status
    # alone identifies the bytes used by the compiler and inspection tool.
    selected = {path for path in root.iterdir()
                if path.is_file() and (path.suffix in (".py", ".c", ".h")
                                       or path.name in ("VERSION", ".python-version"))}
    for name in ("src", "lib", "tools", "ryu", "mpz"):
        for path in (root / name).rglob("*"):
            if (path.is_file() and path.suffix in (".py", ".c", ".h")
                    and not any(part in ("__pycache__", ".lake") for part in path.parts)):
                selected.add(path)
    for work in workloads:
        source = Path(work["source"])
        selected.add(source)
        for suffix in (".path", ".in", ".out", ".err"):
            sidecar = source.with_suffix(suffix)
            if sidecar.is_file():
                selected.add(sidecar)
    return {str(path.relative_to(root)): {"bytes": path.stat().st_size, "sha256": digest(path)}
            for path in sorted(selected)}


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_command(command, root, directory, label, env, timeout):
    stdout = directory / (label + ".stdout")
    stderr = directory / (label + ".stderr")
    before_load = os.getloadavg()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    timed_out = threading.Event()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        start = time.perf_counter_ns()
        process = subprocess.Popen(command, cwd=root, env=env, stdout=out, stderr=err,
                                   start_new_session=True)

        def terminate_owned_group():
            if process.returncode is None:
                timed_out.set()
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        watchdog = threading.Timer(timeout, terminate_owned_group)
        watchdog.daemon = True
        watchdog.start()
        try:
            try:
                child_affinity = sorted(os.sched_getaffinity(process.pid))
            except ProcessLookupError:
                child_affinity = None
            # Per-child wait4 avoids RUSAGE_CHILDREN's accumulating RSS maximum.
            # No polling interval is added to the short FFI wall measurements.
            waited, status, usage = os.wait4(process.pid, 0)
            elapsed = (time.perf_counter_ns() - start) / 1e9
            require(waited == process.pid, "wait4 returned another process")
            process.returncode = os.waitstatus_to_exitcode(status)
        except BaseException:
            terminate_owned_group()
            process.wait()
            raise
        finally:
            watchdog.cancel()
            watchdog.join()
    return {
        "label": label, "command": command, "cwd": str(root),
        "started_utc": started_utc, "exit_code": process.returncode,
        "timed_out": timed_out.is_set(), "wall_seconds": elapsed,
        "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime,
        "cpu_seconds": usage.ru_utime + usage.ru_stime, "peak_rss_kib": usage.ru_maxrss,
        "voluntary_context_switches": usage.ru_nvcsw,
        "involuntary_context_switches": usage.ru_nivcsw,
        "load_average_before": list(before_load), "load_average_after": list(os.getloadavg()),
        "runner_affinity": sorted(os.sched_getaffinity(0)), "child_affinity_at_spawn": child_affinity,
        "stdout": file_identity(stdout), "stderr": file_identity(stderr),
    }


def native_evidence(sample, output):
    require(sample["exit_code"] == 0 and not sample["timed_out"],
            f"{sample['label']}: compiler failed; see {sample['stderr']['path']}")
    require(sample["stdout"]["bytes"] == 0, f"{sample['label']}: unexpected stdout")
    errors = Path(sample["stderr"]["path"]).read_text(encoding="utf-8")
    summaries = GC.findall(errors)
    require(len(summaries) == 1, f"{sample['label']}: expected exactly one GC summary")
    timings = []
    for line in errors.splitlines():
        if line.startswith("pystachy-timing\t"):
            _, stage, value = line.split("\t")
            seconds = float(value)
            require(math.isfinite(seconds) and seconds >= 0, "invalid compiler timing")
            timings.append({"stage": stage, "seconds": seconds})
        else:
            require(line.startswith("gc:"), f"{sample['label']}: unexpected diagnostic {line!r}")
    require(timings, f"{sample['label']}: no compiler stage timings")
    collections, millis, heap, live = summaries[0]
    sample.update(output=file_identity(output), output_retained=True, timings=timings,
                  gc={"collections": int(collections), "milliseconds": float(millis),
                      "heap_peak_mib": float(heap), "live_at_last_collection_mib": float(live)})


def inspector_evidence(sample, directory, source, variant, root):
    require(sample["exit_code"] == 0 and not sample["timed_out"],
            f"{sample['label']}: inspector failed; see {sample['stderr']['path']}")
    require(sample["stderr"]["bytes"] == 0, f"{sample['label']}: inspector stderr is nonempty")
    report_path = directory / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    target = "finalize" if variant == "finalize" else "lower"
    require(report["status"] == "ok" and report["settings"]["stop_after"] == target,
            "inspector did not complete the requested target")
    require(report["settings"]["captures"] == "typed-after"
            and report["settings"]["function_filter"] == ""
            and report["settings"]["executes_program"] is False, "unexpected inspection scope")
    require(report["verification"]["requested"] is True
            and report["verification"]["completed"] is True, "IR verification incomplete")
    require(not report["diagnostics"], "inspection includes diagnostics")
    observed = report["input"]
    require(observed["path"] == str(source) and observed["sha256"] == digest(source),
            "inspection input differs from the requested file")
    require(observed["changed_during_compilation"] is False and observed["modules"],
            "inspection source inventory missing or changed")
    for module in observed["modules"]:
        path = Path(module["path"])
        if not path.is_absolute():
            path = root / path
        raw = path.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        require(module["changed_since_read"] is False
                and module["sha256"] == hashlib.sha256(raw).hexdigest()
                and module["source_sha256"] == hashlib.sha256(normalized).hexdigest(),
                f"inspection module provenance differs: {path}")
    stages = {entry["name"]: entry for entry in report["stages"]}
    require(stages["typed-before"]["status"] == "skipped"
            and stages["typed-after"]["status"] == "completed", "unexpected snapshot status")
    require(report["artifacts"].get("typed-after") == "typed-after.json", "missing typed-after artifact")
    snapshot_path = directory / "typed-after.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    require(snapshot["stage"] == "typed-after" and snapshot["status"] == "completed"
            and snapshot["functions"] and "guard_inventory" in snapshot, "snapshot or guard evidence missing")
    require(report["artifact_sha256"]["typed-after"] == digest(snapshot_path), "snapshot digest differs")
    attempts = report["attempts"]
    require(attempts and snapshot["attempt"] == attempts[-1]["index"], "snapshot attempt mismatch")
    pipeline = attempts[-1]["pipeline"]
    expected = STAGES[:5] if variant == "finalize" else STAGES
    require(attempts[-1]["status"] == "completed" and pipeline["status"] == "completed"
            and pipeline["stage"] == target and pipeline["completed_stages"] == expected
            and pipeline["active_stage"] is None, "terminal pipeline incomplete")
    require(all(item["status"] == "retry" for item in attempts[:-1]), "nonretry preceding attempt")
    llvm = directory / "llvm.ll"
    if variant == "finalize":
        require("llvm" not in report["artifacts"] and stages["llvm"]["status"] == "skipped"
                and stages["llvm"]["artifact"] is None and not list(directory.rglob("*.ll")),
                "finalized inspection emitted LLVM")
        require((directory / "compiler.stdout").read_bytes().strip() == b"",
                "finalized inspection serialized unexpected stdout")
    else:
        require(report["artifacts"].get("llvm") == "llvm.ll"
                and stages["llvm"]["status"] == "completed" and llvm.is_file()
                and llvm.stat().st_size > 0, "default full inspection lacks LLVM")
        sample.update(llvm=file_identity(llvm), llvm_retained=True)
    sample.update(output=file_identity(snapshot_path), output_retained=True,
                  inspection_report=file_identity(report_path),
                  attempt_count=len(attempts), selected_functions=len(snapshot["functions"]),
                  consumed_modules=len(observed["modules"]), pipeline=expected,
                  inspector_elapsed_seconds=report["elapsed_seconds"],
                  no_llvm_verified=variant == "finalize")


def distribution(values):
    return {"count": len(values), "median": statistics.median(values),
            "min": min(values), "max": max(values)} if values else None


def summarize(samples, first, second):
    summary = {variant: {metric: distribution([sample[metric] for sample in samples
                                             if sample["variant"] == variant])
                         for metric in METRICS} for variant in (first, second)}
    pairs = []
    for number in sorted({sample["pair"] for sample in samples}):
        values = {sample["variant"]: sample for sample in samples if sample["pair"] == number}
        if set(values) != {first, second}:
            continue
        pairs.append({"pair": number, "order": [sample["variant"] for sample in samples
                                                  if sample["pair"] == number],
                      "numerator": second, "denominator": first,
                      "ratios": {metric: values[second][metric] / values[first][metric]
                                 if values[first][metric] else None for metric in METRICS}})
    summary["pairs"] = pairs
    summary["paired_ratios"] = {metric: distribution([pair["ratios"][metric] for pair in pairs
                                                      if pair["ratios"][metric] is not None])
                                for metric in METRICS}
    summary["ratio_of_separate_medians"] = {
        metric: summary[second][metric]["median"] / summary[first][metric]["median"]
        if summary[first][metric] and summary[second][metric] and summary[first][metric]["median"] else None
        for metric in METRICS}
    return summary


def positive_float(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return result


def positive_int(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--mode", choices=("all", "native", "inspect"), default="all")
    parser.add_argument("--old", type=Path, help="baseline native compiler (required in native/all mode)")
    parser.add_argument("--new", type=Path, help="candidate native compiler (required in native/all mode)")
    parser.add_argument("--root", required=True, type=Path, help="common source checkout and PYSTACHY_HOME")
    parser.add_argument("--output", required=True, type=Path, help="new evidence directory; must not exist")
    parser.add_argument("--pairs", type=positive_int, default=5)
    parser.add_argument("--cpu", type=int, help="one CPU in the current allowed affinity; otherwise its first CPU")
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help="hosted inspection interpreter")
    parser.add_argument("--inspect-library", type=Path, default=Path("tests/programs/library/lib_textwrap.py"),
                        help="moderate library corpus fixture, relative to root")
    parser.add_argument("--timeout", type=positive_float, default=60, help="hard per-command deadline in seconds")
    parser.add_argument("--warmup-limit", type=positive_float, default=5,
                        help="abort after an over-budget short workload warmup before collecting timed pairs")
    parser.add_argument("--self-warmup-limit", type=positive_float, default=10,
                        help="self-compilation warmup budget in seconds")
    return parser.parse_args()


def main():
    args = parse_args()
    require(sys.platform == "linux", "Linux wait4/RSS and taskset semantics are required")
    root = args.root.resolve(strict=True)
    taskset = shutil.which("taskset")
    require(taskset is not None, "taskset unavailable")
    allowed = sorted(os.sched_getaffinity(0))
    cpu = allowed[0] if args.cpu is None else args.cpu
    require(cpu in allowed, "selected CPU is outside the allowed affinity")
    os.sched_setaffinity(0, {cpu})  # Children inherit the pin before taskset execs.
    binaries = {}
    if args.mode in ("all", "native"):
        require(args.old is not None and args.new is not None, "native mode needs --old and --new")
        binaries = {"old": args.old.absolute(), "new": args.new.absolute()}
    if args.mode in ("all", "inspect"):
        binaries["python"] = args.python.absolute()
    for path in binaries.values():
        require(path.is_file() and os.access(path, os.X_OK), f"missing executable {path}")
    workloads = []
    if args.mode in ("all", "native"):
        workloads.extend({"name": name, "mode": "native", "source": str(root / source),
                          "command": command, "variants": ["old", "new"], "warmup_limit": limit}
                         for name, command, source, limit in (
                             ("self", "ir", "pystachy.py", args.self_warmup_limit),
                             ("runtime", "rt", "runtime.py", args.warmup_limit),
                             ("ffi", "ir", "tests/ffi/c_libc.py", args.warmup_limit)))
    if args.mode in ("all", "inspect"):
        for name, source in (("library", args.inspect_library), ("ffi", Path("tests/ffi/c_libc.py"))):
            path = (root / source).resolve(strict=True)
            require(path.is_relative_to(root), "inspection source must belong to the common checkout")
            workloads.append({"name": name, "mode": "inspect", "source": str(path),
                              "variants": ["full", "finalize"], "warmup_limit": args.warmup_limit})
    for work in workloads:
        require(Path(work["source"]).is_file(), f"missing input {work['source']}")
        require(not Path(work["source"]).with_suffix(".path").exists(),
                "fixture has a .path sidecar; select a directly compilable fixture")
    output = args.output.resolve()
    require(not output.is_relative_to(root), "put measurement evidence outside the source checkout")
    output.mkdir(parents=True, exist_ok=False)
    stripped = sorted(key for key in os.environ if key.startswith(("PYSTACHY_", "PYTHON")))
    env = {key: value for key, value in os.environ.items() if key not in stripped}
    env.update(PYSTACHY_HOME=str(root), PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1",
               LC_ALL="C.UTF-8", TZ="UTC")
    native_env = env | {"PYSTACHY_TIMING": "1", "PYSTACHY_GC": "stats"}
    relevant_env = lambda values: {key: value for key, value in values.items()
                                  if key.startswith(("PYSTACHY_", "PYTHON"))
                                  or key in ("LC_ALL", "TZ", "PATH")}
    manifest = {
        "schema_version": 1, "status": "running", "mode": args.mode, "pairs_requested": args.pairs,
        "warmups_per_variant": 1, "measurement_script": file_identity(Path(__file__).resolve()),
        "scope": {"native": "Native compiler source-to-LLVM, using identical absolute input paths and library root.",
                  "inspect": "Hosted inspector CLI through snapshot publication, full lowering versus finalized typed IR."},
        "limitations": [
            "Advisory shared-host measurements; no speed or regression claim follows from five pairs alone.",
            "All commands are sequential and pinned; caches are warm, not dropped; no LLVM machine-code generation or program execution.",
            "Wall time includes taskset/process startup and output writes; hashing, byte comparisons and deletions are outside timed regions.",
            "Native GC/timing instrumentation is enabled identically; GC heap/collections are not allocation counts.",
            "wait4 CPU includes waited descendants. Linux ru_maxrss is the largest process high-water mark, not summed process-tree RSS.",
            "Both binaries consume this one checkout; adjacent checkout revisions are hints, not build provenance for existing binaries.",
            "Warmups are recorded and excluded from summary ratios; short/self warmup budgets fail closed before collecting a long batch.",
        ],
        "root": str(root), "output": str(output), "cwd": str(Path.cwd()),
        "source_commit": git(root, "rev-parse", "HEAD"), "source_tree": git(root, "rev-parse", "HEAD^{tree}"),
        "git_status_before": git(root, "status", "--short"), "platform": platform.platform(),
        "machine": platform.machine(), "python_runner": sys.version, "cpu": cpu,
        "allowed_affinity_before_pin": allowed, "runner_affinity": sorted(os.sched_getaffinity(0)),
        "cpuinfo": Path("/proc/cpuinfo").read_text(),
        "clock": {"name": "perf_counter_ns", "resolution": time.get_clock_info("perf_counter").resolution},
        "taskset": file_identity(Path(taskset)), "removed_environment_keys": stripped,
        "environments": {"native": relevant_env(native_env), "inspect": relevant_env(env)},
        "sources_before": source_manifest(root, workloads),
        "binaries_before": {name: file_identity(path) for name, path in binaries.items()},
        "binary_adjacent_checkout_revisions": {name: git(path.parent, "rev-parse", "HEAD")
                                                for name, path in binaries.items()},
        "workloads": [], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if "old" in binaries:
        sizes = manifest["binaries_before"]
        manifest["binary_size"] = {"old": sizes["old"]["bytes"], "new": sizes["new"]["bytes"],
                                   "delta_bytes": sizes["new"]["bytes"] - sizes["old"]["bytes"],
                                   "ratio_new_over_old": sizes["new"]["bytes"] / sizes["old"]["bytes"]}
    destination = output / "report.json"
    save = lambda: write_json(destination, manifest)
    save()
    print(f"Evidence: {output}; CPU {cpu}; pairs {args.pairs}; mode {args.mode}", flush=True)
    try:
        for work in workloads:
            work = dict(work, status="running", warmups=[], samples=[])
            manifest["workloads"].append(work)
            directory = output / (work["mode"] + "-" + work["name"])
            directory.mkdir()
            reference = None
            reference_sample = None
            first, second = work["variants"]
            orders = [(0, [first, second])] + [(index, [first, second] if index % 2 else [second, first])
                                             for index in range(1, args.pairs + 1)]
            for pair, order in orders:
                for variant in order:
                    label = ("warmup" if pair == 0 else f"pair-{pair}") + "-" + variant
                    if work["mode"] == "native":
                        artifact = directory / (label + ".ll")
                        command = [taskset, "-c", str(cpu), str(binaries[variant]), work["command"],
                                   work["source"], "-o", str(artifact)]
                        current_env = native_env
                    else:
                        artifact_dir = directory / label
                        artifact = artifact_dir / "typed-after.json"
                        command = [taskset, "-c", str(cpu), str(binaries["python"]),
                                   str(root / "tools/inspect_compiler.py"), work["source"],
                                   "--output", str(artifact_dir), "--typed-after-only", "--guard-evidence",
                                   "--timeout", str(max(1, args.timeout - 2))]
                        if variant == "finalize":
                            command += ["--stop-after", "finalize"]
                        current_env = env
                    sample = run_command(command, root, directory, label, current_env, args.timeout)
                    sample.update(pair=pair, variant=variant, warmup=pair == 0)
                    (work["warmups"] if pair == 0 else work["samples"]).append(sample)
                    save()  # Preserve failed-process measurements before checking outputs.
                    if work["mode"] == "native":
                        native_evidence(sample, artifact)
                    else:
                        inspector_evidence(sample, artifact_dir, Path(work["source"]), variant, root)
                    if reference is None:
                        reference, reference_sample = artifact, sample
                        sample["exact_bytes_match_reference"] = True
                        work["equivalent_output"] = {"sha256": sample["output"]["sha256"],
                                                     "bytes": sample["output"]["bytes"],
                                                     "all_samples_equal": False}
                    else:
                        sample["exact_bytes_match_reference"] = same_bytes(reference, artifact)
                        require(sample["exact_bytes_match_reference"],
                                f"{work['mode']}/{work['name']}/{label}: output differs; files retained")
                        artifact.unlink()
                        sample["output_retained"] = False
                        sample["discard_reason"] = "exact byte match to the recorded warmup reference"
                    if "llvm" in sample:
                        Path(sample["llvm"]["path"]).unlink()
                        sample["llvm_retained"] = False
                        sample["llvm_discard_reason"] = "default full inspection completed; only finalized snapshots are compared"
                    work["summary"] = summarize(work["samples"], first, second)
                    save()
                    comparison = "reference recorded" if sample is reference_sample else "bytes match"
                    print(f"{work['mode']}/{work['name']}/{label}: {sample['wall_seconds']:.6f} s; "
                          f"CPU {sample['cpu_seconds']:.6f} s; RSS {sample['peak_rss_kib']} KiB; {comparison}", flush=True)
                    if pair == 0:
                        require(sample["wall_seconds"] <= work["warmup_limit"],
                                f"{work['mode']}/{work['name']}: warmup exceeded {work['warmup_limit']} s budget; "
                                "stop and select a smaller workload or explicitly revise the bound")
            require(len(work["samples"]) == args.pairs * 2, "incomplete pair count")
            # Keep one typed snapshot with guard evidence per inspection workload;
            # discard every native LLVM file only after all exact comparisons.
            if work["mode"] == "native":
                reference.unlink()
                reference_sample["output_retained"] = False
                reference_sample["discard_reason"] = "all warmup and measured outputs byte-equal; hashes retained"
            else:
                work["retained_snapshot"] = str(reference)
            work["equivalent_output"]["all_samples_equal"] = True
            work["status"] = "completed"
            save()
        manifest["status"] = "completed"
    except BaseException as error:  # noqa: BLE001 - record interrupted and failed measurements, then exit nonzero.
        manifest["status"] = "failed"
        manifest["error"] = {"type": type(error).__name__, "message": str(error)}
        if manifest["workloads"] and manifest["workloads"][-1]["status"] == "running":
            manifest["workloads"][-1]["status"] = "failed"
        print(f"Measurement failed: {error}", file=sys.stderr, flush=True)
    finally:
        try:
            manifest["sources_after"] = source_manifest(root, workloads)
            manifest["binaries_after"] = {name: file_identity(path) for name, path in binaries.items()}
            manifest["measurement_script_after"] = file_identity(Path(__file__).resolve())
            manifest["git_status_after"] = git(root, "status", "--short")
            manifest["source_and_binaries_unchanged"] = (
                manifest["sources_before"] == manifest["sources_after"]
                and manifest["binaries_before"] == manifest["binaries_after"]
                and manifest["measurement_script"] == manifest["measurement_script_after"])
            if not manifest["source_and_binaries_unchanged"]:
                manifest["status"] = "failed"
                manifest["identity_error"] = "sources, compiler/interpreter binaries, or runner changed during measurement"
        except Exception as error:  # noqa: BLE001 - record an identity-check failure without claiming completion.
            manifest["status"] = "failed"
            manifest["identity_error"] = f"{type(error).__name__}: {error}"
        manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save()
    print(f"{manifest['status']}: {destination}", flush=True)
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
