"""Build the print edition of the report: one topic per A4 page, charts drawn by charts.js.

usage: python3 build_print.py OUT.html
Reads print/data.json (prepare.py), the follow-up evidence and d3 from the dashboard's node_modules.
"""
import html
import json
import sys
from datetime import datetime
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
D = json.load(open(S / "print/data.json"))
MAIN, A5 = "1111-1943_8434a911", "1111-1528_b2182a4f"
EVIDENCE_SHA = sys.argv[2] if len(sys.argv) > 2 else "f25374fd"

rows = sorted(D["samples"], key=lambda r: r["date"])
by = {r["label"]: r for r in rows}
main, a5 = by[MAIN], by[A5]
first = rows[0]
a2 = next(r for r in rows if r["release"] == "v0.1.0-alpha.2")

# Main's speed was timed in a separate run, paired with alpha.5; its indices here are alpha.5's
# index from the history run scaled by main/alpha.5 in the paired run (derived, drawn hollow).
chk = D["check"]
main_core_ratio = main["core"] / chk["a5_core_again"]
main_micro_ratio = main["micro"] / chk["a5_micro_again"]
main["core_paired"], main["micro_paired"] = main["core"], main["micro"]
main["core"] = a5["core"] * main_core_ratio
main["micro"] = a5["micro"] * main_micro_ratio
main["derived"] = True
D["speedups"] = [r for r in D["speedups"] if r["label"] != MAIN]
D["rejected"] = 5389

esc = html.escape


def n(v, d=0):
    return "—" if v is None else f"{v:,.{d}f}"


def day(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%-d %b")


def table(head, body, cls="", num=()):
    th = "".join(f'<th class="{"num" if i in num else ""}">{h}</th>' for i, h in enumerate(head))
    trs = "".join("<tr>" + "".join(f'<td class="{"num" if i in num else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                  for r in body)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


def issue(k):
    return f"#{k}"


ev = f"https://github.com/den-run-ai/pystachy/blob/{EVIDENCE_SHA}/research/speed-vs-surface-2026-11-12"

# ---------- page 1: summary ----------
glance = table(
    ["", "First day<br>8 Oct", "v0.1.0-alpha.2<br>20 Oct", "v0.4.0-alpha.5<br>11 Nov", "main 8434a911<br>12 Nov"],
    [
        ["CPython test methods passing (of 5,905)", first["methods"], a2["methods"], a5["methods"], main["methods"]],
        ["Language and builtins methods (of 2,445)", first["language"], a2["language"], a5["language"], main["language"]],
        ["Adapted pyperformance ports working (of 25)", first["ports"], a2["ports"], a5["ports"], main["ports"]],
        ["Unmodified pyperformance files compiling (of 52)", first["upstream"], a2["upstream"], a5["upstream"], main["upstream"]],
        ["Microbenchmark speed index (× CPython)", n(first["micro"], 1), n(a2["micro"], 1), n(a5["micro"], 1), n(main["micro"], 1) + "*"],
        ["Core ports speed index (× CPython)", "—", n(a2["core"], 1), n(a5["core"], 1), n(main["core"], 1) + "*"],
        ["AOT build of nbody (s)", n(first["nbody_build"], 2), n(a2["nbody_build"], 2), n(a5["nbody_build"], 2), n(main["nbody_build"], 2) + "*"],
        ["Compiler bootstrap (s)", n(first["bootstrap"]), n(a2["bootstrap"]), n(a5["bootstrap"]), n(main["bootstrap"])],
    ], cls="glance", num=(1, 2, 3, 4))

contents = [("2", "Recommendations"), ("3", "What was measured"), ("4", "Speed against surface"),
            ("5", "Surface over time"), ("6", "Speed over time"), ("7", "Speed by benchmark"),
            ("8", "Runtime regressions"), ("9", "Compile cost"), ("10", "Remaining blockers"),
            ("11", "Removing one blocker"), ("12", "Porting or compiler work"), ("13", "Data per commit")]
toc = "".join(f"<li><span>{p}</span>{esc(t)}</li>" for p, t in contents)

p1 = f"""
<section class="page" id="summary">
  <p class="eyebrow">Pystachy research report · 12 November 2026</p>
  <h1 class="title">Speed and Python surface across Pystachy's history</h1>
  <p class="lead">From 8 October to 11 November 2026, the share of CPython's own unit tests that Pystachy runs
  without hand edits rose from 0.3% to 6.7%, with no loss of speed relative to CPython; bounded <code>match</code>
  raised it to 8.3% on main. The added surface cost compile time and two benchmark regressions.</p>
  {glance}
  <p class="note">* main was timed in a separate run together with alpha.5: its speed indices are alpha.5's scaled by
  the ratio measured in that run, and its build time is that run's measurement (pages 3 and 6).</p>
  <p>Passing methods rose by about 26 a day for two weeks, then by 26 in total over three weeks while 31,000 lines were
  added. Language and builtins methods stayed at 218 from 28 October until bounded <code>match</code> added 92.</p>
  <p>Speed held. The six day-one microbenchmarks ran 18.1 times faster than CPython on the first day and 18.0 times at
  alpha.5; the 16 pyperformance ports measured since 15 October went from 7.4 to 11.9 times. Two benchmarks regressed
  and are still slower on main: <code>float</code> by 37% since #1268 and <code>words</code> by 22% since #667.</p>
  <p>Compile time absorbed the cost. The bootstrap grew from 12 s to 239 s in step with the compiler's size. An AOT
  build of the 82-line nbody benchmark grew from 0.31 s to 1.13 s, because every build re-optimizes the whole runtime;
  compiling nbody's own code still takes about 10 ms.</p>
  <p>On main, 9% of the 5,389 rejected methods need runtime reflection, 42% a missing module or name, and 32% a
  class-model, inference or <code>match</code> feature a static compiler can implement. Removing one first error made
  only 0–43% of the targeted methods pass, because tests combine many dynamic features.</p>
  <ol class="toc">{toc}</ol>
</section>"""

# ---------- page 2: recommendations ----------
filed = table(["Issue", "Kind", "Title", "Page"], [
    ["#1300", "Regression", "Recover float's 37% AOT slowdown from listguard loop copies", "8"],
    ["#1301", "Regression", "Recover words' 22% AOT slowdown from code-point strings", "8"],
    ["#1302", "Process", "Time all pyperformance ports in the weekly performance run", "8"],
    ["#1303", "Process", "Record CPython method triage and build cost per release", "5"],
    ["#1304", "Gap", "Compile classes defined inside functions", "10–11"],
    ["#1305", "Gap", "Support mapping, starred and class patterns in match", "11"],
    ["#1306", "Index", "Rank Python surface work by measured CPython method unlocks", "10–11"],
], cls="issues", num=(3,))

p2 = f"""
<section class="page" id="recommendations">
  <p class="eyebrow">Decision</p>
  <h1>Recommendations and issues filed</h1>
  <p class="lead">Fix the two regressions, measure speed and surface at every release, and spend compiler work where
  it compounds across CPython's tests and ported code.</p>
  <ol class="recs">
    <li>Recover the <code>float</code> and <code>words</code> slowdowns (#1300, #1301). Both mechanisms are identified:
    listguard's loop copies stop LLVM from inlining a constructor, and string methods count code points they do not
    need.</li>
    <li>Time all 31 benchmark workloads in the weekly performance run (#1302), and record the CPython method triage and
    build cost for every release (#1303). Together they would have shown the regressions and the three-week plateau
    when they happened.</li>
    <li>Infer more field and container types (#118, #618). They are the first error of 784 rejected methods, and type
    annotations or explicit types make up 161 of the 367 adaptations in the ported benchmarks.</li>
    <li>Then extend the class model: classes defined inside functions (#1304); builtin, generic and multiple bases
    (#7, #962); and the remaining <code>match</code> patterns (#1305). Order this work by how many methods each change
    makes pass, measured with probes rather than first-error counts (#1306).</li>
    <li>Before further class-model work, test one design change: in modules that opt in to dynamic <code>Any</code>,
    store fields whose type cannot be inferred as dynamic values instead of rejecting the module. Measure it on the
    CPython methods and on the 45 pyperformance files that do not compile unmodified.</li>
    <li>Reduce the fixed AOT build cost (#706) and the super-linear growth of the GC-stressed self-compilation
    (#1181).</li>
    <li>Leave <code>eval</code>, <code>exec</code>, <code>pickle</code> and frame introspection to embedded CPython
    (#170) and document them as deviations, rather than compiling them.</li>
  </ol>
  <h2>Issues filed on 12 November 2026</h2>
  {filed}
  <p>Already tracked and not filed again: AOT build cost (#706), compile-stage timing (#1011), self-compilation cost
  (#1181), field inference (#118, #618), the class model (#7), standard-library and C-module gaps (#11, #491),
  <code>enum</code> (#610), <code>collections</code> (#256) and <code>array</code> (#716).</p>
</section>"""

# ---------- page 3: method ----------
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

p3 = f"""
<section class="page" id="method">
  <p class="eyebrow">Method</p>
  <h1>What was measured</h1>
  <p class="lead">Each sampled commit was built from source and given the same fixed inputs: CPython's own unit
  tests, pyperformance's benchmark files and a fixed set of timed programs.</p>
  <h2>Commits</h2>
  <p>The history covers 34 commits on main from 8 October to 11 November 2026 (dates are UTC): the last commit of
  most days and 8 of the 15 release tags. Each commit was built in its own worktree by its own <code>make</code> bootstrap (CPython
  3.13.18 hosting stage 1, LLVM 18.1.3). Main at <code>8434a911</code>
  (12 November, the alpha.6 feature freeze) was measured the same way in a follow-up.</p>
  <h2>Workloads</h2>
  {workloads}
  <p>The speed index is the geometric mean of per-benchmark speedups, where a speedup is CPython's time divided by
  Pystachy's AOT time on the same source. It uses a fixed set: the six microbenchmarks, or the 16 ports that worked at
  every sample from 15 October; <code>unpack_sequence</code> is excluded because AOT removes its timed loop.</p>
  <h2>Timing</h2>
  <p>Timing ran after all builds on an otherwise idle 4-vCPU x86-64 VM, each executable pinned to one CPU. Every
  repetition ran CPython 3.13.18 and all commits in an order rotated by one position, and every output was checked.
  Values are medians of 5 runs (ports) or 7 (microbenchmarks): pyperf's timed region for ports, process wall time for
  microbenchmarks.</p>
  <h2>Classifying rejections</h2>
  <p>A rejected method is classified by its first compiler error: library (a missing module or name), syntax (an
  unimplemented construct), typing (inference needs an annotation), dynamic (Python's dynamic class model and
  reflection) or other. Page 10 regroups the same errors by what removing them needs.</p>
  <h2>Limits</h2>
  <p>Only a method's first error is visible, so first-error counts overstate what one fix unlocks (page 11). Methods
  ran through the JIT; AOT output was checked for the benchmarks only. Re-timing alpha.5 in a later run moved its core
  index by 5% and single ports by up to 40%, so cross-run comparisons use pairs timed together.</p>
</section>"""

# ---------- page 4: speed against surface ----------
p4 = f"""
<section class="page" id="trajectory">
  <p class="eyebrow">Central result</p>
  <h1>Speed against Python surface</h1>
  <p class="lead">Passing CPython test methods grew from 15 to 492 while the speed index held or rose; at the level of
  the index, the added surface did not cost run-time speed.</p>
  <figure><div id="fig-trajectory"></div>
  <figcaption>One point per sampled commit, joined in date order. Blue: the six day-one microbenchmarks; orange: the
  16 pyperformance ports that worked at every sample from 15 October. The hollow points are main, derived from the
  paired run (page 6).</figcaption></figure>
  <p>The microbenchmark index stayed between 16.5× and 18.2× at every sample, while passing methods went from 15 to
  397. Individual microbenchmarks moved in both directions: <code>words</code> lost 24% and <code>fib</code> 8%,
  while <code>nbody</code> gained 18% and <code>sieve</code> 15%.</p>
  <p>The core index rose from 7.4× to 11.3× between 15 and 19 October, during the largest surface gains. Most of that
  rise came from <code>lib/re</code> work that made the three regex ports 4.4 to 7.7 times faster (page 7). After
  20 October both measures moved little until bounded <code>match</code> reached main.</p>
  <p>The index is a geometric mean, so it hides regressions in single benchmarks (page 8), and it measures run time
  only; compile time is on page 9.</p>
</section>"""

# ---------- page 5: surface over time ----------
rel = [r for r in rows if r["release"]]
rel_table = table(["Release", "Date (UTC)", "Methods passing", "Language and builtins", "Library", "Ports working",
                   "Unmodified files"],
                  [[esc(r["release"]) if r["release"] != "main" else "main <code>8434a911</code>", day(r["date"]),
                    r["methods"], r["language"], r["library"], r["ports"], r["upstream"]] for r in rel],
                  cls="compact", num=(2, 3, 4, 5, 6))
p5 = f"""
<section class="page" id="surface">
  <p class="eyebrow">Surface</p>
  <h1>Python surface over time</h1>
  <p class="lead">Passing methods grew by about 26 a day for two weeks, then by 26 in total over three weeks, until
  95 more passed on main, 92 of them through bounded <code>match</code>.</p>
  <figure><div id="fig-surface"></div>
  <figcaption>CPython test methods that compile and match CPython's output, per sampled commit; 5,905 methods in
  total, 2,445 of them in language and builtins test files.</figcaption></figure>
  {rel_table}
  <p>The plateau coincided with a shift of effort. After 20 October the compiler's share of changed lines fell from
  16% to 5% and the library's from 8% to 3%, while benchmarks and examples rose from 3% to 31% and tools and CI from
  4% to 12%. Over weeks three to five the compiler, library and runtime still grew by 31,000 lines, but only 26
  methods began to pass: 0.1 to 1.4 per thousand lines, against 3.4 to 3.8 in the first two weeks.</p>
  <p>The kind of blocker removed changed too. In the first two weeks, newly passing methods had been blocked by a
  missing library piece (169), syntax (96), typing (39) or the dynamic class model (19). From alpha.2 to alpha.5, none
  blocked by the dynamic model and 7 blocked by typing began to pass.</p>
</section>"""

# ---------- page 6: speed over time ----------
def pick(prefix):
    return next(r for r in rows if r["label"].startswith(prefix))


sel = [("First day", pick("1007")), ("First core sample", pick("1015")), ("After lib/re work", pick("1019")),
       ("v0.1.0-alpha.2", a2), ("v0.1.0-alpha.4", pick("1102")), ("Highest core index", pick("1110")),
       ("v0.4.0-alpha.5", a5), ("main (derived*)", main)]
speed_table = table(["Sample", "Date (UTC)", "Commit", "Core index", "Microbenchmark index", "Ports working"],
                    [[esc(k), day(r["date"]), f"<code>{r['sha']}</code>", n(r["core"], 2), n(r["micro"], 2), r["ports"]]
                     for k, r in sel], cls="compact", num=(3, 4, 5))
p6 = f"""
<section class="page" id="speed">
  <p class="eyebrow">Speed</p>
  <h1>Speed over time</h1>
  <p class="lead">The core index rose from 7.4× to 11.3× CPython between 15 and 19 October and stayed between 11.1×
  and 12.2× afterwards; the microbenchmark index stayed near 18×.</p>
  <figure><div id="fig-speed"></div>
  <figcaption>Geometric mean of AOT speedups over CPython 3.13 per sampled commit. Hollow points: main, derived from
  the paired run.</figcaption></figure>
  {speed_table}
  <p class="note">* alpha.5's index scaled by the main-to-alpha.5 ratio measured in one paired run: 0.986 for the core
  ports and 1.004 for the microbenchmarks. In that run the indices were {main['core_paired']:.2f} and
  {main['micro_paired']:.2f} for main, against {chk['a5_core_again']:.2f} and {chk['a5_micro_again']:.2f} for
  alpha.5.</p>
  <p>The fall from 12.2× to 11.9× on 11 November is mostly <code>float</code>: its speedup fell by a
  quarter at #1268, which moves a 16-port geometric mean by about 2%. Successive samples also move by up to about 3%
  in both directions; differences of that size cannot be told apart from noise in this setup.</p>
  <p>On main, the paired run puts both indices within 2% of alpha.5, smaller than the 5% by which the same alpha.5
  build differed between two runs. Main is therefore indistinguishable from alpha.5 in speed.</p>
</section>"""

# ---------- page 7: speed by benchmark ----------
CH = [
    ("regex_dna", "18–19 Oct", "1,506 → 196", "<code>lib/re</code> matcher work (#676, #680, #682, #683, #685)", "32 merges; not bisected"),
    ("regex_effbot", "18–19 Oct", "1,032 → 168", "Same <code>lib/re</code> work", "Not bisected"),
    ("regex_v8", "18–19 Oct", "1,047 → 235", "Same <code>lib/re</code> work", "Not bisected"),
    ("scimark", "18–19 Oct", "19.2 → 10.1", "Likely field TBAA (#724) or tuple returns by value (#727)", "Not bisected"),
    ("barnes_hut", "18–19 Oct", "24.9 → 13.4", "Likely the same two changes", "Not bisected"),
    ("words (micro)", "17–18 Oct", "59.3 → 77.7", "Code-point strings, stage 1 (#667)", "Bisected to <code>a355c83f</code>"),
    ("float", "11 Nov", "32.7 → 43.5", "listguard loop versioning (#1268)", "Bisected to <code>b40ee875</code>"),
]
changes = table(["Benchmark", "Interval", "Time (ms)", "Cause", "Evidence"],
                [[f"<code>{b}</code>", i, t, c, e] for b, i, t, c, e in CH], cls="compact changes", num=(2,))
sp_a5 = {r["benchmark"]: r["speedup"] for r in D["speedups"] if r["label"] == A5}
slow = sorted((v, b) for b, v in sp_a5.items() if v < 2)
p7 = f"""
<section class="page" id="benchmarks">
  <p class="eyebrow">Speed</p>
  <h1>Speed by benchmark</h1>
  <p class="lead">Most ports kept the speed they reached in mid-October. The largest changes were the
  <code>lib/re</code> work on 19 October and two regressions that are still present on main.</p>
  <div class="legend">
    <span><i style="background:#d03b3b;opacity:1"></i>¼× CPython</span><span><i style="background:#d03b3b;opacity:.55"></i>½×</span>
    <span><i style="background:#2a78d6;opacity:.1;outline:1px solid #e2e0da"></i>1×</span><span><i style="background:#2a78d6;opacity:.4"></i>4×</span>
    <span><i style="background:#2a78d6;opacity:.7"></i>16×</span><span><i style="background:#2a78d6;opacity:1"></i>64× or more</span>
    <span><i class="empty"></i>did not build, or output differed</span>
  </div>
  <figure><div id="fig-heatmap"></div>
  <figcaption>AOT speedup over CPython 3.13 per benchmark (rows: microbenchmarks, then ports by speedup at alpha.5)
  and sampled commit (columns, 8 October to 11 November). Each row's source is fixed, so a change along a row is a
  compiler or library change.</figcaption></figure>
  {changes}
  <p>At alpha.5, speedups range from {slow[0][0]:.2f}× (<code>{slow[0][1]}</code>) to 77× (<code>richards_super</code>).
  Seven ports run less than twice as fast as CPython: {", ".join(f"<code>{b}</code>" for v, b in slow)}. The fastest
  are dominated by typed numeric loops and method calls; the slowest spend their time in library and runtime code for
  JSON, big integers, regular expressions, sets, generators and logging.</p>
</section>"""

# ---------- page 8: regressions ----------
rt = D["retime"]
reg = table(["Benchmark", "Before", "At the merge", "v0.4.0-alpha.5", "main", "CPython 3.13"], [
    ["<code>float</code> (pyperformance port)", f"{rt['float']['bis_0ec827ac34']['median_ms']:.2f} ms<br><span class='sub'>0ec827ac</span>",
     f"{rt['float']['bis_b40ee875bf']['median_ms']:.2f} ms<br><span class='sub'>#1268, b40ee875</span>",
     f"{rt['float']['1111-1528_b2182a4f']['median_ms']:.2f} ms", f"{rt['float']['1111-1943_8434a911']['median_ms']:.2f} ms<br><span class='sub'>+37%</span>",
     f"{rt['float']['cpython']['median_ms']:.1f} ms"],
    ["<code>words</code> (microbenchmark)", f"{rt['words']['bis_6d4ed3d117']['median_ms']:.2f} ms<br><span class='sub'>6d4ed3d1</span>",
     f"{rt['words']['bis_a355c83ff7']['median_ms']:.2f} ms<br><span class='sub'>#667, a355c83f</span>",
     f"{rt['words']['1111-1528_b2182a4f']['median_ms']:.2f} ms", f"{rt['words']['1111-1943_8434a911']['median_ms']:.2f} ms<br><span class='sub'>+22%</span>",
     f"{rt['words']['cpython']['median_ms']:.1f} ms"],
], cls="compact", num=(1, 2, 3, 4, 5))
p8 = f"""
<section class="page" id="regressions">
  <p class="eyebrow">Speed</p>
  <h1>Two runtime regressions</h1>
  <p class="lead"><code>float</code> is 37% slower on main than before #1268, and <code>words</code> 22% slower than
  before #667. Both causes are identified (#1300, #1301), and neither benchmark is in the per-merge performance
  check.</p>
  {reg}
  <p class="note">AOT executables, medians of 15 interleaved runs pinned to one CPU on 12 November. "Before" is the
  merge's first parent. <code>float</code> reports pyperf's timed region; <code>words</code> reports process wall
  time.</p>
  <h2><code>float</code> and #1268</h2>
  <p>The slowdown is not extra work: instructions rose by 1.4% (350.3M to 355.3M), and page faults and peak memory are
  unchanged. #1268's listguard pass copies the loop <code>for i in range(n): points[i] = Point(i)</code> into a checked
  and an unchecked version, so the constructor <code>Point.__init__</code> gains a second call site and LLVM stops
  inlining it. With the compiler from before #1268, adding one never-executed second <code>Point(0)</code> call to the
  source produces the same out-of-line constructor and the same slowdown, from 34.1 ms to 44.8 ms. Any small callee in
  a versioned loop is exposed in the same way.</p>
  <h2><code>words</code> and #667</h2>
  <p>Instructions rose from 433M to 617M at #667 and are 539M on main. Two costs remain. First,
  <code>w.upper().startswith("L")</code> runs 400,000 times, and each call counts the code points of a freshly created
  string, although a call without explicit bounds does not need the count (64M instructions). Second, the heap peak
  rose from 34.9 MiB to 59.1 MiB, and one garbage collection taking 0.8 ms became two taking 5.0 ms; the cause of the
  growth is not yet known.</p>
  <h2>Why they went unnoticed</h2>
  <p>The Performance smoke workflow times eleven workloads, and neither benchmark is among them; its weekly run
  compares main against a fixed reference on the same eleven. Instruction counts alone would also have missed
  <code>float</code>, whose time rose by 32% at #1268 for 1.4% more instructions. #1302 proposes weekly timing of all
  31 workloads.</p>
</section>"""

# ---------- page 9: compile cost ----------
split = table(["Commit", "Frontend only (<code>pystachy ir</code>)", "Full AOT build", "Program IR (lines)"], [
    ["First day, <code>4f7d51c5</code>", "5–10 ms", "0.34 s", "946"],
    ["v0.1.0-alpha.2, <code>afb59cd3</code>", "9–15 ms", "0.69–0.80 s", "979"],
    ["main, <code>8434a911</code>", "9–12 ms", "1.19–1.37 s", "842"],
], cls="compact", num=(1, 2, 3))
p9 = f"""
<section class="page" id="compile">
  <p class="eyebrow">Cost</p>
  <h1>Compile cost</h1>
  <p class="lead">Compile time grew with the compiler and its runtime, not with the programs being compiled.</p>
  <figure><div id="fig-cost"></div>
  <figcaption>Left: <code>pystachy build</code> of three fixed programs, pinned to one CPU, medians of two runs.
  Right: the full <code>make</code> bootstrap of each commit. Hollow points: main, from the follow-up run.</figcaption>
  </figure>
  {split}
  <p class="note">nbody (82 lines), three runs per commit pinned to one CPU on 12 November.</p>
  <p>The bootstrap compiles the compiler with itself until its output stops changing, so its time follows the
  compiler's size: 12 s for 4,423 lines on the first day and 239 s for 66,836 lines on main, while the compiler's own
  IR grew from 52,488 to 912,733 lines. That is 2.7 to 4.8 s per thousand compiler lines at every sample. The
  GC-stressed self-compilation that CI runs grows faster than the compiler, about with its square (#1181).</p>
  <p>Compiling nbody's own code takes 5 to 15 ms at every measured commit, and its IR even shrank (table). The full
  AOT build grew from 0.31 s on the first day to 1.13 s at alpha.5 because each build links and re-optimizes the whole
  runtime, which grew from 2,154 to 14,800 lines. #706 measured 0.12 s for an nbody build with a precompiled runtime,
  but such executables ran 1.23 to 2.71 times slower. The JIT caches its compiled runtime, so running the small programs end to end stayed near
  0.1 s (0.12 s on the first day, {main['jit_micro']:.2f} s on main).</p>
  <p>The bootstrap growth is the expected price of a self-hosting compiler fifteen times larger. The added AOT build
  time buys nothing for small programs, whose speed did not change, and is the most fixable of these costs.</p>
</section>"""

# ---------- page 10: blockers ----------
p10 = f"""
<section class="page" id="blockers">
  <p class="eyebrow">Surface</p>
  <h1>What blocks the remaining tests</h1>
  <p class="lead">On main, 5,389 of the 5,905 methods are rejected at compile time. 42% need a missing module or
  name, 32% a class-model, inference or <code>match</code> feature that a static compiler can implement, and 9%
  runtime reflection.</p>
  <div class="legend">
    <span><i style="background:#2a78d6"></i>Missing module or name</span>
    <span><i style="background:#eb6834"></i>Feature a static compiler can implement</span>
    <span><i style="background:#1baf7a"></i>Runtime reflection</span>
    <span><i style="background:#b9b8b1"></i>Other first errors</span>
  </div>
  <figure><div id="fig-groups"></div>
  <figcaption>First compiler error of each rejected method on main <code>8434a911</code>, grouped by what removing it
  needs (<code>followup/scripts/groups.py</code>). Other missing stdlib modules include <code>configparser</code>,
  <code>decimal</code>, <code>_pyio</code>, <code>locale</code>, <code>pprint</code>, <code>queue</code>,
  <code>calendar</code> and <code>array</code>.</figcaption></figure>
  <p>The largest single groups are not reflective. Field and class-attribute types that inference cannot determine
  stop 688 methods. Classes defined inside functions stop 365; in 78% of these methods the local classes capture no
  variable of the enclosing function. Builtin base classes, mostly <code>set</code> and <code>frozenset</code> in
  <code>test_set</code>, stop 178. Three names missing from Pystachy's <code>enum</code> (<code>member</code>,
  <code>verify</code> and <code>STRICT</code>) stop all 885 methods of <code>test_enum</code> at their imports.</p>
  <p>Reflection is concentrated in five places: <code>pickle</code> round trips (247 methods in 28 files), modules or
  classes used as values (73), <code>eval</code>, <code>exec</code>, <code>compile</code> and the <code>ast</code> and
  <code>dis</code> modules (58), <code>str.format</code> with a computed format string (49), and exception attributes
  such as <code>__traceback__</code> (48).</p>
  <p>The first-error classifier described on page 3 puts the class-model features together with reflection under
  "dynamic". By that classifier, dynamic and typing errors make up 81% of language-test rejections on main (76% at
  alpha.5), but most of them are features a static compiler can implement, not reflection.</p>
</section>"""

# ---------- page 11: probes ----------
probes = table(["Probe on main", "Methods targeted", "Then pass", "Most common next error"], [
    ["Bounded <code>match</code> (#1272), methods rejected for <code>match</code> at alpha.5", "216", "92 (43%)",
     "Starred, mapping and class patterns (71)"],
    ["Local classes that capture nothing, moved to module scope", "218", "23 (11%)", "Builtin base classes (33), async functions (11)"],
    ["A <code>gc</code> stand-in", "141", "11 (8%)", "Classes defined inside functions (51)"],
    ["<code>inspect.cleandoc</code>", "52", "0", "<code>compile()</code> of a source string (44)"],
    ["CPython's pure-Python stdlib on the import path (alpha.5)", "2,429", "0", "A missing module or name (2,031)"],
    ["Every method opted in to dynamic <code>Any</code>", "5,905", "+7, −7", "No net change"],
], cls="compact", num=(1, 2))
p11 = f"""
<section class="page" id="probes">
  <p class="eyebrow">Surface</p>
  <h1>What removing one blocker unlocks</h1>
  <p class="lead">Removing a single first error rarely makes a test pass: probes made between 0% and 43% of the
  targeted methods pass, because the next error is usually another missing feature.</p>
  {probes}
  <p class="note">The <code>match</code> row compares alpha.5 with main. Every other probe removes one first error
  mechanically and reruns the methods through the JIT, on main or, for the standard-library probe, on alpha.5.
  Hoisting skipped methods whose local classes capture a variable or clash in name, and dropped those whose CPython
  output changed once hoisted.</p>
  <p>Tests exercise features together. A test that defines a class inside a function often also subclasses a builtin
  type, uses async functions or returns values from unannotated functions, so those errors come next once the local
  class is moved out. <code>match</code> converted best because <code>test_patma</code> tests <code>match</code>
  itself.</p>
  <p>Library work meets the same stacking. With CPython's own pure-Python standard library on the import path, none of
  the 2,429 library-blocked methods passed: they next needed C modules, such as <code>_contextvars</code> for
  <code>decimal</code> (260 methods) or <code>array</code> (84), names that Pystachy's own modules lack, or dynamic code
  inside CPython's library (219).</p>
  <p>The dynamic <code>Any</code> opt-in does not reach these blockers. It gives dynamic storage to values a program
  declares as <code>Any</code>, while the blocked tests fail on inference and class features. Opting every method in
  made 7 more pass and rejected 7 that otherwise pass, through <code>math</code> functions applied to <code>Any</code>
  values, star-unpacking an <code>Any</code> into a call, and an assignment expression in a comprehension.</p>
  <p>Ranking work by first-error counts therefore overstates its effect. #1306 lists the groups with their owners and
  asks for conversion probes before prioritizing.</p>
</section>"""

# ---------- page 12: porting vs compiler ----------
cm = D["census_main"]
census = table(["First error on main", "Files", "Examples"], [
    ["Missing module or name", len(cm.get("library", [])),
     "<code>asyncio</code>, <code>multiprocessing</code>, <code>subprocess</code>, <code>decimal</code>, <code>array</code>, "
     "<code>hashlib</code>, <code>sqlite3</code>, <code>xml</code>"],
    ["Typing", len(cm.get("typing", [])), "Field types (barnes_hut, bpe_tokeniser, float, go), a class attribute (chaos), "
     "empty containers (comprehensions, json_dumps)"],
    ["Dynamic class model or reflection", len(cm.get("dynamic", [])), "<code>gc</code> (2), <code>pickle</code>, builtin or "
     "unsupported bases (deltablue, typing_runtime_protocols), generic templates as bases (richards, richards_super)"],
    ["Other", len(cm.get("other", [])), "Async functions (2), type annotations (2), a class-body default, <code>map()</code>, "
     "a function attribute"],
], cls="compact", num=(1,))
p12 = f"""
<section class="page" id="porting">
  <p class="eyebrow">Assessment</p>
  <h1>Porting libraries versus extending the compiler</h1>
  <p class="lead">Adapting code works for a bounded set of libraries but does not raise the surface for unmodified
  code: all 25 adapted pyperformance ports run, against 7 of the 52 unmodified files.</p>
  {census}
  <p class="note">The 45 unmodified pyperformance 1.14.0 files that <code>pystachy ir</code> rejects on main, by first
  error.</p>
  <p>Type edits are the largest group of adaptations in the ported benchmarks: 91 of the 367 adaptation markers add
  annotations and 70 more make a type explicit, such as float literals or ranges turned into lists; replacing pyperf's
  runner accounts for 94. The <code>float</code> port, for example, annotates one parameter, three fields and one list.
  Better inference would let such files compile unmodified, and field inference is also the largest typing blocker in
  CPython's tests (688 methods).</p>
  <p>Library breadth grows slowly through porting alone. From alpha.2 to main the shipped library grew by 8,400 lines
  (46,979 to 55,378) and 22 more library-test methods pass (160 to 182). Every port is also a copy to keep in step with
  its upstream.</p>
  <p>For code that depends on reflection or C extensions, embedding CPython (#170) avoids both porting and compiler
  work: the compiled program calls CPython for those parts.</p>
  <h2>Is the design too limiting?</h2>
  <p>Runtime reflection, which a typed, interpreter-free compiler cannot provide directly, accounts for about 9% of
  the rejected CPython tests. Passing most of
  CPython's own test suite would still need most of Python's dynamic class model, and each class-model feature makes
  few tests pass on its own, so that suite is a poor target. For the programs and libraries that users run, the
  combination that scales is better inference for unmodified code, ports for a bounded set of key libraries, and
  embedded CPython for the dynamic remainder. This is a judgment from the measurements above, not a measured
  result.</p>
</section>"""

# ---------- page 13: appendix ----------
app_rows = []
for r in rows:
    rel_ = r["release"].lstrip("v")
    star = "*" if r.get("derived") else ""
    app_rows.append([day(r["date"]), f"<code>{r['sha']}</code>", esc(rel_), r["methods"], r["language"], r["ports"],
                     r["upstream"], n(r["core"], 2) + (star if r["core"] is not None else ""), n(r["micro"], 2) + star,
                     n(r["nbody_build"], 2) + star, n(r["bootstrap"]), n(r["compiler_lines"])])
appendix = table(["Date", "Commit", "Release", "Methods", "Language", "Ports", "Unmod.", "Core ×", "Micro ×",
                  "nbody build (s)", "Bootstrap (s)", "Compiler lines"], app_rows, cls="appendix",
                 num=(3, 4, 5, 6, 7, 8, 9, 10, 11))
p13 = f"""
<section class="page" id="appendix">
  <p class="eyebrow">Appendix</p>
  <h1>Measurements per commit</h1>
  {appendix}
  <p class="note">* main, from the follow-up run (page 3). Dates are UTC commit dates. Methods and Language: CPython
  test methods passing, of 5,905 and 2,445. Ports: adapted pyperformance ports working, of 25. Unmod.: unmodified
  pyperformance files compiling, of 52.</p>
  <h2>Data and reproduction</h2>
  <p>Inputs, raw results and scripts are on branch <code>claude/peaceful-faraday-2yr9q6</code> under
  <code>research/speed-vs-surface-2026-11-12</code>: charted rows in <code>data/</code>, timing, build, census and
  per-method results in <code>raw/</code>, the 12 November measurements on main in <code>followup/</code>, and the
  harness in <code>scripts/</code>. It is a research record, not for merging into main. Prepared with Claude Code
  assistance at the repository owner's request.</p>
</section>"""

CSS = (S / "print/print.css").read_text()
d3src = (S / "page/node_modules/d3/dist/d3.min.js").read_text()
charts = (S / "print/charts.js").read_text()
data = json.dumps(D, default=float).replace("</", "<\\/")
doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Pystachy speed and surface</title>
<style>{CSS}</style></head>
<body>
{p1}{p2}{p3}{p4}{p5}{p6}{p7}{p8}{p9}{p10}{p11}{p12}{p13}
<script>{d3src}</script>
<script>window.__DATA = {data};</script>
<script>{charts}</script>
</body></html>"""
Path(sys.argv[1]).write_text(doc)
print("wrote", sys.argv[1], len(doc), "bytes")
