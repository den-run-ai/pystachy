"""Largest speed changes between consecutive sampled commits, with their causes (data/changes.json).

usage: python3 changes.py DATADIR
Times come from data/speedups.json (the one timing run). Causes are curated: bisected in the first
edition, or the merges the interval contains. #1332's effect on words (-4% in a 15-run re-timing) is
within this run's noise, so it is reported with the re-timing, not here. Also prints every change of 15% or more between
consecutive samples after 11 November, so new ones are not missed.
"""
import collections
import json
import sys
from pathlib import Path

D = Path(sys.argv[1])
speed = json.load(open(D / "speedups.json"))
samples = sorted(json.load(open(D / "samples.json")), key=lambda r: r["date"])
labels = [s["label"] for s in samples]
t = collections.defaultdict(dict)
for r in speed:
    t[r["benchmark"]][r["label"]] = r["aot_s"] * 1000

# (benchmark, from label, to label, cause, evidence)
CURATED = [
    ("regex_dna", "1018-1740_bb5ac4ab", "1019-2327_b040f45e",
     "Faster: lib/re matcher work (#676, #680, #682, #683, #685)", "32 merges; not bisected"),
    ("regex_effbot", "1018-1740_bb5ac4ab", "1019-2327_b040f45e", "Faster: same lib/re work", "same interval"),
    ("regex_v8", "1018-1740_bb5ac4ab", "1019-2327_b040f45e", "Faster: same lib/re work", "same interval"),
    ("scimark", "1018-1740_bb5ac4ab", "1019-2327_b040f45e",
     "Faster: likely field TBAA (#724) or tuple returns by value (#727)", "same interval"),
    ("barnes_hut", "1018-1740_bb5ac4ab", "1019-2327_b040f45e",
     "Faster: likely the same two changes", "same interval"),
    ("micro_words", "1017-1821_63977813", "1018-1740_bb5ac4ab",
     "Slower: Unicode code-point strings, stage 1 (#667)", "bisected to a355c83f"),
    ("float", "1110-2331_d02995cb", "1111-1528_b2182a4f",
     "Slower: listguard bounds-check hoisting with Lean checks (#1268)", "bisected to b40ee875"),
    ("float", "1112-0850_0b13a212", "1112-1351_30822255",
     "Faster: listguard keeps sole calls inlinable in loop copies (#1336)", "#1389, v0.4.0-rc.1; closes #1300"),
]
rows = []
for b, f, to, cause, evidence in CURATED:
    before, after = t[b].get(f), t[b].get(to)
    if before is None or after is None:
        print("missing", b, f, to)
        continue
    day = lambda lab: next(s["date"][:10] for s in samples if s["label"] == lab)
    rows.append({"benchmark": b, "from_date": day(f), "to_date": day(to), "before_ms": round(before, 1),
                 "after_ms": round(after, 1), "time_ratio": round(after / before, 3), "change": cause, "evidence": evidence})
rows.sort(key=lambda r: (r["from_date"], r["time_ratio"]))
for i, r in enumerate(rows):
    rows_i = {"rank": i + 1}
    rows_i.update(r)
    rows[i] = rows_i
json.dump(rows, open(D / "changes.json", "w"), indent=0)
for r in rows:
    print(f"{r['benchmark']:14s} {r['from_date']} -> {r['to_date']}  {r['before_ms']:8.1f} -> {r['after_ms']:8.1f} ms  x{r['time_ratio']}")

print("\nchanges of 15% or more between consecutive samples after 11 November:")
start = labels.index("1111-1528_b2182a4f")
for a, b in zip(labels[start:], labels[start + 1:]):
    for bench, v in sorted(t.items()):
        if a in v and b in v and (v[b] / v[a] > 1.15 or v[b] / v[a] < 1 / 1.15):
            print(f"  {bench:16s} {a} -> {b}: {v[a]:.1f} -> {v[b]:.1f} ms (x{v[b] / v[a]:.2f})")
