"""Assemble per-commit results into one dataset for the charts.

usage: python3 report.py COMMITS.txt OUT.json [TIMING.json]
"""
import collections
import json
import math
import re
import statistics
import sys
from pathlib import Path

from classify import category, group, strip

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
SW = S / "sweep"
R = S / "results"
CATS = ["library", "syntax", "typing", "dynamic", "other"]


def load(path):
    return json.load(open(path)) if Path(path).exists() else None


def short(detail):
    """A first error without its file name, the long list of builtin modules, or per-test names."""
    s = strip(detail)
    s = re.sub(r" \((sys, os|available: ).*$", "", s)
    s = re.sub(r": Pystachy's ([a-z_]+) module has no '([A-Za-z_]+)'.*$", "", s)
    return s[:140]


def geomean(xs):
    xs = [x for x in xs if x and x > 0]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def main():
    commits_file, out = sys.argv[1:3]
    timing = load(sys.argv[3]) if len(sys.argv) > 3 else None
    samples = [line.split() for line in open(commits_file) if line.strip()]
    git = {row["sha"]: row for row in json.load(open(SW / "git_metrics.json"))}
    qualified = json.load(open(SW / "qualified.json"))
    qual = [r for r in qualified["records"] if r["cpython"] == "ok"]
    denom = collections.Counter(group(r["file"]) for r in qual)
    files = sorted({r["file"] for r in qual})
    per_file_total = collections.Counter(r["file"] for r in qual)
    specs = json.load(open(SW / "perf_specs.json"))
    ref = json.load(open(SW / "cpython_ref.json"))["ref"]

    # timing summaries: median per (benchmark, label); CPython medians as the baseline
    tsum = {}
    if timing:
        for name, rows in timing.get("aot", {}).items():
            key = "loop" if specs[name]["kind"] == "pyperformance" else "wall"
            tsum[name] = {}
            for lab, recs in rows.items():
                good = [r for r in recs if r.get("ok")]
                if not good:
                    continue
                vals = [r[key] for r in good if r.get(key) is not None]
                cpu = [r["cpu"] for r in good]
                walls = [r["wall"] for r in good]
                tsum[name][lab] = {"median": statistics.median(vals) if vals else None,
                                   "min": min(vals) if vals else None,
                                   "cpu_median": statistics.median(cpu), "wall_median": statistics.median(walls),
                                   "n": len(good),
                                   "spread": (max(vals) - min(vals)) / statistics.median(vals) if vals and statistics.median(vals) > 0 else None}
    jsum = {}
    if timing:
        for name, rows in timing.get("jit", {}).items():
            jsum[name] = {lab: statistics.median([r["wall"] for r in recs if r.get("ok")])
                          for lab, recs in rows.items() if any(r.get("ok") for r in recs)}

    bsum = {}
    if timing:
        for name, rows in timing.get("build", {}).items():
            bsum[name] = {lab: statistics.median([r["wall"] for r in recs if r.get("ok")])
                          for lab, recs in rows.items() if any(r.get("ok") for r in recs)}

    out_samples = []
    prev_status = None
    transitions = []
    for label, sha in samples:
        g = git.get(sha, {})
        s = {"label": label, "sha": sha, "time": g.get("time"), "subject": g.get("subject"), "tags": g.get("tags", []),
             "loc": g.get("loc"), "corpus": g.get("corpus")}
        b = load(R / f"build-{label}.json")
        if b:
            s["build"] = {k: b[k] for k in ("ok", "build_s", "compiler_ir_lines", "binary_bytes") if k in b}
        m = load(R / f"methods-{label}.json")
        status = {}
        if m:
            recs = m["records"]
            st = collections.Counter(r["status"] for r in recs)
            passed = [r for r in recs if r["status"] in ("match", "match-python-int")]
            pg = collections.Counter(group(r["file"]) for r in passed)
            cats = collections.Counter(category(r.get("detail", "")) for r in recs if r["status"] == "compile-error")
            cats_g = {grp: collections.Counter(category(r.get("detail", "")) for r in recs
                                               if r["status"] == "compile-error" and group(r["file"]) == grp)
                      for grp in ("language", "library")}
            pf = collections.Counter(r["file"] for r in passed)
            s["methods"] = {
                "total": len(recs), "pass": len(passed), "match": st.get("match", 0),
                "match_python_int": st.get("match-python-int", 0), "compile_error": st.get("compile-error", 0),
                "differs": st.get("differs", 0), "timeout": st.get("timeout", 0),
                "pass_language": pg.get("language", 0), "pass_library": pg.get("library", 0),
                "denom_language": denom["language"], "denom_library": denom["library"],
                "file_balanced": sum(pf[f] / per_file_total[f] for f in files) / len(files),
                "files_with_pass": sum(1 for f in files if pf[f]),
                "blockers": {c: cats.get(c, 0) for c in CATS},
                "blockers_language": {c: cats_g["language"].get(c, 0) for c in CATS},
                "blockers_library": {c: cats_g["library"].get(c, 0) for c in CATS},
                "top_blockers": [[k, v] for k, v in collections.Counter(
                    short(r.get("detail", "")) for r in recs if r["status"] == "compile-error").most_common(15)],
            }
            status = {(r["file"], r["test"]): (r["status"], category(r.get("detail", ""))
                                               if r["status"] == "compile-error" else r["status"]) for r in recs}
            if prev_status is not None:
                gained = collections.Counter()
                lost = 0
                for key, (st_now, _) in status.items():
                    was, why = prev_status.get(key, ("missing", "missing"))
                    now_pass = st_now in ("match", "match-python-int")
                    was_pass = was in ("match", "match-python-int")
                    if now_pass and not was_pass:
                        gained[why] += 1
                    if was_pass and not now_pass:
                        lost += 1
                transitions.append({"to": label, "gained_by_previous_blocker": dict(gained),
                                    "gained": sum(gained.values()), "lost": lost})
            prev_status = status
        c = load(R / f"census-{label}.json")
        if c:
            s["census"] = {"compiled": sorted(k for k, v in c.items() if v["status"] == "compiled"),
                           "first_errors": {k: v["first_error"][:160] for k, v in c.items() if v["status"] != "compiled"}}
        p = load(R / f"perfprep-{label}.json")
        if p:
            s["perfprep"] = {name: {"aot": bool(v.get("aot_correct")), "jit": bool(v.get("jit_correct")),
                                    "aot_build_s": v.get("aot_build_s"), "exe_bytes": v.get("exe_bytes"),
                                    "error": (v.get("aot_error") or v.get("aot_mismatch") or "")[:160]}
                             for name, v in p.items()}
        if tsum:
            sp = {}
            for name in specs:
                base = tsum.get(name, {}).get("cpython", {}).get("median")
                mine = tsum.get(name, {}).get(label, {}).get("median")
                if base and mine:
                    sp[name] = base / mine
            s["speedup"] = sp
        if jsum:
            s["jit_wall"] = {name: v[label] for name, v in jsum.items() if label in v}
        if bsum:
            s["build_wall"] = {name: v[label] for name, v in bsum.items() if label in v}
        out_samples.append(s)

    result = {"samples": out_samples, "transitions": transitions,
              "commits": [{"sha": r["sha"], "time": r["time"], "tags": r["tags"], "loc": r["loc"], "corpus": r["corpus"]}
                          for r in json.load(open(SW / "git_metrics.json"))],
              "denominators": {"methods": len(qual), **denom, "files": len(files), "census": 52,
                               "ports": sum(1 for v in specs.values() if v["kind"] == "pyperformance"),
                               "micro": sum(1 for v in specs.values() if v["kind"] == "micro")},
              "benchmarks": {k: v["kind"] for k, v in specs.items()},
              "cpython": {name: tsum.get(name, {}).get("cpython") for name in specs} if tsum else None,
              "cpython_version": qualified["python"].split()[0]}
    json.dump(result, open(out, "w"), indent=1)
    for s in out_samples:
        m = s.get("methods", {})
        pp = s.get("perfprep", {})
        print(s["label"], "pass", m.get("pass"), "lang", m.get("pass_language"), "lib", m.get("pass_library"),
              "census", len(s.get("census", {}).get("compiled", [])),
              "ports", sum(1 for k, v in pp.items() if v["aot"] and specs[k]["kind"] == "pyperformance"),
              "micro", sum(1 for k, v in pp.items() if v["aot"] and specs[k]["kind"] == "micro"),
              "blockers", m.get("blockers"))


if __name__ == "__main__":
    main()
