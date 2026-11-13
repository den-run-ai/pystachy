"""Summarize jit_variants.py results: one row per workload, medians and paired ratios (opt2/default).

usage: summarize.py RESULTS_DIR [ORDER...]
Compile is driver.prepare_run (frontend, IR passes and opt) plus the runner's load and code
generation; the rest of the wall time is execution and process start-up. Timer columns are the
program's own stage timers (UMAP: knn, layout; pyperformance ports: the timed loop).
"""

import json
import statistics
import sys
from pathlib import Path

directory = Path(sys.argv[1])
order = sys.argv[2:] or sorted(p.stem for p in directory.glob("*.json"))


def med(rows: list[dict], key) -> float:
    return statistics.median(key(r) for r in rows)


def compile_s(r: dict) -> float:
    return r.get("driver.prepare_run", 0.0) + r.get("program.jit_load", 0.0) + r.get("program.jit_codegen", 0.0)


def paired(a: list[dict], b: list[dict], key) -> float:
    return statistics.median(key(y) / key(x) for x, y in zip(a, b, strict=True) if key(x) > 0)


print("| Workload | Rounds | Wall default | Wall opt2 | Paired | Optimize default | Optimize opt2 | Compile default | Compile opt2 | Timer | Timer default | Timer opt2 | Timer paired | RSS default MiB | RSS opt2 MiB |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|")
for name in order:
    data = json.loads((directory / f"{name}.json").read_text())
    d, o = data["runs"]["default"], data["runs"]["opt2"]
    timers = sorted(k for k in d[0] if k.startswith("timer.") and k not in ("timer.data", "timer.graph"))
    timers = [t for t in timers if t != "timer.loop"] + [t for t in timers if t == "timer.loop"]
    cells = [name, str(data["rounds"]),
             f"{med(d, lambda r: r['wall']):.3f}", f"{med(o, lambda r: r['wall']):.3f}",
             f"{paired(d, o, lambda r: r['wall']):.3f}",
             f"{med(d, lambda r: r.get('program.jit_optimize', 0.0)):.3f}", f"{med(o, lambda r: r.get('program.jit_optimize', 0.0)):.3f}",
             f"{med(d, compile_s):.3f}", f"{med(o, compile_s):.3f}"]
    if timers:
        rows = []
        for t in timers:
            rows.append((t.removeprefix("timer."), med(d, lambda r, t=t: r[t]), med(o, lambda r, t=t: r[t]), paired(d, o, lambda r, t=t: r[t])))
        cells += ["<br>".join(r[0] for r in rows), "<br>".join(f"{r[1]:.3f}" for r in rows),
                  "<br>".join(f"{r[2]:.3f}" for r in rows), "<br>".join(f"{r[3]:.3f}" for r in rows)]
    else:
        cells += ["", "", "", ""]
    cells += [f"{med(d, lambda r: r['peak_rss_mib']):.1f}", f"{med(o, lambda r: r['peak_rss_mib']):.1f}"]
    print("| " + " | ".join(cells) + " |")
