"""Interleaved self-compilation cost: wall time and peak RSS of `COMPILER ir pystachy.py`.

usage: python3 -I cost.py REPO OUTDIR SAMPLES CPU NAME=COMPILER...

Each round runs every compiler once, rotating the order, pinned to one CPU with taskset.
Peak RSS is the child's ru_maxrss from wait4 (KiB). Every output must be byte-identical.
"""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time


def one(repo, compiler, out, cpu):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = ""
    start = time.perf_counter()
    proc = subprocess.Popen(["taskset", "-c", str(cpu), compiler, "ir", "pystachy.py", "-o", str(out)],
                            cwd=repo, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    _, status, usage = os.wait4(proc.pid, 0)
    elapsed = time.perf_counter() - start
    proc.returncode = os.waitstatus_to_exitcode(status)
    stderr = proc.stderr.read().decode(errors="replace")
    if proc.returncode != 0:
        raise SystemExit(f"{compiler} failed: {stderr}")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    return elapsed, usage.ru_maxrss, usage.ru_utime + usage.ru_stime, digest


def main():
    repo, outdir, samples, cpu = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    compilers = [arg.split("=", 1) for arg in sys.argv[5:]]
    outdir.mkdir(parents=True, exist_ok=True)
    records = {name: [] for name, _ in compilers}
    digests = set()
    for _ in range(1):  # one untimed warm-up each (page cache)
        for name, compiler in compilers:
            one(repo, str(Path(compiler).resolve()), outdir / f"{name}.ll", cpu)
    for i in range(samples):
        order = compilers if i % 2 == 0 else list(reversed(compilers))
        for name, compiler in order:
            wall, rss, cpu_s, digest = one(repo, str(Path(compiler).resolve()), outdir / f"{name}.ll", cpu)
            records[name].append({"wall": wall, "rss_kib": rss, "cpu": cpu_s})
            digests.add(digest)
    summary = {}
    for name, compiler in compilers:
        r = records[name]
        summary[name] = {
            "compiler": compiler, "size_bytes": Path(compiler).stat().st_size, "samples": len(r),
            "wall_median": statistics.median(x["wall"] for x in r),
            "wall_min": min(x["wall"] for x in r), "wall_max": max(x["wall"] for x in r),
            "cpu_median": statistics.median(x["cpu"] for x in r),
            "rss_median_kib": statistics.median(x["rss_kib"] for x in r),
            "rss_min_kib": min(x["rss_kib"] for x in r), "rss_max_kib": max(x["rss_kib"] for x in r),
        }
    result = {"samples_per_compiler": samples, "cpu": cpu, "identical_ir": len(digests) == 1,
              "ir_sha256": sorted(digests), "summary": summary, "records": records,
              "loadavg_after": os.getloadavg()}
    (outdir / "cost.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=1))


if __name__ == "__main__":
    main()
