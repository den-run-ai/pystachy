"""Allocator and collector benchmark: time, peak RSS and page faults, variants interleaved.

Each variant is a compiler and the PYSTACHY_HOME whose runtime.c it builds programs with, optionally
with a preloaded C allocator (LD_PRELOAD) in place of the C library's malloc. Every round runs every
(workload, variant, tier) once, rotating the variants' order; outputs must agree across variants
and tiers. The program's own timer (a TIME line, or the workload's own report) excludes start-up
and compilation; wall time, CPU time, peak RSS (getrusage) and minor page faults are the process's.

  python3 -I bench/allocator/run.py --variant main=../main/pystachy:../main \\
      --variant proto=./pystachy:. --rounds 5 --cpu 3 --tiers aot,jit --json build/alloc.json

A variant `name=COMPILER[:HOME][+LIB]` preloads LIB (e.g. a libmimalloc.so) into the program, and
then reuses the AOT build of the variant before it with the same compiler and home. --names takes
microGPT's names.txt (bench/microgpt/README.md) for a 150-step training run; without it microGPT
is skipped. Results are advisory: shared hosts are noisy, and no threshold applies.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TIME = r"^TIME (\S+)"
# name, source, arguments, extra environment, timer regex, stdout lines kept for the output check
WORKLOADS = [
    ("nodes", f"{HERE}/nodes.py", ["200"], {}, TIME, None),
    ("vectors", f"{HERE}/vectors.py", ["3000000"], {}, TIME, None),
    ("slice20k", f"{HERE}/slice_tail.py", ["20000", "2000000000"], {}, TIME, None),
    ("slice4k", f"{HERE}/slice_tail.py", ["4000", "1000000000"], {}, TIME, None),
    ("chevron", f"{HERE}/chevron.py", ["slice", "400", "1400"], {}, TIME, None),
    ("peak", f"{HERE}/peak.py", ["400", "4000000"], {}, TIME, None),
    ("strbuild", f"{HERE}/strbuild.py", ["20000"], {}, TIME, None),
    ("lists", f"{HERE}/lists.py", ["3000"], {}, TIME, None),
    ("json_repair", f"{ROOT}/bench/json_repair/bench.py", ["2000"], {"PYSTACHY_PATH": f"{ROOT}/ports"},
     r"^seconds (\S+)", ["outputs", "per_round", "records", "checksum"]),
    ("words", f"{ROOT}/bench/words.py", [], {}, None, None),
    ("dictcount", f"{ROOT}/bench/dictcount.py", [], {}, None, None),
    ("dynany_graph", f"{ROOT}/tools/dynany_bench.py", ["graph-smoke", "3000"], {}, r"^seconds (\S+)", None),
]


def microgpt(names: str, work: str) -> tuple:
    # bench/microgpt/microgpt.py for 150 of its 1000 steps, timed from the first step to inference
    src = open(f"{ROOT}/bench/microgpt/microgpt.py", encoding="utf-8").read()
    head = "num_steps = 1000 # number of training steps\n"
    loop = "for step in range(num_steps):\n"
    infer = 'print("\\n--- inference (new, hallucinated names) ---")\n'
    if src.count(head) != 1 or src.count(loop) != 1 or src.count(infer) != 1:
        raise SystemExit("bench/microgpt/microgpt.py changed: update bench/allocator/run.py's microgpt()")
    src = src.replace(head, head + "import sys as _sys, time as _time\n_t0 = _time.perf_counter()\n")
    src = src.replace(loop, "for step in range(150):\n")
    src = src.replace(infer, 'print("TIME", _time.perf_counter() - _t0, file=_sys.stderr)\n' + infer)
    os.makedirs(work, exist_ok=True)
    with open(f"{work}/microgpt150.py", "w", encoding="utf-8") as f:
        f.write(src)
    with open(names, "rb") as f, open(f"{work}/input.txt", "wb") as g:
        g.write(f.read())
    return ("microgpt150", f"{work}/microgpt150.py", [], {}, TIME, None)


def run(argv: list[str], env: dict[str, str], cwd: str, timer: str | None, keep: list[str] | None) -> dict:
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        t0 = time.perf_counter()
        p = subprocess.Popen(argv, env=env, cwd=cwd, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
        _, status, ru = os.wait4(p.pid, 0)
        wall = time.perf_counter() - t0
        out.seek(0)
        err.seek(0)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
    prog = None
    kept = []
    for line in (o + "\n" + e).splitlines():
        m = re.match(timer, line) if timer else None
        if m:
            prog = float(m.group(1))
    for line in o.splitlines():
        if timer and re.match(timer, line):
            continue
        if keep is None or any(line.startswith(k) for k in keep):
            kept.append(line)
    return {"rc": os.waitstatus_to_exitcode(status), "wall": wall, "cpu": ru.ru_utime + ru.ru_stime,
            "maxrss_kib": ru.ru_maxrss, "minflt": ru.ru_minflt, "prog": prog,
            "out": hashlib.sha256("\n".join(kept).encode()).hexdigest()[:16],
            "gc": [line for line in e.splitlines() if line.startswith("gc:")], "stderr_tail": e[-300:]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", action="append", required=True, help="NAME=COMPILER[:HOME][+LIB]")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--cpu", help="pin the programs to this CPU (taskset -c)")
    ap.add_argument("--tiers", default="aot", help="aot, jit or aot,jit")
    ap.add_argument("--only", help="comma-separated workload names")
    ap.add_argument("--names", help="microGPT's names.txt, for its 150-step workload")
    ap.add_argument("--json", help="write every run here")
    a = ap.parse_args()
    work = tempfile.mkdtemp(prefix="pystachy-alloc.")
    loads = list(WORKLOADS) + ([microgpt(a.names, f"{work}/microgpt")] if a.names else [])
    if a.only:
        loads = [w for w in loads if w[0] in a.only.split(",")]
    variants = []
    for spec in a.variant:
        name, rest = spec.split("=", 1)
        rest, _, lib = rest.partition("+")
        comp, _, home = rest.partition(":")
        variants.append({"name": name, "compiler": comp, "home": os.path.abspath(home or ROOT), "preload": lib})
    tiers = a.tiers.split(",")
    pin = ["taskset", "-c", a.cpu] if a.cpu else []
    # the variants' settings only, but the LLVM that the user chose (as tests/verify.sh keeps it)
    base = {k: v for k, v in os.environ.items() if (k == "PYSTACHY_LLVM" or not k.startswith("PYSTACHY_")) and k != "LD_PRELOAD"}
    exes: dict[tuple[str, str], str] = {}
    for v in variants:
        same = [u for u in variants if u is not v and u["compiler"] == v["compiler"] and u["home"] == v["home"]
                and (u["name"], loads[0][0]) in exes] if loads else []
        for w in loads:
            if "aot" not in tiers:
                break
            if same:
                exes[(v["name"], w[0])] = exes[(same[0]["name"], w[0])]
                continue
            exe = f"{work}/{v['name']}-{w[0]}"
            env = dict(base, PYSTACHY_HOME=v["home"], **w[3])
            r = subprocess.run(shlex.split(v["compiler"]) + ["build", w[1], "-o", exe], env=env,
                               cwd=os.path.dirname(w[1]), capture_output=True, text=True)
            if r.returncode:
                raise SystemExit(f"{v['name']}: cannot build {w[0]}:\n{r.stderr[-2000:]}")
            exes[(v["name"], w[0])] = exe
    results = []
    for rnd in range(a.rounds):
        order = variants[rnd % len(variants):] + variants[:rnd % len(variants)]
        for w in loads:
            for v in order:
                for tier in tiers:
                    env = dict(base, PYSTACHY_HOME=v["home"], **w[3])
                    if v["preload"]:
                        env["LD_PRELOAD"] = v["preload"]
                    if tier == "aot":
                        argv = pin + [exes[(v["name"], w[0])]] + w[2]
                    else:
                        argv = pin + shlex.split(v["compiler"]) + ["run", w[1]] + w[2]
                    r = run(argv, env, os.path.dirname(w[1]), w[4], w[5])
                    r.update({"round": rnd, "variant": v["name"], "tier": tier, "workload": w[0]})
                    results.append(r)
                    print(f"round {rnd} {w[0]} {v['name']} {tier}: rc {r['rc']}, {r['prog'] or r['wall']:.3f} s,"
                          f" {r['maxrss_kib'] / 1024:.1f} MiB", file=sys.stderr, flush=True)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"variants": variants, "tiers": tiers, "rounds": a.rounds, "cpu": a.cpu,
                       "workloads": [w[:4] for w in loads], "results": results}, f, indent=1)
    rows: dict[tuple[str, str, str], list[dict]] = {}
    for r in results:
        rows.setdefault((r["workload"], r["tier"], r["variant"]), []).append(r)
    first: dict[str, str] = {}
    print(f"{'workload':13} {'tier':4} {'variant':12} {'program_s':>9} {'wall_s':>7} {'rss_MiB':>8} {'faults':>8}  check")
    for (w, t, v), rs in rows.items():
        outs = {r["out"] for r in rs}
        first.setdefault(w, min(outs))
        ok = all(r["rc"] == 0 for r in rs) and outs == {first[w]}
        med = statistics.median
        progs = [r["prog"] for r in rs if r["prog"] is not None]
        print(f"{w:13} {t:4} {v:12} {med(progs) if progs else float('nan'):9.3f} {med([r['wall'] for r in rs]):7.3f}"
              f" {med([r['maxrss_kib'] for r in rs]) / 1024:8.1f} {med([r['minflt'] for r in rs]):8.0f}  {'ok' if ok else 'DIFFERS'}")


main()
