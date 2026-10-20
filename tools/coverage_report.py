"""Coverage reports: the hosted compiler's, from tools/coverage.sh's parts, and the native runtime's.

usage: python3 tools/coverage_report.py [DIR]   (default build/coverage; a python with coverage.py)
       python3 tools/coverage_report.py --runtime DIR COMMIT DIRTY   (tools/runtime_coverage.sh's)

tools/coverage.sh measures each part (a suite, or a shard of the corpus) into DIR/parts/: data.PART,
its coverage data, PART.json, its counts, and PART.log, its tests' report. The first form checks that
every part passed with data from each of its compiler processes, that no suite was measured twice, that
the corpus shards are all there and that the parts measured one commit; then it combines them into
DIR/data and writes DIR/html/ (each line marked with the suites that ran it), DIR/coverage.json,
DIR/summary.md (statements and branches apart: in all, for each suite alone and for each module) and
DIR/badge.json (both, as a shields.io endpoint badge). It fails on missing or inconsistent parts,
never on a percentage.

The second form writes the summary.md and badge.json of tools/runtime_coverage.sh's DIR from llvm-cov's
coverage.json and lcov.info there, and its suites.tsv: lines, branches, functions and regions for each
file, and for each section of runtime.c (its "/* ---------- NAME" comments).
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITES = {  # what each suite runs, in the order the summary lists them
    "corpus": "`tests/run.sh`, JIT and AOT",
    "ffi": "`tests/ffi/run.sh`, JIT and AOT",
    "cache": "`tests/cache.sh`",
    "unit": "`tools/test_typed*.py`, `tools/test_function_summaries.py`",
    "ir": "`tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts",
}
RUNTIME_SUITES = {
    "corpus": "`tests/run.sh`, JIT and AOT",
    "ffi": "`tests/ffi/run.sh`, AOT and extension modules",
}
BADGES = "https://github.com/den-run-ai/pystachy/blob/badges/"


def pct(covered: int, total: int) -> str:
    """covered of total as coverage.py shows a percentage: one decimal, never 0.0 or 100.0 unless exact."""
    if total == 0:
        return "-"
    p = 100.0 * covered / total
    if 0 < p < 0.1:
        p = 0.1
    elif 99.9 < p < 100:
        p = 99.9
    return f"{p:.1f}%"


def badge(path: str, label: str, first: tuple[str, int, int], second: tuple[str, int, int]) -> None:
    """A shields.io endpoint badge of two percentages, coloured by the lower."""
    low = min(100.0 * c / t if t else 100.0 for _, c, t in (first, second))
    color = next(c for t, c in [(90, "brightgreen"), (80, "green"), (70, "yellowgreen"), (60, "yellow"), (50, "orange"), (0, "red")] if low >= t)
    message = ", ".join(f"{pct(c, t)} {name}" for name, c, t in (first, second))
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"schemaVersion": 1, "label": label, "message": message, "color": color}) + "\n")


def parts_of(d: str) -> tuple[list[dict], list[str]]:
    """The parts in d/parts/, and what is wrong with them."""
    parts: list[dict] = []
    errors: list[str] = []
    for path in sorted(glob.glob(os.path.join(d, "parts", "*.json"))):
        name = os.path.basename(path)[: -len(".json")]
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        m["data"] = os.path.join(d, "parts", "data." + name)
        if m.get("part") != name or m.get("suite") not in SUITES:
            errors.append(f"{path}: not a part of tools/coverage.sh's suites")
            continue
        if not os.path.isfile(m["data"]):
            errors.append(f"{name}: no data ({m['data']})")
        elif m["processes"] == 0 or m["data_files"] != m["processes"] - (1 if m["suite"] == "cache" else 0):
            errors.append(f"{name}: {m['data_files']} coverage data files, for {m['processes']} processes")
        parts.append(m)
    if not parts and not errors:
        errors.append(f"no parts in {os.path.join(d, 'parts')} (tools/coverage.sh writes them)")
    for s in SUITES:
        mine = [m for m in parts if m["suite"] == s]
        shards = sorted(tuple(m["shard"]) for m in mine if m["shard"] is not None)
        if len(mine) > 1 and (len(shards) != len(mine) or len({n for _, n in shards}) != 1):
            errors.append(f"{s}: measured {len(mine)} times: {', '.join(m['part'] for m in mine)}")
        elif shards and shards != [(i, shards[0][1]) for i in range(shards[0][1])]:
            errors.append(f"{s}: shards {', '.join(f'{i}/{n}' for i, n in shards)}, not all {shards[0][1]} of them")
    if len({m["commit"] for m in parts}) > 1:
        errors.append("the parts measured different commits: " + ", ".join(sorted({m["commit"] for m in parts})))
    return parts, errors


def checks(parts: list[dict]) -> str:
    """The parts' reports: "N passed, M failed" summed over shards, else each as it was."""
    got = [re.fullmatch(r"(\d+) passed, (\d+) failed", m["report"]) for m in parts]
    if len(parts) > 1 and all(got):
        return f"{sum(int(g.group(1)) for g in got)} passed, {sum(int(g.group(2)) for g in got)} failed"
    return "; ".join(m["report"] for m in parts)


def counts(report: dict) -> tuple[tuple[int, int], tuple[int, int]]:
    """(covered, all) statements and branches of a coverage.py JSON report."""
    t = report["totals"]
    return (t["covered_lines"], t["num_statements"]), (t["covered_branches"], t["num_branches"])


def hosted(d: str) -> int:
    import coverage

    parts, errors = parts_of(d)
    if errors:
        for e in errors:
            print(f"tools/coverage_report.py: {e}", file=sys.stderr)
        return 1
    data = os.path.join(d, "data")
    for p in [data, data + "-journal"]:
        if os.path.exists(p):
            os.remove(p)  # (combine adds to what the data file holds)
    cov = coverage.Coverage(data_file=data, config_file=".coveragerc")
    cov.combine([m["data"] for m in parts], strict=True, keep=True)
    cov.save()
    cov.load()
    cov.html_report(directory=os.path.join(d, "html"))
    out = os.path.join(d, "coverage.json")
    cov.json_report(outfile=out)
    with open(out, encoding="utf-8") as f:
        whole = json.load(f)
    suites = [s for s in SUITES if any(m["suite"] == s for m in parts)]
    alone: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for s in suites:  # each suite's data alone: its context
            cov.json_report(outfile=os.path.join(tmp, s), contexts=[f"^{s}$"])
            with open(os.path.join(tmp, s), encoding="utf-8") as f:
                alone[s] = json.load(f)
    (st, br) = counts(whole)
    others = "corpus" in alone and len(suites) > 1
    corpus = alone["corpus"]["files"] if "corpus" in alone else {}
    # what the other suites run that the corpus does not
    extra = [0, 0]
    for name, f in whole["files"].items():
        c = corpus.get(name, {"executed_lines": [], "executed_branches": []})
        extra[0] += len(set(f["executed_lines"]) - set(c["executed_lines"]))
        extra[1] += len({tuple(b) for b in f["executed_branches"]} - {tuple(b) for b in c["executed_branches"]})

    dirty = " with uncommitted changes" if any(m["dirty"] for m in parts) else ""
    procs = sum(m["processes"] for m in parts)
    lines = [
        "## Hosted compiler coverage",
        "",
        f"Commit `{parts[0]['commit']}`{dirty}: statements **{pct(*st)}** ({st[0]} of {st[1]}) and branches"
        f" **{pct(*br)}** ({br[0]} of {br[1]}); {whole['totals']['percent_covered_display']}% together,"
        f" coverage.py's total. {len(suites)} suites, {procs} processes measured.",
        "The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`,"
        " `lib/` or the compiled programs, which run as native code"
        f" ([native runtime coverage]({BADGES}runtime-coverage.md)).",
        "",
        "| Suite | Runs | Checks | Processes | Time | Statements | Branches |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for s in suites:
        mine = [m for m in parts if m["suite"] == s]
        runs = SUITES[s]
        if mine[0]["shard"] is not None:
            runs += f" ({len(mine)} shards)"
        if any(m["selected"] for m in mine):
            runs += f", {sum(m['cases'] for m in mine)} cases selected"
        (cs, cb) = counts(alone[s])
        lines.append(f"| {s} | {runs} | {checks(mine)} | {sum(m['processes'] for m in mine)}"
                     f" | {sum(m['seconds'] for m in mine)} s | {pct(*cs)} | {pct(*cb)} |")
    lines.append(f"| **all** | | | **{procs}** | | **{pct(*st)}** | **{pct(*br)}** |")
    if others:
        lines += ["", f"The other suites run {extra[0]} statements and {extra[1]} branches that the corpus does not."]
    print("\n".join(lines[2:]))  # (the totals and the suites, for the log)
    lines += [
        "",
        "| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total |"
        + (" Corpus alone |" if others else ""),
        "|---|---:|---:|---:|---:|---:|---:|---:|" + ("---:|" if others else ""),
    ]
    for name, f in sorted(whole["files"].items()):
        s = f["summary"]
        if s["num_statements"] == 0:
            continue  # (an empty __init__.py)
        row = (f"| `{name}` | {s['num_statements']} | {s['missing_lines']} | {pct(s['covered_lines'], s['num_statements'])}"
               f" | {s['num_branches']} | {s['num_branches'] - s['covered_branches']}"
               f" | {pct(s['covered_branches'], s['num_branches'])} | {s['percent_covered_display']}% |")
        if others:
            c = corpus.get(name)
            row += f" {c['summary']['percent_covered_display'] + '%' if c else '-'} |"
        lines.append(row)
    with open(os.path.join(d, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    badge(os.path.join(d, "badge.json"), "hosted compiler coverage", ("statements", *st), ("branches", *br))
    print(f"hosted compiler coverage: statements {pct(*st)}, branches {pct(*br)} ({d}/html/index.html, {d}/summary.md)")
    return 0


def lcov(path: str) -> dict[str, dict]:
    """lcov.info's records: for each file, its lines' counts, its branches (line, taken) and functions."""
    files: dict[str, dict] = {}
    cur: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            key, _, value = line.rstrip("\n").partition(":")
            if key == "SF":
                cur = files.setdefault(os.path.normpath(value), {"lines": {}, "branches": [], "functions": {}, "starts": {}})
            elif key == "DA":
                n, c = value.split(",")[:2]
                cur["lines"][int(n)] = cur["lines"].get(int(n), 0) + int(c)
            elif key == "BRDA":
                n, _, _, taken = value.split(",")
                cur["branches"].append((int(n), taken not in ("-", "0")))
            elif key == "FN":
                n, name = value.split(",", 1)
                cur["starts"][name] = int(n)
            elif key == "FNDA":
                c, name = value.split(",", 1)
                cur["functions"][name] = cur["functions"].get(name, 0) + int(c)
    return files


def runtime(d: str, rev: str, dirty: str, source: str = os.path.join(ROOT, "runtime.c")) -> int:
    with open(os.path.join(d, "coverage.json"), encoding="utf-8") as f:
        export = json.load(f)["data"][0]
    records = lcov(os.path.join(d, "lcov.info"))
    suites = []
    with open(os.path.join(d, "suites.tsv"), encoding="utf-8") as f:
        for line in f:
            name, report, secs = line.rstrip("\n").split("\t")
            suites.append((name, report, int(secs)))
    t = export["totals"]
    ln, br, fn, rg = t["lines"], t["branches"], t["functions"], t["regions"]
    rt = records.get("runtime.c", {"functions": {}})
    runs = rt["functions"].get("pys_init", 0)
    lines = [
        "## Native runtime coverage",
        "",
        f"Commit `{rev}`{' with uncommitted changes' if dirty == 'true' else ''}: lines **{pct(ln['covered'], ln['count'])}**"
        f" ({ln['covered']} of {ln['count']}) and branches **{pct(br['covered'], br['count'])}** ({br['covered']} of"
        f" {br['count']}) of `runtime.c` (with the `ryu/` files it includes), `pyembed.c` and `pyext.c`, as clang's"
        f" source-based coverage counts them; functions {pct(fn['covered'], fn['count'])}, regions"
        f" {pct(rg['covered'], rg['count'])}. `pys_init` ran {runs} times: the program runs whose profiles were written.",
        "Programs built by the native compiler against an instrumented runtime; `runtime.py`, compiled by Pystachy,"
        " is not measured, nor are the C probes. The compiler's own coverage is the"
        f" [hosted compiler coverage]({BADGES}coverage.md).",
        "",
        "| Suite | Runs | Checks | Time |",
        "|---|---|---|---:|",
    ]
    lines += [f"| {n} | {RUNTIME_SUITES[n]} | {r} | {s} s |" for n, r, s in suites]
    print("\n".join(lines[2:]))
    lines += [
        "",
        "| File | Lines | Missed | Lines % | Branches | Missed | Branches % | Functions % | Regions % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for f in sorted(export["files"], key=lambda f: f["filename"]):
        s = f["summary"]
        lines.append(f"| `{os.path.normpath(f['filename'])}` | {s['lines']['count']} | {s['lines']['count'] - s['lines']['covered']}"
                     f" | {pct(s['lines']['covered'], s['lines']['count'])} | {s['branches']['count']}"
                     f" | {s['branches']['notcovered']} | {pct(s['branches']['covered'], s['branches']['count'])}"
                     f" | {pct(s['functions']['covered'], s['functions']['count'])} | {pct(s['regions']['covered'], s['regions']['count'])} |")
    lines.append(f"| **Total** | {ln['count']} | {ln['count'] - ln['covered']} | **{pct(ln['covered'], ln['count'])}** | {br['count']}"
                 f" | {br['notcovered']} | **{pct(br['covered'], br['count'])}** | {pct(fn['covered'], fn['count'])}"
                 f" | {pct(rg['covered'], rg['count'])} |")
    # runtime.c by section: each "/* ---------- NAME" comment starts one, up to the next
    sections = [(1, "(declarations)")]
    with open(source, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            m = re.match(r"/\* -{10} (.*?)(?: -{10}.*)?$", line)
            if m:
                sections.append((i, m.group(1).rstrip(" -")))
    if "runtime.c" in records:
        def section(n: int) -> int:
            return max(k for k, (start, _) in enumerate(sections) if start <= n)
        agg = [[0, 0, 0, 0, 0, 0] for _ in sections]  # lines, covered; branches, taken; functions, run
        for n, c in rt["lines"].items():
            agg[section(n)][0] += 1
            agg[section(n)][1] += c > 0
        for n, taken in rt["branches"]:
            agg[section(n)][2] += 1
            agg[section(n)][3] += taken
        for name, start in rt["starts"].items():
            agg[section(start)][4] += 1
            agg[section(start)][5] += rt["functions"].get(name, 0) > 0
        lines += [
            "",
            "`runtime.c` by section (the comments that start them):",
            "",
            "| Section | From line | Lines | Lines % | Branches | Branches % | Functions | Functions % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for (start, name), a in zip(sections, agg, strict=True):
            if a[0] or a[2] or a[4]:
                lines.append(f"| {name} | {start} | {a[0]} | {pct(a[1], a[0])} | {a[2]} | {pct(a[3], a[2])} | {a[4]} | {pct(a[5], a[4])} |")
    with open(os.path.join(d, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    badge(os.path.join(d, "badge.json"), "native runtime coverage", ("lines", ln["covered"], ln["count"]), ("branches", br["covered"], br["count"]))
    print(f"native runtime coverage: lines {pct(ln['covered'], ln['count'])}, branches {pct(br['covered'], br['count'])}"
          f" ({d}/html/index.html, {d}/summary.md)")
    return 0


def main(argv: list[str]) -> int:
    os.chdir(ROOT)
    if len(argv) > 1 and argv[1] == "--runtime":
        if len(argv) != 5:
            print(__doc__, file=sys.stderr)
            return 2
        return runtime(argv[2], argv[3], argv[4])
    if len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    return hosted(argv[1] if len(argv) > 1 else "build/coverage")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
