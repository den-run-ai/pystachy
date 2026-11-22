# Speed and Python surface across Pystachy's history, third edition (2026-11-22)

Raw evaluation for a research branch; not for merging into `main` (`research/` is rejected by
`tools/check_repository_hygiene.py` on production branches). Prepared with an AI coding agent at the
repository owner's request.

This edition extends `research/speed-vs-surface-2026-11-18` (the second edition) and
`research/speed-vs-surface-2026-11-12` (the first), both left unchanged, through `main` `4998521d`
(v0.7.0-alpha.2, 21 November 2026), with the same inputs and harness. It measures 56 commits
and times all of them again in one run, so its speed numbers differ slightly from earlier editions'.

## Progress since the second edition

Between `3cf23d20` (v0.6.0-alpha.1, the second edition's last measurement, 17 November) and `4998521d`,
main took 886 commits, nine first-parent merges and eight release tags, which carried 139 pull requests:

| | v0.6.0-alpha.1 (second edition) | v0.6.0 | v0.7.0-alpha.2 |
|---|---:|---:|---:|
| CPython test methods passing (of 5,905) | 638 | 655 | 683 |
| Language and builtins tests passing (of 2,445) | 454 | 469 | 479 |
| Library tests passing (of 3,460) | 184 | 186 | 204 |
| Methods rejected at compile time | 5,242 | 5,226 | 5,196 |
| … whose first error is a missing module or name (`groups.py`) | 2,221 | — | 1,044 |
| … whose first error is a class-model, inference or `match` feature | 1,500 | — | 2,391 |
| Unmodified upstream pyperformance files compiling (of 52) | 7 | 9 | 9 |
| Adapted ports and microbenchmarks matching CPython (of 31) | 31 | 31 | 31 |
| Core ports speed index (× CPython 3.13) | 11.49 | 11.79 | 11.78 |
| Microbenchmark speed index (× CPython 3.13) | 17.69 | 18.55 | 18.14 |
| `pystachy build` of `bench/nbody.py` | 0.27 s | 0.25 s | 0.31 s |
| Compiler lines (`pystachy.py` and `src/`) | 71,678 | 77,868 | 83,625 |
| Compiler IR at the bootstrap fixed point (lines) | 981,589 | 1,064,204 | 1,141,334 |
| Bootstrap, rebuilt alone on the idle machine (s) | 289 | — | 415 |

The 45 newly passing methods, with no method lost:

| Change | Pull request | Release | Methods |
|---|---|---|---:|
| Classes defined inside functions that run at most once | #1613 | v0.7.0-alpha.1 | 21 (11 files) |
| The `gc` module | #1351, landed in #1548 | v0.6.0-alpha.3 | 12 (`test_dict` 8, `test_tuple` 3, `test_weakref` 1) |
| `enum.member` and `enum`'s private helpers | #1563 | v0.7.0-alpha.1 | 7 (`test_enum`) |
| `bytearray` | #1478 | v0.6.0-alpha.3 | 2 (`test_bytes`, `test_copy`) |
| Fixes among the 40 pull requests of #1546 | #1546 | v0.6.0-alpha.2 | 3 (`test_bool`, `test_format`, `test_set`) |

v0.6.0-rc.1, rc.2, v0.6.0, v0.6.1 and v0.7.0-alpha.2 changed no result apart from
`MersenneTwister_TestBasicOps.test_randrange_bug_1590891`, which passes at random: with promoting integers,
`randrange(10**12, -10**20, -200)` overflows 64 bits inside the shipped `random` module for most seeds
(1 of 12 runs passed with v0.6.0-alpha.1's compiler, 3 of 12 with v0.7.0-alpha.2's). It is counted as
measured, so totals can move by one between neighbouring commits. Set aside, this harness reproduces the
project's own counts exactly: 641 at v0.6.0-alpha.2 (#1560) and 683 at v0.7.0-alpha.1 (draft #1673).

Most of the week's surface work moved first errors rather than passes. `enum`'s missing names were the
first error of all 885 `test_enum` methods that stopped at an import; with #1563, 7 pass and most
of the rest stop at a class attribute's type (the field group grew from 444 to 928),
an enum class made at run time (206) or `super()` in a secondary base
(105). `gc` (#1351) made 12 of the 142 methods it stopped pass, as a
stand-in had made 11 of 141 on 12 November; `inspect` (#1417) made none of 54 pass, 44 now
stopping at `compile()` of a string, as its probe had predicted. #1613 made 21 of the 368
local-class methods pass; 247 still stop there (`raw/progress-*.json`, `raw/groups-*.txt`).

Run-time speed did not move beyond noise. The core ports' index was 11.49× CPython 3.13 at v0.6.0-alpha.1 and
11.78× at v0.7.0-alpha.2, the microbenchmark index 17.69× and 18.14×; the nine samples from 17 to 21 November
range from 11.34× to 11.79× and from 17.29× to 18.66×. Single benchmarks are noisier: v0.6.0-rc.2 and v0.6.0
build byte-identical `sieve` executables whose medians differ by 22% in this run. Re-timed 15 times
(`raw/retime-*.json`), only `chaos` moved beyond noise since 17 November: 27.4 ms at v0.6.0-alpha.2 and 25.3
ms at alpha.3, whose float fast paths removed its `trunc()` calls (#1437); `nqueens`, `regex_dna`, `raytrace`,
`richards_super` and `spectral` did not.

This run's indices are lower than the second edition's for the same 48 commits, by 6% on average for the core
index and 2% for the microbenchmark index (at most 8.7%): the runs used different hosts, and CPython took
553.9 ms for `float` here against 520.8 ms then. Compare speed within one edition. `float`'s fix holds: 40.8
ms before #1268, 39.4 ms after #1336 and 40.4 ms now. `words` takes 71.1 ms at v0.7.0-alpha.2 against 67.8 ms
before #667 (+5%); v0.6.0-alpha.1 was 9% slower here and 19% in the second edition's run, so the gap depends
on the host, while the heap growth of #667 remains (#1301). `fib` has run about 4% slower since #1377 (37.8 →
39.3 ms), the code-placement effect that #1377's evaluation found.

AOT builds stayed cheap: `pystachy build` of `bench/nbody.py` took 0.27 s on 17 November and
0.31 s at v0.7.0-alpha.2 (pinned, medians of three after an untimed run); nbody's executable grew from
155,280 to 156,792 bytes. The compiler grew by 17% in four days,
from 71,678 to 83,625 lines, and its IR at the bootstrap fixed point from
981,589 to 1,141,334 lines. Rebuilt one at a time on the idle machine
(`raw/bootstrap-idle.json`), the bootstrap took 248 s at `8434a911` (12 November),
289 s at v0.6.0-alpha.1 and 415 s at v0.7.0-alpha.2 (247, 287
and 413 s of CPU). The pipeline's own single builds, made beside the previous commit's test sweep on
22 November, took 370 s at v0.6.0-alpha.2 and 427 s at v0.7.0-alpha.2.

The frontend explains about half of the bootstrap's growth since 17 November. With each compiler compiling its own
source on the idle machine (`raw/selfcompile.json`, `raw/frontend-series.json`), the native frontend took
5.0 to 6.6 s at v0.6.0-alpha.1 and 12.4 to 16.2 s at v0.7.0-alpha.2 over all runs, the frontend run by CPython (the
bootstrap's first step) 30.4 s and 82.8 s, and the full native build (frontend and LLVM
`-O2`) 128 s and 146 s. The source, not the compiler, became slower to compile:
v0.6.0-alpha.1's compiler needs 12.5 to 13.0 s on v0.7.0-alpha.2's source, and
v0.7.0-alpha.2's compiler 6.2 to 8.5 s on v0.6.0-alpha.1's. Its inference takes three passes
instead of one, because in three functions a variable holds two types and each join restarts the whole program
(`scripts/rejoin_sites.py`, `raw/retry-probe.json`): `k` in `driver.compile_program` (`int | str`, since `e65f8066` in
v0.6.0-alpha.2), `known` in `driver.main` (`bool | str`, #1646) and `x`, `y` in `ircheck.gen_verify` (`int | str`, #1637),
both in v0.7.0-alpha.2. Renamed in a scratch copy (nothing in the repository changed), the source compiled in one
pass: 6.4 to 7.0 s natively and 39.7 s under CPython. The GC-stressed self-compilation reached 590 s of its 600 s
bound at v0.7.0-alpha.1 when collecting every 5,000 allocations; #1629 widened the interval to 7,000 (412 and
417 s on CI), and restoring 5,000 needs the reduction #1181 asks for.

## Relevant pull requests, documentation and issues

Issues this report filed or relied on, as of 22 November:

| Issue | Status |
|---|---|
| #1300 `float` +37% after #1268 | Closed. #1336 landed in v0.4.0-rc.1; this edition's re-timing confirms the fix holds |
| #1301 `words` +22% after #667 | Open. #1518 (Unicode tables, v0.6.0-alpha.2 and alpha.3) cut `bench/words.py`'s instructions by 2.8%; the larger heap and second collection remain |
| #1302 weekly timing of all ports | Closed. The weekly workflow (#1339) has run once, on 16 November; the next run, due 23 November, will time 38 ports. Results stay in 90-day CI artifacts |
| #1303 triage and build cost per release | Open. #1560 gives 641 methods at v0.6.0-alpha.2 and draft #1673 683 at v0.7.0-alpha.1, both reproduced here; the comparison tool and release step are only in drafts #1673 and #1685 |
| #1304 classes defined inside functions | Open, partly addressed: #1613 (v0.7.0-alpha.1) compiles classes in functions that run at most once; 21 methods pass, 247 still stop there |
| #1305 mapping, starred and class patterns | Open. Mapping and class patterns on ordinary classes are still rejected (57 methods); no pull request adds them |
| #1306 rank surface work by measured unlocks | Closed as a duplicate; #1560 now plans 0.7.0 from measured blockers |
| #706 AOT build cost | Closed by #1377 (precompiled runtime, v0.5.0-alpha.2) |
| #1181 GC-stressed self-compilation | Open. 590 s of the 600 s bound at v0.7.0-alpha.1; interval widened from 5,000 to 7,000 allocations |
| #118 field inference | Open. #1295, #1368, #1375 (alpha.2) and #1388 (alpha.3) landed; drafts #1665 and #1686 continue it |

Documentation: no release note from v0.6.0-alpha.2 to v0.7.0-alpha.2 states a CPython test-method count,
a bootstrap time or a benchmark timing, apart from Unicode case methods taking 0.3 to 1.9 times CPython's
time (v0.6.0-alpha.3, v0.6.0) and "38 of 52" pyperformance benchmarks ported (v0.7.0-alpha.1). The README's
performance table still shows commit `f07472a5`'s measurements of 11 November; its example executable is now
175 kB and its test counts "more than 2,900" programs and "more than 2,200" rejections. `docs/testing.md`
records the gc-self numbers above; `docs/stdlib.md` adds `pprint`, `subprocess`, `concurrent.futures`, `gc`,
parts of `inspect` and `importlib`, and `enum`'s functional API at module level; `docs/llvm-toolchain.md`
records a `make` bootstrap of 308 to 315 s on a compiler from about v0.6.0-rc.1.

Open pull requests that reach the largest remaining blockers: enum classes stored in class attributes
(#1686), field and annotation inference (#1665, #1657, #1687, #1674, #1688), a `match` fall-through fix that
makes 10 more `test_patma` methods pass (#1689), per-release counts (#1673, #1685) and compile cost (#1664,
#1670). None adds mapping or class patterns, `pickle`, `configparser`, `locale`, `array` or the remaining
local-class forms.

## Findings over the whole history

| | Oct 8 (first day) | Oct 20 (v0.1.0-alpha.2) | Nov 11 (v0.4.0-alpha.5) | Nov 17 (v0.6.0-alpha.1) | Nov 21 (v0.7.0-alpha.2) |
|---|---:|---:|---:|---:|---:|
| CPython test methods passing (of 5,905) | 15 | 371 | 397 | 638 | 683 |
| Language and builtins tests passing (of 2,445) | 14 | 211 | 218 | 454 | 479 |
| Adapted pyperformance ports working (of 25) | 0 | 20 | 25 | 25 | 25 |
| Unmodified upstream pyperformance files compiling (of 52) | 0 | 7 | 7 | 7 | 9 |
| Compiler / library / runtime lines | 4,423 / 0 / 2,154 | 45,928 / 46,979 / 9,804 | 66,345 / 55,294 / 14,800 | 71,678 / 59,716 / 15,018 | 83,625 / 75,411 / 17,557 |
| Compiler IR at the bootstrap fixed point (lines) | 52,488 | 707,289 | 906,887 | 981,589 | 1,141,334 |
| Microbenchmark speed index (× CPython 3.13) | 17.54 | 17.42 | 17.44 | 17.69 | 18.14 |
| Core ports speed index (× CPython 3.13) | — | 10.66 | 11.40 | 11.49 | 11.78 |
| `pystachy build` of `bench/nbody.py` (s) | 0.34 | 0.86 | 1.17 | 0.27 | 0.31 |

Weeks one and two added about 26 passing methods a day; weeks three to five added 26 in total while
compiler, library and runtime grew by about 31,000 lines. Then 286 more passed: bounded `match` (#1272, +95
by 12 November), v0.6.0-alpha.1's field inference and starred patterns (+138), the `gc` module, local classes
and `enum` names of 18 to 20 November (+40), and 13 through smaller fixes.

What blocks the rest at v0.7.0-alpha.2, by first error: grouped by what removing them needs
(`scripts/groups.py`), the 5,196 rejected methods need a missing module or name (1,044),
a class-model, inference or `match` feature (2,391) or runtime reflection (510);
1,251 are unassigned. The largest groups are other missing
modules (1,044), field and class-attribute types (928), builtin base classes
(262), classes inside functions (247), enum classes made at run time or
with mixins (206) and `pickle` (188). On 17 November the largest were other
missing modules (1,140), the `enum` names (885) and field types (444).
In the language and builtins tests, dynamic-model (955) and static-typing
(578) first errors make up
79% of
1,949 rejections. Putting CPython 3.13.16's pure-Python standard library on the
path (`import_sweep.py --overlay`) unlocks none of the 1,421 methods blocked by a missing library piece;
`configparser`'s 288 stop at a `@cached_property` without a return annotation and `locale`'s 176 at a
redefinition. Opting every test in to dynamic `Any` passes 8 more and 5 fewer.

From 18 to 21 November the compiler's share of changed lines was 11% and the library's
11%; tests took 29%, benchmarks and examples 19%, tools and CI
17%, and the new `wasm/` directory 3% (`raw/change_shares.json`). From 12 to
17 November the compiler took 10%, the library 8% and Lean proofs
24%.

## What was measured

56 commits on `main` between 7 October and 21 November 2026 (`commits.txt`): the last commit of
most days, 27 of the 34 release tags (every tag after 11 November) and `71e14a88`, which separates #1519
from #1522. Each was built in its own worktree by its own `make` bootstrap (CPython 3.13.18 for stage 1,
LLVM 18.1.3) and reached its own fixed point: the first 35 on 12 November, 13 on 18 November and the last 8
on 22 November. Every workload is fixed: the inputs are frozen copies, identical for every commit.

| Workload | Source | What counts |
|---|---|---|
| CPython test methods | `tools/cpython_test_methods.py` at `b2182a4f` extracted 9,855 unittest methods from the 144 pinned CPython 3.13.16 test files of `tests/upstream/core-methods.sha256` (all hashes verified); 5,905 complete under CPython 3.13.18 and form the denominator | The commit's `pystachy run` (JIT) prints CPython's stdout and stderr and exits the same way, as `triage` compares, including the promoting-int retry |
| Upstream pyperformance | The 52 `run_benchmark.py` files of pyperformance 1.14.0 (sdist SHA-256 `91f74393…`), runner replaced by `census_source()` | `pystachy ir` compiles the file |
| Adapted ports | The 25 ports in `bench/pyperformance` at `b2182a4f` plus the six original `bench/*.py` microbenchmarks; main now has 38 ports, but the set stays fixed | AOT output equals CPython's; then timed |

Method results are classified by the text of the first compiler error (`classify.py`) and regrouped
by what removing it needs (`groups.py`). Rules for messages that first appear after 17 November (secondary
bases, nested classes after a call, enum class forms) were added; they match no earlier error, so the
earlier samples classify exactly as in the second edition. Only the first error of each method is visible.

Timing ran on 22 November after every build and analysis had finished, on an otherwise idle 4-vCPU
x86-64 VM: AOT executables pinned to one CPU, each repetition running CPython 3.13.18 and all 56 commits
in an order rotated by one position, with output checked on every run (`timing.py`). Ports report
pyperf's timed region; microbenchmarks report process wall time. The performance index is the geometric
mean of per-benchmark speedups over CPython on the same source, over a fixed set: the six
microbenchmarks, or the 16 ports that worked at every sample since the first one with ten working
ports. `unpack_sequence` is excluded: AOT removes its timed loop. JIT and `pystachy build` times are
medians of three runs after one untimed run per commit. Over the 48 commits that the second
edition also timed, the two runs' indices agree within 8.7% (core) and
8.0% (micro), with median differences of 6.0% and
2.1% (`raw/edition-agreement.json`). Pipeline bootstrap times are single builds, each run
beside the previous commit's test sweep on one of three days; the three idle rebuilds compare directly.

## Files

- `export/report.pdf`: the print edition, one topic per page (`print/` builds it); `export/report.html`
  (self-contained, works offline) and `export/report.md` (renders on GitHub) keep the dashboard layout,
  with one PNG per chart in `export/images/` and every dataset as CSV and JSON in `export/data/`.
- `commits.txt`: the 56 sampled commits (label, SHA).
- `data/*.json`: the rows charted on the dashboard (`samples`, `speedups`, `history` for all 693
  first-parent commits, `blockers_head`, `unlocks`, `census`, `changes`, `overlay_head`).
- `raw/methods_matrix.csv.gz`: one row per qualified method, one status code per commit (P pass, I pass
  with promoting ints, D compiled but differs, T timeout; rejected: L library, S syntax, Y typing,
  M dynamic, O other). `raw/methods_head_errors.csv.gz`: every method's status and first error at the
  latest commit.
- `raw/timing.json`: every timed run. `raw/builds.json`: bootstrap time, compiler IR lines, binary size.
  `raw/retime-*.json`: the 15-run re-timings of `float`, `words` and `fib`. `raw/bootstrap-idle.json`: the
  three idle-machine bootstraps. `raw/edition-agreement.json`: this run against the second edition's.
  `raw/selfcompile.json`, `raw/frontend-series.json`, `raw/retry-probe.json`: each compiler compiling its own
  source, the frontend per release and across sources, and what restarts its inference.
- `raw/progress-prev-to-head.json`, `raw/progress-report-to-head.json`, `raw/progress-steps.txt`: methods
  gained and lost since the second and first editions' last commits, and between consecutive samples, with
  their earlier first errors. `raw/groups-*.txt`: rejected methods grouped by what removing their first
  error needs, on 12 November, 17 November and 21 November. `raw/change_shares.json`: changed lines by area in
  four periods.
- `raw/methods_head_overlay.json.gz`, `raw/methods_head_dynamic_any.json.gz`: the latest commit with
  CPython's pure-Python standard library on the path, and with every method opted in to dynamic `Any`.
- `scripts/`: the harness; `pipeline.sh` and `after_builds.sh` show the order in which it ran,
  `figures.py` prints figures the text quotes and `readme.py` writes this README.
- `page/`: the dashboard (`index.html`, `render.js`) and `export.js`, which wrote `export/`.

## Reproduce

Paths in the scripts point at the session's scratch directory; adjust `S` first.

```sh
python3.13 -I scripts/extract_qualify.py CPYTHON-3.13.16-SRC sweep/methods sweep/qualified.json -j 2
scripts/pipeline.sh commits.txt          # build, method sweep, census, AOT/JIT checks
scripts/after_builds.sh                  # latest-commit probes, timing, re-timings, idle bootstraps
python3 scripts/git_metrics.py REPO origin/main sweep/git_metrics.json
python3 scripts/report.py commits.txt evolution.json raw/timing.json
python3 scripts/datasets.py evolution.json data
python3 scripts/changes.py data && python3 scripts/analysis.py data
python3 scripts/readme.py . README.md
```

To redraw the charts from the committed `data/` (`export.js` reads `page/data` and d3 from
`page/node_modules`; it needs Playwright's Chromium):

```sh
cd page && ln -s ../data data && npm install d3@7.9.0 && node export.js OUTDIR
```
