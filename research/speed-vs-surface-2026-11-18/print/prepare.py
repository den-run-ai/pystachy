"""Collect every figure the print report uses into print/data.json.

usage: python3 prepare.py
Reads the regenerated datasets (data/, export/data/perf_index.csv), the per-commit build records,
the blocker groups and census at the latest commit, and the float/words re-timing.
All samples, including main 8434a911 and the commits after it, were timed in one run.
"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
V = S / "v2"
sys.path.insert(0, str(V / "scripts"))
from classify import category  # noqa: E402

REPORT, HEAD = "1111-1943_8434a911", None  # REPORT: the last commit the 12 November report measured

samples = sorted(json.load(open(V / "data/samples.json")), key=lambda r: r["date"])
HEAD = samples[-1]["label"]
pidx = {r["label"]: r for r in csv.DictReader(open(V / "export/data/perf_index.csv"))}
speed = json.load(open(V / "data/speedups.json"))
core = sorted({r["benchmark"] for r in speed if r["core"] and r["kind"] != "micro"})
micro = sorted({r["benchmark"] for r in speed if r["kind"] == "micro"})


def build(label):
    return json.load(open(S / f"results/build-{label}.json"))


rows = []
for s in samples:
    p = pidx[s["label"]]
    rows.append({
        "label": s["label"], "sha": s["sha"][:8], "date": s["date"], "release": s["release"] or "",
        "methods": s["methods_pass"], "language": s["pass_language"], "library": s["pass_library"],
        "differs": s["compiled_but_differs"],
        "ports": s["ports_working"], "upstream": s["upstream_compiled"],
        "core": float(p["core_index"]) if p["core_index"] else None,
        "micro": float(p["micro_index"]) if p["micro_index"] else None,
        "nbody_build": s["aot_build_nbody_s"], "richards_build": s["aot_build_richards_s"],
        "raytrace_build": s["aot_build_raytrace_s"], "jit_micro": s["jit_micro_median_s"],
        "bootstrap": round(build(s["label"])["build_s"], 1), "ir": s["compiler_ir_lines"],
        "compiler_lines": s["compiler_lines"], "library_lines": s["library_lines"], "runtime_lines": s["runtime_lines"],
        "lang_blocked": {k: s[f"lang_blocked_{k}"] for k in ("library", "syntax", "typing", "dynamic", "other")},
        "blocked": {k: s[f"blocked_{k}"] for k in ("library", "syntax", "typing", "dynamic", "other")},
    })


def groups_file(path):
    out = []
    for line in open(path):
        g = re.match(r"(\w+)\s+(\d+)\s+language\s+(\d+)\s+files\s+(\d+)\s+(.*)$", line.rstrip())
        if g:
            out.append({"need": g[1], "methods": int(g[2]), "language": int(g[3]), "files": int(g[4]), "name": g[5]})
    return out


census = json.load(open(S / f"results/census-{HEAD}.json"))
cens = collections.defaultdict(list)
for name, v in census.items():
    if v["status"] != "compiled":
        cens[category(v["first_error"])].append(name)

speed_rows = [{"label": r["label"], "benchmark": r["benchmark"], "kind": r["kind"], "speedup": r["speedup"]} for r in speed]
retime = {}
for b in ("float", "micro_words"):
    f = V / f"raw/retime-{b}.json"
    if f.exists():
        retime[b] = json.load(open(f))["results"]

def print_change(c):
    """A changes.json row as the print table shows it: interval, time, cause, evidence."""
    import datetime as dt
    d0, d1 = (dt.date.fromisoformat(c[k]) for k in ("from_date", "to_date"))
    interval = f"{d1.day} {d1:%b}" if d0 == d1 else (f"{d0.day}–{d1.day} {d1:%b}" if d0.month == d1.month
                                                        else f"{d0.day} {d0:%b}–{d1.day} {d1:%b}")
    f = (lambda v: f"{v:,.0f}") if max(c["before_ms"], c["after_ms"]) >= 100 else (lambda v: f"{v:.1f}")
    cause = c["change"].split(": ", 1)[-1]
    for w in ("lib/re", "startswith/endswith"):
        cause = cause.replace(w, f"<code>{w}</code>")
    name = c["benchmark"].replace("micro_", "") + (" (micro)" if c["benchmark"].startswith("micro_") else "")
    return {"benchmark": name, "interval": interval, "time": f"{f(c['before_ms'])} → {f(c['after_ms'])}",
            "cause": cause[0].upper() + cause[1:], "evidence": c["evidence"][0].upper() + c["evidence"][1:]}


data = {"samples": rows, "speedups": speed_rows, "core": core, "micro": micro, "report_label": REPORT, "head_label": HEAD,
        "changes": [print_change(c) for c in json.load(open(V / "data/changes.json"))],
        "groups": groups_file(V / f"raw/groups-{HEAD[-8:]}.txt"),
        "groups_report": groups_file(V / f"raw/groups-{REPORT[-8:]}.txt"),
        "census_head": dict(cens), "retime": retime,
        "progress": json.load(open(V / "raw/progress-report-to-head.json")),
        "change_shares": json.load(open(V / "raw/change_shares.json"))}
json.dump(data, open(V / "print/data.json", "w"), indent=1, default=float)
head, rep = rows[-1], next(r for r in rows if r["label"] == REPORT)
print("head", {k: head[k] for k in ("label", "methods", "language", "library", "ports", "upstream", "core", "micro",
                                     "nbody_build", "bootstrap", "jit_micro")})
print("report", {k: rep[k] for k in ("label", "methods", "language", "library", "ports", "upstream", "core", "micro",
                                      "nbody_build", "bootstrap", "jit_micro")})
print("census head", {k: len(v) for k, v in cens.items()})
