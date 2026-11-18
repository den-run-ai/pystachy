# Speed and Python surface across Pystachy's history, second edition (2026-11-18)

Raw evaluation for a research branch; not for merging into `main` (`research/` is rejected by
`tools/check_repository_hygiene.py` on production branches). Prepared with an AI coding agent at the
repository owner's request.

This edition extends `research/speed-vs-surface-2026-11-12` (the first edition, left unchanged) through
`main` `3cf23d20` (v0.6.0-alpha.1, 17 November 2026), with the same inputs and harness. It measures 48
commits instead of 34 and times all of them again in one run, so its speed numbers differ slightly from
the first edition's.

## Progress since the first edition

Between `8434a911` (the first edition's last measurement, 12 November) and `3cf23d20`, main took 474
commits, 22 first-parent merges and 11 release tags:

| | main `8434a911` (first edition) | v0.5.0 | v0.6.0-alpha.1 |
|---|---:|---:|---:|
| CPython test methods passing (of 5,905) | 492 | 500 | 638 |
| Language and builtins tests passing (of 2,445) | 310 | 316 | 454 |
| Library tests passing (of 3,460) | 182 | 184 | 184 |
| Methods rejected at compile time | 5,389 | 5,380 | 5,242 |
| Unmodified upstream pyperformance files compiling (of 52) | 7 | 7 | 7 |
| Adapted ports and microbenchmarks matching CPython (of 31) | 31 | 31 | 31 |
| Core ports speed index (× CPython 3.13) | 11.96 | 12.16 | 12.25 |
| Microbenchmark speed index (× CPython 3.13) | 17.89 | 18.04 | 17.76 |
| `pystachy build` of `bench/nbody.py` | 0.98 s | 0.21 s | 0.21 s |
| Compiler lines (`pystachy.py` and `src/`) | 66,836 | 70,431 | 71,678 |
| Compiler IR at the bootstrap fixed point (lines) | 912,733 | 963,719 | 981,589 |

The 146 newly passing methods, with no method lost:

| Change | Pull request | Release | Methods |
|---|---|---|---:|
| Fields typed from `set()` and `frozenset()` calls (`self.set = set(...)`) | #1374, landed in #1522 | v0.6.0-alpha.1 | 100 (`test_set`) |
| Starred sequence patterns and list subjects in `match` | #1345, landed in #1522 | v0.6.0-alpha.1 | 38 (`test_patma`) |
| `complex` numbers | #1408, landed in #1494 | v0.5.0-alpha.3 | 5 |
| `None` as a set element | #1412, landed in #1494 | v0.5.0-alpha.3 | 1 |
| `csv.DictWriter.writerow` called through its class | landed in #1481 | v0.5.0-alpha.1 | 2 |

Eight of the eleven tags changed no test result. The fourteen typing, inference and library pull
requests of #1519 changed the first error of 38 methods (mostly `base64` → `array`) and made none
pass. Field inference moved more methods than it unlocked: fields whose type cannot be inferred
were the first error of 688 methods on 12 November and are of 444 now; 100 of the difference pass,
and most of the rest stop at an empty set or a value-type mismatch (`raw/progress-steps.txt`,
`raw/groups-*.txt`).

Run-time speed did not move beyond noise. The core ports' index was 11.96× CPython 3.13 at `8434a911` and
12.25× at v0.6.0-alpha.1, the microbenchmark index 17.89× and 17.76×; successive samples move by up to about
3%. `float`'s regression is fixed: in a 15-run re-timing (`raw/retime-float.json`) it took 38.8 ms before
#1268, 46.4 ms on 12 November, 36.1 ms after #1336 (v0.4.0-rc.1) and 35.3 ms now (CPython: 520.8 ms).
`words` improved by 4% at #1332 (69.9 → 67.2 ms) and takes 67.7 ms now, still 19% slower than before #667
(57.0 ms; CPython: 171.8 ms; #1301). `micro_fib` has run about 6% slower since v0.5.0-alpha.2 (fastest run
34.8 → 36.7 ms); #1377's evaluation found the same with identical code for `fib` at a different address and
equal instruction counts.

AOT builds became three to five times faster at v0.5.0-alpha.2, where the precompiled runtime (#1377,
closing #706) landed: `pystachy build` of `bench/nbody.py` took 1.14 s at v0.5.0-alpha.1 and 0.21 s at
v0.5.0-alpha.2, richards 1.29 → 0.40 s and raytrace 1.23 → 0.41 s (pinned, medians of three after an untimed
run). Executables grew by about a third (nbody: 115,280 → 151,048 bytes). The bootstrap grew with the
compiler, from 274 s at v0.4.0-alpha.6 to 319 s at v0.6.0-alpha.1 in builds made on 18 November, while the
compiler's IR grew from 912,869 to 981,589 lines. `8434a911` took 239 s on 12 November and the nearly
identical alpha.6 compiler 274 s on 18 November, so compare bootstrap times within one day's builds.

## Relevant pull requests, documentation and issues

Issues the first edition filed or relied on, as of 18 November:

| Issue | Status |
|---|---|
| #1300 `float` +37% after #1268 | Closed. #1336 (listguard keeps sole calls inlinable) landed in v0.4.0-rc.1 `30822255` |
| #1301 `words` +22% after #667 | Open. #1332 (no code-point count in whole-string `startswith`/`endswith`) landed at `bf699eb5`; the larger heap and second collection remain |
| #1302 weekly timing of all ports | Closed. The weekly workflow #1339 landed in v0.5.0-alpha.1; it ran once, on 16 November |
| #1303 triage and build cost per release | Open. One manual comparison (v0.4.0 → v0.5.0: 492 → 500 methods), which this edition reproduces exactly; no tool or release step |
| #1304 classes defined inside functions | Open. No pull request; 368 methods stop there first |
| #1305 mapping, starred and class patterns | Open. Starred patterns and list subjects landed (#1345); mapping and class patterns remain (52 methods) |
| #1306 rank surface work by measured unlocks | Closed as a duplicate of #5 and #1303 |
| #706 AOT build cost | Closed by #1377 (precompiled runtime, v0.5.0-alpha.2) |
| #1181 GC-stressed self-compilation | Open, awaiting a scope decision; about 290 s of its 600 s limit at v0.5.0-rc.1 |
| #118 field inference | Open. #1286, #1376, #1384 (in #1519) and #1374 (in #1522) landed; #1295, #1375, #1368 and #1388 are open |

Documentation: none of the eleven release notes from v0.4.0-alpha.6 to v0.6.0-alpha.1 states a CPython
test-method count; v0.5.0-alpha.2's notes give the precompiled runtime's build measurements. The
README's performance table was relabelled to commit `f07472a5` (10 November) without new measurements.
`docs/testing.md` describes the weekly AOT performance workflow, `docs/stdlib.md` adds `decimal`,
`hashlib`, `hmac`, `base64`, `platform`, `sysconfig` and `importlib.metadata`, and
`docs/language/compatibility.md` records the new `complex` and class-union deviations.

Open pull requests that reach the largest remaining blockers: drafts for `gc` (#1351), `inspect` (#1417)
and `pprint` (#1344); class objects as values (#1315, #1361, #1372, #1406, #1407); generic and secondary
bases (#1335, #1352, #1350, #1373, #1391); field inference from globals (#1295, #1375, #1368, #1388); and
native `unittest` cases (#1287). None addresses classes defined inside functions, mapping or class
patterns, the missing `enum` names or `pickle`.

## Findings over the whole history

| | Oct 8 (first day) | Oct 20 (v0.1.0-alpha.2) | Nov 11 (v0.4.0-alpha.5) | Nov 17 (v0.6.0-alpha.1) |
|---|---:|---:|---:|---:|
| CPython test methods passing (of 5,905) | 15 | 371 | 397 | 638 |
| Language and builtins tests passing (of 2,445) | 14 | 211 | 218 | 454 |
| Adapted pyperformance ports working (of 25) | 0 | 20 | 25 | 25 |
| Unmodified upstream pyperformance files compiling (of 52) | 0 | 7 | 7 | 7 |
| Compiler / library / runtime lines | 4,423 / 0 / 2,154 | 45,928 / 46,979 / 9,804 | 66,345 / 55,294 / 14,800 | 71,678 / 59,716 / 15,018 |
| Compiler IR at the bootstrap fixed point (lines) | 52,488 | 707,289 | 906,887 | 981,589 |
| Microbenchmark speed index (× CPython 3.13) | 17.90 | 17.17 | 17.88 | 17.76 |
| Core ports speed index (× CPython 3.13) | — | 11.46 | 12.19 | 12.25 |
| `pystachy build` of `bench/nbody.py` (s) | 0.34 | 0.65 | 1.14 | 0.21 |

Weeks one and two added about 26 passing methods a day; weeks three to five added 26 in total while
compiler, library and runtime grew by about 31,000 lines, and language and builtins tests stayed at 218 from
27 October to 11 November. Then 241 more passed: bounded `match` (#1272, +95 by 12 November), `complex`
numbers and two small fixes (+8), and v0.6.0-alpha.1 (+138). Passing methods grew by 61% in the six days
after alpha.5, against 7% in the 22 days before it.

What blocks the rest at v0.6.0-alpha.1, by first error: in the language and builtins tests, dynamic-model
(1,076) and static-typing (533) errors make up 81% of 1,975 rejections, as on 12 November. Grouped by what
removing them needs (`scripts/groups.py`), the 5,242 rejected methods need a missing module or name (2,221),
a class-model, inference or `match` feature (1,500) or runtime reflection (483); 1,038 are unassigned. The
largest groups are other missing modules (1,140), `enum.member`/`verify`/`STRICT` (885, all of `test_enum`),
field and class-attribute types (444), classes inside functions (368) and `pickle` (247). Putting CPython
3.13.16's pure-Python standard library on the path (`import_sweep.py --overlay`) unlocks none of the 2,400
library-blocked methods: 1,487 stop at another missing module or name, 543 at dynamic code and 288 at
`configparser`'s `@cached_property` without a return annotation. Opting every test in to dynamic `Any`
leaves 638 passing (+7, −7).

After 20 October the compiler's share of changed lines fell from 16% to 5% and the library's from 8% to 3%,
while benchmarks and examples rose from 3% to 30% and tools/CI from 4% to 12%. From 12 to 17 November the
compiler's share was 10% and the library's 8%; tests took 39% and Lean proofs 24% (`raw/change_shares.json`).

The added surface did not cost run-time speed. The six day-one microbenchmarks ran
17.9× CPython 3.13 on the first day and 17.8× at v0.6.0-alpha.1. The 16 pyperformance ports working since
15 October went from 7.5× to 11.5× on 19 October (`lib/re` work, #676, #680, #682, #683, #685, and likely
#724/#727 for scimark and barnes_hut) and are at 12.2×. The first edition bisected two regressions, `words`
+30% at #667 and `float` +30% at #1268 (sizes from this run); #1336 fixed `float` and #1332 only part of
`words`. Compile time grew with the compiler and its runtime until #1377: the AOT build of the 82-line
day-one `bench/nbody.py` went from 0.34 s to 1.14 s at v0.5.0-alpha.1 and back to 0.21 s, while the
bootstrap went from 12 s to about 5 minutes. JIT end to end on the small programs stayed near 0.1 s.

## What was measured

Forty-eight commits on `main` between 7 October and 17 November 2026 (`commits.txt`): the last commit
of most days, 19 of the 26 release tags (every tag after 11 November) and `71e14a88`, which separates
#1519 from #1522. Each was built in its own worktree by its own `make` bootstrap (CPython 3.13.18 for
stage 1, LLVM 18.1.3) and reached its own fixed point; the first 35 were built on 12 November and the
other 13 on 18 November. Every workload is fixed, and none of their inputs changed on main in the window.

| Workload | Source | What counts |
|---|---|---|
| CPython test methods | `tools/cpython_test_methods.py` at `b2182a4f` extracted 9,855 unittest methods from the 144 pinned CPython 3.13.16 test files of `tests/upstream/core-methods.sha256` (all hashes verified); 5,905 complete under CPython 3.13.18 and form the denominator | The commit's `pystachy run` (JIT) prints CPython's stdout and stderr and exits the same way, as `triage` compares, including the promoting-int retry |
| Upstream pyperformance | The 52 `run_benchmark.py` files of pyperformance 1.14.0 (sdist SHA-256 `91f74393…`), runner replaced by `census_source()` | `pystachy ir` compiles the file |
| Adapted ports | The 25 ports in `bench/pyperformance` at `b2182a4f` plus the six original `bench/*.py` microbenchmarks (unchanged since the first commit) | AOT output equals CPython's; then timed |

Method results are classified by the text of the first compiler error (`classify.py`) and regrouped
by what removing it needs (`groups.py`). Only the first error of each method is visible.

Timing ran on 18 November after every build and analysis had finished, on an otherwise idle 4-vCPU
x86-64 VM: AOT executables pinned to one CPU, each repetition running CPython 3.13.18 and all 48 commits
in an order rotated by one position, with output checked on every run (`timing.py`). Ports report
pyperf's timed region; microbenchmarks report process wall time. The performance index is the geometric
mean of per-benchmark speedups over CPython on the same source, over a fixed set: the six
microbenchmarks, or the 16 ports that worked at every sample since the first one with ten working
ports. `unpack_sequence` is excluded: AOT removes its timed loop. JIT and `pystachy build` times are
medians of three runs after one untimed run per commit: a container restart just before the timing had
emptied the file cache, and the first attempt's two-run medians included cold runs
(`raw/timing-cold-jit-build.json`), so those two phases were run again (`scripts/timing_jit_build.sh`);
the AOT run timings, five or seven rotated runs per commit, were kept. Bootstrap times are single builds,
each run beside the previous commit's test sweep.

## Files

- `export/report.pdf`: the print edition, one topic per page (`print/` builds it); `export/report.html`
  (self-contained, works offline) and `export/report.md` (renders on GitHub) keep the dashboard layout,
  with one PNG per chart in `export/images/` and every dataset as CSV and JSON in `export/data/`.
- `commits.txt`: the 48 sampled commits (label, SHA).
- `data/*.json`: the rows charted on the dashboard (`samples`, `speedups`, `history` for all 684
  first-parent commits, `blockers_head`, `unlocks`, `census`, `changes`, `overlay_head`).
- `raw/methods_matrix.csv.gz`: one row per qualified method, one status code per commit (P pass, I pass
  with promoting ints, D compiled but differs, T timeout; rejected: L library, S syntax, Y typing,
  M dynamic, O other). `raw/methods_head_errors.csv.gz`: every method's status and first error at the
  latest commit.
- `raw/timing.json`: every timed run. `raw/builds.json`: bootstrap time, compiler IR lines, binary size.
  `raw/retime-*.json`: the 15-run re-timing of `float` and `words`. `raw/timing-cold-jit-build.json`: the
  discarded first JIT and build timings.
- `raw/progress-report-to-head.json`, `raw/progress-steps.txt`: methods gained and lost from the first
  edition's last commit to the latest, and between consecutive new samples, with their earlier first
  errors. `raw/groups-*.txt`: rejected methods grouped by what removing their first error needs, on
  12 and 17 November. `raw/change_shares.json`: changed lines by area in three periods.
- `raw/methods_head_overlay.json.gz`, `raw/methods_head_dynamic_any.json.gz`: the latest commit with
  CPython's pure-Python standard library on the path, and with every method opted in to dynamic `Any`.
- `scripts/`: the harness; `pipeline.sh`, `after_builds.sh`, `timing_phase.sh` and `timing_jit_build.sh`
  show the order in which it ran, and `figures.py` prints the figures this README quotes.
- `page/`: the dashboard (`index.html`, `render.js`) and `export.js`, which wrote `export/`.

## Reproduce

Paths in the scripts point at the session's scratch directory; adjust `S` first.

```sh
python3.13 -I scripts/extract_qualify.py CPYTHON-3.13.16-SRC sweep/methods sweep/qualified.json -j 2
scripts/pipeline.sh commits.txt          # build, method sweep, census, AOT/JIT checks
scripts/after_builds.sh                  # latest-commit probes, then timing on the idle machine
scripts/timing_jit_build.sh              # JIT and build phases again, with a warm-up run (resumable)
python3 scripts/git_metrics.py REPO origin/main sweep/git_metrics.json
python3 scripts/report.py commits.txt evolution.json raw/timing.json
python3 scripts/datasets.py evolution.json data
python3 scripts/analysis.py data
```

To redraw the charts from the committed `data/` (`export.js` reads `page/data` and d3 from
`page/node_modules`; it needs Playwright's Chromium):

```sh
cd page && ln -s ../data data && npm install d3@7.9.0 && node export.js OUTDIR
```
