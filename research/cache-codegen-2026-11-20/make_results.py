"""Write the PR's bench/results JSON from the raw measurement files.
usage: make_results.py OUT.json"""
import json
import math
import statistics
import sys

SP = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad"
W = f"{SP}/cgap"


def table(path, first, other, codegen=False):
    runs = json.load(open(path))["runs"]
    progs = sorted({k.split("|")[0] for k in runs})
    out, ratios_all = {}, []
    for p in progs:
        base, rows = runs.get(f"{p}|{first}"), runs.get(f"{p}|{other}")
        if not base or not rows:
            continue
        if codegen:
            metrics = ["jit_codegen"] if "jit_codegen" in base[0] and "jit_codegen" in rows[0] else []
        else:
            metrics = [m for m in ("knn", "layout") if m in base[0]] or (["seconds"] if "seconds" in base[0] else ["run"] if "run" in base[0] else ["wall"])
        for m in metrics:
            if m not in rows[0]:
                continue
            ratios = [a[m] / b[m] for a, b in zip(rows, base) if b[m] > 0]
            med = statistics.median(ratios)
            ratios_all.append(med)
            out[f"{p}.{m}"] = {first: round(statistics.median(r[m] for r in base), 4), other: round(statistics.median(r[m] for r in rows), 4),
                               "paired_ratio": round(med, 3), "ratio_range": [round(min(ratios), 3), round(max(ratios), 3)]}
    geo = math.exp(sum(map(math.log, ratios_all)) / len(ratios_all))
    return out, round(geo, 3), len(ratios_all)


result = {"notes": (
    "The JIT runner given clang's default CPU on x86-64 Linux (-mcpu=x86-64), as the program cache's clang compiles "
    "the same module; before, the runner, lli and llc named no CPU, which LLVM tunes as an i586, without the 64-bit "
    "division bypass (a 32-bit divide where both operands fit) that x86-64's generic tuning adds. Sapphire Rapids VM "
    "(Xeon 2.1 GHz), Ubuntu LLVM 18.1.3; every process pinned to CPU 1, compilers interleaved with rotating order, "
    "5 rounds; paired median ratios (this branch / main; below 1 is faster) with each round's range. main_runner: "
    "main d35417c96 against this branch, program cache off: UMAP probe stages (10,000 points, 16 dimensions, "
    "200 epochs), divmicro (floor division and modulo by run-time divisors, source below), bench/pyperformance at "
    "its measured sizes (the programs' own 'seconds'), bench/*.py ('run': wall time minus the driver's preparation, "
    "loading and code generation). codegen: the runner's program.jit_codegen. all_drafts: a scratch merge of main "
    "with the open performance drafts, where #1468 inlines the runtime's floor division and modulo into JIT code: "
    "the runner against the program cache's executable of the same program, before and after this change "
    "(PYSTACHY_JIT_CPU=generic, and the host's CPU with #1575 keeping the host's tuning). One executable's kNN stage "
    "ranged from 0.94 to 1.35 s over 12 runs on this VM: single-program differences of a few percent are noise.")}
main, geo, n = table(f"{W}/main-runner-ab.json", "main", "x86")
cg, cgeo, cn = table(f"{W}/main-runner-ab.json", "main", "x86", codegen=True)
result["main_runner"] = {"geomean_paired_ratio": geo, "timings": n, "programs": main}
result["codegen"] = {"geomean_paired_ratio": cgeo, "programs": cn, "umap": cg.get("umap.jit_codegen")}
try:
    result["all_drafts"] = json.load(open(f"{W}/all-drafts-summary.json"))
except OSError:
    pass
result["sources"] = {"divmicro": open(f"{W}/divmicro.py").read()}
json.dump(result, open(sys.argv[1], "w"), indent=1)
print("geomean", geo, "over", n, "codegen", cgeo)
