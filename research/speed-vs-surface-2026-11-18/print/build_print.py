"""Build the print edition of the report: one topic per A4 page, charts drawn by charts.js.

usage: python3 build_print.py OUT.html [EVIDENCE_SHA]
Reads print/data.json (prepare.py) and d3 from the dashboard's node_modules.
Second edition (18 November 2026): every sample, old and new, timed in one run.
"""
import html
import json
import sys
from datetime import datetime
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
V = S / "v2"
D = json.load(open(V / "print/data.json"))
EVIDENCE_SHA = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
FOLDER = "research/speed-vs-surface-2026-11-18"

rows = sorted(D["samples"], key=lambda r: r["date"])
by = {r["label"]: r for r in rows}
first, head = rows[0], rows[-1]
rep = by[D["report_label"]]                      # main 8434a911, the first edition's last measurement
a5 = by["1111-1528_b2182a4f"]
a2 = next(r for r in rows if r["release"] == "v0.1.0-alpha.2")
v50 = next(r for r in rows if r["release"] == "v0.5.0")
a2_50 = next(r for r in rows if r["release"] == "v0.5.0-alpha.2")
pre_aot = next(r for r in rows if r["release"] == "v0.5.0-alpha.1")
core_first = next(r for r in rows if r["core"] is not None)
new = [r for r in rows if r["date"] > rep["date"]]
P = D["progress"]
G, G0 = D["groups"], D["groups_report"]
rejected = sum(head["blocked"].values())
rejected_rep = sum(rep["blocked"].values())
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
field_h, field_r = gname(G, "field"), gname(G0, "field")
local_h, enum_h, pickle_h = gname(G, "local classes"), gname(G, "enum."), gname(G, "pickle")
builtin_h, match_h, match_r = gname(G, "builtin base"), gname(G, "match patterns"), gname(G0, "match patterns")
gc_h, inspect_h, empty_h, empty_r = gname(G, "gc module"), gname(G, "inspect"), gname(G, "empty containers"), gname(G0, "empty containers")
rt = D["retime"]
fl, wd = rt.get("float", {}), rt.get("micro_words", {})


def ms(res, lab):
    return res[lab]["median_ms"] if lab in res else None


HEADL = D["head_label"]
build_drop = rows and pre_aot["nbody_build"] / a2_50["nbody_build"]
ev = f"https://github.com/den-run-ai/pystachy/blob/{EVIDENCE_SHA}/{FOLDER}"


# ---------- figures the text quotes ----------
def sp_at(lab, b):
    return next((r["speedup"] for r in D["speedups"] if r["label"] == lab and r["benchmark"] == b), None)


def change(b, a_lab, b_lab):
    x, y = sp_at(a_lab, b), sp_at(b_lab, b)
    return y / x - 1 if x and y else None


MICRO_CH = {b: change(b, first["label"], HEADL) for b in D["micro"]}
mi = [r["micro"] for r in rows if r["micro"] is not None]
co_after = [r["core"] for r in rows if r["core"] is not None and r["date"] >= a2["date"]]
o18, o19 = by["1018-1740_bb5ac4ab"], by["1019-2327_b040f45e"]
regex_gain = [sp_at(o19["label"], b) / sp_at(o18["label"], b) for b in ("regex_dna", "regex_effbot", "regex_v8")]
fl_rep, fl_rc1 = sp_at(rep["label"], "float"), sp_at("1112-1351_30822255", "float")
a6 = by["1112-0850_0b13a212"]
exe = {lab: json.load(open(S / f"results/perfprep-{lab}.json"))["micro_nbody"]["exe_bytes"] for lab in (pre_aot["label"], a2_50["label"])}
FIRST_EDITION_AGREEMENT = "within 5%, with a median difference under 1%"  # 34 common commits; see raw/analysis.txt

# ---------- page 1: summary ----------
glance = table(
    ["", "First day<br>8 Oct", "v0.1.0-alpha.2<br>20 Oct", "First edition<br>12 Nov", "v0.6.0-alpha.1<br>17 Nov"],
    [
        ["CPython test methods passing (of 5,905)", first["methods"], a2["methods"], rep["methods"], head["methods"]],
        ["Language and builtins methods (of 2,445)", first["language"], a2["language"], rep["language"], head["language"]],
        ["Adapted pyperformance ports working (of 25)", first["ports"], a2["ports"], rep["ports"], head["ports"]],
        ["Unmodified pyperformance files compiling (of 52)", first["upstream"], a2["upstream"], rep["upstream"], head["upstream"]],
        ["Microbenchmark speed index (× CPython)", n(first["micro"], 1), n(a2["micro"], 1), n(rep["micro"], 1), n(head["micro"], 1)],
        ["Core ports speed index (× CPython)", "—", n(a2["core"], 1), n(rep["core"], 1), n(head["core"], 1)],
        ["AOT build of nbody (s)", n(first["nbody_build"], 2), n(a2["nbody_build"], 2), n(rep["nbody_build"], 2), n(head["nbody_build"], 2)],
    ], cls="glance", num=(1, 2, 3, 4))

contents = [("2", "Progress since 12 November"), ("3", "Recommendations and issues"), ("4", "What was measured"),
            ("5", "Speed against surface"), ("6", "Surface over time"), ("7", "Speed over time"),
            ("8", "Speed by benchmark"), ("9", "Runtime regressions"), ("10", "Compile cost"),
            ("11", "Remaining blockers"), ("12", "Removing one blocker"), ("13", "Porting or compiler work"),
            ("14", "Data per commit")]
toc = "".join(f"<li><span>{p}</span>{esc(t)}</li>" for p, t in contents)

p1 = f"""
<section class="page" id="summary">
  <p class="eyebrow">Pystachy research report · second edition, 18 November 2026</p>
  <h1 class="title">Speed and Python surface across Pystachy's history</h1>
  <p class="lead">From 8 October to 17 November 2026, the share of CPython's own unit tests that Pystachy runs
  without hand edits rose from 0.3% to {pct(head['methods'], 5905, 1)}. Speed relative to CPython did not fall
  along the way. Since the first edition of this report on 12 November, passing tests rose from {rep['methods']} to
  {head['methods']}, and AOT builds of small programs became about {build_drop:.0f} times faster.</p>
  {glance}
  <p>Passing methods rose by about 26 a day for two weeks, then by 26 in total over the next three. Two
  compiler steps added most of the rest: bounded <code>match</code> (+95 by 12 November) and v0.6.0-alpha.1 (+138 on
  17 November), through fields typed from <code>set()</code> calls (#1374) and starred sequence patterns (#1345).</p>
  <p>Run-time speed held: the microbenchmark index was {first['micro']:.1f}× CPython on the first day and
  {head['micro']:.1f}× at v0.6.0-alpha.1, and the core ports' index went from {core_first['core']:.1f}× (15 October) to
  {head['core']:.1f}×. Of the two regressions the first edition bisected, <code>float</code> is fixed (#1336) and <code>words</code> is still {100 * (ms(wd, HEADL) / ms(wd, 'bis_6d4ed3d117') - 1):.0f}%
  slower than before #667 (#1301).</p>
  <p>The precompiled runtime (#1377, v0.5.0-alpha.2) cut the AOT build of the 82-line nbody benchmark from
  {pre_aot['nbody_build']:.2f} s to {a2_50['nbody_build']:.2f} s ({first['nbody_build']:.2f} s on the first day), with
  executables about a third larger. The bootstrap still grows with the compiler: {a6['bootstrap']:.0f} s at
  v0.4.0-alpha.6 and {head['bootstrap']:.0f} s at v0.6.0-alpha.1.</p>
  <p>Of the {rejected:,} methods still rejected, {pct(lib_h, rejected)} need a missing module or name and
  {pct(comp_h, rejected)} a class-model, inference or <code>match</code> feature. The largest groups without an open
  pull request are classes defined inside functions ({local_h['methods']} methods, #1304) and three names missing from
  <code>enum</code> ({enum_h['methods']}).</p>
  <ol class="toc">{toc}</ol>
</section>"""

# ---------- page 2: progress since the first edition ----------
prog_rows = [rep] + new
prog = table(["Date", "Release", "Commit", "Methods", "Language", "Core ×", "Micro ×", "nbody build (s)", "Bootstrap (s)"],
             [[day(r["date"]), esc(r["release"] or ("main" if r is rep else "—")), f"<code>{r['sha']}</code>", r["methods"],
               r["language"], n(r["core"], 2), n(r["micro"], 2), n(r["nbody_build"], 2), n(r["bootstrap"])]
              for r in prog_rows], cls="compact", num=(3, 4, 5, 6, 7, 8))
SOURCES = [
    ["Fields typed from <code>set()</code> and <code>frozenset()</code> calls", "#1374 · v0.6.0-alpha.1", "100 (<code>test_set</code>)"],
    ["Starred sequence patterns and list subjects in <code>match</code>", "#1345 · v0.6.0-alpha.1", "38 (<code>test_patma</code>)"],
    ["<code>complex</code> numbers", "#1408 · v0.5.0-alpha.3", "5"],
    ["<code>None</code> as a set element", "#1412 · v0.5.0-alpha.3", "1 (<code>test_set</code>)"],
    ["<code>csv.DictWriter.writerow</code> called through its class", "#1481 · v0.5.0-alpha.1", "2 (<code>test_csv</code>)"],
]
sources = table(["Change", "Pull request · release", "Methods"], SOURCES, cls="compact sources")
p2 = f"""
<section class="page" id="progress">
  <p class="eyebrow">Progress</p>
  <h1>What changed since 12 November</h1>
  <p class="lead">In six days main took 474 commits and 11 release tags. Passing methods rose from {rep['methods']} to
  {head['methods']}; {P['gained_language']} of the {P['gained']} new passes are language and builtins tests, and
  {P['gained'] - 8} of them came from two pull requests that landed on 17 November.</p>
  {prog}
  <p class="note">All tags from v0.4.0-alpha.6 to v0.6.0-alpha.1, <code>bf699eb5</code> (the untagged RC.2 fixes) and
  <code>71e14a88</code>, between #1519 and #1522. Speed and build times: one run of all 48 samples on
  18 November. Bootstrap: built on 18 November, except 8434a911 (12 November).</p>
  <h2>Where the {P['gained']} new passes came from</h2>
  {sources}
  <p>No method that passed on 12 November fails now; #1374 and #1345 both landed in #1522. Field inference moved
  more methods than it unlocked: a field stopped {field_r['methods']} methods first on 12 November and stops
  {field_h['methods']} now, and most of those that do not pass stop next at an empty set or a value-type mismatch. The
  fourteen pull requests of #1519 changed the first error of 38 methods and made none pass.</p>
  <p>Seven of the 52 unmodified pyperformance files compile, as on 12 November, though six stop later now that
  <code>decimal</code>, <code>hashlib</code> and <code>base64</code> exist. All 31 benchmark workloads match
  CPython in AOT and JIT at every new commit.</p>
</section>"""

# ---------- page 3: recommendations and issue status ----------
STATUS = [
    ["#1300", "<code>float</code> slower by 37% after #1268", "Closed. Fixed by #1336 in v0.4.0-rc.1"],
    ["#1301", "<code>words</code> slower by 22% after #667", "Open. #1332 removed the code-point counting (RC.2); the larger heap remains"],
    ["#1302", "Weekly timing of every benchmark", "Closed. The weekly workflow (#1339) landed in v0.5.0-alpha.1 and has run once"],
    ["#1303", "Method triage and build cost per release", "Open. One manual comparison, v0.4.0 to v0.5.0; no tool or release step"],
    ["#1304", "Classes defined inside functions", "Open. No pull request"],
    ["#1305", "Mapping, starred and class patterns", "Open. Starred patterns and list subjects landed (#1345); mapping and class patterns remain"],
    ["#1306", "Rank surface work by measured unlocks", "Closed as a duplicate of #5 and #1303"],
    ["#706", "AOT build cost", "Closed. The precompiled runtime (#1377) landed in v0.5.0-alpha.2"],
]
status = table(["Issue", "Filed for", "Status on 18 November"], STATUS, cls="issues compact")
p3 = f"""
<section class="page" id="recommendations">
  <p class="eyebrow">Decision</p>
  <h1>Recommendations and the issues filed</h1>
  <p class="lead">The first edition's recommendations stand with two changes: AOT build cost is solved, and inference
  work proved able to unlock a whole test file at once. Spend the next compiler work on the large blockers that have
  no pull request yet.</p>
  <ol class="recs">
    <li>Keep extending field and container inference (#118, #618). One pull request (#1374) made 100 methods pass;
    field types are still the first error of {field_h['methods']} methods and empty containers of {empty_h['methods']}.
    Open pull requests #1295, #1375, #1368 and #1388 continue this work.</li>
    <li>Compile classes defined inside functions (#1304): {local_h['methods']} methods in 51 files, unchanged since
    12 November and without a pull request. Then builtin base classes ({builtin_h['methods']}, mostly
    <code>test_set</code>) and mapping and class patterns ({match_h['methods']}, #1305).</li>
    <li>Add <code>enum.member</code>, <code>enum.verify</code> and <code>enum.STRICT</code>, then probe
    <code>test_enum</code>: its {enum_h['methods']} methods all stop at that import, so their next errors are unknown.
    Draft #1351 adds <code>gc</code> ({gc_h['methods']} methods).</li>
    <li>Automate the per-release triage (#1303). This report's harness reproduced the manual v0.4.0 and v0.5.0 counts
    exactly (492 and 500); none of the eleven release notes since 12 November states a test count.</li>
    <li>Finish the <code>words</code> regression (#1301): string scans no longer count code points, but the heap peak
    and collection count that grew at #667 remain.</li>
    <li>Watch the bootstrap and the GC-stressed self-compilation (#1181), which grow with the compiler; the AOT build
    cost of #706 no longer does.</li>
    <li>Leave <code>eval</code>, <code>exec</code>, <code>pickle</code> and frame introspection to embedded CPython
    (#170), as before.</li>
  </ol>
  <h2>Status of the issues the first edition filed or relied on</h2>
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
    ["Adapted benchmarks", "The 25 ports in <code>bench/pyperformance</code> and the six day-one <code>bench/*.py</code> "
     "microbenchmarks, unchanged across commits", "AOT output equals CPython's; then timed"],
], cls="method")

p4 = f"""
<section class="page" id="method">
  <p class="eyebrow">Method</p>
  <h1>What was measured</h1>
  <p class="lead">Each sampled commit was built from source and given the same fixed inputs: CPython's own unit
  tests, pyperformance's benchmark files and a fixed set of timed programs.</p>
  <h2>Commits</h2>
  <p>The history covers {len(rows)} commits on main from 8 October to 17 November 2026 (UTC): the last commit of
  most days and 19 of the 26 release tags, every tag after 11 November included. Each was built in its own worktree by
  its own <code>make</code> bootstrap (CPython 3.13.18 hosting stage 1, LLVM 18.1.3): the first 35 on 12 November,
  the other 13 on 18 November.</p>
  <h2>Workloads</h2>
  {workloads}
  <p>The speed index is the geometric mean of per-benchmark speedups, where a speedup is CPython's time divided by
  Pystachy's AOT time on the same source. It uses a fixed set: the six microbenchmarks, or the {len(D['core'])} ports
  that worked at every sample from 15 October; <code>unpack_sequence</code> is excluded because AOT removes its timed
  loop. None of these inputs changed between 12 and 17 November.</p>
  <h2>Timing</h2>
  <p>All {len(rows)} samples were timed in one run on 18 November on an otherwise idle 4-vCPU x86-64 VM, each
  executable pinned to one CPU. Every repetition ran CPython 3.13.18 and all commits in an order rotated by one
  position, with every output checked. Values are medians of 5 runs (ports: pyperf's timed region) or 7
  (microbenchmarks: process wall time). JIT and build times are medians of 3 runs after one untimed run per
  commit.</p>
  <h2>Classifying rejections</h2>
  <p>A rejected method is classified by its first compiler error: library (a missing module or name), syntax,
  typing (inference needs an annotation), dynamic (Python's dynamic class model and reflection) or other. Page 11
  regroups the same errors by what removing them needs.</p>
  <h2>Limits</h2>
  <p>Only a method's first error is visible, so first-error counts overstate what one fix unlocks (page 12). Methods
  ran through the JIT. Bootstrap times are single builds run beside another commit's test sweep; compare them within
  one day's builds.</p>
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
  methods went from {first['methods']} to {head['methods']}. Individual microbenchmarks moved in both directions:
  <code>words</code> lost {-100 * MICRO_CH['micro_words']:.0f}% and <code>fib</code> {-100 * MICRO_CH['micro_fib']:.0f}%, while
  <code>nbody</code> gained {100 * MICRO_CH['micro_nbody']:.0f}% and <code>sieve</code> {100 * MICRO_CH['micro_sieve']:.0f}%.</p>
  <p>The core index rose from {core_first['core']:.1f}× to {o19['core']:.1f}× between 15 and 19 October, during the
  largest early surface gains; most of that rise came from <code>lib/re</code> work that made the three regex ports
  {min(regex_gain):.1f} to {max(regex_gain):.1f} times faster (page 8). The two later surface steps, bounded
  <code>match</code> and the inference of v0.6.0-alpha.1, left both indices where they were.</p>
  <p>The index is a geometric mean, so it hides changes in single benchmarks (pages 8 and 9), and it measures run
  time only; compile time is on page 10.</p>
</section>"""

# ---------- page 6: surface over time ----------
REL_SHOWN = ["v0.1.0-alpha.1", "v0.1.0-alpha.2", "v0.1.0-alpha.4", "v0.2.0", "v0.3.0", "v0.4.0-alpha.5", "v0.4.0",
             "v0.5.0-alpha.3", "v0.5.0", "v0.6.0-alpha.1"]
rel = [r for r in rows if r["release"] in REL_SHOWN or r is rep]
rel_table = table(["Release", "Date (UTC)", "Methods passing", "Language and builtins", "Library", "Ports working",
                   "Unmodified files"],
                  [[esc(r["release"]) if r is not rep else "main <code>8434a911</code>", day(r["date"]),
                    r["methods"], r["language"], r["library"], r["ports"], r["upstream"]] for r in rel],
                  cls="compact", num=(2, 3, 4, 5, 6))
cs = D["change_shares"]
k1, k2, k3 = list(cs)


def share(k, a):
    return f"{100 * cs[k]['share'].get(a, 0):.0f}%"


p6 = f"""
<section class="page" id="surface">
  <p class="eyebrow">Surface</p>
  <h1>Python surface over time</h1>
  <p class="lead">Passing methods grew by about 26 a day for two weeks and by 26 in total over the next three. Since
  then two steps added most of the gain: bounded <code>match</code> by 12 November (+95) and v0.6.0-alpha.1 on
  17 November (+138).</p>
  <figure><div id="fig-surface"></div>
  <figcaption>CPython test methods that compile and match CPython's output, per sampled commit; 5,905 methods in
  total, 2,445 of them in language and builtins test files.</figcaption></figure>
  {rel_table}
  <p class="note">Selected releases; page 14 lists every sample.</p>
  <p>Both steps came from compiler work. From 20 October to 11 November the compiler's share of changed lines was
  {share(k2, 'compiler')} and the library's {share(k2, 'library')}, against {share(k1, 'compiler')} and
  {share(k1, 'library')} in the first two weeks; benchmarks and examples took {share(k2, 'bench/examples')}. Between
  12 and 17 November the compiler's share rose to {share(k3, 'compiler')} and the library's to
  {share(k3, 'library')}, while tests took {share(k3, 'tests')} and Lean proofs {share(k3, 'lean proofs')}.</p>
  <p>Library tests barely moved: {a2['library']} methods passed at alpha.2, {rep['library']} on 12 November and
  {head['library']} now. The new <code>decimal</code>, <code>hashlib</code>, <code>base64</code> and
  <code>sysconfig</code> modules moved the first error of the affected tests to the next missing module, most often
  <code>array</code>, rather than making them pass.</p>
</section>"""

# ---------- page 7: speed over time ----------
def pick(prefix):
    return next(r for r in rows if r["label"].startswith(prefix))


sel = [("First day", first), ("First core sample", core_first), ("After lib/re work", pick("1019")),
       ("v0.1.0-alpha.2", a2), ("v0.4.0-alpha.5", a5), ("First edition (main)", rep), ("v0.4.0-rc.1 (float fix)", pick("1112-1351")),
       ("v0.5.0-alpha.2 (precompiled runtime)", a2_50), ("v0.5.0", v50), ("v0.6.0-alpha.1", head)]
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
  18 November.</figcaption></figure>
  {speed_table}
  <p>Since the first edition both indices moved within noise: the core index from {rep['core']:.2f} to
  {head['core']:.2f} and the microbenchmark index from {rep['micro']:.2f} to {head['micro']:.2f}. Fixing
  <code>float</code> in v0.4.0-rc.1 raised its speedup from {fl_rep:.1f}× to {fl_rc1:.1f}×, which lifts a 16-port
  geometric mean by about {100 * ((fl_rc1 / fl_rep) ** (1 / 16) - 1):.1f}%. <code>fib</code> has run about 6% slower since
  v0.5.0-alpha.2; the evaluation of #1377 found the same slowdown with identical code for <code>fib</code> at a
  different address and equal instruction counts, a code-placement effect rather than more work.</p>
  <p>Successive samples move by up to about 3% in both directions, and a single port by up to 15% when one of
  its five runs is slow (<code>nqueens</code> at 8434a911). Differences of that size cannot be told apart from noise in
  this setup. The 34 commits that both editions timed, in separate runs, agree {FIRST_EDITION_AGREEMENT} on each
  index.</p>
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
  <code>lib/re</code> work of 19 October and the two regressions; since the first edition, only <code>float</code>'s
  recovery moved a port by more than the noise.</p>
  <div class="legend">
    <span><i style="background:#d03b3b;opacity:1"></i>¼× CPython</span><span><i style="background:#d03b3b;opacity:.55"></i>½×</span>
    <span><i style="background:#2a78d6;opacity:.1;outline:1px solid #e2e0da"></i>1×</span><span><i style="background:#2a78d6;opacity:.4"></i>4×</span>
    <span><i style="background:#2a78d6;opacity:.7"></i>16×</span><span><i style="background:#2a78d6;opacity:1"></i>64× or more</span>
    <span><i class="empty"></i>did not build, or output differed</span>
  </div>
  <figure><div id="fig-heatmap"></div>
  <figcaption>AOT speedup over CPython 3.13 per benchmark (rows: microbenchmarks, then ports by speedup at
  v0.6.0-alpha.1) and sampled commit (columns). Each row's source is fixed, so a change along a row is a compiler or
  library change.</figcaption></figure>
  {changes}
  <p>At v0.6.0-alpha.1, speedups range from {slow[0][0]:.2f}× (<code>{slow[0][1]}</code>) to {fast[0]:.0f}×
  (<code>{fast[1].replace('micro_', '')}</code>). The {len(slow)} ports under 2× ({", ".join(f"<code>{b}</code>" for v, b in slow)})
  spend their time in library and runtime code for JSON, big integers, regular expressions, sets, generators and
  logging.</p>
</section>"""

# ---------- page 9: regressions ----------
def cell(res, lab, sub=""):
    v = ms(res, lab)
    return "—" if v is None else f"{v:.2f} ms" + (f"<br><span class='sub'>{sub}</span>" if sub else "")


reg = table(["Benchmark", "Before", "At the merge", "First edition", "After the fix", "v0.6.0-alpha.1", "CPython 3.13"], [
    ["<code>float</code> (pyperformance port)", cell(fl, "bis_0ec827ac34", "0ec827ac"), cell(fl, "bis_b40ee875bf", "#1268"),
     cell(fl, "1111-1943_8434a911", "8434a911"), cell(fl, "1112-1351_30822255", "#1336, rc.1"), cell(fl, HEADL),
     f"{ms(fl, 'cpython') or 0:.1f} ms"],
    ["<code>words</code> (microbenchmark)", cell(wd, "bis_6d4ed3d117", "6d4ed3d1"), cell(wd, "bis_a355c83ff7", "#667"),
     cell(wd, "1111-1943_8434a911", "8434a911"), cell(wd, "1112-2100_bf699eb5", "#1332, RC.2"), cell(wd, HEADL),
     f"{ms(wd, 'cpython') or 0:.1f} ms"],
], cls="compact", num=(1, 2, 3, 4, 5, 6))
p9 = f"""
<section class="page" id="regressions">
  <p class="eyebrow">Speed</p>
  <h1>The two runtime regressions</h1>
  <p class="lead"><code>float</code> is fixed: since v0.4.0-rc.1 it runs as fast as before #1268 or
  slightly faster. <code>words</code> improved slightly with #1332 but is still {100 * (ms(wd, HEADL) / ms(wd, 'bis_6d4ed3d117') - 1):.0f}%
  slower than before #667 (#1301).</p>
  {reg}
  <p class="note">AOT executables, medians of 15 interleaved runs pinned to one CPU on 18 November. "Before" is the
  regressing merge's first parent. <code>float</code> reports pyperf's timed region; <code>words</code> reports
  process wall time.</p>
  <h2><code>float</code>: fixed by #1336</h2>
  <p>#1268's listguard pass copied the loop <code>for i in range(n): points[i] = Point(i)</code> into a checked and an
  unchecked version, so the constructor <code>Point.__init__</code> gained a second call site and LLVM stopped
  inlining it. #1336 marks a call that a loop copy duplicates as <code>alwaysinline</code> and counts the callee's
  size toward listguard's code-growth limit. In the 15-run comparison the port took {ms(fl, 'bis_0ec827ac34'):.1f} ms before #1268,
  {ms(fl, '1111-1943_8434a911'):.1f} ms on 12 November, {ms(fl, '1112-1351_30822255'):.1f} ms after the fix and
  {ms(fl, HEADL):.1f} ms at v0.6.0-alpha.1.</p>
  <h2><code>words</code>: partly fixed by #1332</h2>
  <p>After #667, <code>w.upper().startswith("L")</code> counted the code points of every fresh string, although a
  call without explicit bounds does not need the count. #1332 skips that count for whole-string
  <code>startswith</code> and <code>endswith</code>. In the 15-run comparison the benchmark went from {ms(wd, '1112-1351_30822255'):.1f} ms at
  v0.4.0-rc.1 to {ms(wd, '1112-2100_bf699eb5'):.1f} ms at the commit that merged #1332
  ({100 * (ms(wd, '1112-2100_bf699eb5') / ms(wd, '1112-1351_30822255') - 1):.0f}%; #1332 measured −7.1% on its own host), and takes
  {ms(wd, HEADL):.1f} ms at v0.6.0-alpha.1, against {ms(wd, 'bis_6d4ed3d117'):.1f} ms before #667. The other cost found on 12 November remains: the heap
  peak grew from 34.9 MiB to 59.1 MiB at #667, and one collection taking 0.8 ms became two taking 5.0 ms (#1301).</p>
  <h2>Detection</h2>
  <p>The weekly performance workflow (#1339, closing #1302) now times all 25 ports and the <code>bench/*.py</code>
  programs against a fixed reference and the previous week's main, flagging slowdowns of 10% or more. Its replays
  flag both historical regressions. It ran once, on 16 November, so it has no trend yet.</p>
</section>"""

# ---------- page 10: compile cost ----------
split = table(["AOT build (s)", "First day", "v0.5.0-alpha.1", "v0.5.0-alpha.2", "v0.6.0-alpha.1"], [
    ["nbody (82 lines)", n(first["nbody_build"], 2), n(pre_aot["nbody_build"], 2), n(a2_50["nbody_build"], 2), n(head["nbody_build"], 2)],
    ["richards", "—", n(pre_aot["richards_build"], 2), n(a2_50["richards_build"], 2), n(head["richards_build"], 2)],
    ["raytrace", "—", n(pre_aot["raytrace_build"], 2), n(a2_50["raytrace_build"], 2), n(head["raytrace_build"], 2)],
], cls="compact", num=(1, 2, 3, 4))
p10 = f"""
<section class="page" id="compile">
  <p class="eyebrow">Cost</p>
  <h1>Compile cost</h1>
  <p class="lead">The precompiled runtime (#1377, v0.5.0-alpha.2) removed most of the AOT build time that had grown
  with the runtime. The bootstrap still grows with the compiler.</p>
  <figure><div id="fig-cost"></div>
  <figcaption>Left: <code>pystachy build</code> of three fixed programs, pinned to one CPU, medians of three runs
  after an untimed one. Right: the full <code>make</code> bootstrap of each commit, a single build; hollow points were
  built on 18 November, the rest on 12 November.</figcaption>
  </figure>
  {split}
  <p>Before #1377, every AOT build linked the runtime's bitcode into the program and optimized the whole module again,
  so an 82-line program's build time followed the runtime's size: {n(first['nbody_build'], 2)} s for nbody on the
  first day and {n(pre_aot['nbody_build'], 2)} s at v0.5.0-alpha.1, while compiling nbody's own code took 5 to 15 ms
  throughout. Since v0.5.0-alpha.2, the runtime is compiled once per runtime cache and each program is optimized
  against an interface that keeps the bodies of small runtime functions. The cost is larger executables: nbody's grew
  from {exe[pre_aot['label']]:,} to {exe[a2_50['label']]:,} bytes. The first build after a runtime change pays about 5 s to prepare the runtime;
  these medians exclude it.</p>
  <p>The bootstrap compiles the compiler with itself until its output stops changing, so its time follows the
  compiler's size: 12 s for 4,423 lines on the first day, 239 s for 66,836 lines on 12 November, and
  {n(by['1112-0850_0b13a212']['bootstrap'])} s to {n(head['bootstrap'])} s for {by['1112-0850_0b13a212']['compiler_lines']:,} to
  {head['compiler_lines']:,} lines in the builds of 18 November. In those six days the compiler's own IR grew from
  {by['1112-0850_0b13a212']['ir']:,} to {head['ir']:,} lines. The {rep['bootstrap']:.0f} s and
  {by['1112-0850_0b13a212']['bootstrap']:.0f} s builds of two nearly identical compilers (8434a911 and v0.4.0-alpha.6)
  show how much the two days' builds differ. The GC-stressed self-compilation that CI runs took about
  290 s at v0.5.0-rc.1, half of its 600 s limit; it grows faster than the compiler (#1181).</p>
  <p>The JIT caches its compiled runtime, so running the small programs end to end stayed near 0.1 s
  ({n(first['jit_micro'], 2)} s on the first day, {n(head['jit_micro'], 2)} s at v0.6.0-alpha.1).</p>
</section>"""

# ---------- page 11: blockers ----------
p11 = f"""
<section class="page" id="blockers">
  <p class="eyebrow">Surface</p>
  <h1>What blocks the remaining tests</h1>
  <p class="lead">At v0.6.0-alpha.1, {rejected:,} of the 5,905 methods are rejected at compile time.
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
  <figcaption>First compiler error of each rejected method at v0.6.0-alpha.1 (<code>3cf23d20</code>), grouped by what
  removing it needs (<code>scripts/groups.py</code>). Other missing stdlib modules include <code>array</code>,
  <code>configparser</code>, <code>_pyio</code>, <code>locale</code>, <code>pprint</code>, <code>queue</code> and
  <code>calendar</code>.</figcaption></figure>
  <p>Since 12 November the rejected methods fell from {rejected_rep:,} to {rejected:,}. Field and class-attribute
  types fell from {field_r['methods']} to {field_h['methods']} methods and <code>match</code> patterns from
  {match_r['methods']} to {match_h['methods']}; empty containers rose from {empty_r['methods']} to
  {empty_h['methods']}, because methods that now get past their fields stop at an empty set or list.</p>
  <p>The other large groups did not change: classes defined inside functions ({local_h['methods']} methods), the
  three names missing from <code>enum</code> ({enum_h['methods']}), <code>pickle</code> round trips
  ({pickle_h['methods']}), builtin base classes ({builtin_h['methods']}), <code>gc</code> ({gc_h['methods']}) and
  <code>inspect</code> ({inspect_h['methods']}). By the first-error classifier of page 4, dynamic and typing errors
  make up {pct(head['lang_blocked']['dynamic'] + head['lang_blocked']['typing'], lang_rej)} of the {lang_rej:,}
  language-test rejections, as on 12 November, but most of them are features a static compiler can implement, not
  reflection.</p>
</section>"""

# ---------- page 12: probes ----------
OV = D.get("overlay", {})
probes = table(["Probe", "Targeted", "Then pass", "Most common next error"], [
    ["Bounded <code>match</code> (#1272), on methods rejected for <code>match</code> at alpha.5", "216", "92 (43%)",
     "Starred, mapping and class patterns"],
    ["Starred patterns and list subjects (#1345), on methods they stopped", "43", "38 (88%)", "Varied"],
    ["Fields typed from <code>set()</code> (#1374), on <code>test_set</code> methods stopped by a field", "353",
     "100 (28%)", "An empty set; a value of another type"],
    ["Local classes that capture nothing, moved to module scope", "218", "23 (11%)", "Builtin bases, async functions"],
    ["A <code>gc</code> stand-in", "141", "11 (8%)", "Classes inside functions"],
    ["<code>inspect.cleandoc</code>", "52", "0", "<code>compile()</code> of a string"],
    ["CPython's pure-Python stdlib on the import path", "2,400", "0", "A missing module or name"],
    ["Every method opted in to dynamic <code>Any</code>", "5,905", "+7, −7", "No net change"],
], cls="compact probes", num=(1, 2))
p12 = f"""
<section class="page" id="probes">
  <p class="eyebrow">Surface</p>
  <h1>What removing one blocker unlocks</h1>
  <p class="lead">Removing a single first error rarely makes a test pass, because the next error is usually another
  missing feature. The exceptions are blockers that a whole test file shares, as <code>match</code> did in
  <code>test_patma</code> and the <code>self.set</code> field did in <code>test_set</code>.</p>
  {probes}
  <p class="note">Hoisting, <code>gc</code> and <code>inspect</code>: probes of 12 November at 8434a911. Standard
  library and dynamic <code>Any</code>: rerun at v0.6.0-alpha.1. Merged changes: the commits before and after.</p>
  <p>Where a blocker is the only one, removing it converts most methods: 38 of the 43 that starred patterns stopped
  now pass. Where tests stack features, it converts few: 100 of the 353 <code>test_set</code> methods stopped by a
  field pass, and the rest stop at an empty set or a value of another type, much as hoisting local classes or adding a
  <code>gc</code> stand-in made 8 to 11% of their targets pass on 12 November.</p>
  <p>With CPython's pure-Python standard library on the import path, none of the 2,400 library-blocked methods
  pass: 1,487 stop at another missing module or name, and <code>configparser</code>'s 288 now stop inside CPython's
  code at a <code>@cached_property</code> without a return annotation. The dynamic <code>Any</code> opt-in again
  changes no total.</p>
  <p>First-error counts therefore overstate a fix's effect unless one blocker covers a whole test file; per-release
  triage (#1303) would measure each step's real conversions.</p>
</section>"""

# ---------- page 13: porting vs compiler ----------
cm = D["census_head"]
census = table(["First error at v0.6.0-alpha.1", "Files", "Examples"], [
    ["Missing module or name", len(cm.get("library", [])), "<code>array</code> (2), <code>asyncio</code> (2), <code>subprocess</code> (2), <code>multiprocessing</code>, <code>sqlite3</code>, <code>xml</code>, <code>fractions</code>; <code>int.to_bytes</code> (base64)"],
    ["Typing", len(cm.get("typing", [])), "Field types (barnes_hut, bpe_tokeniser, float, go, hexiom), empty containers (comprehensions, json_dumps), value types (json_loads, logging, meteor_contest), a recursive function's return type (decimal_factorial)"],
    ["Dynamic class model or reflection", len(cm.get("dynamic", [])), "Generic templates as bases (pyflate, richards, richards_super), <code>gc</code> (2), <code>decimal.Decimal</code> as a value (decimal_pi, telco), unsupported bases (deltablue, typing_runtime_protocols), <code>pickle</code>"],
    ["Other", len(cm.get("other", [])), "Async functions (2), type annotations (2), <code>map()</code>, a function attribute"],
], cls="compact", num=(1,))
p13 = f"""
<section class="page" id="porting">
  <p class="eyebrow">Assessment</p>
  <h1>Porting libraries versus extending the compiler</h1>
  <p class="lead">Adapting code works for a bounded set of libraries but does not raise the surface for unmodified
  code: all 25 adapted pyperformance ports run, against 7 of the 52 unmodified files.</p>
  {census}
  <p class="note">The {52 - head['upstream']} unmodified pyperformance 1.14.0 files that <code>pystachy ir</code>
  rejects at v0.6.0-alpha.1, by first error.</p>
  <p>Type edits are the largest group of adaptations in the ported benchmarks: 91 of the 367 adaptation markers add
  annotations and 70 more make a type explicit, such as float literals or ranges turned into lists; replacing pyperf's
  runner accounts for 94. Better inference would let such files compile unmodified, and the week's largest gain
  (#1374) was inference.</p>
  <p>Library breadth grows slowly through porting alone. From alpha.2 to v0.6.0-alpha.1 the shipped library grew by
  {head['library_lines'] - a2['library_lines']:,} lines ({a2['library_lines']:,} to {head['library_lines']:,}) and
  {head['library'] - a2['library']} more library-test methods pass ({a2['library']} to {head['library']}). New modules
  first move tests to their next missing module. Every port is also a copy to keep in step with its upstream.</p>
  <p>For code that depends on reflection or C extensions, embedding CPython (#170) avoids both porting and compiler
  work: the compiled program calls CPython for those parts.</p>
  <h2>Is the design too limiting?</h2>
  <p>Runtime reflection, which a typed, interpreter-free compiler cannot provide directly, accounts for about
  {pct(refl_h, rejected)} of the rejected CPython tests. The week's gains came from inference and syntax, not from
  dynamic semantics, which supports the first edition's judgment: for the programs and libraries that users run, the
  combination that scales is better inference for unmodified code, ports for a bounded set of key libraries, and
  embedded CPython for the dynamic remainder. This remains a judgment from the measurements, not a measured
  result.</p>
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
Path(sys.argv[1]).write_text(doc)
print("wrote", sys.argv[1], len(doc), "bytes")
