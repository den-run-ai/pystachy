"""Markdown report and CSV/JSON data for the offline export, generated from the dashboard's datasets.

usage: python3 export_md.py DATADIR SOURCES.json OUTDIR
Writes OUTDIR/report.md (images referenced as images/NN-*.png) and OUTDIR/data/*.csv|json.
"""
import collections
import csv
import json
import math
import shutil
import sys
from pathlib import Path


def gm(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def fx(v, nd=1):
    return "—" if v is None else f"{v:.{nd}f}×"


def num(v):
    return "—" if v is None else f"{v:,}"


def day(iso):
    import datetime
    d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return d.strftime("%b %-d")


def table(headers, rows, align=None):
    align = align or ["l"] * len(headers)
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---:" if a == "r" else "---" for a in align) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)


def main():
    D, sources_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    (out / "data").mkdir(parents=True, exist_ok=True)
    load = lambda n: json.load(open(D / f"{n}.json"))
    samples = sorted(load("samples"), key=lambda r: r["date"])
    speed = load("speedups")
    blockers = sorted(load("blockers_head"), key=lambda r: r["rank"])
    unlocks = sorted(load("unlocks"), key=lambda r: r["date"])
    census = load("census")
    changes = sorted(load("changes"), key=lambda r: r["rank"])
    overlay = sorted(load("overlay_head"), key=lambda r: r["order"])
    history = sorted(load("history"), key=lambda r: r["date"])
    sources = json.load(open(sources_path))

    # performance index exactly as the page's calculation: all members of the set must be measured
    core = sorted({r["benchmark"] for r in speed if r["kind"] == "pyperformance" and r["core"]})
    micro = sorted({r["benchmark"] for r in speed if r["kind"] == "micro"})
    by = collections.defaultdict(dict)
    for r in speed:
        by[r["label"]][r["benchmark"]] = r
    idx = []
    for s in samples:
        b = by.get(s["label"], {})
        row = {"label": s["label"], "date": s["date"], "release": s["release"]}
        row["core_index"] = round(gm([b[x]["speedup"] for x in core]), 3) if all(x in b for x in core) else None
        row["micro_index"] = round(gm([b[x]["speedup"] for x in micro]), 3) if all(x in b for x in micro) else None
        idx.append(row)
    ix = {r["label"]: r for r in idx}

    # data files: JSON as charted, CSV for spreadsheets
    for name in ("samples", "speedups", "history", "blockers_head", "unlocks", "census", "changes", "overlay_head"):
        shutil.copy(D / f"{name}.json", out / "data" / f"{name}.json")
        rows = load(name)
        with open(out / "data" / f"{name}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    with open(out / "data" / "perf_index.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(idx[0].keys()))
        w.writeheader()
        w.writerows(idx)

    first, last = samples[0], samples[-1]
    a2 = next(s for s in samples if s["release"] == "v0.1.0-alpha.2")
    after = [u for u in unlocks if u["date"] > a2["date"]]
    blocked = sum(last[f"lang_blocked_{k}"] for k in ("library", "syntax", "typing", "dynamic", "other"))
    design = last["lang_blocked_typing"] + last["lang_blocked_dynamic"]
    core_first = next(r for r in idx if r["core_index"])
    ov = {r["order"]: r for r in overlay}
    L = []
    w = L.append
    rep = next(s for s in samples if s["label"] == "1111-1943_8434a911")
    a5 = next(s for s in samples if s["release"] == "v0.4.0-alpha.5")
    pre = next(s for s in samples if s["release"] == "v0.5.0-alpha.1")
    post = next(s for s in samples if s["release"] == "v0.5.0-alpha.2")
    newer = [s for s in samples if s["date"] > rep["date"]]
    w("# Pystachy speed vs surface\n")
    w(f"Performance against the amount of unmodified Python that Pystachy runs, across {len(samples)} commits of `main` "
      f"from the project's first day ({day(first['date'])}) to {day(last['date'])} 2026; dates are UTC. Second edition, 18 November "
      "2026: the first edition (12 November) measured 35 of these commits, and all of them were timed again together. Scripts and raw "
      "data: `research/speed-vs-surface-2026-11-18` on the branch `claude/peaceful-faraday-2yr9q6`.\n")
    w("## Summary\n")
    w(f"- **Surface grew in two phases and two steps.** CPython test methods passing went from {first['methods_pass']} on the first "
      f"day to {a2['methods_pass']} at v0.1.0-alpha.2 ({day(a2['date'])}) and {a5['methods_pass']} at v0.4.0-alpha.5 ({day(a5['date'])}). "
      f"Bounded `match` (#1272) raised it to {rep['methods_pass']} on {day(rep['date'])}, and v0.6.0-alpha.1 to {last['methods_pass']} "
      f"({last['methods_pass'] / last['methods_total']:.1%} of {last['methods_total']:,}). Language and builtins tests: "
      f"{first['pass_language']} → {a2['pass_language']} → {a5['pass_language']} → {rep['pass_language']} → {last['pass_language']} "
      f"of {last['language_total']:,}.")
    w(f"- **Most of the latest gain came from two pull requests.** Fields typed from `set()` calls (#1374) made 100 `test_set` "
      "methods pass and starred sequence patterns (#1345) 38 `test_patma` methods, both in #1522 on 17 November. No method that "
      "passed on 12 November fails.")
    w(f"- **The remaining blockers are mostly class-model and inference features.** At the latest commit, static-typing "
      f"({last['lang_blocked_typing']:,}) and dynamic-model ({last['lang_blocked_dynamic']:,}) first errors are {design / blocked:.0%} "
      f"of the {blocked:,} rejections in the language and builtins tests; classes defined inside functions (#1304) and three names "
      "missing from `enum` are the largest groups without an open pull request.")
    w(f"- **Neither escape hatch helps unmodified code.** Adding CPython's own pure-Python standard library makes "
      f"{ov[4]['methods']} of the {ov[3]['methods']:,} library-blocked methods pass; opting every test in to dynamic `Any` "
      f"leaves {ov[2.5]['methods']} passing.")
    w(f"- **Speed held.** The six day-one microbenchmarks ran {fx(ix[first['label']]['micro_index'])} CPython 3.13 "
      f"on the first day and {fx(ix[last['label']]['micro_index'])} at the latest commit. The {len(core)}-port pyperformance core set went "
      f"from {fx(core_first['core_index'])} ({day(core_first['date'])}) to {fx(ix[last['label']]['core_index'])}, mostly from regex-library "
      "work on Oct 19.")
    reg = {c["benchmark"]: c for c in changes if c["change"].startswith("Slower")}
    w(f"- **One regression fixed, one partly.** `float` (+{(reg['float']['time_ratio'] - 1) * 100:.0f}% at #1268) recovered in "
      f"v0.4.0-rc.1 through #1336; `words` (+{(reg['micro_words']['time_ratio'] - 1) * 100:.0f}% at #667) improved slightly through "
      "#1332 but keeps the larger heap of #667 (#1301).")
    w(f"- **AOT builds got cheaper; the bootstrap did not.** `pystachy build` of the day-one nbody took {first['aot_build_nbody_s']:.2f} s "
      f"on the first day and {pre['aot_build_nbody_s']:.2f} s at v0.5.0-alpha.1; the precompiled runtime (#1377) cut it to "
      f"{post['aot_build_nbody_s']:.2f} s at v0.5.0-alpha.2 ({last['aot_build_nbody_s']:.2f} s now). Compiler IR at the bootstrap "
      f"fixed point grew from {first['compiler_ir_lines']:,} to {last['compiler_ir_lines']:,} lines. JIT end to end on the small "
      f"programs went from {first['jit_micro_median_s']:.2f} s to {last['jit_micro_median_s']:.2f} s.\n")

    w("## Since the first edition (12 November)\n")
    w(f"Main took 474 commits and 11 release tags between {rep['sha'][:8]} and {last['sha'][:8]}. Every tag was measured, with the "
      "untagged RC.2 fixes (`bf699eb5`) and `71e14a88`, which separates #1519 from #1522.\n")
    w(table(["Date", "Release", "Commit", "Methods", "Language", "Library", "Micro index", "Core index", "nbody build"],
            [[day(s["date"]), s["release"] or "—", f"`{s['sha'][:8]}`", s["methods_pass"], s["pass_language"], s["pass_library"],
              fx(ix[s["label"]]["micro_index"]), fx(ix[s["label"]]["core_index"]),
              f"{s['aot_build_nbody_s']:.2f} s" if s["aot_build_nbody_s"] else "—"] for s in [rep] + newer],
            ["l", "l", "l", "r", "r", "r", "r", "r", "r"]) + "\n")
    w(table(["Change", "Pull request", "Release", "Methods that now pass"], [
        ["Fields typed from `set()` and `frozenset()` calls", "#1374 in #1522", "v0.6.0-alpha.1", "100 (`test_set`)"],
        ["Starred sequence patterns and list subjects in `match`", "#1345 in #1522", "v0.6.0-alpha.1", "38 (`test_patma`)"],
        ["`complex` numbers", "#1408 in #1494", "v0.5.0-alpha.3", "5"],
        ["`None` as a set element", "#1412 in #1494", "v0.5.0-alpha.3", "1"],
        ["`csv.DictWriter.writerow` called through its class", "in #1481", "v0.5.0-alpha.1", "2"]],
        ["l", "l", "l", "r"]) + "\n")
    w("Issues the first edition filed: #1300 (`float`) closed, fixed by #1336; #1301 (`words`) open after #1332; #1302 (weekly timing) "
      "closed by the weekly workflow #1339; #1303 (per-release triage) open with one manual comparison; #1304 (classes inside functions) "
      "open with no pull request; #1305 (`match` patterns) open after #1345; #1306 closed as a duplicate. #706 (AOT build cost) closed "
      "by #1377.\n")
    w("## Speed against Python surface\n")
    w("One point per sampled commit, joined in time order. Across: extracted CPython test methods it runs with CPython's output. "
      "Up: geometric-mean AOT speedup over CPython 3.13 on the same sources (log scale).\n")
    w("![Speed against all CPython test methods passing](images/01-speed-vs-surface-all-methods.png)\n")
    w("The same against language and builtins tests only, and against unmodified upstream pyperformance files that compile:\n")
    w("![Speed against language tests passing](images/02-speed-vs-surface-language-tests.png)\n")
    w("![Speed against upstream files compiling](images/03-speed-vs-surface-upstream-files.png)\n")

    w("## Surface and speed over time\n")
    w("![CPython test methods passing over time](images/04-methods-passing-over-time.png)\n")
    w("![Benchmarks that work over time](images/05-benchmarks-working-over-time.png)\n")
    w("![Performance index over time](images/06-performance-index-over-time.png)\n")
    marks = [s for s in samples if s["release"]] + [first]
    marks = sorted({s["label"]: s for s in marks + [last]}.values(), key=lambda s: s["date"])
    w(table(["Date", "Release", "Methods passing", "Language tests", "Library tests", "Ports working", "Upstream files", "Micro index", "Core index"],
            [[day(s["date"]), s["release"] or "—", s["methods_pass"], s["pass_language"], s["pass_library"], s["ports_working"],
              s["upstream_compiled"], fx(ix[s["label"]]["micro_index"]), fx(ix[s["label"]]["core_index"])] for s in marks],
            ["l", "l", "r", "r", "r", "r", "r", "r", "r"]) + "\n")

    w("## What stops the remaining CPython tests\n")
    w("The first compiler error of every method that does not compile, grouped by cause. Library and syntax gaps are unbuilt work. "
      "Typing and dynamic-model errors come from the typed, interpreter-free design: values whose single static type cannot be "
      "inferred, and classes, modules or code used as runtime values. Imports come first in a program, so a missing module hides "
      "any later error.\n")
    w("![First errors, language and builtins tests](images/07-first-errors-language-tests.png)\n")
    w("![First errors, all tests](images/08-first-errors-all-tests.png)\n")
    w("![Newly passing methods by previous blocker](images/09-newly-passing-by-previous-blocker.png)\n")
    w("### Most common first errors at the latest commit\n")
    w(table(["#", "First compiler error", "Cause", "Methods"],
            [[b["rank"], f"`{b['message']}`", b["category"], b["methods"]] for b in blockers], ["r", "l", "l", "r"]) + "\n")
    w("### With CPython's own standard library added (latest commit)\n")
    w(f"CPython 3.13.16's pure-Python standard library on the import path (`tools/import_sweep.py --overlay`, which leaves out the "
      f"modules Pystachy ships): {ov[4]['methods']} of the {ov[3]['methods']:,} methods blocked by a missing library piece pass. "
      f"Their next errors:\n")
    w(table(["Where the method now stops", "Cause", "Methods"],
            [[r["group"], r["outcome"], f"{r['methods']:,}"] for r in overlay if r["order"] >= 5], ["l", "l", "r"]) + "\n")

    w("## Speed by benchmark and commit\n")
    w("AOT speed relative to CPython 3.13 on the same source. Blue is faster than CPython, red is slower; an empty cell means that "
      "commit could not build the benchmark or printed different output.\n")
    w("![Speed by benchmark and commit](images/10-speed-by-benchmark-heatmap.png)\n")
    w("### Largest speed changes and their causes\n")
    w(table(["Benchmark", "From", "To", "ms before", "ms after", "Change", "Evidence"],
            [[c["benchmark"], c["from_date"], c["to_date"], f"{c['before_ms']:,.1f}", f"{c['after_ms']:,.1f}", c["change"], c["evidence"]]
             for c in changes], ["l", "l", "l", "r", "r", "l", "l"]) + "\n")
    w("### Each benchmark: first sampled commit where it worked, and the latest\n")
    rows = []
    for bname in sorted({r["benchmark"] for r in speed}):
        pts = [by[s["label"]][bname] for s in samples if bname in by.get(s["label"], {})]
        f0, f1 = pts[0], pts[-1]
        rows.append([bname, day(f0["date"]), fx(f0["speedup"], 2), fx(f1["speedup"], 2), f"{(f0['aot_s'] / f1['aot_s'] - 1) * 100:+.0f}%"])
    w(table(["Benchmark", "Works since", "Speed then", "Speed now", "Change"], rows, ["l", "l", "r", "r", "r"]) + "\n")
    w("### The 52 unmodified upstream pyperformance files\n")
    w(table(["Benchmark", "Compiles unmodified", "First sampled commit that compiled it", "First error at the latest commit"],
            [[c["benchmark"], "yes" if c["compiles_unmodified_at_head"] else "no", day(c["first_compiled"]) if c["first_compiled"] else "—",
              f"`{c['head_first_error']}`" if c["head_first_error"] else "—"]
             for c in sorted(census, key=lambda c: (not c["compiles_unmodified_at_head"], c["benchmark"]))]) + "\n")

    w("## What the surface cost\n")
    w("![Lines of source at every commit](images/11-source-lines.png)\n")
    w("![Compile time for fixed programs](images/12-compile-time.png)\n")
    w(table(["Date", "Release", "Compiler lines", "Library lines", "Runtime lines", "Compiler IR lines", "AOT build nbody", "AOT build richards", "AOT build raytrace", "JIT small programs"],
            [[day(s["date"]), s["release"] or "—", num(s["compiler_lines"]), num(s["library_lines"]), num(s["runtime_lines"]), num(s["compiler_ir_lines"]),
              f"{s['aot_build_nbody_s']:.2f} s" if s["aot_build_nbody_s"] else "—",
              f"{s['aot_build_richards_s']:.2f} s" if s["aot_build_richards_s"] else "—",
              f"{s['aot_build_raytrace_s']:.2f} s" if s["aot_build_raytrace_s"] else "—",
              f"{s['jit_micro_median_s']:.2f} s" if s["jit_micro_median_s"] else "—"] for s in marks],
            ["l", "l", "r", "r", "r", "r", "r", "r", "r", "r"]) + "\n")

    w("## How this was measured\n")
    for line in [
        "Commits: 48 points on `main` from 7 October to 17 November 2026: an end-of-day commit for most days, 19 of the 26 release tags (every tag after 11 November) and `71e14a88`, which separates #1519 from #1522. Each was built with its own `make` bootstrap (CPython 3.13 hosting stage 1, LLVM 18.1.3) in a separate worktree and checked at its own fixed point: the first 35 on 12 November, the rest on 18 November.",
        "CPython test methods: today's `tools/cpython_test_methods.py` extracted 9,855 unittest methods from the 144 pinned CPython 3.13.16 test files of `tests/upstream/core-methods.sha256` (hashes verified); 5,905 complete under CPython 3.13.18 and form the denominator. A method passes when the commit's JIT prints CPython's stdout and stderr and exits the same way, including on a retry with promoting ints. The counts at v0.4.0 and v0.5.0 (492 and 500) equal the manual triage in #1303, which used the same harness.",
        "Language and builtins tests are the 60 files that test syntax, builtins and core types (`test_set`, `test_patma`, `test_builtin`, `test_exceptions` and the like); the rest test standard-library modules.",
        "Performance: today's 25 adapted pyperformance ports and the six original microbenchmarks, built AOT by each commit and run pinned to one CPU on an otherwise idle 4-vCPU x86-64 VM, every commit interleaved in each repetition with CPython 3.13.18. Ports report pyperf's timed region; microbenchmarks report process wall time. Every run's output must equal CPython's. `unpack_sequence` is left out because AOT removes its timed loop.",
        "Repetitions: all 48 commits timed together in one run on 18 November, five runs per port and seven per microbenchmark at every commit, medians reported. Between a benchmark's second-fastest and second-slowest run the spread was typically 1–10% (up to about 25% for the shortest programs), so index changes under about 5% are within noise.",
        f"The core set is the {len(core)} ports whose output matched at every sampled commit since the first one with ten working ports (15 October): {', '.join(core)}.",
        "Compile time: `pystachy build` of nbody (day-one), richards and raytrace, two runs each pinned to one CPU; JIT end-to-end runs of the six day-one programs with the program cache off and a warm runtime cache.",
        "Causes are assigned from the text of the first compiler error. A method needs every blocker removed, and only the first is visible, so the categories show what is in front, not everything that remains.",
        "Bisection (first edition): `float` over the 7 first-parent merges between Nov 10 and alpha.5, and `words` over the 15 between Oct 17 and Oct 18, timing each probe 9 times pinned to one CPU. On 18 November both were re-timed 15 times at the bisected endpoints, the first edition's last commit, the fixes and the latest commit.",
    ]:
        w(f"- {line}")
    w("")
    w("## Data\n")
    w("Every chart and table above comes from these files in `data/` (JSON as charted, CSV for spreadsheets):\n")
    w(table(["File", "What it holds"], [[f"`{s['id']}`", f"**{s['title']}.** {s['description']}"] for s in sources]
            + [["`perf_index`", "**Performance index per commit.** The core and micro indices above, computed from `speedups` (CSV only)."]]) + "\n")

    w("## Appendix: every sampled commit\n")
    w(table(["Date", "Release", "Commit", "Methods", "Language", "Library", "Differs", "Ports", "Upstream", "Micro", "Core",
             "Blocked: library", "syntax", "typing", "dynamic", "other"],
            [[day(s["date"]), s["release"] or "—", f"`{s['sha']}`", s["methods_pass"], s["pass_language"], s["pass_library"],
              s["compiled_but_differs"], s["ports_working"], s["upstream_compiled"], fx(ix[s["label"]]["micro_index"]),
              fx(ix[s["label"]]["core_index"]), s["blocked_library"], s["blocked_syntax"], s["blocked_typing"],
              s["blocked_dynamic"], s["blocked_other"]] for s in samples],
            ["l", "l", "l"] + ["r"] * 13) + "\n")
    (out / "report.md").write_text("\n".join(L))
    print("report.md:", len("\n".join(L)), "chars;", len(list((out / "data").iterdir())), "data files")


if __name__ == "__main__":
    main()
