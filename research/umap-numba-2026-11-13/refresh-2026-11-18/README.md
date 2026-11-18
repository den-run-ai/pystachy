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
