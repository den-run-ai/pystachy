# UMAP probe against Numba, refreshed (18 November 2026)

Raw evaluation, not for merging. Same probe, input and Numba twins as `../README.md`
(10,000 points, 16 dimensions, k = 15, 200 epochs, seed 7); a new container, so absolute
times are not comparable with earlier sessions' (Numba's twin took 3.36 s on 14 November, 3.83 s here).

- main: `3cf23d20` (v0.6.0-alpha.1; none of the drafts below; has #706's precompiled AOT runtime).
- stack: a local merge of main with drafts #1436, #1437, #1442, #1449, #1450, #1455, #1456,
  #1468 and #1477 (`d0aa2934`, not pushed; Lean proof files and tests kept as main's where they
  conflicted, compiler imports united).
- `bench.py 5`: 5 rounds, rotating order, each process on CPU 1, JIT with the program cache off;
  every Pystachy run printed the recorded 13 November output (which the Numba twin matches bit for
  bit); Numba's kNN found the same neighbours in both modes. Raw rows: `bench5.json`.

| Variant | kNN s | Layout s | kNN / Numba strict | Layout / Numba twin | Layout / umap-learn |
|---|---:|---:|---:|---:|---:|
| main, JIT | 5.447 | 5.660 | 6.71 | 1.466 | 1.298 |
| main, AOT | 3.179 | 4.629 | 3.92 | 1.204 | 1.043 |
| stack, JIT | 1.569 | 4.142 | 1.98 | 1.088 | 0.959 |
| stack, JIT, `PYSTACHY_JIT_OPT=2` | 1.053 | 4.035 | 1.39 | 1.044 | 0.921 |
| stack, AOT | 0.924 | 4.063 | 1.25 | 1.060 | 0.941 |
| Numba, strict | 0.812 | 3.834 (twin) | 1 | 1 | |
| Numba, fastmath | 0.377 | | 0.46 | | |
| umap-learn's kernel (float32) | | 4.368 | | | 1 |

Times are medians; ratios are medians of per-round ratios. `loops_asm.py` on the AOT
executables (`f.main`, into which both stages are inlined): the stack's kNN distance loop runs 19
instructions per 4 elements with no exits (main: 25 instructions and 3 checks per element); the
layout's edge loop has 211 instructions and 22 exits and calls libm's `pow` (main: 232, 36 exits
and `pys_fpow`).

## What the checks left in the loops are (stack, JIT `-O2`, 2,000 points)

`loop_exits.py` on the module the JIT ran (`f.main`, both stages inlined into it):

- Layout (one component of the epoch, edge and negative-sample loops, 642 instructions): list
  bounds checks on the edge loop's own index (`head[i]`, `tail[i]`, `epoch_of_next_sample[i]`
  and the other per-edge lists: listguard does not version this loop) and on `emb[j * 2]`,
  `emb[k * 2]` (indices read from data, or `% n_vertices`); OverflowError checks on index
  arithmetic; the zero-division checks of three float divisions; NaN, infinity and range checks of
  `int()` of the negative-sample count; and, in the JIT only, `rtj.opt_in_trap` checks in the
  copies of `pys_list_set` (`pys_plain` is not known there; AOT builds fold it) and three calls of
  `pys_fpow` (over the copies' 40-instruction limit; AOT inlines it through #706's interface).
- kNN (91 blocks): the distance loop's guarded copy has no checks; around it, per pair and per
  point, OverflowError checks of `i * dim` and `j * dim`, bounds checks of `best_d`/`best_i` in the
  insertion, a `math` import check per `math.sqrt` and the JIT's opt-in traps.

## Follow-up: what each gap took (18 November, later)

- **Default JIT pipeline: draft #1540** (stacked on #1456). The cleanup left kNN's inner loop at 13
  instructions per element (`-O2`: 7): a range loop's step `sadd.with.overflow(i, 1)` exits the
  loop on overflow, so its latch exits and `loop-rotate` refuses it; unrotated, LICM cannot hoist
  the items pointer, and the loop reloads it and spilled values every iteration. Spliced into the
  cleanup by `jit-loop-passes/opt-wrapper.sh` (`asmcheck.sh` prints the loop): `licm`,
  `loop-rotate`, `indvars`, `gvn`, `loop-unroll`, `loop-vectorize` and the late `-O2` function
  passes changed nothing; `correlated-propagation` (which proves the step from the header's
  `i < stop`) plus a fold (`instcombine` or `sccp`; `instsimplify` and `early-cse` do not fold its
  `extractvalue`) plus `simplifycfg`, `loop-rotate` and `licm` gives the 7-instruction loop. On
  `imports.py`'s 63,000-line module that costs about 0.1 s (`-time-passes`: correlated propagation
  31 ms, SCCP 22 ms, rotation 19 ms, LICM 15 ms), so the draft runs it only within the inlining
  budget. `screening.json` (the `instcombine` form on every module) showed regex_effbot's timed
  loop 0.84× but `opt` +0.1 to +0.16 s on the three modules over the budget: a later choice.
  Final A/B, callgrind and timings: the draft's `bench/results/jit-loop-passes-2026-11-18.json`;
  `umap-stack.json`: kNN 1.609 s → 1.321 s on the stack (paired 0.821), `-O2` 1.157 s, AOT 0.926
  s, Numba strict 0.748 s; layout unchanged.
- **Checks guards could hoist.** `listguard` copies only innermost loops (docs/typed-ir.md), and the
  layout's edge loop holds the negative-sample loop; it also calls `tau_rand_int`, which stores
  into a list. Copying outer loops and proving such calls keep list lengths is not a small change,
  for 1 to 2% of a layout dominated by `pow`. Not attempted.
- **JIT-only `opt_in()` traps.** They sit only on paths that opt-in values lead to, and JIT `-O2`
  already matches AOT on the layout (4.04 s against 4.06 s). Nothing measurable to win. Dropped.
- **SIMD across points.** LLVM's unroll-and-jam would need `data` and `best_d` (both `list[float]`
  items, one TBAA type) proved apart; the VPlan outer-loop path does not take the kNN loop's
  control flow. Not attempted.
- **Drafts refreshed with main `3cf23d20`:** #1442 (`bacd349b`, and `c6cc7c93` naming its tagged
  `List`/`Slot` in main's companion test), #1455 (`a9751229`), #1450 (`e01b4f54`), #1468
  (`5bce6de8`), #1477 (`75b1fd54`); each built at a fixed point and passed its focused checks
  locally.

## Bounds checks and SIMD in general (19 November)

Survey (`listguard-survey/`): every range loop with a list access in `bench/`, `bench/pyperformance/`,
`bench/extended/`, eighteen loop-pattern kernels and the UMAP probe, by why listguard gave it no
copy (a patched `guard_plan` logging its reason, hosted compiler, `pystachy ir`). Planned 94; a call
whose callee writes a list 84 (mostly `regex_v8`'s regex calls); a loop holding a loop 60; a start
or step that is not a constant >= 0 / > 0 55; an append 46; no list indexed by the loop's index 19.
In the numeric programs the misses are outer loops (nbody, SciMark LU, FFT, sparse, spectral, UMAP
layout and kNN) and variable starts (`range(j + 1, n)`, `range(row[r], row[r + 1])`).

- **Variable starts and steps: draft #1569.** Lean already proves a register start (`-c <= s`
  before the loop) and, once the copy branches on `i < stop` instead of the variable step's
  `select`, a variable step. Default JIT: Gaussian elimination's row update 0.12×, triangular sum
  0.25×; AOT: CSR product 0.53× (main's AOT already vectorized the row update through LLVM's own
  versioning). SciMark's LU indexes rows through `Array2D.__getitem__` and qualifies either way.
- **Appends: the draft stacked on #1569.** listguard's invariant is "no list gets shorter", not "no
  length changes": appends, inserts and extends keep the tests before the loop true. The Lean model
  needed a `grow` node and a `lenGe` fact (a length read before growth is a lower bound); without
  them every copy of a loop that appends would be unproved, and CI's Lean corpus (dynamic-Any
  programs, which use the identity variants) would reject them.
- **Not done: loops that count down, and based indexes from a variable start.** Implemented and
  differentially tested (`patches/lgvar-full.diff` in the session scratchpad, not pushed), but the
  Lean access checker rejects their copies. Rules they need in `ruleStep`, each an `omega` case:
  `.lt a b` from `.off b a k` with k >= 1; `.lt a b` from `.off a c k` with k <= 0 and `.lt c b`;
  `.ge a k` from `.lt b a` and `.ge b j` with k <= j + 1; and, for a base from a variable start,
  a lower bound of `b + i` from `b + lo` and `lo <= i`. Then the descending copy's invariant
  `i < hi` (hi = start + 1) carries through its join.
- **Not done: calls that only assign items** (UMAP's `tau_rand_int`). Needs a per-function "shortens
  no list" summary in the compiler and the same in `check_lean_effects`' independent scan, so that
  such a call becomes a `grow` node.
- **Not done: outer loops.** Version innermost loops first, then copy the outer loop with the
  inner versions inside (inner bodies x4), duplicating the inner `Loop` records with renamed
  labels and values (`stop` and `inc` may be defined in the outer body). Small gains where the
  inner loops dominate (LU, spectral); the UMAP edge loop also needs the call summary above.
- **SIMD.** LLVM -O2 (AOT) vectorizes a check-free copy (`saxpy`, `scale`, `stencil`, the LU row
  update); what still blocks it is Python's semantics: OverflowError checks on int arithmetic
  (`s += x[i]`, `x[i] * 3 + 1`, `k * m + j` indexes), ZeroDivisionError checks on division,
  `math.sqrt`'s domain check and libm call, and strict float reductions (correct: no reassociation).
  The default JIT never vectorizes: no `loop-vectorize`, correlated propagation's
  `extractvalue(insertvalue({poison, false}, i + 1, 0), 0)` hides the induction variable from
  SCEV until `instcombine` folds it, and `lljit.c` builds its target machine with no CPU or
  features (SSE2 vectors even on AVX-512 hosts).
- **Loop passes over the inlining budget: not worth it now.** On main `8259611e` with #1540,
  regex_effbot's timed loop is 1.00× with #1540's passes (0.96× with `instcombine` in place of
  `sccp`), at +0.09 to +0.17 s of `opt` on the four modules over the budget (imports, router,
  regex_effbot, regex_v8); the 16% of the 18 November screening came from an older main.
- **SIMD measurements** (`listguard-survey/var-*.json`, `variants.py`, 5–7 interleaved rounds on CPU
  1). JIT, #1540's loop passes against the same plus `instcombine,loop-vectorize,instcombine,
  simplifycfg`: listguard's copies of `saxpy` and `scale` over 4,000 items 0.73× and 0.78× of wall
  time (launch included); with #1569 and #1570 also merged, Gaussian elimination's row update
  0.57×; `opt` +16 ms on 8,500- and 13,000-line modules. AOT `-march=native` (AVX2 `ymm`, which
  `PYSTACHY_CFLAGS` already allows) against generic SSE2: the LU row update 0.84×, memory-bound
  `saxpy`/`stencil` over 2 million items 0.99×/1.02×.
- **A copy's index overflow checks.** The JIT copy of `b[i] = (a[i - 1] + a[i] + a[i + 1]) * 0.25`
  keeps `sadd.with.overflow(i, -1)` and its exit: correlated propagation in the JIT does not prove
  it (AOT's -O2 does), and the exit both blocks vectorization and keeps the items pointer's load in
  the loop (not dereferenceable, so not hoisted past the exit). listguard could add `i + c` without
  a check in its copy, as it adds `b + i` (the tests keep `0 <= i + c < len`); each such plain add
  then needs Lean's `noWrap` from facts the certificate has, to re-check across the corpus.
- **Loop passes over the budget, data.** `listguard-survey/effbot-over-budget.json`.

## The remaining gaps, as drafts (19 November, evening)

Five more drafts. Each JIT and listguard draft stacks on the one before it: #1540 → #1571 → #1575 and
#1569 → #1570 → #1576 → #1577 → #1578 → #1579. Data and scripts: `gaps-2026-11-19/`.

- **Host CPU in the JIT: #1575.** `opt -mcpu=native` names the host's CPU on each function where a
  loop vectorizer runs (within the inlining budget, or `PYSTACHY_JIT_OPT=2`); `PYSTACHY_JIT_CPU=
  generic` keeps SSE2. saxpy/scale copies over 1,000 items 0.73×/0.81× of run time (AVX-512, which
  LLVM keeps to 256 bits). A first scimark run of five rounds read 1.21×; eleven rounds, 1.01×. The
  first push named the host's CPU everywhere: CI's cache-gc ran past 15 minutes (gc-self 518 s
  against 446 s), so programs over the budget, the compiler among them, keep the target's CPU. #1577's
  cache-gc, which this change does not touch, also ran past 15 minutes (runtime-cache 372 s against
  247 s): that group sits at 11 to 15 minutes on these runners.
- **Loops that count down: #1576.** Lean needed three ordering rules, then `absurd`: on itertools'
  `combinations`, the first iteration of an empty range loop has facts that contradict each other,
  around which the new rules strengthened a bound without end (`ab-down2.json`: JIT rev 0.17×,
  recurrence 0.78×; AOT recurrence 0.31×). The first run's recurrence decayed to subnormal floats,
  which dominated it and read as AOT 1.6×; `ab-down.json` keeps that run.
- **A copy's offsets without overflow checks: #1577.** A stencil's copy vectorizes in the JIT with
  #1540's and #1571's passes: 0.46× with SSE2, 0.24× with the host's CPU (`var-off-stencil.json`).
- **Calls that only assign items: #1578.** `list_shrinkers`, and the Lean scan's `sL`/`gL`: a sum
  that calls a generator of random numbers per item 0.83× JIT, 0.91× AOT (`ab-calls.json`); the
  Lean corpus proves 34 more accesses.
- **Outer loops: #1579, a trade-off.** JIT: a loop over points around one over their three
  coordinates 0.46×, the UMAP probe's layout 0.96×; AOT: the same point loop 1.16×; scimark's JIT
  launch 1.09× (IR +16%, `irsize-outer.tsv`). Not localized: the point kernel is inlined into
  `main` in the AOT build. UMAP's edge loop (461 ops) stays over the 400-op limit; with 800 the copy
  left its AOT layout unchanged (`var-umap-ops.json`: 0.997×), so the checks there cost little next
  to its `pow` calls and data-dependent reads.

## All drafts together, against Numba (19 November, night)

A local merge (`2af26404`, not pushed) of main `d35417c9` (v0.6.0-rc.1) with #1442, #1468, #1477,
#1575 (with #1540 and #1571) and #1578 (with #1569, #1570, #1576 and #1577); not #1579. Two drafts
conflict with this main: #1442's `list.len` lowering moved into main's machine IR (`a4c7d778`),
ported here as `all-drafts-2026-11-19/list-tbaa-on-machine-ir.diff`; #1468's driver and jitprobe
conflicts took both sides. Built to a fixed point; every run printed the recorded output.
`bench_all.py 5`: same probe, input and Numba 0.68.1 twins as above, CPU 1 of a Sapphire Rapids VM.

| Variant | kNN s | Layout s | kNN / Numba strict | Layout / Numba twin | Layout / umap-learn |
|---|---:|---:|---:|---:|---:|
| JIT (default: the host's CPU) | 1.111 | 4.125 | 1.57 | 1.060 | 0.964 |
| JIT, `PYSTACHY_JIT_CPU=generic` | 0.951 | 4.174 | 1.41 | 1.069 | 0.969 |
| JIT, `PYSTACHY_JIT_OPT=2` | 0.967 | 4.106 | 1.45 | 1.041 | 0.954 |
| AOT | 0.856 | 3.989 | 1.29 | 1.025 | 0.933 |
| AOT, `PYSTACHY_CFLAGS=-march=native` | 0.947 | 4.053 | 1.38 | 1.038 | 0.944 |
| Numba, strict / fastmath | 0.689 / 0.314 | 3.904 (twin) | 1 | 1 | |
| umap-learn's kernel (float32) | | 4.306 | | | 1 |

- **#1575 slows this kNN in the JIT.** `jitab.py 7`: kNN 1.19× (0.99 to 1.23) with the host's CPU,
  layout 1.01×, the whole process 1.03×. The optimized IR differs only in its CPU attributes;
  `llc -O2` of both (`knn-loop-asm.txt`): with `sapphirerapids` the loop around the distance loop
  reloads 16 values from the stack (generic: 10), one of them the guarded copy's bound, on each of
  its iterations (`cmpq 112(%rsp)`). The AOT difference did not repeat (`aot4.py 5`: generic 0.954,
  native 0.951, `-march=sapphirerapids -mtune=generic` 0.950, `-mtune=sapphirerapids` 0.904); the
  same generic executable took 0.82 to 1.02 s across the two runs.
- **What is left.** The layout is within 3 to 6% of Numba's twin and faster than umap-learn's own
  kernel. kNN's guarded distance loop has no checks (JIT: 7 instructions per element, not unrolled;
  AOT: 19 per 4); around it, per pair, overflow and bounds checks remain (`loop_exits.py`), which
  Numba's code does not make. Numba's fastmath reassociates the sum to vectorize it (0.314 s); Python's
  left-to-right sum does not allow that, so no default can.
- For scale, earlier today main (alpha.3) with the listguard drafts and no JIT drafts, JIT: kNN 2.49
  s, layout 5.17 s (`gaps-2026-11-19/var-outer-umap.json`).

## Refreshes, and the host-CPU slowdown fixed (19 November, late)

- **#1442, #1468 and #1477 refreshed on main `d35417c9` (rc.1).** #1442's `list.len` lowering moved into
  main's machine IR: a list's length is now a `mach.load` of kind `list.length`, printed with the
  `@list` tag and `!range`. #1468's and #1477's conflicts kept both sides (main's `PYSTACHY_JIT_OPT=2`
  next to the helpers). Each built at a fixed point and passed its checks (PR bodies).
- **#1575's kNN slowdown is the tuning, not the instruction set.** `llc -O2` of the all-drafts module
  (`reloads.py`): the loop around kNN's distance copy reloads 10 values with no named CPU (LLVM's
  default tuning, i586's) and 16 with any named tuning (generic, x86-64-v3, -v4, sapphirerapids), with
  or without AVX. The runner now takes `-default-tuning`, which drops `target-cpu` and keeps
  `target-features` (`opt-wrapper.sh` simulated it first: `strip-*.json`). All drafts, 7 rounds
  (`fix-umap*.json`): runner kNN 1.19× before, 1.07× after (0.97 to 1.13 per round; the code differs
  from generic's only in VEX encodings), whole run 1.01×; cached executables kNN 0.89×, whole run
  0.97×. The branch alone (`branch-*.json`): kNN 1.00× and 1.01×, saxpy 0.71×, scale 0.81×.
- **An older gap this exposed.** The program cache's executables, which clang compiles with x86-64's
  generic tuning, run kNN in 1.32 to 1.34 s against the runner's 0.95 to 0.97 s on the same IR
  (`cache-umap.json`, generic CPU): the cached path, the native CLI's default, is the slower one.
  Not addressed.
