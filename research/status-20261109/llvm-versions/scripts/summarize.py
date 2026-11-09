"""Print compact median [min-max] tables (ms) from the vbench result files, with % vs LLVM 18."""
import glob
import json
import os
import sys

R = sys.argv[1]
V = ["18", "20", "22", "23"]


def cell(s, base=None):
    t = f"{s['median_ms']:.0f} [{s['min_ms']:.0f}-{s['max_ms']:.0f}]"
    if base:
        t += f" {100 * (s['median_ms'] / base['median_ms'] - 1):+.0f}%"
    return t


def load(pattern):
    out = {}
    for f in sorted(glob.glob(os.path.join(R, pattern))):
        out.update(json.load(open(f))["results"])
    return out


jit = load("jit-*.json")
if jit:
    print("## JIT, cold, program cache off (ms)")
    for mode in ("orc", "llc_O0_orc", "mcjit_O0"):
        print(f"### {mode}")
        print("| workload | " + " | ".join(V) + " |")
        for wl, r in jit.items():
            base = r.get(f"18/{mode}")
            print(f"| {wl} | " + " | ".join(cell(r[f'{n}/{mode}'], base if n != '18' else None) if f'{n}/{mode}' in r else '-' for n in V) + " |")
miss = load("miss-*.json")
if miss:
    print("## Program cache miss after an edit, then hit (ms)")
    print("| workload | " + " | ".join(f"miss {n}" for n in V) + " | " + " | ".join(f"hit {n}" for n in V) + " |")
    for wl, r in miss.items():
        print(f"| {wl} | " + " | ".join(cell(r['miss'][n], r['miss']['18'] if n != '18' else None) for n in V)
              + " | " + " | ".join(f"{r['hit'][n]['median_ms']:.0f}" for n in V) + " |")
aot = load("aot-*.json")
if aot:
    print("## AOT build (ms)")
    print("| workload | " + " | ".join(V) + " |")
    for wl, r in aot.items():
        print(f"| {wl} | " + " | ".join(cell(r[n], r['18'] if n != '18' else None) for n in V) + " |")
speed = load("speed-*.json")
if speed:
    print("## AOT executables: timed part (ms) and process wall (ms)")
    print("| benchmark | " + " | ".join(V) + " | wall 18 / 23 |")
    for b, r in speed.items():
        tp = r["timed_part"]
        print(f"| {b} | " + " | ".join(cell(tp[n], tp['18'] if n != '18' else None) for n in V)
              + f" | {r['wall']['18']['median_ms']:.0f} / {r['wall']['23']['median_ms']:.0f} |")
st = os.path.join(R, "stages.json")
if os.path.exists(st):
    s = json.load(open(st))["results"]
    print("## Stage medians (ms): JIT opt / lli after prepare; AOT optimize / codegen")
    for wl, r in s.items():
        row = []
        for n in V:
            j, a = r[f"jit/{n}"], r[f"aot/{n}"]
            opt = a.get("program.llvm_optimize", 0) + a.get("program.late_inline", 0)
            cg = a.get("program.codegen", a.get("program.optimize_codegen", 0))
            row.append(f"{n}: {j.get('program.jit_optimize', 0):.0f}/{j.get('lli_after_prepare', 0):.0f}; {opt:.0f}/{cg:.0f}")
        print(f"| {wl} | " + " | ".join(row) + " |")
sa = os.path.join(R, "selfaot.json")
if os.path.exists(sa):
    s = json.load(open(sa))["results"]
    print("## Self-build AOT stages (ms)")
    for n, runs in s.items():
        for x in runs:
            print(n, {k: v for k, v in x.items() if k.startswith("program.") or k == "wall"})
