# Why cached executables ran UMAP's kNN slower than the JIT runner (20 November 2026)

Raw evaluation, not for merging. Follows `../umap-numba-2026-11-13/refresh-2026-11-18/README.md`'s
"older gap": with the generic CPU, the program cache's executables ran kNN in 1.32 to 1.34 s against
the runner's 0.95 to 0.97 s on the same optimized module.

Setup: Sapphire Rapids VM (Xeon 2.1 GHz, 4 CPUs), Ubuntu LLVM 18.1.3, every timed process pinned to
CPU 1, variants interleaved with rotating order, 5 rounds, paired medians. Trees: main `d35417c9`
(rc.1) and the all-drafts merge `e12a580c` (`../umap-numba-2026-11-13/all-drafts-2026-11-19`), each
with `experiment-hook.patch` (uncommitted: `PYSTACHY_X_PCCOMPILE` replaces the cache's object compile,
`PYSTACHY_X_AOTFLAGS` extends AOT code generation) and built at a fixed point. All-drafts runs use
`PYSTACHY_JIT_CPU=generic`. `cgap.py` builds each program's cached executable per variant and times
them; `exes.py` times prebuilt executables; `summarize.py` prints the tables (`allx-suite-*.txt`).

## Mechanism

- The cache compiles the JIT tier's `opt` output with `clang -O2 -Xclang -disable-llvm-passes`:
  `-target-cpu x86-64`, which LLVM tunes as generic (for IR input `-mtune` changes nothing). The
  runner creates its target machine with no CPU, as lli does: LLVM's fallback, i586's tuning.
- The tuning difference that changes kNN is `idivq-to-divl` (CodeGenPrepare's 64-bit division bypass:
  a 32-bit `div` behind a run-time check). In LLVM 18 generic, x86-64, x86-64-v3, skylake,
  icelake-server, alderlake and sapphirerapids tuning all enable it; znver3, znver4 and no CPU do not.
  `llc` on the all-drafts module (`reloads.py`): with it, kNN's per-pair loop reloads 16 values and
  the distance copy compares against `dim` in a stack slot; without it, 10 reloads, `dim` in a
  register. kNN has no division: the bypass lengthens other phases of the fully inlined `main`, and
  `dim`, live until the final `print`, loses its register in kNN. #1575's host-CPU slowdown was the
  same switch (`-default-tuning` drops it).
- Placement: the cached executable's 33-byte distance loop starts at offset 48 of a 64-byte line.
- On rc.1 the program object has no division (`//` and `%` are runtime calls; 0 `div` in UMAP's and
  the micro's `f.main`): the bypass flag leaves the executable byte-identical. The divisions come
  from #1468's inlined copies of `pys_floordiv` and `pys_mod`.

## Results

| Comparison | kNN | Other |
|---|---:|---|
| rc.1, cached: runner's code generation (`llc`) / clang (`rc1x-umap.json`) | 1.00 | layout 1.04, division micro 1.00 |
| All drafts, runner / cached (`allx-umap.json`) | 0.84 | layout 0.95, division micro 1.63 |
| All drafts, cache module rebuilt: bypass off / on (`align-umap.json`) | 0.89 | 64-byte loops: 0.93; both 0.73 |
| All drafts suite, bypass off (`allx-suite-1`) | 0.92 | geomean 1.012; division micro 1.59, regex_v8 1.23 |
| All drafts suite, runner's code generation | 0.90 | geomean 1.006; division micro 1.58 |
| All drafts suite, 64-byte loops, two runs | 0.79, 0.91 | geomean 0.991, 0.988; single programs +-10% |
| All drafts suite, innermost loops 64 / 32 bytes (`allx-suite-2`) | 0.88 / 1.04 | geomean 0.982 / 1.000 |

Ratios are variant / reference (below 1 is faster); the suite covers 43 programs (`bench/*.py`,
`bench/pyperformance` at its measured sizes, the UMAP probe's two stages, `divmicro.py`).
One cached executable's kNN ranged from 0.94 to 1.35 s over 12 runs, with or without ASLR
(`spread-clang-umap.txt`): directions held in every round, magnitudes did not.

## Conclusions

- No code generation setting closes the gap for free. Turning the bypass off makes kNN faster and
  division-heavy loops 1.6 times slower; with #1468 the runner, which never had it, is the slower
  path for division.
- Loop alignment at 64 bytes helps kNN in every round and averages about 1% over the suite, with
  per-program swings both ways; 32 bytes is worse for the 33-byte loop.
- Measurements with `PYSTACHY_PROGRAM_CACHE=0` time the runner's code, which differs from what the
  default (cached) path runs.

## Implemented (20 November, later)

- #1612 (`claude/dreamy-shannon-bb3cu1-jit-x86-64`, on main `d35417c9`): the driver gives the runner,
  lli and llc clang's default CPU on x86-64 Linux (`-mcpu=x86-64`; the runner takes lli's `-mcpu`).
  Runner on main against the branch (`main-runner-ab.json`, `runner_ab.py`, 43 programs, 5 rounds):
  geomean 0.990, UMAP kNN 0.96 and layout 0.97, the division micro 1.02 (main divides in the
  runtime), code generation 1.014.
- #1575 reverts `-default-tuning` (head `39b4181f`, the tree of `a1d94d2a`).
- All drafts with both (scratch `e99f79e6`), runner over cached (`all-drafts-summary.json`): generic
  CPU, division micro 1.63 before and 1.01 after, kNN 0.84 and 1.02, layout 0.95 and 1.00; host
  CPU, 0.97, 0.96 and 1.01. In the host-CPU run, json_loads and regex_v8 read 0.86 and 0.88, but
  regex_v8's cached executable is byte-identical to the generic run's, where it read 0.99:
  run-to-run variance.
