"""Advisory native frontend comparison; run only while other task work is idle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import tempfile
import time


BASE = "80490143"
GC = re.compile(r"gc: (\d+) collections, ([0-9.]+) ms; heap peak ([0-9.]+) MiB; live ([0-9.]+) MiB at the last")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            value.update(part)
    return value.hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def source_manifest(root):
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "pystachy.py", "src", "lib", "runtime.py", "runtime.c", "ryu", "mpz"],
        cwd=root,
    ).decode().split("\0")
    return {path: digest(root / path) for path in paths if path}


def run_sample(root, directory, binary, variant, label, cpu, env):
    output = directory / (label + ".ll")
    stderr = directory / (label + ".stderr")
    stdout = directory / (label + ".stdout")
    command = ["/usr/bin/taskset", "-c", str(cpu), str(binary), "ir", "pystachy.py", "-o", str(output)]
    before_load = os.getloadavg()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with stdout.open("wb") as out, stderr.open("wb") as err:
        started = time.perf_counter_ns()
        process = subprocess.Popen(command, cwd=root, env=env, stdout=out, stderr=err)
        # wait4 reports CPU and peak RSS for this exact compiler process. This
        # is not the accumulating maximum of RUSAGE_CHILDREN across all runs.
        waited, status, usage = os.wait4(process.pid, 0)
        elapsed = (time.perf_counter_ns() - started) / 1e9
        assert waited == process.pid
        process.returncode = os.waitstatus_to_exitcode(status)
    text = stderr.read_text()
    if process.returncode != 0:
        raise RuntimeError(f"{label}: exit {process.returncode}; see {stderr}")
    if stdout.stat().st_size:
        raise RuntimeError(f"{label}: unexpected stdout; see {stdout}")
    gc = GC.findall(text)
    if len(gc) != 1:
        raise RuntimeError(f"{label}: expected one GC summary, found {len(gc)}")
    timings = []
    for line in text.splitlines():
        if line.startswith("pystachy-timing\t"):
            _, stage, seconds = line.split("\t")
            timings.append({"stage": stage, "seconds": float(seconds)})
        elif not line.startswith("gc:"):
            raise RuntimeError(f"{label}: unexpected diagnostic {line!r}")
    fields = gc[0]
    return {
        "variant": variant, "label": label, "command": command,
        "started_utc": started_utc, "exit_code": process.returncode,
        "wall_seconds": elapsed, "user_seconds": usage.ru_utime,
        "system_seconds": usage.ru_stime, "peak_rss_kib": usage.ru_maxrss,
        "voluntary_context_switches": usage.ru_nvcsw,
        "involuntary_context_switches": usage.ru_nivcsw,
        "load_average_before": before_load, "load_average_after": os.getloadavg(),
        "gc": {"collections": int(fields[0]), "milliseconds": float(fields[1]),
               "heap_peak_mib": float(fields[2]), "live_at_last_collection_mib": float(fields[3])},
        "timings": timings, "output": str(output), "output_bytes": output.stat().st_size,
        "output_sha256": digest(output), "stderr": str(stderr), "stdout": str(stdout),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cpu", type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    allowed = sorted(os.sched_getaffinity(0))
    cpu = allowed[0] if args.cpu is None else args.cpu
    if cpu not in allowed:
        raise ValueError("selected CPU is not allowed")
    binaries = {"main": root / "build/ref/pystachy", "stages": root / "pystachy"}
    base = git(root, "rev-parse", BASE)
    if (root / "build/ref/commit").read_text().strip() != base:
        raise ValueError("baseline binary source identity differs from expected main")
    for binary in binaries.values():
        if not os.access(binary, os.X_OK):
            raise ValueError(f"missing compiler {binary}")
    directory = args.output.resolve() if args.output else Path(tempfile.mkdtemp(
        prefix="stage-overhead-", dir=root.parent))
    if args.output:
        directory.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env.update(PYSTACHY_HOME=str(root), PYSTACHY_GC="stats", PYSTACHY_TIMING="1")
    sources = source_manifest(root)
    manifest = {
        "schema_version": 1, "scope": "native source-to-LLVM self-compilation; no LLVM optimization/code generation",
        "advisory": "shared host; no other task-owned heavy work; five interleaved pairs do not establish a speedup",
        "allocation_counts": "unavailable in ordinary binaries; GC collections and heap metrics are not allocation counts",
        "root": str(root), "source_commit": git(root, "rev-parse", "HEAD"),
        "source_tree": git(root, "rev-parse", "HEAD^{tree}"), "base_commit": base,
        "git_status": git(root, "status", "--short"), "sources": sources,
        "binaries": {name: {"path": str(path), "bytes": path.stat().st_size,
                             "sha256": digest(path)} for name, path in binaries.items()},
        "platform": platform.platform(), "machine": platform.machine(),
        "cpu": cpu, "allowed_cpus": allowed, "cpuinfo": Path("/proc/cpuinfo").read_text(),
        "environment": {key: value for key, value in env.items() if key.startswith("PYSTACHY_")},
        "warmups": [], "samples": [],
    }
    destination = directory / "report.json"
    def save():
        destination.write_text(json.dumps(manifest, indent=2) + "\n")
    save()
    print(f"Artifacts: {directory}; pinned CPU {cpu}", flush=True)
    expected = None
    for variant in ("main", "stages"):
        sample = run_sample(root, directory, binaries[variant], variant, "warmup-" + variant, cpu, env)
        expected = expected or sample["output_sha256"]
        if sample["output_sha256"] != expected:
            raise RuntimeError("warmup compiler outputs differ")
        manifest["warmups"].append(sample)
        save()
        print(f"Warmup {variant}: {sample['wall_seconds']:.6f} s", flush=True)
    for pair in range(5):
        order = ("main", "stages") if pair % 2 == 0 else ("stages", "main")
        for variant in order:
            sample = run_sample(root, directory, binaries[variant], variant, f"pair-{pair + 1}-{variant}", cpu, env)
            sample["pair"] = pair + 1
            if sample["output_sha256"] != expected:
                raise RuntimeError(f"{sample['label']}: LLVM hash differs")
            manifest["samples"].append(sample)
            save()
            print(f"{sample['label']}: {sample['wall_seconds']:.6f} s; RSS {sample['peak_rss_kib']} KiB; "
                  f"GC {sample['gc']['collections']}/{sample['gc']['milliseconds']} ms", flush=True)
    if source_manifest(root) != sources:
        raise RuntimeError("source changed during measurement")
    for variant, binary in binaries.items():
        if digest(binary) != manifest["binaries"][variant]["sha256"]:
            raise RuntimeError("compiler changed during measurement")
    summary = {}
    for variant in binaries:
        samples = [sample for sample in manifest["samples"] if sample["variant"] == variant]
        summary[variant] = {
            "count": len(samples),
            **{field: {"median": statistics.median([sample[field] for sample in samples]),
                       "min": min(sample[field] for sample in samples),
                       "max": max(sample[field] for sample in samples)}
               for field in ("wall_seconds", "user_seconds", "system_seconds", "peak_rss_kib")},
            "gc": {field: {"median": statistics.median([sample["gc"][field] for sample in samples]),
                            "min": min(sample["gc"][field] for sample in samples),
                            "max": max(sample["gc"][field] for sample in samples)}
                   for field in ("collections", "milliseconds", "heap_peak_mib", "live_at_last_collection_mib")},
        }
    summary["wall_median_ratio_stages_over_main"] = summary["stages"]["wall_seconds"]["median"] / summary["main"]["wall_seconds"]["median"]
    summary["binary_size_ratio_stages_over_main"] = manifest["binaries"]["stages"]["bytes"] / manifest["binaries"]["main"]["bytes"]
    summary["output_sha256"] = expected
    manifest["summary"] = summary
    manifest["source_and_binaries_unchanged"] = True
    save()
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
