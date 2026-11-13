# UMAP's Numba core against Pystachy, one thread (13 November 2026)

Raw evaluation behind the float power and int/float comparison runtime PRs. Not for merging.

## Question

Could UMAP's accelerated core, compiled by Pystachy, beat the same algorithm compiled by Numba
on one thread? Where Pystachy loses, which compiler or runtime shape costs the time?

## Setup

- Pystachy main `63e4e52` (prototype runtimes applied to its `runtime.c`), CPython 3.13.18,
  LLVM/clang 18.1.3, glibc 2.39, Linux 6.18 on a shared 4-vCPU Intel Xeon @ 2.10 GHz (AVX-512).
- umap-learn 0.6.0 (PyPI; source `17ce948977b3410f71ca58a1a291356f66ad1f2e`), Numba 0.68.1,
  NumPy 2.5.4, SciPy 1.18.1, scikit-learn 1.9.1, pynndescent 0.7.0.
- [`umap_core.py`](umap_core.py): typed Python following umap-learn's 0.5.x-compatible path for
  Euclidean data with random initialization: exact kNN, `smooth_knn_dist`, membership strengths,
  fuzzy union, `make_epochs_per_sample` and the SGD layout with UMAP's Tausworthe generator, in
  float64. It follows umap-learn's BSD-3-Clause code ([license](UMAP-LICENSE.txt)).
- Input: 10,000 points, 16 dimensions, 10 Gaussian clusters, k = 15, 200 epochs, seed 7
  (`umap_core 10000 16 10 15 200 7`).
- [`numba_twin.py`](numba_twin.py): the probe's layout kernel over float64 NumPy arrays, `@njit`
  without fastmath, and umap-learn's own float32 kernel on the same graph and initial layout.
  The twin's embedding equals the probe's bit for bit (79,432,897 updates).
- [`bench_layout.sh`](bench_layout.sh): rounds that rotate the variants' order, each process
  pinned to one CPU (`taskset -c 1`), `NUMBA_NUM_THREADS=1`; Numba times its second (warm) call.
  Its paths are this session's scratch directory.

## Layout: 7 rounds ([bench3.tsv](bench3.tsv))

| Variant | Median | Paired ratio to the Numba twin |
|---|---:|---:|
| Pystachy main | 4.627 s | 1.125 (slower in 7/7 rounds) |
| main + prototype runtime ([patch](prototype-runtime.patch)) | 4.131 s | 0.998 (faster in 4/7) |
| the same with `PYSTACHY_CFLAGS=-march=native` | 4.075 s | 1.015 (faster in 2/7) |
| Numba twin | 4.067 s | 1 |
| umap-learn's Numba kernel | 4.468 s | prototype 0.909 of it (faster in 7/7) |

The prototype made the layout 12.6% faster (paired median 0.874, 7/7 rounds). Earlier rounds
([bench1.tsv](bench1.tsv), [bench2.tsv](bench2.tsv)) cover intermediate prototypes: a branchless
`clip()` (conditional expression) ran slower, and `-march=native` alone gave 3.8% on main.

Where main lost (machine code and callgrind, 2,000-point run): `pys_fpow` stayed out of line
(`no_builtin("pow")`, #656) and called `floor@plt` on every power, which clang speculated above
its guard; its own instructions were 8.2% of the program's. Each `epoch_of_next_sample[i] > n`
called `pys_cmp_if`, whose `trunc()` is a libm call on x86-64 without SSE4.1 (43M calls). Calls
that may write memory made LLVM reload list lengths and data pointers in the loop.

## Exact kNN distance loop, same source, 3 runs each

| Variant | Seconds |
|---|---:|
| Pystachy (with the prototype runtime) | 2.54–2.75 |
| Pystachy, four accumulators ([`umap_core_knn4.py`](umap_core_knn4.py)) | 2.32–2.57 |
| Numba, strict IEEE order ([`numba_knn.py`](numba_knn.py)) | 0.65–0.72 |
| Numba, `fastmath=True` | 0.36–0.39 |

All found the same neighbours. Pystachy's loop runs 26 instructions per element against Numba's
4 (unrolled 8 times): an overflow-checked `bi + d`, negative-index normalization and a bounds
check per read, and the list's length and data pointer reloaded on each iteration (no
`dereferenceable` fact lets LLVM hoist them past the overflow exits). `-O3 -march=native` leaves
the loop unchanged. listguard's copies (#209) cover constant offsets (`xs[i + 1]`), not
`data[bi + d]`.

## Start-up (same input, fresh processes)

| Process | Wall | Peak RSS |
|---|---:|---:|
| Pystachy AOT probe (exact kNN included) | 7.3 s | 52 MiB |
| umap-learn `fit_transform`, one thread, warm Numba cache | 31.7 s | 541 MiB |

About 23–25 s of the umap-learn process is Numba compilation; a second fit in the same process
took 4.6 s (1.5 s with 4 threads). Both embeddings separate all 10 clusters.

## The two runtime PRs, against main `bf699eb`

The prototype became two changes. Float powers (`**`, `pow()` and `math.pow()`) run inline and
return libm's value wherever it is finite, which is always CPython's result; only non-finite
results take the out-of-line error path. Int/float comparisons decide ints within 2**53 with one
float comparison. Same host; each build's output equals main's. Instructions are callgrind's for
the whole process ([first builds](prs/callgrind-totals.txt), [final power build](prs/cg-powg.txt));
times are 7 rounds of [`time_variants.py`](prs/time_variants.py), pinned and rotated, as paired
medians with the rounds in which the PR was faster.

| Program | Power PR: instructions, time | Comparison PR: instructions, time |
|---|---:|---:|
| [`pow_loop.py`](prs/pow_loop.py) (`x ** e`, `math.pow`) | −19.3%, 0.821 in 6/7 ([json](prs/tg_pow.json)) | +0.3%, 0.991 |
| [`negpow_loop.py`](prs/negpow_loop.py) (signed bases, integral exponents) | −20.5%, 0.788 in 7/7 ([json](prs/tg_negpow.json)) | not run |
| [`cmp_loop.py`](prs/cmp_loop.py) (`due[i] <= step`) | 0.0%, 0.984 | −26.0%, 0.556 in 7/7 ([json](prs/t_cmp.json)) |
| UMAP probe, 2,000 points (instructions) / layout of 10,000 (time) | −9.6%, 0.943 in 7/7 ([json](prs/tg_umap.json)) | −1.6%, 0.938 in 7/7 ([json](prs/t_umap.json)) |
| adapted microGPT, 1000 steps | 0.997 in 4/7 ([json](prs/tg_microgpt.json)) | 0.993 in 5/7 ([json](prs/t_microgpt.json)) |

Earlier versions of the power change gave the UMAP layout 0.899 and 0.920 on this host
([first](prs/t_umap.json), with the comparison PR's columns); the shared VM moves such medians by a
few percent between sessions. [`countlibm.c`](prs/countlibm.c), preloaded, counts libm calls: the UMAP
probe at 2,000 points made 18,255,622 `pow` and as many `floor` calls on main, and microGPT
17,721,627 of each; the power PR makes no `floor` call in either, and the comparison PR removes the
probe's 8,295,600 `trunc` calls. microGPT's powers stay: #899's bias-correction powers read module
globals, which LLVM reloads after the loop's stores.
