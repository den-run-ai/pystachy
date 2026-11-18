"""Summary statistics for the write-up, from the page datasets.

usage: python3 analysis.py DATADIR
"""
import collections
import datetime
import json
import math
import sys
from pathlib import Path


def d(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else float("nan")


def main():
    D = Path(sys.argv[1])
    samples = sorted(json.load(open(D / "samples.json")), key=lambda r: r["date"])
    speed = json.load(open(D / "speedups.json"))
    unl = sorted(json.load(open(D / "unlocks.json")), key=lambda r: r["date"])
    hist = sorted(json.load(open(D / "history.json")), key=lambda r: r["date"])

    core = sorted({r["benchmark"] for r in speed if r["kind"] == "pyperformance" and r["core"]})
    micro = sorted({r["benchmark"] for r in speed if r["kind"] == "micro"})
    by = collections.defaultdict(dict)
    for r in speed:
        by[r["label"]][r["benchmark"]] = r["speedup"]
    print(f"core set ({len(core)}): {core}")
    print("\nlabel               date        rel            pass  lang  lib  ports up52 |  micro   core  | work-bound design-bound (language tests) | compiler lib runtime  jit")
    for s in samples:
        b = by.get(s["label"], {})
        mi = geomean([b[x] for x in micro]) if all(x in b for x in micro) else float("nan")
        co = geomean([b[x] for x in core]) if all(x in b for x in core) else float("nan")
        lt = s["language_total"]
        work = s["lang_blocked_library"] + s["lang_blocked_syntax"]
        design = s["lang_blocked_typing"] + s["lang_blocked_dynamic"]
        print(f"{s['label']:19s} {s['date'][:10]} {s['release'][:14]:14s} {s['methods_pass']:5d} {s['pass_language']:5d} {s['pass_library']:4d} "
              f"{s['ports_working']:5d} {s['upstream_compiled']:4d} | {mi:6.2f} {co:6.2f} | {work / lt:6.1%} {design / lt:6.1%}          | "
              f"{s['compiler_lines']:6d} {s['library_lines']:5d} {s['runtime_lines']:5d} {s['jit_micro_median_s'] or 0:5.2f}")

    print("\nweekly growth (methods passing, by sample nearest each boundary)")
    t0 = d(samples[0]["date"])
    weeks = collections.OrderedDict()
    for s in samples:
        w = int((d(s["date"]) - t0).days // 7)
        weeks.setdefault(w, []).append(s)
    prev = samples[0]
    for w, ss in weeks.items():
        last = ss[-1]
        days = max(1e-9, (d(last["date"]) - d(prev["date"])).total_seconds() / 86400)
        dl = (last["compiler_lines"] + last["library_lines"] + last["runtime_lines"]) - (prev["compiler_lines"] + prev["library_lines"] + prev["runtime_lines"])
        dm = last["methods_pass"] - prev["methods_pass"]
        print(f"  week {w + 1}: {prev['date'][:10]} -> {last['date'][:10]}: +{dm} methods (+{last['pass_language'] - prev['pass_language']} language, "
              f"+{last['pass_library'] - prev['pass_library']} library), {dm / days:.1f}/day; +{dl} source lines; "
              f"{dm / max(1, dl) * 1000:.1f} methods per 1k lines")
        prev = last

    print("\nnewly passing methods by previous blocker, per week")
    for w, ss in weeks.items():
        labs = {s["label"] for s in ss}
        rows = [u for u in unl if u["label"] in labs]
        tot = collections.Counter()
        for u in rows:
            for k in ("library", "syntax", "typing", "dynamic", "other"):
                tot[k] += u["from_" + k]
        n = sum(tot.values())
        lost = sum(u["lost"] for u in rows)
        print(f"  week {w + 1}: gained {n}, lost {lost}: " + ", ".join(f"{k} {v} ({v / n:.0%})" if n else f"{k} 0" for k, v in tot.items()))

    first, last = hist[0], hist[-1]
    print(f"\nsource lines: compiler {first['compiler_lines']} -> {last['compiler_lines']}, library {first['library_lines']} -> {last['library_lines']}, "
          f"runtime {first['runtime_lines']} -> {last['runtime_lines']}; corpus programs {first['corpus_programs']} -> {last['corpus_programs']}, "
          f"rejection cases {first['corpus_rejections']} -> {last['corpus_rejections']}")

    print("\nper-benchmark change, first sample where it works -> last sample")
    labels = [s["label"] for s in samples]
    for bname in sorted({r["benchmark"] for r in speed}):
        pts = [(lab, by[lab][bname]) for lab in labels if bname in by.get(lab, {})]
        if len(pts) >= 2:
            (l0, v0), (l1, v1) = pts[0], pts[-1]
            print(f"  {bname:18s} {v0:7.2f}x ({l0[:9]}) -> {v1:7.2f}x ({l1[:9]})  {v1 / v0 - 1:+7.1%}  min {min(v for _, v in pts):.2f} max {max(v for _, v in pts):.2f}")


if __name__ == "__main__":
    main()
