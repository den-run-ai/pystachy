"""Timing phase: run only on an otherwise idle machine, after every build and analysis finished.

usage: python3.13 -I timing.py COMMITS.txt OUT.json [--aot-reps N] [--micro-reps N] [--jit-reps N] [--cpu C]

AOT: each repetition runs CPython and every commit whose executable printed CPython's output in
perfprep, in an order rotated by one position per repetition (so slow drift of the host spreads
over all commits), each process pinned to CPU C. Records wall, CPU (user+sys) and the port's own
'seconds' line (the region pyperf would time). Every run's stdout must equal CPython's.
JIT: `pystachy run` end to end (frontend, LLVM and execution; program cache off, runtime cache
warm), not pinned, interleaved the same way.
"""
import json
import os
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
SW = S / "sweep"
PY = "/usr/local/bin/python3.13"
# JIT end to end only for the small day-one programs and three larger ports; compile time alone for three.
JIT_SET = {"micro_fib", "micro_mandel", "micro_nbody", "micro_sieve", "micro_spectral", "micro_words",
           "richards", "raytrace", "go"}
BUILD_SET = ["micro_nbody", "richards", "raytrace"]


def measure(cmd, cwd, env, expected, pin):
    if pin is not None:
        cmd = ["taskset", "-c", str(pin)] + cmd
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=600)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    wall = time.perf_counter() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    out, err = p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")
    found = re.findall(r"^seconds (\S+)$", err, re.M)
    rec = {"ok": p.returncode == 0 and out == expected, "wall": wall,
           "cpu": after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime,
           "loop": float(found[0]) if len(found) == 1 else None}
    if not rec["ok"]:
        rec["error"] = (out[-200:] + " | " + err[-300:]).strip()
    return rec


def main():
    args = sys.argv[1:]
    opts = {"--aot-reps": "5", "--micro-reps": "7", "--jit-reps": "2", "--cpu": "3"}
    for k in list(opts):
        if k in args:
            i = args.index(k)
            opts[k] = args[i + 1]
            del args[i:i + 2]
    commits_file, out = args
    labels = [line.split()[0] for line in open(commits_file) if line.strip()]
    specs = json.load(open(SW / "perf_specs.json"))
    ref = json.load(open(SW / "cpython_ref.json"))["ref"]
    prep = {}
    for label in labels:
        f = S / "results" / f"perfprep-{label}.json"
        if f.exists():
            prep[label] = json.load(open(f))
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_PROGRAM_CACHE"] = "0"
    root = SW / "perfroot"
    pin = int(opts["--cpu"])
    results = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "options": opts,
               "load_before": os.getloadavg(), "aot": {}, "jit": {}}
    t_start = time.monotonic()
    for name, spec in specs.items():
        reps = int(opts["--micro-reps"] if spec["kind"] == "micro" else opts["--aot-reps"])
        src = str(root / spec["src"])
        runners = [("cpython", [PY, src] + spec["args"])]
        runners += [(lab, [str(S / "exe" / lab / name)] + spec["args"]) for lab in labels
                    if prep.get(lab, {}).get(name, {}).get("aot_correct")]
        rows = {lab: [] for lab, _ in runners}
        for r in range(reps):
            k = r % len(runners)
            for lab, cmd in runners[k:] + runners[:k]:
                rows[lab].append(measure(cmd, root, env, ref[name]["stdout"], pin))
        results["aot"][name] = rows
        print(f"aot {name}: {len(runners) - 1} commits x {reps} ({time.monotonic() - t_start:.0f}s)", flush=True)
        json.dump(results, open(out, "w"))
    for name, spec in specs.items():
        if name not in JIT_SET:
            continue
        reps = int(opts["--jit-reps"])
        src = str(root / spec["src"])
        runners = [(lab, [str(S / "wt" / lab / "pystachy"), "run", src] + spec["args"]) for lab in labels
                   if prep.get(lab, {}).get(name, {}).get("jit_correct")]
        rows = {lab: [] for lab, _ in runners}
        for r in range(reps):
            k = r % max(1, len(runners))
            for lab, cmd in runners[k:] + runners[:k]:
                rows[lab].append(measure(cmd, str(S / "wt" / lab), env, ref[name]["stdout"], None))
        results["jit"][name] = rows
        print(f"jit {name}: {len(runners)} commits x {reps} ({time.monotonic() - t_start:.0f}s)", flush=True)
        json.dump(results, open(out, "w"))
    # Compile cost alone: `pystachy build` (frontend, LLVM -O2, link) of fixed programs, pinned.
    results["build"] = {}
    for name in BUILD_SET:
        spec = specs[name]
        src = str(root / spec["src"])
        labs = [lab for lab in labels if prep.get(lab, {}).get(name, {}).get("aot_correct")]
        rows = {lab: [] for lab in labs}
        for r in range(2):
            k = r % max(1, len(labs))
            for lab in labs[k:] + labs[:k]:
                exe = S / "exe" / lab / f"{name}.timing-build"
                cmd = ["taskset", "-c", str(pin), str(S / "wt" / lab / "pystachy"), "build", src, "-o", str(exe)]
                t0 = time.perf_counter()
                p = subprocess.run(cmd, cwd=str(S / "wt" / lab), env=env, capture_output=True, timeout=900)
                rows[lab].append({"ok": p.returncode == 0, "wall": time.perf_counter() - t0})
                exe.unlink(missing_ok=True)
        results["build"][name] = rows
        print(f"build {name}: {len(labs)} commits x 2 ({time.monotonic() - t_start:.0f}s)", flush=True)
        json.dump(results, open(out, "w"))
    results["load_after"] = os.getloadavg()
    results["elapsed_s"] = time.monotonic() - t_start
    json.dump(results, open(out, "w"))
    print("timing done", flush=True)


if __name__ == "__main__":
    main()
