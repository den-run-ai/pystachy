"""Print the figures the write-up quotes, from the regenerated datasets (no measurement).

usage: python3 figures.py DATADIR
"""
import collections
import csv
import json
import math
import statistics
import sys
from pathlib import Path

D = Path(sys.argv[1])
samples = sorted(json.load(open(D / "samples.json")), key=lambda r: r["date"])
speed = json.load(open(D / "speedups.json"))
idx = {r["label"]: r for r in csv.DictReader(open(D.parent / "export/data/perf_index.csv"))}
by = collections.defaultdict(dict)
for r in speed:
    by[r["label"]][r["benchmark"]] = r
L = {s["label"]: s for s in samples}
key = {"first": samples[0]["label"], "a2": next(s["label"] for s in samples if s["release"] == "v0.1.0-alpha.2"),
       "a5": "1111-1528_b2182a4f", "rep": "1111-1943_8434a911", "rc1": "1112-1351_30822255",
       "a1_50": "1114-0748_a73c56c9", "a2_50": "1114-1000_80490143", "v50": "1116-2350_d58034c1",
       "71e1": "1117-0158_71e14a88", "prev": "1117-1034_3cf23d20", "a2_60": "1117-2325_e2b97bb4",
       "a3_60": "1118-1050_8259611e", "v60": "1119-2044_817c9cd9", "a1_70": "1120-1407_41dffd36",
       "head": samples[-1]["label"]}
print("indices (core, micro) and builds:")
for k, lab in key.items():
    s = L[lab]
    print(f"  {k:6s} {lab:20s} core {idx[lab]['core_index'] or '-':>7s} micro {idx[lab]['micro_index'] or '-':>7s} "
          f"nbody {s['aot_build_nbody_s']} richards {s['aot_build_richards_s']} raytrace {s['aot_build_raytrace_s']} "
          f"jit {s['jit_micro_median_s']} jit_richards {s['jit_richards_s']}")
core = [float(idx[s["label"]]["core_index"]) for s in samples if idx[s["label"]]["core_index"]]
micro = [float(idx[s["label"]]["micro_index"]) for s in samples if idx[s["label"]]["micro_index"]]
print(f"core range {min(core):.2f}-{max(core):.2f}; micro range {min(micro):.2f}-{max(micro):.2f}")
after = [s for s in samples if s["date"] >= L["1020-1311_afb59cd3"]["date"]]
ca = [float(idx[s["label"]]["core_index"]) for s in after]
print(f"core after alpha.2: {min(ca):.2f}-{max(ca):.2f}")
new = [s for s in samples if s["date"] > L[key["rep"]]["date"]]
print("new samples core:", [round(float(idx[s['label']]['core_index']), 2) for s in new])
print("new samples micro:", [round(float(idx[s['label']]['micro_index']), 2) for s in new])

print("\nper benchmark speedup: first-working, a5, rep, rc1, a2_50, prev, head; change prev->head")
for b in sorted({r["benchmark"] for r in speed}):
    def sp(lab):
        r = by[lab].get(b)
        return r["speedup"] if r else None
    pts = [(s["label"], by[s["label"]][b]["speedup"]) for s in samples if b in by[s["label"]]]
    v = [sp(key[k]) for k in ("a5", "rep", "rc1", "a2_50", "prev", "head")]
    ch = v[5] / v[4] - 1 if v[4] and v[5] else float("nan")
    f = lambda x: f"{x:7.2f}" if x else "     - "
    print(f"  {b:16s} first {pts[0][1]:7.2f} ({pts[0][0][:9]})  a5 {f(v[0])} rep {f(v[1])} rc1 {f(v[2])} a2_50 {f(v[3])} "
          f"prev {f(v[4])} head {f(v[5])}  prev->head {ch:+.1%}")

print("\nbootstrap and IR:")
for s in samples[-10:]:
    print(f"  {s['label']:20s} {s['release'] or '':16s} ir {s['compiler_ir_lines']} lines {s['compiler_lines']} "
          f"methods {s['methods_pass']} lang {s['pass_language']}")
