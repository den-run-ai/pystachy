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
