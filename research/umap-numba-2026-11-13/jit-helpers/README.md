# The runtime's small functions inlined into JIT code (#705): measurements (14 November 2026)

[#1468](https://github.com/den-run-ai/pystachy/pull/1468) gives a program that the JIT's inliner
runs over `available_externally` copies of the small runtime functions it calls
(`jit_helpers.py`), so that a `list[float]` read or assignment, float division, `math.sqrt()`, a
shift or an int `%` is inlined into a loop, as an AOT build inlines the runtime. These are the
measurements behind it; the compact, committed copy is `bench/results/jit-helpers-2026-11-14.json`
on that branch (commit `feab588a`). Variant A, "calls", is `PYSTACHY_OPT=-jithelpers` (main's
behavior); B, "helpers", the default with the copies.

## Setup

Native compiler of `c162676b` (main `5f81cc25` plus the copies), x86-64, Ubuntu LLVM 18.1.3,
CPython 3.13.18 as the oracle, a 4-vCPU VM whose host adds about ±10% between runs (the first and
final matrices below differ by that much on some rows; CPU steal stays near 1%). Every run's output
equals CPython's.

- `run_helpers.sh` / `jit_variants.py`: interleaved rounds, rotating order, `taskset -c 1`, program
  cache off, `PYSTACHY_TIMING=1`; `results/` is the final tree's run, `results-first/` the run of
  the first commit (`12581b86`, before `pys_bytes_get` was left out).
- `cache_hits.py`: program cache hits (no compilation) in a private cache, 5 rounds (`hits/`).
- `callgrind_variants.sh`: callgrind's instruction count of the program cache's executable of
  each variant (built from the module the JIT pipeline optimized) — deterministic
  (`callgrind.tsv`).
- `four_final.py`: the UMAP probe on #1450's head, #1456 and #1468 merged (scratch tree
  `e14bc678`), hosted frontend, 3 rounds: the program's own stage timers only.

## Instructions executed (callgrind)

| Program | Calls | Helpers | Ratio |
|---|---:|---:|---:|
| spectral_norm 5 | 188,694,470 | 83,939,900 | 0.445 |
| scimark 1 | 221,107,200 | 128,107,853 | 0.579 |
| nbody 5 | 542,742,726 | 319,139,259 | 0.588 |
| UMAP probe, 1,000 points, 20 epochs | 1,369,015,402 | 996,204,835 | 0.728 |
| chaos 2 | 65,341,331 | 58,974,160 | 0.903 |
| richards 10 | 101,463,272 | 92,724,855 | 0.914 |
| json_loads 200 | 917,950,051 | 902,254,001 | 0.983 |
| fannkuch 1 | 985,344,587 | 976,954,109 | 0.991 |
| regex_v8 2 | 18,199,270,833 | 18,199,270,815 | 1.000 (above the inliner's IR budget: no copies) |

## Program cache hits (5 paired rounds)

| Program | Wall, calls | Wall, helpers | Paired |
|---|---:|---:|---:|
| UMAP probe, 10,000 points | 10.056 | 7.759 | 0.776 (kNN 0.743, layout 0.792) |
| spectral_norm 100 | 0.253 | 0.158 | 0.611 |
| scimark 20 | 0.333 | 0.202 | 0.632 |
| nbody 100 | 0.771 | 0.574 | 0.748 |
| json_loads 10000 | 3.772 | 3.360 | 0.924 |
| richards 200 | 0.212 | 0.207 | 0.931 |

## Uncached launches

`table-uncached.md` has every row. Compile time (frontend, `opt`, code generation) grows with the
inlined code: up to 75 ms (scimark, 0.109 → 0.184 s), so a short run is slower (scimark at its
default size 1.38×, go 1.21×) while a longer one is faster (scimark with ten times its loops
0.84×, nbody 0.72×, spectral_norm 0.65×). Programs above the inliner's 20,000-line budget (the
import-heavy command, the router, the regex ports) get no copies. The whole JIT corpus (4,643
cases, 4 workers, cache off) took 122 and 126 s with calls, 129 and 129 s with helpers (4%).
About a third of the inlined code in these programs lies outside any loop (`loop_sites.py`); only
inlining where a loop (or a function called from one) calls would cut that, a follow-up.

`pys_bytes_get` is left out: programs call it only off `listfast`'s inline read, and its copy
made json_loads' loop 5% slower; without it, 4% faster (`json_nobytes.json`, the first commit's
table with that item removed).

## The UMAP probe with #1450, #1456 and #1468 (seconds, medians of 3)

| Stage | Cleanup, calls | Cleanup, helpers | `-O2`, calls | `-O2`, helpers |
|---|---:|---:|---:|---:|
| kNN | 2.153 | 1.336 | 1.649 | 0.943 |
| layout | 5.019 | 4.260 | 4.972 | 3.839 |

Numba in the same session (`../numba_knn.py`, `../numba_twin.py`, one thread, warm call, 3
runs): kNN strict 0.534–0.797 s (median 0.755), fastmath 0.275–0.390 s; layout twin 2.939–3.462 s
(median 3.355), bit-identical embedding. So with the three PRs and `PYSTACHY_JIT_OPT=2`, the JIT
runs the exact kNN within about 25% of Numba's strict IEEE order and the layout within about 15%;
without `-O2` (the default), 1.8× and 1.3×. Not interleaved with the Pystachy runs.
