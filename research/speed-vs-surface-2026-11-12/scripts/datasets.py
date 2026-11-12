"""Flatten evolution.json into the row files the dashboard charts (JSON arrays of flat objects).

usage: python3 datasets.py EVOLUTION.json OUTDIR
"""
import datetime
import json
import math
import re
import sys
from pathlib import Path

from classify import category

MIN_AOT_SECONDS = 1e-3  # a timed region below 1 ms was optimized away (unpack_sequence); not a speed


def iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rnd(v):
    return round(v, 3) if v is not None else None


def clean(msg):
    msg = re.sub(r"^[^ ]*\.py: (error: )?", "", msg or "")
    return re.sub(r" \((sys, os|available: ).*$", "", msg)


def release(tags):
    tags = [t for t in tags if t.startswith("v")]
    return tags[0] if tags else ""


def main():
    ev = json.load(open(sys.argv[1]))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    samples = [s for s in ev["samples"] if s.get("methods")]
    samples.sort(key=lambda s: s["time"])
    kinds = ev["benchmarks"]
    den = ev["denominators"]

    # the fixed core set: ports whose AOT output matched CPython at every sample from the first
    # sample where at least 10 ports worked, and whose timed region is a real measurement
    ports = [b for b, k in kinds.items() if k == "pyperformance"]
    micro = [b for b, k in kinds.items() if k == "micro"]
    samples = [s for s in samples if s.get("perfprep")]
    working = {s["label"]: {b for b, v in s.get("perfprep", {}).items() if v["aot"]} for s in samples}
    start = next((i for i, s in enumerate(samples) if len(working[s["label"]] & set(ports)) >= 10), len(samples) - 1)
    core = [b for b in ports if all(b in working[s["label"]] for s in samples[start:])]
    cpy = ev.get("cpython") or {}
    # a benchmark whose AOT timed region falls under MIN_AOT_SECONDS at any sample measures nothing
    # there (the loop was optimized away); it is left out of every chart and index, not just that sample
    tiny = {b for s in samples for b, sp in s.get("speedup", {}).items()
            if (cpy.get(b) or {}).get("median") and (cpy[b]["median"] / sp) < MIN_AOT_SECONDS}
    core = [b for b in core if b not in tiny]

    speed_rows = []
    for s in samples:
        for b, sp in sorted(s.get("speedup", {}).items()):
            base = (cpy.get(b) or {}).get("median")
            aot = base / sp if base and sp else None
            if b in tiny or aot is None:
                continue
            speed_rows.append({"label": s["label"], "date": iso(s["time"]), "benchmark": b, "kind": kinds[b],
                               "core": b in core or kinds[b] == "micro", "cpython_s": round(base, 6),
                               "aot_s": round(aot, 6), "speedup": round(sp, 4)})
    json.dump(speed_rows, open(out / "speedups.json", "w"), indent=0)

    sample_rows = []
    for s in samples:
        m = s["methods"]
        pp = s.get("perfprep", {})
        jit = [s.get("jit_wall", {}).get(b) for b in micro]
        jit = [x for x in jit if x]
        loc = s.get("loc") or {}
        row = {
            "label": s["label"], "date": iso(s["time"]), "sha": s["sha"][:10], "release": release(s.get("tags", [])),
            "subject": (s.get("subject") or "")[:90],
            "methods_pass": m["pass"], "methods_total": m["total"], "pass_language": m["pass_language"],
            "language_total": m["denom_language"], "pass_library": m["pass_library"], "library_total": m["denom_library"],
            "pass_promoting_int": m["match_python_int"], "compiled_but_differs": m["differs"], "timeouts": m["timeout"],
            "files_with_pass": m["files_with_pass"],
            "blocked_library": m["blockers"]["library"], "blocked_syntax": m["blockers"]["syntax"],
            "blocked_typing": m["blockers"]["typing"], "blocked_dynamic": m["blockers"]["dynamic"],
            "blocked_other": m["blockers"]["other"],
            "lang_blocked_library": m["blockers_language"]["library"], "lang_blocked_syntax": m["blockers_language"]["syntax"],
            "lang_blocked_typing": m["blockers_language"]["typing"], "lang_blocked_dynamic": m["blockers_language"]["dynamic"],
            "lang_blocked_other": m["blockers_language"]["other"],
            "upstream_compiled": len(s.get("census", {}).get("compiled", [])),
            "ports_working": sum(1 for b in ports if pp.get(b, {}).get("aot")),
            "micro_working": sum(1 for b in micro if pp.get(b, {}).get("aot")),
            "compiler_lines": loc.get("compiler", 0), "runtime_lines": loc.get("runtime", 0), "library_lines": loc.get("library", 0),
            "compiler_ir_lines": (s.get("build") or {}).get("compiler_ir_lines"),
            "jit_micro_median_s": round(sorted(jit)[len(jit) // 2], 4) if jit else None,
            "aot_build_nbody_s": rnd((s.get("build_wall") or {}).get("micro_nbody")),
            "aot_build_richards_s": rnd((s.get("build_wall") or {}).get("richards")),
            "aot_build_raytrace_s": rnd((s.get("build_wall") or {}).get("raytrace")),
            "jit_richards_s": rnd((s.get("jit_wall") or {}).get("richards")),
        }
        sample_rows.append(row)
    json.dump(sample_rows, open(out / "samples.json", "w"), indent=0)

    hist = []
    for c in ev["commits"]:
        if not c["loc"]:
            continue
        hist.append({"sha": c["sha"][:10], "date": iso(c["time"]), "release": release(c["tags"]),
                     "compiler_lines": c["loc"].get("compiler", 0), "runtime_lines": c["loc"].get("runtime", 0),
                     "library_lines": c["loc"].get("library", 0),
                     "corpus_programs": (c["corpus"] or {}).get("programs", 0),
                     "corpus_rejections": (c["corpus"] or {}).get("errors", 0),
                     "corpus_deviations": (c["corpus"] or {}).get("deviations", 0)})
    json.dump(hist, open(out / "history.json", "w"), indent=0)

    head = samples[-1]
    blk = [{"rank": i + 1, "message": msg, "category": category(msg), "methods": n}
           for i, (msg, n) in enumerate(head["methods"]["top_blockers"])]
    json.dump(blk, open(out / "blockers_head.json", "w"), indent=0)

    trans = {t["to"]: t for t in ev["transitions"]}
    unl = []
    for prev, s in zip(samples, samples[1:]):
        t = trans.get(s["label"], {})
        g = t.get("gained_by_previous_blocker", {})
        unl.append({"label": s["label"], "date": iso(s["time"]), "from_label": prev["label"],
                    "from_library": g.get("library", 0), "from_syntax": g.get("syntax", 0),
                    "from_typing": g.get("typing", 0), "from_dynamic": g.get("dynamic", 0),
                    "from_other": g.get("other", 0) + g.get("differs", 0) + g.get("timeout", 0),
                    "gained": t.get("gained", 0), "lost": t.get("lost", 0)})
    json.dump(unl, open(out / "unlocks.json", "w"), indent=0)

    cen = []
    names = sorted(set().union(*[set(s.get("census", {}).get("compiled", [])) | set(s.get("census", {}).get("first_errors", {})) for s in samples]))
    for b in names:
        first = next((s for s in samples if b in s.get("census", {}).get("compiled", [])), None)
        cen.append({"benchmark": b, "ported": b in ports or b == "logging",
                    "compiles_unmodified_at_head": b in head.get("census", {}).get("compiled", []),
                    "first_compiled": iso(first["time"]) if first else "",
                    "head_first_error": clean(head.get("census", {}).get("first_errors", {}).get(b, ""))})
    json.dump(cen, open(out / "census.json", "w"), indent=0)
    print(f"samples {len(sample_rows)}, speed rows {len(speed_rows)}, excluded {sorted(tiny)}, core {len(core)} from {samples[start]['label']}: {core}")


if __name__ == "__main__":
    main()
