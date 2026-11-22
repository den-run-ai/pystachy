"""Split the bootstrap's cost: each commit's compiler compiling its own source, on the idle machine.

usage: python3.13 -I selfcompile.py OUT.json LABEL...
For each sampled commit (its built worktree under $S/wt), times, in its own checkout:
  native-ir     ./pystachy ir pystachy.py             (the native compiler's frontend only)
  native-build  ./pystachy build pystachy.py          (frontend, LLVM -O2 and linking: one bootstrap stage)
  hosted-ir     python3.13 pystachy.py ir pystachy.py (the frontend run by CPython, as stage 1 runs it)
Native measures run twice and hosted once, commits interleaved (A B C, then C B A). Records wall and the
CPU time (user + sys) of the command's processes.
"""
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
PY = "/usr/local/bin/python3.13"


def timed(cmd, cwd, env):
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True)
    wall = time.perf_counter() - t0
    r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
    return {"ok": p.returncode == 0, "wall_s": round(wall, 2), "cpu_s": round(cpu, 2),
            **({} if p.returncode == 0 else {"error": p.stderr.decode(errors="replace")[-300:]})}


def main():
    out, labels = sys.argv[1], sys.argv[2:]
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_PROGRAM_CACHE"] = "0"
    benv = dict(env, PYSTACHY_AOT_OPT="2")
    tmp = Path(tempfile.mkdtemp(prefix="selfc.", dir=S))
    res = {lab: {"native-ir": [], "native-build": [], "hosted-ir": []} for lab in labels}
    orders = [labels, labels[::-1]]
    for rep, order in enumerate(orders):
        for lab in order:
            wt = S / "wt" / lab
            res[lab]["native-ir"].append(timed(["./pystachy", "ir", "pystachy.py", "-o", str(tmp / f"{lab}.ll")], wt, env))
            res[lab]["native-build"].append(timed(["./pystachy", "build", "pystachy.py", "-o", str(tmp / f"{lab}.exe")], wt, benv))
            if rep == 0:
                res[lab]["hosted-ir"].append(timed([PY, "pystachy.py", "ir", "pystachy.py", "-o", str(tmp / f"{lab}.h.ll")], wt, env))
            print(lab, {k: [r["wall_s"] for r in v] for k, v in res[lab].items()}, flush=True)
            json.dump({"labels": labels, "results": res}, open(out, "w"), indent=1)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()


if __name__ == "__main__":
    main()
