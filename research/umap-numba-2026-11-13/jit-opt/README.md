# LLVM's -O2 pipeline for the JIT tier: what it costs and buys (13 November 2026)

[#1456](https://github.com/den-run-ai/pystachy/pull/1456) adds `PYSTACHY_JIT_OPT=2`, which runs
LLVM's `default<O2>` over the program's module in place of the JIT's cleanup (`globaldce,
always-inline,cgscc(inline,function(mem2reg,instcombine,simplifycfg)),function(early-cse,adce)`).
These are the measurements behind it. The compact, committed copy is
`bench/results/jit-opt2-2026-11-13.json` on that branch (commit `ed0c46e0`); this directory keeps
the raw per-run files, logs and scripts.

## Setup

Native compiler of `5e2398ee` (main `5f81cc25` plus the setting), x86-64 (Intel Xeon @ 2.10GHz),
Ubuntu LLVM 18.1.3, CPython 3.13.18 as the oracle. `jit_variants.py` runs each workload in
interleaved rounds (rotating order), each run pinned with `taskset -c 1`, program cache off
(`PYSTACHY_PROGRAM_CACHE=0`: every run compiles), `PYSTACHY_TIMING=1`; every run's output must
equal CPython's. `cache_hits.py` runs the program cache in a private directory seeded with the
runtime artifacts: one traced miss per variant (not compared: the first miss in a fresh cache also
builds the runtime's shared artifacts), then interleaved traced hits. The scripts carry this
session's scratch paths (`/tmp/claude-0/...`); `run_all.sh` lists every workload and argument.

## Uncached launches

`python3 summarize.py results` (paired = median of opt2/default per round). Compile is
`driver.prepare_run` (frontend, typed-IR passes, `opt`) plus the runner's load and code generation.

| Workload | Rounds | Wall default | Wall opt2 | Paired | opt default | opt opt2 | Timer | Timer paired |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| tiny (`print(1)`) | 7 | 0.035 | 0.036 | 1.021 | 0.014 | 0.015 | | |
| padded (600 helpers) | 5 | 0.077 | 0.087 | 1.124 | 0.024 | 0.033 | | |
| imports (re, textwrap, json, fnmatch) | 5 | 1.591 | 2.905 | 1.833 | 0.250 | 1.548 | | |
| router (1,000 events) | 5 | 1.312 | 2.234 | 1.713 | 0.202 | 1.163 | | |
| UMAP probe | 3 | 11.160 | 10.631 | 0.956 | 0.058 | 0.183 | knn / layout | 0.868 / 1.011 |
| bench/*.py (7 programs) | 3 | 0.09-0.22 | 0.10-0.22 | 0.95-1.13 | | | | |
| pyperformance, default sizes (17) | 3 | 0.08-4.15 | 0.10-5.81 | 1.05-1.76 | | | loop | 0.71-1.06 |
| richards 200 | 5 | 0.406 | 0.432 | 1.069 | 0.065 | 0.161 | loop | 0.702 |
| regex_effbot 200 | 5 | 4.371 | 4.980 | 1.144 | 0.232 | 1.437 | loop | 0.790 |
| regex_v8 100 | 5 | 5.674 | 7.012 | 1.275 | 0.325 | 1.924 | loop | 0.839 |
| go 40 | 5 | 0.564 | 0.628 | 1.129 | 0.043 | 0.141 | loop | 0.932 |
| json_loads 10000 | 5 | 4.200 | 4.310 | 1.013 | 0.091 | 0.314 | loop | 0.962 |
| chaos 100 | 5 | 0.434 | 0.523 | 1.207 | 0.043 | 0.143 | loop | 0.978 |
| raytrace 40 | 5 | 0.409 | 0.495 | 1.195 | 0.051 | 0.136 | loop | 1.041 |
| scimark 20 | 5 | 0.496 | 0.589 | 1.191 | 0.040 | 0.133 | loop | 1.016 |
| nbody 100 | 5 | 0.984 | 1.024 | 1.060 | 0.023 | 0.046 | loop | 1.041 |
| generators 100 | 5 | 1.961 | 1.822 | 0.941 | 0.038 | 0.077 | loop | 0.915 |

Every row is in `results/`; the full table, with code generation and peak RSS, is
`python3 summarize.py results`. Peak RSS (the largest process) moves by -1.0 to +5.1 MiB, the
most for regex_v8 (128.5 to 133.7 MiB).

## Program cache hits

A hit runs the executable built from the optimized module, with no frontend or LLVM work.

| Workload | Arguments | Hit wall default | Hit wall opt2 | Paired | Timers (paired) |
|---|---|---:|---:|---:|---|
| richards | 200 | 0.235 | 0.172 | 0.733 | loop 0.669 |
| regex_effbot | 200 | 3.119 | 2.730 | 0.844 | loop 0.849 |
| regex_v8 | 100 | 3.808 | 3.177 | 0.824 | loop 0.845 |
| generators | 100 | 1.852 | 1.919 | 1.043 | loop 1.045 |
| nbody | 100 | 1.009 | 1.034 | 1.036 | loop 1.036 |
| raytrace | 40 | 0.323 | 0.299 | 1.003 | loop 0.986 |
| imports | | 0.050 | 0.050 | 0.994 | |
| UMAP probe | 10000 16 10 15 200 7 | 10.773 | 10.859 | 1.002 | knn 1.015, layout 1.008 |

generators runs 0.915x uncached but 1.045x as a hit: the JIT runner and the cached executable
generate code differently (ORC against clang, a dlopened runtime against a linked one), so a
pipeline's effect differs between them too.

## With #1450: where the UMAP kNN still loses to AOT

`stacked_umap.json`: #1450's head `4602ba28` plus the setting, hosted frontend (only the program's
own stage timers count), 3 rounds: kNN 2.392 s with the cleanup, 2.106 s with `-O2` (paired
0.827); layout 5.784 s and 5.733 s. AOT runs this kNN in 0.92 s (`../jit-gap/README.md`).

`stacked-knn-O2.ll` is the kNN loop of that tree under `-O2` (400 points, the same code): #1450's
guarded copy of the distance loop (`L272.i`) is AOT's, two loads, `fsub`, `fmul` and `fadd` an
element, but each of the 10^8 pairs then reads `best_d[k - 1]` with a call of `pys_list_get`
(`L125.i`), which AOT inlines from runtime.c, with the guard's tests. A call per pair also limits
how far the core overlaps one pair's dependent `fadd` chain with the next's. Inlining the small
runtime helpers in JIT code
([#705](https://github.com/den-run-ai/pystachy/issues/705)) is the next step for this loop; no
pipeline removes an opaque call.
