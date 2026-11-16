"""Cost of `pystachy check` against `pystachy ir` with one compiler, interleaved on one core.

usage: python3 -I check_cost.py COMPILER CPU SAMPLES PROGRAM...

Each round runs `ir PROGRAM -o /dev/null` and `check PROGRAM`, alternating which goes first,
pinned with taskset. Wall time from perf_counter, peak RSS from wait4 (KiB).
"""
import json
import os
import statistics
import subprocess
import sys
import time


def one(cmd, cpu):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = os.environ.get("PYSTACHY_HOME", "")
    start = time.perf_counter()
    p = subprocess.Popen(["taskset", "-c", str(cpu)] + cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    _, status, usage = os.wait4(p.pid, 0)
    wall = time.perf_counter() - start
    err = p.stderr.read()
    return wall, usage.ru_maxrss, os.waitstatus_to_exitcode(status), err


def main():
    compiler, cpu, samples = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    out = {}
    for program in sys.argv[4:]:
        cmds = {"ir": [compiler, "ir", program, "-o", "/dev/null"], "check": [compiler, "check", program]}
        for cmd in cmds.values():
            one(cmd, cpu)  # (warm-up: page cache)
        rec = {k: [] for k in cmds}
        for i in range(samples):
            for name in (["ir", "check"] if i % 2 == 0 else ["check", "ir"]):
                wall, rss, code, err = one(cmds[name], cpu)
                rec[name].append({"wall": wall, "rss_kib": rss, "exit": code})
        out[program] = {name: {"wall_median": statistics.median(x["wall"] for x in r),
                               "wall_min": min(x["wall"] for x in r),
                               "rss_median_kib": statistics.median(x["rss_kib"] for x in r),
                               "exits": sorted({x["exit"] for x in r})} for name, r in rec.items()}
        out[program]["check_over_ir_wall"] = out[program]["check"]["wall_median"] / out[program]["ir"]["wall_median"]
    print(json.dumps({"compiler": compiler, "cpu": cpu, "samples": samples, "programs": out,
                      "loadavg_after": os.getloadavg()}, indent=1))


if __name__ == "__main__":
    main()
