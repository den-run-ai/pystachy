"""Collect every figure the print report uses into print/data.json (history sweep + main follow-up).

usage: python3 prepare.py
"""
import csv, gzip, json, re, statistics, sys
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
R = Path("/home/user/pystachy/research/speed-vs-surface-2026-11-12")
sys.path.insert(0, str(S / "sweep"))
from classify import category, group  # noqa: E402

MAIN, A5 = "1111-1943_8434a911", "1111-1528_b2182a4f"
specs = json.load(open(S / "sweep/perf_specs.json"))


def summarize(timing):
    """Medians per benchmark and label, as report.py computes them."""
    t = json.load(open(timing))
    out = {"aot": {}, "jit": {}, "build": {}}
    for name, rows in t["aot"].items():
        key = "loop" if specs[name]["kind"] == "pyperformance" else "wall"
        for lab, recs in rows.items():
            vals = [r[key] for r in recs if r.get("ok") and r.get(key) is not None]
            out["aot"].setdefault(name, {})[lab] = statistics.median(vals) if vals else None
    for name, rows in t.get("jit", {}).items():
        for lab, recs in rows.items():
            vals = [r["wall"] for r in recs if r.get("ok")]
            out["jit"].setdefault(name, {})[lab] = statistics.median(vals) if vals else None
    for name, rows in t.get("build", {}).items():
        for lab, recs in rows.items():
            vals = [r["wall"] for r in recs if r.get("ok")]
            out["build"].setdefault(name, {})[lab] = statistics.median(vals) if vals else None
    return out


def geomean(xs):
    xs = [x for x in xs if x]
    return statistics.geometric_mean(xs) if xs else None


samples = json.load(open(R / "data/samples.json"))
pidx = {r["label"]: r for r in csv.DictReader(open(R / "export/data/perf_index.csv"))}
builds = {b["label"]: b for b in json.load(open(R / "raw/builds.json"))}
speed = json.load(open(R / "data/speedups.json"))
core = sorted({r["benchmark"] for r in speed if r["core"] and r["kind"] != "micro"})
micro = sorted({r["benchmark"] for r in speed if r["kind"] == "micro"})

rows = []
for s in samples:
    p = pidx[s["label"]]
    rows.append({
        "label": s["label"], "sha": s["sha"][:8], "date": s["date"], "release": s["release"] or "",
        "methods": s["methods_pass"], "language": s["pass_language"], "library": s["pass_library"],
        "ports": s["ports_working"], "upstream": s["upstream_compiled"],
        "core": float(p["core_index"]) if p["core_index"] else None,
        "micro": float(p["micro_index"]) if p["micro_index"] else None,
        "nbody_build": s["aot_build_nbody_s"], "richards_build": s["aot_build_richards_s"],
        "raytrace_build": s["aot_build_raytrace_s"], "jit_micro": s["jit_micro_median_s"],
        "bootstrap": round(builds[s["label"]]["build_s"], 1), "ir": s["compiler_ir_lines"],
        "compiler_lines": s["compiler_lines"], "library_lines": s["library_lines"], "runtime_lines": s["runtime_lines"],
        "lang_blocked": {k: s[f"lang_blocked_{k}"] for k in ("library", "syntax", "typing", "dynamic", "other")},
    })

# Main: surface from the follow-up sweep; speed, build and JIT from a run timing alpha.5 and main together.
m = json.load(open(S / f"results/methods-{MAIN}.json"))["records"]
P = ("match", "match-python-int")
tm = summarize(S / "results/timing-main.json")
cpy = {b: v.get("cpython") for b, v in tm["aot"].items()}
main_speed, a5_again = {}, {}
for b, v in tm["aot"].items():
    if b == "unpack_sequence" or not cpy[b]:
        continue
    if v.get(MAIN):
        main_speed[b] = cpy[b] / v[MAIN]
    if v.get(A5):
        a5_again[b] = cpy[b] / v[A5]
prep = json.load(open(S / f"results/perfprep-{MAIN}.json"))
jit_micro = sorted(tm["jit"][b][MAIN] for b in micro if tm["jit"].get(b, {}).get(MAIN))
main_row = {
    "label": MAIN, "sha": "8434a911", "date": "2026-11-12T03:43:30Z", "release": "main",
    "methods": sum(r["status"] in P for r in m),
    "language": sum(r["status"] in P and group(r["file"]) == "language" for r in m),
    "library": sum(r["status"] in P and group(r["file"]) != "language" for r in m),
    "ports": sum(1 for b, r in prep.items() if r.get("aot_correct") and not b.startswith("micro_")),
    "upstream": sum(1 for v in json.load(open(S / f"results/census-{MAIN}.json")).values() if v["status"] == "compiled"),
    "core": geomean([main_speed.get(b) for b in core]), "micro": geomean([main_speed.get(b) for b in micro]),
    "nbody_build": tm["build"]["micro_nbody"].get(MAIN), "richards_build": tm["build"]["richards"].get(MAIN),
    "raytrace_build": tm["build"]["raytrace"].get(MAIN), "jit_micro": jit_micro[len(jit_micro) // 2],
    "bootstrap": 239.1, "ir": 912733, "compiler_lines": 66836, "library_lines": 55378, "runtime_lines": 14800,
    "lang_blocked": dict(__import__("collections").Counter(
        category(r.get("detail", "")) for r in m if r["status"] == "compile-error" and group(r["file"]) == "language")),
}
rows.append(main_row)
a5 = next(r for r in rows if r["label"] == A5)
check = {"a5_core_original": a5["core"], "a5_core_again": geomean([a5_again.get(b) for b in core]),
         "a5_micro_original": a5["micro"], "a5_micro_again": geomean([a5_again.get(b) for b in micro]),
         "a5_build_again": {k: tm["build"][k].get(A5) for k in tm["build"]}}

speed_rows = [{"label": r["label"], "benchmark": r["benchmark"], "kind": r["kind"], "speedup": r["speedup"]} for r in speed]
speed_rows += [{"label": MAIN, "benchmark": b, "kind": specs[b]["kind"] if specs[b]["kind"] == "micro" else "port",
                "speedup": round(v, 4)} for b, v in main_speed.items()]

groups = []
for line in open(R / "followup/raw/groups-8434a911.txt"):
    g = re.match(r"(\w+)\s+(\d+)\s+language\s+(\d+)\s+files\s+(\d+)\s+(.*)$", line.rstrip())
    if g:
        groups.append({"need": g[1], "methods": int(g[2]), "language": int(g[3]), "files": int(g[4]), "name": g[5]})

census = json.load(open(S / f"results/census-{MAIN}.json"))
cens = {}
for name, v in census.items():
    if v["status"] != "compiled":
        cens.setdefault(category(v["first_error"]), []).append(name)

data = {"samples": rows, "speedups": speed_rows, "core": core, "micro": micro, "check": check,
        "changes": json.load(open(R / "data/changes.json")), "groups": groups, "census_main": cens,
        "retime": {b: json.load(open(R / f"followup/raw/retime-{b}.json"))["results"] for b in ("float", "words")}}
json.dump(data, open(S / "print/data.json", "w"), indent=1, default=float)
print("main", {k: main_row[k] for k in ("methods", "language", "library", "ports", "upstream", "core", "micro",
                                         "nbody_build", "richards_build", "raytrace_build", "jit_micro")})
print("check", check)
print("census main", {k: len(v) for k, v in cens.items()})
