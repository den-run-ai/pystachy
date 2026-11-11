"""Reproduce long AOT pyperf pairs after the match controller completes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pyperf


root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
report_path = root / "build/match-dispatch-measured.json"
report = json.loads(report_path.read_text())
assert report["status"] == "passed", "The complete correctness controller must pass first"
exe = Path(report["artifact_directory"]) / "dispatch.exe"
assert hashlib.sha256(exe.read_bytes()).hexdigest() == report["aot_binary_sha256"]
outputs = {variant: root / f"build/match-pyperf-{variant}.json" for variant in ("match", "if")}
assert all(not path.exists() for path in outputs.values()), "Use fresh output files"
loops, size, workers, values = 100000, 4096, 3, 5
settings = report["effective_settings"]
assert size == settings["size"] and loops % settings["loops"] == 0
factor = loops // settings["loops"]
cpu = report["metadata"]["cpu_affinity"][0]
os.sched_setaffinity(0, {cpu})
environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
environment.update(PYTHONHASHSEED="0", LC_ALL="C.UTF-8")
manifest_path = root / "build/match-pyperf-manifest.json"
manifest = {
    "status": "incomplete", "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "git_revision": report["metadata"]["git_revision"],
    "controller_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
    "executable_sha256": report["aot_binary_sha256"], "pyperf_version": pyperf.__version__,
    "workload_loops": loops, "input_size": size, "worker_processes": workers,
    "values_per_worker": values, "warmups_per_worker": 1, "pyperf_loops": 1,
    "cpu_affinity": [cpu], "load_average_start": os.getloadavg(),
    "scope": "Full AOT process timings; each worker block alternates match/if order. The preflight checksum scales the independently validated CPython controller checksum by the exact linear outer-loop count.",
    "preflight": [], "commands": [],
}


def save():
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")


save()
try:
    for index, case in enumerate(report["cases"]):
        kind, shape = case["kind"], case["shape"]
        for variant in ("match", "if"):
            command = [str(exe), kind, variant, shape, str(loops), str(size)]
            result = subprocess.run(command, env=environment, capture_output=True, text=True,
                                    check=True, timeout=120, cwd=root)
            rows = result.stdout.splitlines()
            expected = case["oracle"][variant]["checksum"] * factor
            assert rows == [str(expected), str(loops * size)], (command, rows, expected)
            timing = result.stderr.split()
            assert len(timing) == 2 and timing[0] == "kernel_wall_ns" and int(timing[1]) > 0
            manifest["preflight"].append({"command": command, "checksum": expected,
                                           "count": loops * size, "kernel_wall_ns": int(timing[1])})
        save()
        for worker in range(workers):
            variants = ("match", "if") if (index + worker) % 2 == 0 else ("if", "match")
            for variant in variants:
                command = [sys.executable, "-m", "pyperf", "command", "--name", f"{kind}-{shape}",
                           "--append", str(outputs[variant]), "--affinity", str(cpu),
                           "-p", "1", "-n", str(values), "-w", "1", "-l", "1",
                           str(exe), kind, variant, shape, str(loops), str(size)]
                print(f"{kind}/{shape} worker {worker + 1}/{workers} {variant}", flush=True)
                subprocess.run(command, check=True, env=environment, cwd=root)
                manifest["commands"].append({"worker": worker, "variant": variant, "command": command})
                save()
    manifest["status"] = "passed"
    manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["load_average_end"] = os.getloadavg()
    save()
    subprocess.run([sys.executable, "-m", "pyperf", "compare_to", str(outputs["if"]),
                    str(outputs["match"]), "--table", "--table-format", "md"], check=True, cwd=root)
except Exception as error:
    manifest["error"] = str(error)
    save()
    raise
