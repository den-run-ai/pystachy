# Speed and Python surface across Pystachy's history (2026-11-12)

Raw evaluation for a research branch; not for merging into `main` (`research/` is
rejected by `tools/check_repository_hygiene.py` on production branches). Prepared
with an AI coding agent at the repository owner's request.

Question: how did performance relate to the amount of Python that Pystachy runs
unmodified, commit by commit, what did the features cost, and is language
coverage stalling because of the typed-IR, interpreter-free design?

## Findings

Surface grew fast for two weeks and then stopped:

| | Oct 8 (first day) | Oct 20 (v0.1.0-alpha.2) | Nov 11 (v0.4.0-alpha.5) |
|---|---:|---:|---:|
| CPython test methods passing (of 5,905) | 15 | 371 | 397 |
| Language and builtins tests passing (of 2,445) | 14 | 211 | 218 |
| Adapted pyperformance ports working (of 25) | 0 | 20 | 25 |
| Unmodified upstream pyperformance files compiling (of 52) | 0 | 7 | 7 |
| Compiler / library / runtime lines | 4,423 / 0 / 2,154 | 45,928 / 46,979 / 9,804 | 66,345 / 55,294 / 14,800 |
| Compiler IR at the bootstrap fixed point (lines) | 52,488 | 707,289 | 906,887 |

Weeks one and two added about 26 passing methods a day; weeks three to five added
26 in total while compiler, library and runtime grew by about 31,000 lines. Language
and builtins tests have been flat at 218 since 27 October.

What blocks the rest, by first error at `b2182a4f`: in the language and builtins
tests, 1,060 dynamic-model errors (classes defined in functions, builtin, generic or
multiple bases, classes and modules as values, statement-bearing class bodies,
`eval`/`exec`, `gc`/`pickle`/`inspect`) and 635 static-typing errors (types the
compiler cannot infer, mostly fields) make up 76% of 2,220 rejections; `match`
(216) is the largest unbuilt syntax. Since alpha.2, no method blocked by the dynamic
model and 7 blocked by typing started to pass. Putting CPython 3.13.16's pure-Python
standard library on the path (`import_sweep.py --overlay`) unlocks none of the 2,429
library-blocked methods: they next hit missing C modules (708), dynamic-model
code in CPython's library and tests (360) or names Pystachy's own ports lack. Opting
every test in to dynamic `Any` leaves 397 passing. After 20 October the compiler's
share of changed lines fell from 16% to 5% and the library's from 8% to 3%, while
benchmarks/examples rose from 3% to 31% and tools/CI from 4% to 12%.

Speed did not pay for the surface. The six day-one microbenchmarks ran 18.1x
CPython 3.13 on the first day and 18.0x at alpha.5. The 16 pyperformance ports
working since 15 October went from 7.4x to 11.3x on 19 October (`lib/re` work,
#676, #680, #682, #683, #685, and likely #724/#727 for scimark and barnes_hut) and
11.9x at alpha.5. Two regressions were bisected: `words` +31% time at #667
(Unicode code-point strings, stage 1) and `float` +33% at #1268 (listguard
bounds-check hoisting with Lean checks; the last sample before alpha.5 measured
32.7 ms, alpha.5 43.5 ms). The cost appeared in compile time instead: `pystachy build`
of the 82-line day-one `bench/nbody.py` went from 0.31 s to 1.13 s, richards and raytrace builds
grew about 60% since mid-October, and the bootstrap from 13 s to about 4 minutes.
JIT end to end on the small programs stayed near 0.1 s.

## What was measured

Thirty-four commits on `main` between 7 October and 11 November 2026: an
end-of-day commit for most days and every release tag (`commits.txt`). Each
was built in its own worktree by its own `make` bootstrap (CPython 3.13.18 for
stage 1, LLVM 18.1.3) and reached its own fixed point. Every workload below is
fixed: the same files are given to every commit.

| Workload | Source | What counts |
|---|---|---|
| CPython test methods | `tools/cpython_test_methods.py` at `b2182a4f` extracted 9,855 unittest methods from the 144 pinned CPython 3.13.16 test files of `tests/upstream/core-methods.sha256` (all hashes verified); 5,905 complete under CPython 3.13.18 and form the denominator | The commit's `pystachy run` (JIT) prints CPython's stdout and stderr and exits the same way, as `triage` compares, including the promoting-int retry |
| Upstream pyperformance | The 52 `run_benchmark.py` files of pyperformance 1.14.0 (sdist SHA-256 `91f74393…`), runner replaced by `census_source()` | `pystachy ir` compiles the file |
| Adapted ports | The 25 ports in `bench/pyperformance` at `b2182a4f` plus the six original `bench/*.py` microbenchmarks (unchanged since the first commit) | AOT output equals CPython's; then timed |

Method results are classified by the text of the first compiler error
(`classify.py`): library (module/name/API not provided), syntax (construct not
implemented), typing (inference needs an annotation, or a value differs from the
one static type chosen for it), dynamic (classes or modules as runtime values,
classes in functions, builtin, generic or multiple bases, dynamic class bodies,
`eval`/`exec`/`compile`, exception/frame/GC introspection and reflective
modules such as `pickle`, `gc`, `inspect`), other. Only the first error of each
method is visible; imports come first, so a missing module hides later errors.

Timing ran after every build and analysis had finished, on an otherwise idle
4-vCPU x86-64 VM: AOT executables pinned to one CPU, each repetition running
CPython 3.13.18 and every commit in an order rotated by one position, with
output checked on every run (`timing.py`). Ports report pyperf's timed region;
microbenchmarks report process wall time. The performance index is the
geometric mean of per-benchmark speedups over CPython on the same source, over
a fixed set: the six microbenchmarks, or the core set of ports that worked at
every sample since the first one with ten working ports. `unpack_sequence` is
excluded: AOT removes its timed loop.

## Files

- `export/`: the report for offline reading: `report.md` (renders on GitHub with its
  images), `report.html` (self-contained, works offline), `report.pdf`, one PNG per
  chart in `images/`, and every dataset as CSV and JSON in `data/`.
- `commits.txt`: sampled commits (label, SHA).
- `data/*.json`: the rows charted on the dashboard (`samples`, `speedups`,
  `history` for all 660 first-parent commits, `blockers_head`, `unlocks`, `census`).
- `methods_matrix.csv.gz`: one row per qualified method, one status code per commit
  (P pass, I pass with promoting ints, D compiled but differs, T timeout; rejected:
  L library, S syntax, Y typing, M dynamic, O other).
- `methods_head_errors.csv.gz`: every method's status and first error at `b2182a4f`.
- `timing.json`: every timed run. `builds.json`: build time, compiler IR lines, binary size.
- `scripts/`: the harness (`build_one.sh`, `pipeline.sh`, `analyze_one.py`,
  `method_sweep.py`, `extract_qualify.py`, `timing.py`, `report.py`,
  `datasets.py`, `classify.py`, `analysis.py`, `git_metrics.py`, `export_matrix.py`).

## Reproduce

Paths in the scripts point at the session's scratch directory; adjust `S` first.

```sh
python3.13 -I scripts/extract_qualify.py CPYTHON-3.13.16-SRC sweep/methods sweep/qualified.json -j 2
scripts/pipeline.sh commits.txt          # build, method sweep, census, AOT/JIT checks
python3.13 -I scripts/timing.py commits.txt timing.json   # idle machine only
python3 scripts/report.py commits.txt evolution.json timing.json
python3 scripts/datasets.py evolution.json data
python3 scripts/analysis.py data
```
