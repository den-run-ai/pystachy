"""Interleaved, CPU-pinned `pystachy run` of one program under JIT settings, with stage records.

usage: jit_variants.py ROUNDS OUT.json PYSTACHY PROGRAM.py [ARGS...] [< STDIN]
Variants: default (the JIT's cleanup) and opt2 (PYSTACHY_JIT_OPT=2). Each round runs both, in
rotating order, pinned to CPU 1, with the program cache off (each run optimizes the program
again) and PYSTACHY_TIMING=1. Records per run: wall seconds, peak RSS of the largest process
(wait4's ru_maxrss), each pystachy-timing stage, and the program's own `NAME=SECONDS` stderr
timers. Every run's stdout must equal the first run's; the first run's must equal CPython's
(python3.13) when --check is given.
"""

import json
import os
import re
import shlex
import statistics
import subprocess
import sys
import tempfile
import time

rounds = int(sys.argv[1])
out_path = sys.argv[2]
pystachy = shlex.split(sys.argv[3])  # (a command: './pystachy', or 'python3.13 pystachy.py')
program = sys.argv[4:]
stdin_data = b"" if sys.stdin.isatty() else sys.stdin.buffer.read()
variants = {"default": {}, "opt2": {"PYSTACHY_JIT_OPT": "2"}}
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
base |= {"PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_TIMING": "1"}
for keep in ("PYSTACHY_CACHE", "PYSTACHY_LLVM", "PYSTACHY_HOME", "PYSTACHY_PATH"):
    if keep in os.environ:
        base[keep] = os.environ[keep]

reference = subprocess.run(["python3.13", *program], input=stdin_data, capture_output=True).stdout


def once(env: dict[str, str]) -> tuple[bytes, dict[str, float]]:
    # (stdout and stderr to files, so that wait4 reaps the child and reports its peak RSS: the
    # largest of its own and of the descendants it waited for, opt and the JIT runner)
    with tempfile.TemporaryFile() as fin, tempfile.TemporaryFile() as fout, tempfile.TemporaryFile() as ferr:
        fin.write(stdin_data)
        fin.seek(0)
        start = time.perf_counter()
        proc = subprocess.Popen(["taskset", "-c", "1", *pystachy, "run", *program], env=base | env,
                                stdin=fin, stdout=fout, stderr=ferr)
        _, status, usage = os.wait4(proc.pid, 0)
        wall = time.perf_counter() - start
        proc.returncode = os.waitstatus_to_exitcode(status)
        fout.seek(0)
        ferr.seek(0)
        out, err = fout.read(), ferr.read()
    if proc.returncode != 0:
        sys.exit(f"{env}: exit {proc.returncode}: {err.decode()[-400:]}")
    row: dict[str, float] = {"wall": wall, "peak_rss_mib": usage.ru_maxrss / 1024}
    for line in err.decode().splitlines():
        if line.startswith("pystachy-timing\t"):
            _, name, seconds = line.split("\t")
            row[name] = row.get(name, 0.0) + float(seconds)
        elif re.fullmatch(r"seconds [0-9.e+-]+", line):
            row["timer.loop"] = float(line.split()[1])  # (the pyperformance ports' timed loop)
        else:
            for name, seconds in re.findall(r"\b([a-z]+)=([0-9]+\.[0-9]+)", line):
                row["timer." + name] = float(seconds)
    return out, row


runs: dict[str, list[dict[str, float]]] = {v: [] for v in variants}
names = list(variants)
first = None
for r in range(rounds):
    order = names[r % len(names):] + names[:r % len(names)]
    for v in order:
        out, row = once(variants[v])
        if first is None:
            first = out
            if out != reference:
                sys.exit(f"{v}: output differs from CPython's")
        elif out != first:
            sys.exit(f"{v}: output differs from the first run's")
        runs[v].append(row)
summary: dict[str, dict[str, float]] = {}
SHOWN = ("wall", "peak_rss_mib", "program.frontend", "program.jit_optimize", "program.jit_codegen")
keys = list(runs[names[0]][0])
for key in keys:
    for v in names:
        ts = [row.get(key, 0.0) for row in runs[v]]
        summary.setdefault(key, {})[v] = statistics.median(ts)
    a, b = summary[key]["default"], summary[key]["opt2"]
    ratios = [runs["opt2"][i].get(key, 0.0) / runs["default"][i][key] for i in range(rounds) if runs["default"][i].get(key)]
    if key in SHOWN or key.startswith("timer."):
        print(f"{os.path.basename(program[0]):28s} {key:24s} default {a:8.3f}  opt2 {b:8.3f}"
              + (f"  paired {statistics.median(ratios):.3f}" if ratios else ""))
json.dump({"program": program, "rounds": rounds, "runs": runs, "summary": summary}, open(out_path, "w"), indent=1)
