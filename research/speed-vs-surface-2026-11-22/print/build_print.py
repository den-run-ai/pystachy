"""Build the print edition of the report: one topic per A4 page, charts drawn by charts.js.

usage: python3 build_print.py OUT.html [EVIDENCE_SHA]
Reads print/data.json (prepare.py) and d3 from the dashboard's node_modules.
Third edition (22 November 2026): all 56 samples timed in one run; progress is reported against the
second edition (v0.6.0-alpha.1, 17 November) and the first (main 8434a911, 12 November).
"""
import html
import json
import sys
from datetime import datetime
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
V = S / "v3"
D = json.load(open(V / "print/data.json"))
EVIDENCE_SHA = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
FOLDER = "research/speed-vs-surface-2026-11-22"

rows = sorted(D["samples"], key=lambda r: r["date"])
by = {r["label"]: r for r in rows}
first, head = rows[0], rows[-1]
rep = by[D["report_label"]]                      # main 8434a911, the first edition's last measurement (12 Nov)
prev = by[D["prev_label"]]                       # v0.6.0-alpha.1 3cf23d20, the second edition's (17 Nov)
a5 = by["1111-1528_b2182a4f"]
a2 = next(r for r in rows if r["release"] == "v0.1.0-alpha.2")
v50 = next(r for r in rows if r["release"] == "v0.5.0")
v60 = next(r for r in rows if r["release"] == "v0.6.0")
a2_50 = next(r for r in rows if r["release"] == "v0.5.0-alpha.2")
pre_aot = next(r for r in rows if r["release"] == "v0.5.0-alpha.1")
a2_60 = next(r for r in rows if r["release"] == "v0.6.0-alpha.2")
a3_60 = next(r for r in rows if r["release"] == "v0.6.0-alpha.3")
a1_70 = next(r for r in rows if r["release"] == "v0.7.0-alpha.1")
core_first = next(r for r in rows if r["core"] is not None)
new = [r for r in rows if r["date"] > prev["date"]]
P, P1 = D["progress"], D["progress_first"]       # 17 Nov -> head, 12 Nov -> head
G, G0, G1 = D["groups"], D["groups_prev"], D["groups_report"]
rejected = sum(head["blocked"].values())
rejected_prev = sum(prev["blocked"].values())
lang_rej = sum(head["lang_blocked"].values())

esc = html.escape


def n(v, d=0):
    return "—" if v is None else f"{v:,.{d}f}"


def pct(a, b, d=0):
    return f"{100 * a / b:.{d}f}%"


def day(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%-d %b")


def table(head_, body, cls="", num=()):
    th = "".join(f'<th class="{"num" if i in num else ""}">{h}</th>' for i, h in enumerate(head_))
    trs = "".join("<tr>" + "".join(f'<td class="{"num" if i in num else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                  for r in body)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


def gsum(groups, need):
    return sum(g["methods"] for g in groups if g["need"] == need)


def gname(groups, prefix):
    return next((g for g in groups if g["name"].startswith(prefix)), {"methods": 0, "language": 0, "files": 0})


lib_h, comp_h, refl_h = gsum(G, "library"), gsum(G, "compile"), gsum(G, "reflect")
lib_p, comp_p, refl_p = gsum(G0, "library"), gsum(G0, "compile"), gsum(G0, "reflect")
field_h, field_p = gname(G, "field"), gname(G0, "field")
local_h, local_p = gname(G, "local classes"), gname(G0, "local classes")
enum_p, enumf_h = gname(G0, "enum."), gname(G, "enum classes made")
second_h, nested_h = gname(G, "secondary bases"), gname(G, "nested classes after")
pickle_h, generic_h = gname(G, "pickle"), gname(G, "inheritance from generic")
builtin_h, match_h = gname(G, "builtin base"), gname(G, "match patterns")
gc_p, inspect_p = gname(G0, "gc module"), gname(G0, "inspect")
empty_h, empty_p = gname(G, "empty containers"), gname(G0, "empty containers")
evalx_h, values_h = gname(G, "eval /"), gname(G, "modules or classes as values")
rt = D["retime"]
fl, wd, fb = rt.get("float", {}), rt.get("micro_words", {}), rt.get("micro_fib", {})
BI = {r["label"]: r for r in (D.get("bootstrap_idle") or {}).get("runs", []) if r.get("ok")}
AG = D.get("agreement") or {}


def ms(res, lab):
    return res[lab]["median_ms"] if lab in res else None


HEADL = D["head_label"]
build_drop = pre_aot["nbody_build"] / a2_50["nbody_build"]
ev = f"https://github.com/den-run-ai/pystachy/blob/{EVIDENCE_SHA}/{FOLDER}"
grow_c = head["compiler_lines"] / prev["compiler_lines"] - 1
grow_ir = head["ir"] / prev["ir"] - 1


# ---------- figures the text quotes ----------
def sp_at(lab, b):
    return next((r["speedup"] for r in D["speedups"] if r["label"] == lab and r["benchmark"] == b), None)


def change(b, a_lab, b_lab):
    x, y = sp_at(a_lab, b), sp_at(b_lab, b)
    return y / x - 1 if x and y else None


MICRO_CH = {b: change(b, first["label"], HEADL) for b in D["micro"]}
PREV_CH = {b: change(b, prev["label"], HEADL) for b in D["core"] + D["micro"]}
PREV_CH = {b: v for b, v in PREV_CH.items() if v is not None}
movers = sorted(PREV_CH.items(), key=lambda kv: -abs(kv[1]))
mi = [r["micro"] for r in rows if r["micro"] is not None]
co_after = [r["core"] for r in rows if r["core"] is not None and r["date"] >= a2["date"]]
o18, o19 = by["1018-1740_bb5ac4ab"], by["1019-2327_b040f45e"]
regex_gain = [sp_at(o19["label"], b) / sp_at(o18["label"], b) for b in ("regex_dna", "regex_effbot", "regex_v8")]
fl_rep, fl_rc1 = sp_at(rep["label"], "float"), sp_at("1112-1351_30822255", "float")
exe = {lab: json.load(open(S / f"results/perfprep-{lab}.json"))["micro_nbody"]["exe_bytes"]
       for lab in (pre_aot["label"], a2_50["label"], prev["label"], HEADL)}


def bname(b):
    return f"<code>{b.replace('micro_', '')}</code>"


def signed(v, d=0):
    return f"{100 * v:+.{d}f}%".replace("-", "−")


words_gap = 100 * (ms(wd, HEADL) / ms(wd, "bis_6d4ed3d117") - 1)
words_gap_prev = 100 * (ms(wd, prev["label"]) / ms(wd, "bis_6d4ed3d117") - 1)
fib_gap = 100 * (ms(fb, HEADL) / ms(fb, pre_aot["label"]) - 1)
recent = [prev] + new
rc_core = [r["core"] for r in recent if r["core"] is not None]
rc_micro = [r["micro"] for r in recent if r["micro"] is not None]
ag_core, ag_micro = (AG.get("core_index") or {}), (AG.get("micro_index") or {})

# ---------- page 1: summary ----------
glance = table(
    ["", "First day<br>8 Oct", "v0.1.0-alpha.2<br>20 Oct", "First edition<br>12 Nov", "Second edition<br>17 Nov",
     "v0.7.0-alpha.2<br>21 Nov"],
    [
        ["CPython test methods passing (of 5,905)", first["methods"], a2["methods"], rep["methods"], prev["methods"], head["methods"]],
        ["Language and builtins methods (of 2,445)", first["language"], a2["language"], rep["language"], prev["language"], head["language"]],
        ["Unmodified pyperformance files compiling (of 52)", first["upstream"], a2["upstream"], rep["upstream"], prev["upstream"], head["upstream"]],
        ["Microbenchmark speed index (× CPython)", n(first["micro"], 1), n(a2["micro"], 1), n(rep["micro"], 1), n(prev["micro"], 1), n(head["micro"], 1)],
        ["Core ports speed index (× CPython)", "—", n(a2["core"], 1), n(rep["core"], 1), n(prev["core"], 1), n(head["core"], 1)],
        ["AOT build of nbody (s)", n(first["nbody_build"], 2), n(a2["nbody_build"], 2), n(rep["nbody_build"], 2), n(prev["nbody_build"], 2), n(head["nbody_build"], 2)],
        ["Compiler source (thousand lines)", n(first["compiler_lines"] / 1000, 1), n(a2["compiler_lines"] / 1000, 1), n(rep["compiler_lines"] / 1000, 1),
         n(prev["compiler_lines"] / 1000, 1), n(head["compiler_lines"] / 1000, 1)],
    ], cls="glance", num=(1, 2, 3, 4, 5))

contents = [("2", "Progress since 17 November"), ("3", "Recommendations and issues"), ("4", "What was measured"),
            ("5", "Speed against surface"), ("6", "Surface over time"), ("7", "Speed over time"),
            ("8", "Speed by benchmark"), ("9", "Runtime regressions"), ("10", "Compile cost"),
            ("11", "Remaining blockers"), ("12", "Removing one blocker"), ("13", "Porting or compiler work"),
            ("14", "Data per commit")]
toc = "".join(f"<li><span>{p}</span>{esc(t)}</li>" for p, t in contents)

p1 = f"""
<section class="page" id="summary">
  <p class="eyebrow">Pystachy research report · third edition, 22 November 2026</p>
  <h1 class="title">Speed and Python surface across Pystachy's history</h1>
  <p class="lead">From 8 October to 21 November 2026, the share of CPython's own unit tests that Pystachy runs
  without hand edits rose from 0.3% to {pct(head['methods'], 5905, 1)}. In the four days since the second edition of
  this report, passing tests rose from {prev['methods']} to {head['methods']}, none was lost, and the compiler grew by
  {100 * grow_c:.0f}%.</p>
  {glance}
  <p>Three changes made {21 + 12 + 7} of the {P['gained']} new passes: classes defined inside functions that run once
  (#1613, 21 methods), the <code>gc</code> module (#1351, 12) and <code>enum</code>'s missing names (#1563, 7). Since the
  first edition (12 November), passing methods rose from {rep['methods']} to {head['methods']}.</p>
  <p>Run-time speed held: the microbenchmark index was {first['micro']:.1f}× CPython on the first day,
  {prev['micro']:.1f}× on 17 November and {head['micro']:.1f}× at v0.7.0-alpha.2; the core ports' index
  {core_first['core']:.1f}× (15 October), {prev['core']:.1f}× and {head['core']:.1f}×. <code>float</code>'s fix holds, and
  <code>words</code> is {words_gap:.0f}% slower than before #667 on this run's host (#1301).</p>
  <p>The compiler grew from {prev['compiler_lines']:,} to {head['compiler_lines']:,} lines and its own IR by
  {100 * grow_ir:.0f}%. Rebuilt one at a time on an idle machine, the bootstrap took {n(BI.get(rep['label'], {}).get('wall_s'))} s
  at the first edition's commit, {n(BI.get(prev['label'], {}).get('wall_s'))} s at the second's and
  {n(BI.get(HEADL, {}).get('wall_s'))} s at v0.7.0-alpha.2, partly because three variables in the compiler that hold two
  types each make its own source compile in three inference passes instead of one (page 10).</p>
  <p>Of the {rejected:,} methods still rejected, {pct(lib_h, rejected)} need a missing module or name, down from
  {pct(lib_p, rejected_prev)} on 17 November, and {pct(comp_h, rejected)} a class-model, inference or
  <code>match</code> feature. Field and class-attribute types now stop the most ({field_h['methods']} methods).</p>
  <ol class="toc">{toc}</ol>
</section>"""

# ---------- page 2: progress since the second edition ----------
prog_rows = [prev] + new
prog = table(["Date", "Release", "Commit", "Methods", "Language", "Core ×", "Micro ×", "nbody build (s)", "Bootstrap (s)"],
             [[day(r["date"]), esc(r["release"] or "—"), f"<code>{r['sha']}</code>", r["methods"],
               r["language"], n(r["core"], 2), n(r["micro"], 2), n(r["nbody_build"], 2), n(r["bootstrap"])]
              for r in prog_rows], cls="compact", num=(3, 4, 5, 6, 7, 8))
SOURCES = [
    ["Classes defined inside functions that run at most once", "#1613 · v0.7.0-alpha.1", "21 (11 files)"],
    ["The <code>gc</code> module", "#1351 · v0.6.0-alpha.3", "12 (<code>test_dict</code>, <code>test_tuple</code>, <code>test_weakref</code>)"],
    ["<code>enum.member</code> and <code>enum</code>'s private helpers", "#1563 · v0.7.0-alpha.1", "7 (<code>test_enum</code>)"],
    ["<code>bytearray</code>", "#1478 · v0.6.0-alpha.3", "2 (<code>test_bytes</code>, <code>test_copy</code>)"],
    ["Fixes among the 40 pull requests of #1546", "v0.6.0-alpha.2", "3 (<code>test_bool</code>, <code>test_format</code>, <code>test_set</code>)"],
]
sources = table(["Change", "Pull request · release", "Methods"], SOURCES, cls="compact sources")
p2 = f"""
<section class="page" id="progress">
  <p class="eyebrow">Progress</p>
  <h1>What changed since 17 November</h1>
  <p class="lead">In four days main took 886 commits and eight release tags, which carried 139 pull requests. Passing
  methods rose from {prev['methods']} to {head['methods']}: {P['gained_language']} of the {P['gained']} new passes are
  language and builtins tests and {P['gained'] - P['gained_language']} library tests.</p>
  {prog}
  <p class="note">All eight tags from v0.6.0-alpha.2 to v0.7.0-alpha.2, and the second edition's v0.6.0-alpha.1. Speed
  and build times: one run of all 56 samples on 22 November. Bootstrap: built on 22 November beside the previous
  commit's test sweep, except v0.6.0-alpha.1 (18 November).</p>
  <h2>Where the {P['gained']} new passes came from</h2>
  {sources}
  <p>No method that passed on 17 November fails now. One <code>test_random</code> method passes or fails at random
  at every commit, because with promoting integers <code>randrange()</code> overflows 64 bits for most seeds; it is counted
  as measured, so the count can move by one between neighbouring commits. With it set aside, this harness gives the
  project's own counts exactly: 641 at v0.6.0-alpha.2 (#1560) and 683 at v0.7.0-alpha.1 (draft #1673).</p>
  <p>Most of the week's surface work moved first errors rather than passes. <code>test_enum</code>'s
  {enum_p['methods']} methods got past their import: 7 pass, and most of the rest stop at a class attribute's type, an
  enum class made at run time or a secondary base. Library-blocked rejections fell from {lib_p:,} to {lib_h:,}.
  Nine of the 52 unmodified pyperformance files compile, against seven on 17 November (<code>gc_collect</code> and
  <code>pprint</code>), and all 31 benchmark workloads match CPython in AOT and JIT at every new commit.</p>
</section>"""

# ---------- page 3: recommendations and issue status ----------
STATUS = [
    ["#1300", "<code>float</code> slower by 37% after #1268", "Closed. Fixed by #1336 in v0.4.0-rc.1"],
    ["#1301", "<code>words</code> slower by 22% after #667", "Open. #1518 cut its instructions by 2.8%; the larger heap remains"],
    ["#1302", "Weekly timing of every benchmark", "Closed. The weekly workflow (#1339) has run once, on 16 November; results stay in CI artifacts"],
    ["#1303", "Method triage and build cost per release", "Open. Counts for two releases (#1560, draft #1673); no tool or release step on main"],
    ["#1304", "Classes defined inside functions", f"Open. #1613 (v0.7.0-alpha.1) covers functions that run once: 21 pass, {local_h['methods']} still stop there"],
    ["#1305", "Mapping, starred and class patterns", f"Open. Mapping and class patterns still rejected ({match_h['methods']} methods); no pull request"],
    ["#1306", "Rank surface work by measured unlocks", "Closed as a duplicate; #1560 now plans 0.7.0 from measured blockers"],
    ["#706", "AOT build cost", "Closed. The precompiled runtime (#1377) landed in v0.5.0-alpha.2"],
    ["#1181", "GC-stressed self-compilation", "Open. 590 s of its 600 s bound at v0.7.0-alpha.1; collections widened from every 5,000 to 7,000 allocations"],
]
status = table(["Issue", "Filed for", "Status on 22 November"], STATUS, cls="issues compact")
p3 = f"""
<section class="page" id="recommendations">
  <p class="eyebrow">Decision</p>
  <h1>Recommendations and the issues filed</h1>
  <p class="lead">Most of the second edition's recommendations were taken up within four days: <code>gc</code>, the
  <code>enum</code> names and the first form of local classes landed, and per-release counts exist in drafts. The
  tests now stop at compiler features, so the next gains depend on inference and the class model.</p>
  <ol class="recs">
    <li>Infer the types of class attributes and fields: they stop {field_h['methods']} methods first, up from
    {field_p['methods']}, because {field_h['methods'] - field_p['methods']} <code>test_enum</code> and other methods now get
    that far. Draft #1686 infers enum classes stored in class attributes.</li>
    <li>Extend builtin base classes beyond <code>list</code> and <code>dict</code> (#1558) to <code>set</code>,
    <code>frozenset</code> and <code>str</code> ({builtin_h['methods']} methods, mostly <code>test_set</code>), and accept
    generic class templates as bases ({generic_h['methods']}, #962).</li>
    <li>Finish classes inside functions (#1304): {local_h['methods']} methods still stop at classes in functions that
    run more than once or whose methods read the function's variables.</li>
    <li>Support enum classes made at run time, with mixins or from <code>ReprEnum</code> ({enumf_h['methods']} methods),
    and <code>super()</code> in methods of secondary bases ({second_h['methods']}).</li>
    <li>Land the per-release count on main (#1303): drafts #1673 and #1685 exist, and this harness reproduces their
    641 and 683.</li>
    <li>Remove the compiler's own inference restarts: renaming three variables that hold two types brings its
    source back to one pass, halving the frontend and saving about 50 s of every bootstrap (page 10). A check that
    the compiler compiles itself in one pass would keep it so; the GC-stressed self-compilation fits its bound only
    since its collection interval was widened (#1181).</li>
    <li>Leave <code>eval</code>, <code>exec</code>, <code>pickle</code> and frame introspection to embedded CPython
    (#170), as before.</li>
  </ol>
  <h2>Status of the issues this report filed or relied on</h2>
  {status}
</section>"""

# ---------- page 4: method ----------
workloads = table(["Workload", "Inputs", "Counts as passing"], [
    ["CPython test methods",
     "9,855 unittest methods extracted by <code>tools/cpython_test_methods.py</code> from 144 pinned CPython 3.13.16 test "
     "files; the 5,905 that complete under CPython 3.13.18 are the denominator, 2,445 of them in 60 language and builtins "
     "files",
     "<code>pystachy run</code> (JIT) prints CPython's stdout and stderr and exits with the same status; a retry with "
     "promoting integers is allowed"],
    ["Unmodified pyperformance", "The 52 <code>run_benchmark.py</code> files of pyperformance 1.14.0, with pyperf's runner "
     "replaced", "<code>pystachy ir</code> compiles the file"],
    ["Adapted benchmarks", "The 25 ports in <code>bench/pyperformance</code> at <code>b2182a4f</code> and the six day-one "
     "<code>bench/*.py</code> microbenchmarks, the same for every commit", "AOT output equals CPython's; then timed"],
], cls="method")

p4 = f"""
<section class="page" id="method">
  <p class="eyebrow">Method</p>
  <h1>What was measured</h1>
  <p class="lead">Each sampled commit was built from source and given the same fixed inputs: CPython's unit tests,
  pyperformance's benchmark files and fixed timed programs.</p>
  <h2>Commits</h2>
  <p>The history covers {len(rows)} commits on main from 8 October to 21 November 2026 (UTC): the last commit of
  most days and 27 of the 34 release tags, every tag after 11 November included. Each was built in its own worktree by
  its own <code>make</code> bootstrap (CPython 3.13.18 hosting stage 1, LLVM 18.1.3): the first 35 on 12 November,
  13 on 18 November and the last 8 on 22 November.</p>
  <h2>Workloads</h2>
  {workloads}
  <p>The speed index is the geometric mean of per-benchmark speedups, where a speedup is CPython's time divided by
  Pystachy's AOT time on the same source. It uses a fixed set: the six microbenchmarks, or the {len(D['core'])} ports
  that worked at every sample from 15 October; <code>unpack_sequence</code> is excluded because AOT removes its timed
  loop. The inputs are frozen copies, identical for every commit.</p>
  <h2>Timing</h2>
  <p>All {len(rows)} samples were timed in one run on 22 November on an otherwise idle 4-vCPU x86-64 VM, each
  executable pinned to one CPU. Every repetition ran CPython 3.13.18 and all commits in an order rotated by one
  position, checking every output. Values are medians of 5 runs (ports: pyperf's timed region) or 7 (microbenchmarks:
  wall time); JIT and build times are medians of 3 runs after an untimed one.</p>
  <h2>Classifying rejections</h2>
  <p>A rejected method is classified by its first compiler error: library (a missing module or name), syntax,
  typing (inference needs an annotation), dynamic (Python's dynamic class model and reflection) or other. Page 11
  regroups the same errors by what removing them needs. New rules cover messages first seen after 17 November;
  earlier samples classify as before.</p>
  <h2>Limits</h2>
  <p>Only a method's first error is visible, so first-error counts overstate what one fix unlocks (page 12). One
  <code>test_random</code> method passes at random (page 2). Pipeline bootstraps ran beside another commit's test sweep
  on three days; only page 10's idle rebuilds compare directly.</p>
</section>"""

# ---------- page 5: speed against surface ----------
p5 = f"""
<section class="page" id="trajectory">
  <p class="eyebrow">Central result</p>
  <h1>Speed against Python surface</h1>
  <p class="lead">Passing CPython test methods grew from {first['methods']} to {head['methods']} while
  both speed indices held or rose: at the level of the index, the added surface did not cost run-time speed.</p>
  <figure><div id="fig-trajectory"></div>
  <figcaption>One point per sampled commit, joined in date order. Blue: the six day-one microbenchmarks; orange: the
  {len(D['core'])} pyperformance ports that worked at every sample from 15 October.</figcaption></figure>
  <p>The microbenchmark index stayed between {min(mi):.1f}× and {max(mi):.1f}× at every sample, while passing
  methods went from {first['methods']} to {head['methods']}. Individual microbenchmarks moved in both directions over
  the whole history: <code>words</code> {signed(MICRO_CH['micro_words'])} and <code>fib</code> {signed(MICRO_CH['micro_fib'])},
  <code>nbody</code> {signed(MICRO_CH['micro_nbody'])} and <code>sieve</code> {signed(MICRO_CH['micro_sieve'])}.</p>
  <p>The core index rose from {core_first['core']:.1f}× to {o19['core']:.1f}× between 15 and 19 October, during the
  largest early surface gains; most of that rise came from <code>lib/re</code> work that made the three regex ports
  {min(regex_gain):.1f} to {max(regex_gain):.1f} times faster (page 8). The later surface steps, bounded
  <code>match</code>, v0.6.0-alpha.1's inference and the local classes, <code>gc</code> and <code>enum</code> names of
  18 to 20 November, left both indices where they were.</p>
  <p>The index is a geometric mean, so it hides changes in single benchmarks (pages 8 and 9), and it measures run
  time only; compile time is on page 10.</p>
</section>"""

# ---------- page 6: surface over time ----------
REL_SHOWN = ["v0.1.0-alpha.1", "v0.1.0-alpha.2", "v0.2.0", "v0.4.0-alpha.5", "v0.4.0",
             "v0.5.0", "v0.6.0-alpha.1", "v0.6.0-alpha.3", "v0.6.0", "v0.7.0-alpha.1", "v0.7.0-alpha.2"]
rel = [r for r in rows if r["release"] in REL_SHOWN or r is rep]
rel_table = table(["Release", "Date (UTC)", "Methods passing", "Language and builtins", "Library", "Ports working",
                   "Unmodified files"],
                  [[esc(r["release"]) if r is not rep else "main <code>8434a911</code>", day(r["date"]),
                    r["methods"], r["language"], r["library"], r["ports"], r["upstream"]] for r in rel],
                  cls="compact", num=(2, 3, 4, 5, 6))
cs = D["change_shares"]
k1, k2, k3, k4 = list(cs)


def share(k, a):
    return f"{100 * cs[k]['share'].get(a, 0):.0f}%"


p6 = f"""
<section class="page" id="surface">
  <p class="eyebrow">Surface</p>
  <h1>Python surface over time</h1>
  <p class="lead">Passing methods grew by about 26 a day for two weeks and by 26 in total over the next three. Since
  then three steps added most of the gain: bounded <code>match</code> by 12 November (+95), v0.6.0-alpha.1 on
  17 November (+138) and the <code>gc</code> module, local classes and <code>enum</code> names of 18 to 20 November
  (+40).</p>
  <figure><div id="fig-surface"></div>
  <figcaption>CPython test methods that compile and match CPython's output, per sampled commit; 5,905 methods in
  total, 2,445 of them in language and builtins test files.</figcaption></figure>
  {rel_table}
  <p class="note">Selected releases; page 14 lists every sample.</p>
  <p>The steps came from compiler and library work. From 20 October to 11 November the compiler's share of changed
  lines was {share(k2, 'compiler')} and the library's {share(k2, 'library')}; benchmarks and examples took
  {share(k2, 'bench/examples')}. From 18 to 21 November the compiler's share was {share(k4, 'compiler')} and the
  library's {share(k4, 'library')}, while tests took {share(k4, 'tests')}, benchmarks {share(k4, 'bench/examples')} and
  tools and CI {share(k4, 'tools/CI')}.</p>
  <p>Library tests moved for the first time since October: {a2['library']} methods passed at alpha.2,
  {prev['library']} on 17 November and {head['library']} now, through <code>gc</code>, <code>bytearray</code> and the
  local classes that library tests define.</p>
</section>"""

# ---------- page 7: speed over time ----------
def pick(prefix):
    return next(r for r in rows if r["label"].startswith(prefix))


sel = [("First day", first), ("First core sample", core_first), ("After lib/re work", pick("1019")),
       ("v0.1.0-alpha.2", a2), ("First edition (main)", rep), ("v0.4.0-rc.1 (float fix)", pick("1112-1351")),
       ("v0.5.0-alpha.2 (precompiled runtime)", a2_50), ("Second edition (v0.6.0-alpha.1)", prev),
       ("v0.6.0-alpha.3 (float fast paths)", a3_60), ("v0.6.0", v60), ("v0.7.0-alpha.2", head)]
speed_table = table(["Sample", "Date (UTC)", "Commit", "Core index", "Microbenchmark index"],
                    [[esc(k), day(r["date"]), f"<code>{r['sha']}</code>", n(r["core"], 2), n(r["micro"], 2)]
                     for k, r in sel], cls="compact", num=(3, 4))
p7 = f"""
<section class="page" id="speed">
  <p class="eyebrow">Speed</p>
  <h1>Speed over time</h1>
  <p class="lead">The core index rose from {core_first['core']:.1f}× to {o19['core']:.1f}× CPython
  between 15 and 19 October and has stayed between {min(co_after):.1f}× and {max(co_after):.1f}× since; the
  microbenchmark index stayed near 18×.</p>
  <figure><div id="fig-speed"></div>
  <figcaption>Geometric mean of AOT speedups over CPython 3.13 per sampled commit, all timed in one run on
  22 November.</figcaption></figure>
  {speed_table}
  <p>Since the second edition both indices moved within noise: the core index from {prev['core']:.2f} to
  {head['core']:.2f} and the microbenchmark index from {prev['micro']:.2f} to {head['micro']:.2f}. The nine samples
  from 17 to 21 November range from {min(rc_core):.2f} to {max(rc_core):.2f} and from {min(rc_micro):.2f} to
  {max(rc_micro):.2f}. Single benchmarks are noisier than the indices: v0.6.0-rc.2 and v0.6.0 build byte-identical
  <code>sieve</code> executables, whose medians differ by 22% in this run.</p>
  <p>This run's indices are lower than the second edition's for the same {AG.get('commits', 48)} commits, by
  {-100 * ag_core.get('mean', 0):.0f}% on average for the core index and {-100 * ag_micro.get('mean', 0):.0f}% for the microbenchmark
  index (at most {100 * ag_core.get('max_abs', 0):.0f}%): the two runs used different hosts, on which CPython itself took
  6% longer for <code>float</code>. Compare indices within one edition. Within this run, fixing <code>float</code> in
  v0.4.0-rc.1 raised its speedup from {fl_rep:.1f}× to {fl_rc1:.1f}×, and <code>fib</code> has run about
  {fib_gap:.0f}% slower since v0.5.0-alpha.2, a code-placement effect that #1377's evaluation traced to identical code
  at a different address.</p>
</section>"""

# ---------- page 8: speed by benchmark ----------
CH = D["changes"]
changes = table(["Benchmark", "Interval", "Time (ms)", "Cause", "Evidence"],
                [[f"<code>{c['benchmark']}</code>", c["interval"], c["time"], c["cause"], c["evidence"]] for c in CH],
                cls="compact changes", num=(2,))
sp_head = {r["benchmark"]: r["speedup"] for r in D["speedups"] if r["label"] == HEADL}
slow = sorted((v, b) for b, v in sp_head.items() if v < 2)
fast = max((v, b) for b, v in sp_head.items())
p8 = f"""
<section class="page" id="benchmarks">
  <p class="eyebrow">Speed</p>
  <h1>Speed by benchmark</h1>
  <p class="lead">Most ports kept the speed they reached in mid-October. The largest changes are the
  <code>lib/re</code> work of 19 October and the two regressions. Since 17 November only <code>chaos</code> moved
  beyond noise: {ms(rt['chaos'], '1117-2325_e2b97bb4'):.1f} ms at v0.6.0-alpha.2 and {ms(rt['chaos'], '1118-1050_8259611e'):.1f} ms at
  alpha.3, whose float fast paths removed its <code>trunc()</code> calls (#1437).</p>
  <div class="legend">
    <span><i style="background:#d03b3b;opacity:1"></i>¼× CPython</span><span><i style="background:#d03b3b;opacity:.55"></i>½×</span>
    <span><i style="background:#2a78d6;opacity:.1;outline:1px solid #e2e0da"></i>1×</span><span><i style="background:#2a78d6;opacity:.4"></i>4×</span>
    <span><i style="background:#2a78d6;opacity:.7"></i>16×</span><span><i style="background:#2a78d6;opacity:1"></i>64× or more</span>
    <span><i class="empty"></i>did not build, or output differed</span>
  </div>
  <figure><div id="fig-heatmap"></div>
  <figcaption>AOT speedup over CPython 3.13 per benchmark (rows: microbenchmarks, then ports by speedup at
  v0.7.0-alpha.2) and sampled commit (columns). Each row's source is fixed, so a change along a row is a compiler or
  library change.</figcaption></figure>
  {changes}
  <p>At v0.7.0-alpha.2 speedups range from {slow[0][0]:.2f}× (<code>{slow[0][1]}</code>) to {fast[0]:.0f}×
  (<code>{fast[1].replace('micro_', '')}</code>); the {len(slow)} ports under 2× spend their time in library and runtime code.</p>
</section>"""

# ---------- page 9: regressions ----------
def cell(res, lab, sub=""):
    v = ms(res, lab)
    return "—" if v is None else f"{v:.2f} ms" + (f"<br><span class='sub'>{sub}</span>" if sub else "")


reg = table(["Benchmark", "Before", "At the change", "After the fix", "17 Nov", "21 Nov", "CPython 3.13"], [
    ["<code>float</code> (port)", cell(fl, "bis_0ec827ac34", "0ec827ac"), cell(fl, "bis_b40ee875bf", "#1268"),
     cell(fl, "1112-1351_30822255", "#1336, rc.1"), cell(fl, prev["label"]), cell(fl, HEADL), f"{ms(fl, 'cpython') or 0:.1f} ms"],
    ["<code>words</code> (micro)", cell(wd, "bis_6d4ed3d117", "6d4ed3d1"), cell(wd, "bis_a355c83ff7", "#667"),
     cell(wd, "1112-2100_bf699eb5", "#1332, RC.2"), cell(wd, prev["label"]), cell(wd, HEADL), f"{ms(wd, 'cpython') or 0:.1f} ms"],
    ["<code>fib</code> (micro)", cell(fb, pre_aot["label"], "v0.5.0-alpha.1"), cell(fb, a2_50["label"], "#1377"),
     "—", cell(fb, prev["label"]), cell(fb, HEADL), f"{ms(fb, 'cpython') or 0:.1f} ms"],
], cls="compact", num=(1, 2, 3, 4, 5, 6))
p9 = f"""
<section class="page" id="regressions">
  <p class="eyebrow">Speed</p>
  <h1>The runtime regressions</h1>
  <p class="lead"><code>float</code> is fixed: since v0.4.0-rc.1 it runs as fast as before #1268. <code>words</code>
  is {words_gap:.0f}% slower than before #667 in this run, and <code>fib</code> about {fib_gap:.0f}% slower than before
  #1377.</p>
  {reg}
  <p class="note">AOT executables, medians of 15 interleaved runs pinned to one CPU on 22 November. "Before" is the
  regressing merge's first parent. <code>float</code> reports pyperf's timed region; <code>words</code> and
  <code>fib</code> report process wall time.</p>
  <h2><code>float</code>: fixed by #1336</h2>
  <p>#1268's listguard pass copied the loop <code>for i in range(n): points[i] = Point(i)</code> into a checked and an
  unchecked version, so the constructor <code>Point.__init__</code> gained a second call site and LLVM stopped
  inlining it. #1336 marks a call that a loop copy duplicates as <code>alwaysinline</code> and counts the callee's
  size toward listguard's code-growth limit. In the 15-run comparison the port took {ms(fl, 'bis_0ec827ac34'):.1f} ms
  before #1268, {ms(fl, '1112-1351_30822255'):.1f} ms after the fix, {ms(fl, prev['label']):.1f} ms on 17 November and
  {ms(fl, HEADL):.1f} ms at v0.7.0-alpha.2.</p>
  <h2><code>words</code>: partly fixed</h2>
  <p>After #667, <code>w.upper().startswith("L")</code> counted the code points of every fresh string. #1332 skips that
  count for whole-string <code>startswith</code> and <code>endswith</code>, and #1518 (v0.6.0-alpha.2 and alpha.3) reads
  the Unicode tables directly, which cut the benchmark's instructions by 2.8% on its author's host. In the 15-run
  comparison <code>words</code> takes {ms(wd, HEADL):.1f} ms at v0.7.0-alpha.2, against {ms(wd, 'bis_6d4ed3d117'):.1f} ms
  before #667 and {ms(wd, prev['label']):.1f} ms at v0.6.0-alpha.1. The gap depends on the host: v0.6.0-alpha.1 was
  {words_gap_prev:.0f}% slower than before #667 in this run and 19% in the second edition's. The heap peak that grew
  from 34.9 MiB to 59.1 MiB at #667, with two collections instead of one, has not been addressed (#1301).</p>
  <h2>Detection</h2>
  <p>The weekly performance workflow (#1339, closing #1302) has still run only once, on 16 November; its next run is
  due on 23 November and will time 38 ports. The per-push performance smoke flagged no slowdown in its nine complete
  runs on main in the window; its run for v0.6.0-alpha.2 failed because that compiler's self-build exceeded the
  smoke's time budget (#1547).</p>
</section>"""

# ---------- page 10: compile cost ----------
split = table(["AOT build (s)", "First day", "v0.5.0-alpha.1", "v0.5.0-alpha.2", "17 Nov", "21 Nov"], [
    ["nbody (82 lines)", n(first["nbody_build"], 2), n(pre_aot["nbody_build"], 2), n(a2_50["nbody_build"], 2), n(prev["nbody_build"], 2), n(head["nbody_build"], 2)],
    ["richards", "—", n(pre_aot["richards_build"], 2), n(a2_50["richards_build"], 2), n(prev["richards_build"], 2), n(head["richards_build"], 2)],
    ["raytrace", "—", n(pre_aot["raytrace_build"], 2), n(a2_50["raytrace_build"], 2), n(prev["raytrace_build"], 2), n(head["raytrace_build"], 2)],
], cls="compact", num=(1, 2, 3, 4, 5))
SC = (D.get("selfcompile") or {}).get("results", {})


def sc(lab, key):
    runs = [x["wall_s"] for x in SC.get(lab, {}).get(key, []) if x.get("ok")]
    return min(runs) if runs else None


idle_rows = [[name, n(r["compiler_lines"]), n(r["ir"]), n(BI.get(r["label"], {}).get("wall_s")),
              n(sc(r["label"], "hosted-ir")), n(sc(r["label"], "native-ir"), 1), n(sc(r["label"], "native-build"))]
             for name, r in (("12 Nov, <code>8434a911</code>", rep), ("17 Nov, <code>3cf23d20</code>", prev),
                             ("21 Nov, <code>4998521d</code>", head))]
idle = table(["Idle machine, 22 Nov", "Compiler lines", "Compiler IR lines", "Bootstrap (s)", "Frontend on CPython (s)",
              "Native frontend (s)", "Native build (s)"], idle_rows, cls="compact", num=(1, 2, 3, 4, 5, 6))
br, bp, bh = (BI.get(x, {}).get("wall_s") for x in (rep["label"], prev["label"], HEADL))
p10 = f"""
<section class="page" id="compile">
  <p class="eyebrow">Cost</p>
  <h1>Compile cost</h1>
  <p class="lead">AOT builds of small programs stay cheap since the precompiled runtime (#1377). The bootstrap
  follows the compiler's size, and the compiler grew by {100 * grow_c:.0f}% in four days.</p>
  <figure><div id="fig-cost"></div>
  <figcaption>Left: <code>pystachy build</code> of three fixed programs, pinned to one CPU, medians of three runs
  after an untimed one. Right: the full <code>make</code> bootstrap of each commit, a single build beside another
  commit's test sweep; hollow points were built on 18 or 22 November, the rest on 12 November. Diamonds: the three
  editions' commits rebuilt one at a time on the idle machine on 22 November.</figcaption>
  </figure>
  {split}
  {idle}
  <p>The idle rebuilds compare directly: {n(br)} s for {rep['compiler_lines']:,} compiler lines on 12 November,
  {n(bp)} s for {prev['compiler_lines']:,} on 17 November and {n(bh)} s for {head['compiler_lines']:,} at
  v0.7.0-alpha.2. In the last four days the compiler and its IR grew by {100 * grow_c:.0f}% and {100 * grow_ir:.0f}%, the
  bootstrap by {100 * (bh / bp - 1):.0f}%. The frontend more than doubled, because the compiler's own source now
  compiles in three inference passes instead of one. In three functions one variable holds
  two types (<code>k</code> in <code>driver.compile_program</code> since v0.6.0-alpha.2; <code>known</code> in
  <code>driver.main</code> and <code>x</code>, <code>y</code> in <code>ircheck.gen_verify</code> since v0.7.0-alpha.2),
  and each join restarts the whole program. Renamed in a scratch copy, the source compiled in one pass: the native
  frontend took 6.4 to 7.0 s instead of 12 to 16 s, and on CPython, the bootstrap's first step, 39.7 s instead of 82.8 s.</p>
  <p>The GC-stressed self-compilation that CI runs took 590 s of its 600 s bound at v0.7.0-alpha.1, collecting every
  5,000 allocations; collecting every 7,000 brought it to 412 to 417 s (#1181).</p>
  <p>Since #1377 (v0.5.0-alpha.2) the runtime is compiled once per runtime cache, so an 82-line program builds in
  {n(head['nbody_build'], 2)} s rather than {n(pre_aot['nbody_build'], 2)} s, with a larger executable.</p>
</section>"""

# ---------- page 11: blockers ----------
p11 = f"""
<section class="page" id="blockers">
  <p class="eyebrow">Surface</p>
  <h1>What blocks the remaining tests</h1>
  <p class="lead">At v0.7.0-alpha.2, {rejected:,} of the 5,905 methods are rejected at compile time.
  {pct(lib_h, rejected)} need a missing module or name, {pct(comp_h, rejected)} a class-model, inference or
  <code>match</code> feature that a static compiler can implement, and {pct(refl_h, rejected)} runtime
  reflection.</p>
  <div class="legend">
    <span><i style="background:#2a78d6"></i>Missing module or name</span>
    <span><i style="background:#eb6834"></i>Feature a static compiler can implement</span>
    <span><i style="background:#1baf7a"></i>Runtime reflection</span>
    <span><i style="background:#b9b8b1"></i>Other first errors</span>
  </div>
  <figure><div id="fig-groups"></div>
  <figcaption>First compiler error of each rejected method at v0.7.0-alpha.2 (<code>4998521d</code>), grouped by what
  removing it needs (<code>scripts/groups.py</code>). Other missing stdlib modules include <code>array</code>,
  <code>configparser</code>, <code>_pyio</code>, <code>locale</code>, <code>queue</code> and
  <code>calendar</code>.</figcaption></figure>
  <p>Since 17 November the rejected methods fell from {rejected_prev:,} to {rejected:,}, but the mix changed more than
  the total. Library-blocked methods fell from {lib_p:,} to {lib_h:,}: the <code>enum</code> names ({enum_p['methods']}
  methods), <code>gc</code> ({gc_p['methods']}) and <code>inspect</code> ({inspect_p['methods']}) no longer stop any.
  Compiler-feature blockers rose from {comp_p:,} to {comp_h:,}, because the same methods now reach class attributes
  ({field_p['methods']} → {field_h['methods']}), enum classes made at run time ({enumf_h['methods']}), nested classes
  after a call ({nested_h['methods']}) and secondary bases ({second_h['methods']}).</p>
  <p>Classes defined inside functions fell from {local_p['methods']} to {local_h['methods']} methods, builtin base
  classes rose to {builtin_h['methods']} and generic class templates as bases to {generic_h['methods']}, as methods got
  past earlier errors. <code>pickle</code> stops {pickle_h['methods']}, empty containers {empty_h['methods']} and
  mapping or class patterns {match_h['methods']}.</p>
</section>"""

# ---------- page 12: probes ----------
OV = D.get("overlay", {})
probes = table(["Probe or change", "Targeted", "Then pass", "Next first error"], [
    ["A <code>gc</code> stand-in, 12 Nov", "141", "11 (8%)", "Classes inside functions"],
    ["The real <code>gc</code> module (#1351), on methods <code>gc</code> stopped on 17 Nov", f"{gc_p['methods']}", "12 (8%)",
     "Classes inside functions (53), varied"],
    ["Capture-free local classes moved to module scope, 12 Nov", "218", "23 (11%)", "Builtin bases, async functions"],
    ["Local classes in functions that run once (#1613), on methods they stopped on 17 Nov", f"{local_p['methods']}",
     "21 (6%)", "Still a local class (183), varied"],
    ["<code>inspect.cleandoc</code>, 12 Nov", "52", "0", "<code>compile()</code> of a string"],
    ["The real <code>inspect</code> (#1417), on methods <code>inspect</code> stopped on 17 Nov", f"{inspect_p['methods']}", "0",
     "<code>compile()</code> of a string (44)"],
    ["<code>enum</code>'s missing names (#1563), on <code>test_enum</code>", f"{enum_p['methods']}", "7 (1%)",
     "Class-attribute types (520), run-time enum classes (178)"],
    ["CPython's pure-Python stdlib on the import path, at v0.7.0-alpha.2", "1,421", "0", "A missing module or name; <code>configparser</code>'s cached property"],
    ["Every method opted in to dynamic <code>Any</code>, at v0.7.0-alpha.2", "5,905", "+8, −5", "No large change"],
], cls="compact probes", num=(1, 2))
p12 = f"""
<section class="page" id="probes">
  <p class="eyebrow">Surface</p>
  <h1>What removing one blocker unlocks</h1>
  <p class="lead">Removing a single first error rarely makes a test pass, because the next error is usually another
  missing feature. This week's changes confirm the probes of 12 November: the real <code>gc</code> and
  <code>inspect</code> modules unlocked what their stand-ins predicted.</p>
  {probes}
  <p class="note">Probes of 12 November at 8434a911; merged changes compare v0.6.0-alpha.1 with v0.7.0-alpha.2. A
  method counts once, under its first error on 17 November.</p>
  <p>Where a blocker is the only one, removing it converts most methods, as starred patterns did (38 of 43). Where
  tests stack features, it converts few: <code>gc</code> made 12 of {gc_p['methods']} pass, as its stand-in had made 11 of
  141, and the next error of 53 others is a class defined inside a function. #1613's first form of local classes
  converted fewer than the probe's hoisting did, because it accepts only functions that run once.</p>
  <p>The <code>enum</code> names show the extreme: all {enum_p['methods']} <code>test_enum</code> methods stopped at one
  import, and with it gone only 7 pass. Most stop next at the type of a class attribute, so one inference change
  (draft #1686) could move several hundred at once, which per-release counts (#1303) would show.</p>
  <p>With CPython's pure-Python standard library on the import path, none of the 1,421 library-blocked methods
  pass; <code>configparser</code>'s 288 still stop at a <code>@cached_property</code> without a return annotation and
  <code>locale</code>'s 176 at a redefinition. Opting every test in to dynamic <code>Any</code> passes 8 more and 5
  fewer.</p>
</section>"""

# ---------- page 13: porting vs compiler ----------
cm = D["census_head"]
census = table(["First error at v0.7.0-alpha.2", "Files", "Examples"], [
    ["Missing module or name", len(cm.get("library", [])), "<code>array</code> (2), <code>asyncio</code> (2), <code>sys.executable</code> (2), <code>multiprocessing</code>, <code>sqlite3</code>, <code>xml</code>, <code>fractions</code>, <code>pyaes</code>, <code>tomli</code>; <code>int.to_bytes</code> (base64), <code>Path.stat</code> (pathlib)"],
    ["Typing", len(cm.get("typing", [])), "Field types (barnes_hut, bpe_tokeniser, float, go, hexiom), a class attribute (chaos), empty containers (comprehensions, gc_traversal, json_dumps), value types (decimal_pi, json_loads, logging, meteor_contest, regex_dna, telco), a recursive function's return type (decimal_factorial), a captured variable (regex_compile)"],
    ["Dynamic class model or reflection", len(cm.get("dynamic", [])), "Generic templates as bases (deltablue, pyflate, richards, richards_super), an unsupported base (typing_runtime_protocols), <code>pickle</code>"],
    ["Other", len(cm.get("other", [])), "Async functions (2), type annotations (2), <code>map()</code>, a function attribute"],
], cls="compact", num=(1,))
p13 = f"""
<section class="page" id="porting">
  <p class="eyebrow">Assessment</p>
  <h1>Porting libraries versus extending the compiler</h1>
  <p class="lead">Adapting code works for a bounded set of libraries but does not raise the surface for unmodified
  code: all 25 adapted pyperformance ports run, against {head['upstream']} of the 52 unmodified files.</p>
  {census}
  <p class="note">The {52 - head['upstream']} unmodified pyperformance 1.14.0 files that <code>pystachy ir</code>
  rejects at v0.7.0-alpha.2, by first error. <code>gc_collect</code> and <code>pprint</code> compile since
  v0.6.0-alpha.3.</p>
  <p>Type edits are the largest group of adaptations in the ported benchmarks: 91 of the 367 adaptation markers add
  annotations and 70 more make a type explicit, such as float literals or ranges turned into lists; replacing pyperf's
  runner accounts for 94. Seventeen unmodified files stop at a type that is not inferred, against 13 on 17 November,
  as files that got past a missing module reached their types.</p>
  <p>Library work moved more this week than before: the shipped library grew from {prev['library_lines']:,} to
  {head['library_lines']:,} lines, and library-test passes rose from {prev['library']} to {head['library']} after staying
  near 184 for three weeks. New modules still first move tests to their next blocker, as <code>enum</code>,
  <code>gc</code> and <code>inspect</code> did. Every port is also a copy to keep in step with its upstream.</p>
  <p>For code that depends on reflection or C extensions, embedding CPython (#170) avoids both porting and compiler
  work: the compiled program calls CPython for those parts.</p>
  <h2>Is the design too limiting?</h2>
  <p>Runtime reflection accounts for about {pct(refl_h, rejected)} of the rejected CPython tests. The gains since
  12 November came from inference, <code>match</code>, the class model and library modules, not from dynamic semantics,
  which supports the earlier judgment: for the programs and libraries that users run, the combination that scales is
  better inference for unmodified code, ports for a bounded set of key libraries, and embedded CPython for the dynamic
  remainder. This remains a judgment from the measurements, not a measured result.</p>
</section>"""

# ---------- page 14: appendix ----------
app_rows = []
for r in rows:
    app_rows.append([day(r["date"]), f"<code>{r['sha']}</code>", esc(r["release"].lstrip("v")), r["methods"], r["language"],
                     r["ports"], r["upstream"], n(r["core"], 2), n(r["micro"], 2), n(r["nbody_build"], 2),
                     n(r["bootstrap"]), n(r["compiler_lines"])])
appendix = table(["Date", "Commit", "Release", "Methods", "Language", "Ports", "Unmod.", "Core ×", "Micro ×",
                  "nbody build (s)", "Bootstrap (s)", "Compiler lines"], app_rows, cls="appendix",
                 num=(3, 4, 5, 6, 7, 8, 9, 10, 11))
p14 = f"""
<section class="page" id="appendix">
  <p class="eyebrow">Appendix</p>
  <h1>Measurements per commit</h1>
  {appendix}
  <p class="note">UTC commit dates. Methods, Language: CPython test methods passing (of 5,905; of 2,445). Ports: of 25.
  Unmod.: unmodified pyperformance files compiling (of 52). Data and scripts: <code>{FOLDER}</code> on branch
  <code>claude/peaceful-faraday-2yr9q6</code>, a research record not for merging. Prepared with Claude Code assistance
  at the repository owner's request.</p>
</section>"""

CSS = (V / "print/print.css").read_text()
d3src = (S / "page/node_modules/d3/dist/d3.min.js").read_text()
charts = (V / "print/charts.js").read_text()
D["rejected"] = rejected
data = json.dumps(D, default=float).replace("</", "<\\/")
doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Pystachy speed and surface</title>
<style>{CSS}</style></head>
<body>
{p1}{p2}{p3}{p4}{p5}{p6}{p7}{p8}{p9}{p10}{p11}{p12}{p13}{p14}
<script>{d3src}</script>
<script>window.__DATA = {data};</script>
<script>{charts}</script>
</body></html>"""
for marker in ("MOVERS_TEXT", "SPEED_SUMMARY"):
    if marker in doc:
        print("warning: placeholder left:", marker)
Path(sys.argv[1]).write_text(doc)
print("wrote", sys.argv[1], len(doc), "bytes")
