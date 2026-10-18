# pyperformance results

Pystachy includes 18 of the 52 benchmarks tried from pyperformance 1.14.0, after the localized
adaptations listed in the [port notes](../bench/pyperformance/README.md). CPython runs the same
adapted files, and every JIT and AOT run must print exactly what CPython printed. These are
comparisons on that source, not pyperformance scores: some inputs, random number generators and data
types differ from upstream.

## Snapshot

Advisory snapshot of 2026-10-16: commit `a74faae`, with the native compiler built from main
`bdc20a2`, CPython 3.13.16 and LLVM 18.1.3 on a 4-core x86-64 VM (Intel Xeon at 2.10 GHz) shared
with other jobs. The one-minute load average was 10.2 when the run started and 11.7 when it ended,
so the processes competed for the cores: each spent 33% or more of its wall time on a CPU, and the
five processes of a benchmark and mode differed by up to 115% of their median wall time (`richards`
AOT). `unpack_sequence`'s AOT runs, which take a few milliseconds, are the exception: 12% and 317%.
Each value is the median of five processes; ratios above 1 mean faster than CPython. The [raw
samples](benchmarks/pyperformance-2026-10-16-a74faae.json) include each process's wall, CPU and
timed seconds, the outputs and the source hashes. That historical record also includes
`deltablue`, which is now excluded from the delivered suite pending a licence provenance decision.
It also predates the expanded `regex_v8` checksum: current runs validate search, split and match
results as well as substitutions outside the timed loops, so its whole-process figures need a
fresh run for comparison with the current suite.

Whole-process wall time:

| Benchmark | Arguments | CPython | JIT | AOT | CPython/AOT |
|---|---|---:|---:|---:|---:|
| `barnes_hut` | 1 | 1.25 s | 0.34 s | 0.076 s | 16.4× |
| `chaos` | 10 | 0.74 s | 0.31 s | 0.048 s | 15.4× |
| `fannkuch` | 2 | 1.22 s | 0.60 s | 0.48 s | 2.5× |
| `float` | 10 | 1.27 s | 0.33 s | 0.082 s | 15.6× |
| `go` | 4 | 0.99 s | 0.41 s | 0.073 s | 13.6× |
| `hexiom` | 100 | 0.96 s | 0.61 s | 0.14 s | 7.0× |
| `meteor_contest` | 6 | 1.31 s | 1.21 s | 0.85 s | 1.5× |
| `nbody` | 10 | 1.47 s | 0.38 s | 0.094 s | 15.7× |
| `nqueens` | 10 | 1.11 s | 0.74 s | 0.44 s | 2.5× |
| `raytrace` | 4 | 1.57 s | 0.58 s | 0.12 s | 13.5× |
| `regex_dna` | 4 | 1.37 s | 5.77 s | 3.37 s | 0.41× |
| `regex_effbot` | 20 | 0.79 s | 4.25 s | 2.03 s | 0.39× |
| `regex_v8` | 20 | 1.04 s | 6.53 s | 2.81 s | 0.37× |
| `richards` | 20 | 1.51 s | 0.52 s | 0.018 s | 84.5× |
| `richards_super` | 20 | 1.59 s | 0.49 s | 0.022 s | 71.4× |
| `scimark` | 2 | 1.19 s | 0.42 s | 0.050 s | 23.9× |
| `spectral_norm` | 10 | 1.38 s | 0.15 s | 0.029 s | 48.2× |
| `unpack_sequence` | 50000 | 1.09 s | 1.09 s | 0.004 s | n/a |

The timed part, which pyperf would time (without startup, compilation, setup or checksums), and the
AOT build time:

| Benchmark | CPython | JIT | AOT | CPython/JIT | CPython/AOT | AOT build |
|---|---:|---:|---:|---:|---:|---:|
| `barnes_hut` | 1.201 s | 0.0837 s | 0.0662 s | 14.4× | 18.1× | 1.1 s |
| `chaos` | 0.690 s | 0.0634 s | 0.0423 s | 10.9× | 16.3× | 1.8 s |
| `fannkuch` | 1.195 s | 0.443 s | 0.474 s | 2.7× | 2.5× | 0.7 s |
| `float` | 1.250 s | 0.123 s | 0.0761 s | 10.2× | 16.4× | 0.7 s |
| `go` | 0.952 s | 0.0680 s | 0.0613 s | 14.0× | 15.5× | 1.5 s |
| `hexiom` | 0.933 s | 0.131 s | 0.121 s | 7.1× | 7.7× | 2.7 s |
| `meteor_contest` | 1.268 s | 0.930 s | 0.834 s | 1.4× | 1.5× | 2.1 s |
| `nbody` | 1.448 s | 0.170 s | 0.0918 s | 8.5× | 15.8× | 1.6 s |
| `nqueens` | 1.071 s | 0.512 s | 0.432 s | 2.1× | 2.5× | 1.4 s |
| `raytrace` | 1.529 s | 0.130 s | 0.103 s | 11.8× | 14.8× | 1.7 s |
| `regex_dna` | 1.219 s | 4.304 s | 3.302 s | 0.28× | 0.37× | 6.5 s |
| `regex_effbot` | 0.733 s | 2.672 s | 1.989 s | 0.27× | 0.37× | 7.1 s |
| `regex_v8` | 0.657 s | 2.421 s | 2.070 s | 0.27× | 0.32× | 14.0 s |
| `richards` | 1.482 s | 0.0251 s | 0.0148 s | 59.0× | 100.3× | 1.9 s |
| `richards_super` | 1.560 s | 0.0239 s | 0.0176 s | 65.2× | 88.6× | 1.8 s |
| `scimark` | 1.140 s | 0.0966 s | 0.0374 s | 11.8× | 30.5× | 1.4 s |
| `spectral_norm` | 1.363 s | 0.0428 s | 0.0186 s | 31.9× | 73.2× | 0.9 s |
| `unpack_sequence` | 1.054 s | 0.469 s | 0.2 µs | 2.2× | n/a | 19.1 s |

## Regex repeat rerun

Advisory paired rerun on 2026-10-18 UTC, against main `a355c83f` (including Unicode #667).
The candidate is local implementation commit `c14b8dd5`; its matcher SHA-256 is
`362cf7148831b2f672a343119c310121608dd8f3c6e2cf5390fd7b2953c37b3d`.
The [raw samples](benchmarks/regex-repeat-2026-10-18.json) retain source/compiler hashes,
commands, checksums, load averages, process wall/CPU times and all timed samples.

CPython 3.13.16 and LLVM 18.1.3 ran on the same shared Linux x86-64 host (Xeon Platinum 8573C).
Five rounds alternated the execution order of CPython, old/new AOT and old/new JIT; all checksums
agreed. The arguments were DNA `4`, effbot `20`, V8 `20`. JIT used a primed runtime cache and
both modes used default optimization. AOT builds and our correctness jobs finished before timings;
other host activity was uncontrolled. These are medians of the in-process timed workload, not
whole-process time or pure warmed matching. Ratios above 1 mean faster than old Pystachy.

| Workload | CPython | Old → new AOT | AOT speedup | Old → new JIT | JIT speedup |
|---|---:|---:|---:|---:|---:|
| `regex_dna` | 0.929 s | 2.515 → 2.262 s | 1.11× | 2.668 → 2.628 s | 1.02× |
| `regex_effbot` | 0.576 s | 1.662 → 0.927 s | 1.79× | 2.038 → 1.074 s | 1.90× |
| `regex_v8` | 0.515 s | 1.765 → 1.495 s | 1.18× | 2.816 → 2.155 s | 1.31× |

`regex_effbot` improves 1.79× AOT and 1.90× JIT: mandatory repeated-word patterns can skip
impossible starts before entering the matcher. Its AOT ranges were 1.542–1.736 s old versus
0.772–1.358 s new; JIT ranges were 1.865–2.421 s versus 0.925–1.620 s. It still trails CPython.
The DNA and V8 ranges overlap, so their median differences are inconclusive on this host.

Whole-process effbot medians were 1.688 → 0.942 s AOT and 3.266 → 2.241 s JIT (CPython 0.614 s).
Whole-process measurements include setup and verification as well as startup/compilation;
subtracting the timed part does not isolate JIT startup, particularly for V8's checksum pass.
AOT build time was not measured in this rerun.

The warmed repeat microbenchmark (`tools/re_repeat_bench.py 1000 --cpu`) separately exercises
ASCII/Unicode folding, finite/lazy/possessive repeats, dense/sparse matches and plain controls.
AOT medians improve 3.82× for ASCII greedy counting, 2.22× for Unicode greedy counting, and
5.53× / 4.81× for ASCII / Unicode sparse searches. The four plain AOT controls remain within
5% of their old medians. JIT sparse searches improve 4.35× / 3.48×, but Unicode lazy repeats
have a 14% slower median with overlapping ranges; not every case improves. The raw file includes
all controls and both execution modes. These advisory timings are not CI thresholds.

Deterministic guards in `make re-probe` enforce the actual reduction in matcher entries:
case-insensitive counting 12,012 → 12, sparse folded searches 24,012 → 12, and mandatory
multi-character repeat searches 10,004 → 5. Removing each optimization fails its guard.
Nullable repeats retain the existing search path. Separate plain/folded predicates preserve
the original plain predicate's generated machine code.

This is partial progress on [#345](https://github.com/den-run-ai/pystachy/issues/345).
[#589](https://github.com/den-run-ai/pystachy/issues/589)'s subject decoding/storage trade-offs
remain separate; neither issue is closed by these workload-specific improvements.

## Reading the results

- AOT ran 14 of the 17 comparable benchmarks faster than CPython, by 1.5× to 84× in whole-process
  time. Object and numeric code gained most: `richards`, `richards_super` and `spectral_norm`.
- The three regex benchmarks were 2.5–2.7× slower AOT in whole-process time, and 2.7–3.2× slower in
  the timed part. `lib/re` is written in the supported subset, while CPython matches in its C `_sre`
  module. The JIT is slower still, because each run also compiles `lib/re`: 4.1 of `regex_v8`'s 6.5
  JIT wall seconds fell outside its timed part, against 0.7 s AOT, which also runs the checksum
  there.
- `fannkuch`, `nqueens` and `meteor_contest` gained 1.5–2.5× in the timed part. Their inner loops
  mostly slice and insert into lists, build tuples and sets, or combine frozensets, which are
  runtime calls; they were not profiled. The `fannkuch` and `nqueens` adaptations also replace slice
  assignment with new lists.
- JIT whole-process time includes compiling the program; besides the regex benchmarks, it was within
  10% of CPython's for `meteor_contest` and `unpack_sequence`.
- `unpack_sequence` does not measure unpacking under AOT: its timed part took 0.2 µs, far too little
  for 40 million unpackings, because optimization removed the repeated unpacking of an unchanged
  tuple and list. Its AOT ratios are omitted. The JIT's timed part was 2.2× faster than CPython's.
- The `random` substitutes in `chaos` and `go`, the `str` data of `regex_dna` and the other
  adaptations make the work differ from upstream pyperformance. With the cores this contended, a
  difference between two runs that is smaller than the spreads above is noise; rerun on an idle
  machine before relying on one, or on a difference between two Pystachy revisions.

## Reproduce

```sh
make
make bench-pyperformance-check
make bench-pyperformance
python3 tools/bench_pyperformance.py --benchmarks regex_v8 richards --runs 9 --json build/pyperformance-two.json
```

The check runs small inputs once and compares outputs without keeping timings. A measured run starts
five processes per mode for each benchmark, rotates the order of the modes, and writes the raw
samples, outputs, commands and source hashes to `build/pyperformance.json`, with the load average at
its start and end, the spread of each mode's five wall times and the least share of its wall time
that a process spent on a CPU. Whole-process time includes interpreter or executable startup; the
JIT's includes compiling the program and its library modules with a primed runtime cache. The timed
part is what each benchmark's main reports: the part that pyperf would time (`TIMED_PART` in
`tools/bench_pyperformance.py`). AOT build time is measured once.

The [port notes](../bench/pyperformance/README.md#blocked) list the first compiler error of each
benchmark that remains blocked, and `--census` reproduces that table from the pinned sdist.
