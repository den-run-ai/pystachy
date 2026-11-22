"""Bootstrap cost on an otherwise idle machine: `make pystachy` for a few commits, one at a time.

usage: python3.13 -I bootstrap_idle.py OUT.json LABEL=SHA...
Each commit is checked out in a fresh worktree (no build/ cache) and built once with the same
command as the sampled builds. Records wall time and the CPU time (user + sys) of the build's
processes, and the load average before and after. The pipeline's own bootstrap times were measured
beside the previous commit's test sweep on three different days, so only these runs compare
directly. The worktrees are removed afterwards.
"""
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
REPO = "/home/user/pystachy"
PY = "/usr/local/bin/python3.13"


def load():
    return [float(x) for x in open("/proc/loadavg").read().split()[:3]]


def main():
    out, pairs = sys.argv[1], [a.split("=", 1) for a in sys.argv[2:]]
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    rows = []
    base = Path(tempfile.mkdtemp(prefix="wt-idle.", dir=S))
    for label, sha in pairs:
        wt = base / label
        subprocess.run(["git", "-C", REPO, "worktree", "add", "--detach", str(wt), sha], check=True,
                       capture_output=True)
        before_load = load()
        r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        t0 = time.perf_counter()
        with open(S / f"logs/idle-build-{label}.log", "w") as log:
            p = subprocess.run(["make", f"PY={PY}", "pystachy"], cwd=wt, env=env, stdout=log, stderr=subprocess.STDOUT)
        wall = time.perf_counter() - t0
        r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
        row = {"label": label, "sha": sha, "ok": p.returncode == 0, "wall_s": round(wall, 1), "cpu_s": round(cpu, 1),
               "load_before": before_load, "load_after": load(),
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        rows.append(row)
        print(json.dumps(row), flush=True)
        subprocess.run(["git", "-C", REPO, "worktree", "remove", "--force", str(wt)], capture_output=True)
        json.dump({"nproc": os.cpu_count(), "command": f"make PY={PY} pystachy", "runs": rows}, open(out, "w"), indent=1)
    shutil.rmtree(base, ignore_errors=True)
    subprocess.run(["git", "-C", REPO, "worktree", "prune"], capture_output=True)


if __name__ == "__main__":
    main()
