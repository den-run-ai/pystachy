"""Find the first-parent commit where one benchmark's AOT time moved from GOOD's level to BAD's.

usage: python3.13 -I bisect_perf.py BENCH GOOD_SHA BAD_SHA OUT.json [--reps N]
Builds each probed commit in its own worktree (build_one.sh), AOT-builds the frozen benchmark,
runs it pinned to CPU 3 (median of N runs, output checked against CPython), and classifies the
commit by whether its time is nearer GOOD's or BAD's on a log scale. Run on an idle machine.
"""
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
SW = S / "sweep"
REPO = "/home/user/pystachy"


def git(*args):
    return subprocess.run(["git", "-C", REPO] + list(args), capture_output=True, text=True, check=True).stdout.strip()


def label(sha):
    return "bis_" + sha[:10]


def measure(sha, bench, reps):
    sha = git("rev-parse", sha)
    existing = [p for p in (S / "wt").iterdir() if p.name.endswith("_" + sha[:8]) and (p / "pystachy").exists()]
    lab = existing[0].name if existing else label(sha)
    wt = S / "wt" / lab
    if not (wt / "pystachy").exists():
        r = subprocess.run([str(SW / "build_one.sh"), lab, sha], capture_output=True, text=True)
        if r.returncode != 0:
            return {"sha": sha, "error": "build failed"}
    spec = json.load(open(SW / "perf_specs.json"))[bench]
    ref = json.load(open(SW / "cpython_ref.json"))["ref"][bench]["stdout"]
    root = SW / "perfroot"
    exe = S / "exe" / lab / bench
    exe.parent.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_PROGRAM_CACHE"] = "0"
    b = subprocess.run([str(wt / "pystachy"), "build", str(root / spec["src"]), "-o", str(exe)], cwd=str(wt), env=env,
                       capture_output=True, text=True)
    if b.returncode != 0:
        return {"sha": sha, "error": "benchmark build failed: " + b.stderr[-200:]}
    vals = []
    for _ in range(reps):
        t0 = time.perf_counter()
        p = subprocess.run(["taskset", "-c", "3", str(exe)] + spec["args"], cwd=str(root), env=env, capture_output=True, text=True)
        wall = time.perf_counter() - t0
        if p.returncode != 0 or p.stdout != ref:
            return {"sha": sha, "error": "output differs"}
        found = re.findall(r"^seconds (\S+)$", p.stderr, re.M)
        vals.append(float(found[0]) if spec["kind"] == "pyperformance" and found else wall)
    return {"sha": sha, "median": statistics.median(vals), "runs": vals}


def main():
    args = sys.argv[1:]
    reps = 9
    if "--reps" in args:
        i = args.index("--reps")
        reps = int(args[i + 1])
        del args[i:i + 2]
    bench, good, bad, out = args
    commits = git("rev-list", "--first-parent", "--reverse", f"{good}..{bad}").split()
    log = {"bench": bench, "good": good, "bad": bad, "probes": []}
    g = measure(good, bench, reps)
    bd = measure(bad, bench, reps)
    log["probes"] += [g, bd]
    print(f"good {good[:10]} {g.get('median')}  bad {bad[:10]} {bd.get('median')}  ({len(commits)} commits)", flush=True)
    lo, hi = -1, len(commits) - 1  # commits[hi] is known bad (the BAD sha itself)
    mid_log = (math.log(g["median"]) + math.log(bd["median"])) / 2
    while hi - lo > 1:
        mid = (lo + hi) // 2
        m = measure(commits[mid], bench, reps)
        log["probes"].append(m)
        if "median" not in m:
            print(f"  {commits[mid][:10]} skipped: {m['error']}", flush=True)
            commits.pop(mid)
            hi -= 1
            continue
        is_bad = (math.log(m["median"]) > mid_log) == (bd["median"] > g["median"])
        print(f"  {commits[mid][:10]} {m['median']:.4f} -> {'bad' if is_bad else 'good'}", flush=True)
        if is_bad:
            hi = mid
        else:
            lo = mid
        json.dump(log, open(out, "w"), indent=1)
    first = commits[hi]
    log["first_bad"] = first
    log["first_bad_subject"] = git("log", "-1", "--format=%s", first)
    log["first_bad_parents"] = git("log", "-1", "--format=%P", first)
    json.dump(log, open(out, "w"), indent=1)
    print("first bad:", first[:10], log["first_bad_subject"], flush=True)


if __name__ == "__main__":
    main()
