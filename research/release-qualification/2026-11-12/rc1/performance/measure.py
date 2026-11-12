"""11 alternating interleaved AOT pairs; invoke only after local-check completion signal."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import platform
import re
import resource
import statistics
import subprocess
import time

HERE = Path(__file__).resolve().parent
CPU = 3
REPS = 11
EXPECTED = (HERE / "output.cpython.txt").read_text()
assert CPU in os.sched_getaffinity(0)
COMMANDS = {name: [str(HERE / ("float." + name)), "10"] for name in ["main", "candidate"]}
ENV = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}

def read_if_exists(path):
    try:
        return Path(path).read_text()
    except (OSError, PermissionError):
        return None

def snapshot():
    paths = ["/proc/loadavg", "/proc/stat", "/sys/fs/cgroup/cpu.stat", "/sys/fs/cgroup/cpu.max",
             "/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor",
             "/sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq"]
    return {path: read_if_exists(path) for path in paths}

def run(name, repetition, warmup):
    cmd = ["taskset", "-c", str(CPU)] + COMMANDS[name]
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.perf_counter_ns()
    result = subprocess.run(cmd, cwd=HERE, env=ENV, capture_output=True, text=True, timeout=30)
    wall = (time.perf_counter_ns() - t0) / 1e9
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    assert result.returncode == 0 and result.stdout == EXPECTED, (name, result.returncode, result.stdout, result.stderr)
    times = re.findall(r"^seconds (\S+)$", result.stderr, re.M)
    assert len(times) == 1, result.stderr
    return {"label": name, "repetition": repetition, "warmup": warmup, "command": cmd,
            "timed_seconds": float(times[0]), "wall_seconds": wall,
            "user_seconds": ru1.ru_utime - ru0.ru_utime, "system_seconds": ru1.ru_stime - ru0.ru_stime,
            "voluntary_context_switches": ru1.ru_nvcsw - ru0.ru_nvcsw,
            "involuntary_context_switches": ru1.ru_nivcsw - ru0.ru_nivcsw,
            "status": result.returncode, "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest()}

report = {"started": datetime.datetime.now(datetime.timezone.utc).isoformat(), "cpu": CPU,
          "allowed_cpus": sorted(os.sched_getaffinity(0)), "repetitions": REPS,
          "metric": "benchmark stderr seconds line; seconds inside float main's loop region",
          "workload": {"source": "bench/pyperformance/float.py", "args": ["10"], "points_per_loop": 100000},
          "platform": platform.platform(), "machine": platform.machine(),
          "cpuinfo": read_if_exists("/proc/cpuinfo"), "before": snapshot(), "warmups": [], "samples": []}
for rep in range(2):
    for name in (["main", "candidate"] if rep % 2 == 0 else ["candidate", "main"]):
        report["warmups"].append(run(name, rep, True))
for rep in range(REPS):
    for name in (["main", "candidate"] if rep % 2 == 0 else ["candidate", "main"]):
        report["samples"].append(run(name, rep, False))
report["after"] = snapshot()
report["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
report["results"] = {}
for name in COMMANDS:
    values = [row["timed_seconds"] * 1000 for row in report["samples"] if row["label"] == name]
    median = statistics.median(values)
    report["results"][name] = {"median_ms": median, "min_ms": min(values), "max_ms": max(values),
                               "mad_ms": statistics.median([abs(value - median) for value in values]),
                               "mean_ms": statistics.mean(values), "stdev_ms": statistics.stdev(values),
                               "samples_ms": values}
main = report["results"]["main"]["median_ms"]
candidate = report["results"]["candidate"]["median_ms"]
report["median_comparison"] = {"candidate_time_reduction_percent": 100 * (main - candidate) / main,
                                "speedup_ratio": main / candidate}
pairs = []
for rep in range(REPS):
    values = {row["label"]: row["timed_seconds"] for row in report["samples"] if row["repetition"] == rep}
    pairs.append(values["main"] / values["candidate"])
report["pairs"] = {"speedup_ratios": pairs, "candidate_faster": sum(ratio > 1 for ratio in pairs),
                   "median_speedup": statistics.median(pairs)}
(HERE / "timing.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"results": report["results"], "comparison": report["median_comparison"], "pairs": report["pairs"]}, indent=2))
