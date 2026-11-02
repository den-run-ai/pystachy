# pyperformance results

Pystachy runs 23 of the 52 benchmarks tried from pyperformance 1.14.0, after the adaptations
listed in the [port notes](../bench/pyperformance/README.md), which also cover the blocked
benchmarks and how to run the suite. CPython runs the same adapted files, and every JIT and AOT
run must print exactly what CPython printed. These are comparisons on that source, not
pyperformance scores: some inputs, random number generators and data types differ from upstream.

## alpha.3 to alpha.4

The compilers of [v0.1.0-alpha.3](https://github.com/den-run-ai/pystachy/releases/tag/v0.1.0-alpha.3)
and [v0.1.0-alpha.4](https://github.com/den-run-ai/pystachy/releases/tag/v0.1.0-alpha.4), each
with its own library and runtime, built the same alpha.4 benchmark sources as AOT executables.
These ran under Callgrind on 2026-11-02 (x86-64 Linux, LLVM 18.1.3), and every output matched
CPython 3.13.18. The table gives whole-process instructions in millions, sorted by change: a
positive change is a regression, a negative one a speedup. `pidigits`, new in alpha.4, has no
row: it needs [promoting ints](python-int.md), and alpha.3's executable raises `OverflowError`.

| Benchmark | alpha.3 | alpha.4 | Change |
|---|---:|---:|---:|
| `generators` | 1,068.6 | 1,262.7 | +18.2% |
| `barnes_hut` | 768.5 | 854.6 | +11.2% |
| `go` | 350.2 | 377.9 | +7.9% |
| `json_dumps` | 1,440.5 | 1,514.0 | +5.1% |
| `nqueens` | 1,148.6 | 1,195.6 | +4.1% |
| `fannkuch` | 868.8 | 901.9 | +3.8% |
| `scimark` | 602.7 | 623.6 | +3.5% |
| `hexiom` | 689.3 | 710.7 | +3.1% |
| `meteor_contest` | 828.6 | 851.9 | +2.8% |
| `regex_effbot` | 1,648.7 | 1,680.5 | +1.9% |
| `nbody` | 570.5 | 580.5 | +1.8% |
| `float` | 339.5 | 344.6 | +1.5% |
| `regex_v8` | 15,371.7 | 15,600.8 | +1.5% |
| `regex_dna` | 1,176.3 | 1,183.9 | +0.6% |
| `unpack_sequence` | 1.2 | 1.2 | +0.4% |
| `spectral_norm` | 691.0 | 691.5 | +0.1% |
| `raytrace` | 681.9 | 680.4 | −0.2% |
| `json_loads` | 1,300.3 | 1,296.1 | −0.3% |
| `richards_super` | 676.8 | 672.4 | −0.7% |
| `richards` | 662.9 | 658.4 | −0.7% |
| `comprehensions` | 435.6 | 424.2 | −2.6% |
| `chaos` | 1,027.7 | 981.6 | −4.5% |
| **Geometric mean** | | | **+2.55%** |

### Notes

- **Recursion checks cause the largest regressions.** alpha.4 enforces
  `sys.setrecursionlimit()` in native code ([#996](https://github.com/den-run-ai/pystachy/pull/996))
  and checks the native stack ([#1026](https://github.com/den-run-ai/pystachy/pull/1026)), so
  runaway recursion raises a catchable `RecursionError`; alpha.3 ignored the limit. `generators`
  pays on every resume of its recursive `yield from`, `barnes_hut` on its recursive force
  calculation, and `go` in part. Outside the suite, `bench/fib.py` executes 37.9% more.
  [#1033](https://github.com/den-run-ai/pystachy/pull/1033), held for after alpha.4, would bring
  `generators` to +13.3% and fib to +24.1%.
- **Allocation removal speeds up `chaos`.** AOT builds now delete objects that hold only numbers
  when nothing reads them ([#1020](https://github.com/den-run-ai/pystachy/pull/1020),
  [#1025](https://github.com/den-run-ai/pystachy/pull/1025)).
- **The smaller regressions are not attributed on alpha.4.** Those above 2% were profiled only on
  an earlier candidate, main `c3aaa068`, which lacked alpha.4's last fixes
  ([function-level attribution](../bench/pyperformance/results/alpha3-vs-candidate-2026-11-02.json)).
- **Counts are deterministic but are not wall time.** Callgrind ignores cache misses and branch
  prediction, and counts each byte that `rep stosb` clears. In paired wall-time runs of
  `c3aaa068`, regressions were smaller than their counts (`generators`, +13% in counts, was
  level), and `regex_dna` took 31% less wall time with almost the same count. Wall times and the
  JIT were not measured on alpha.4.
- **Counts include startup and the untimed output checks.** Those make up most of `regex_v8`'s
  count (its checksum pass) and of `unpack_sequence`'s, whose unpacking AOT optimizes away.
- **Executables and builds grew.** alpha.4's executables are 12% larger than alpha.3's, and single
  builds on the shared host took 20–30% longer (geometric means).

## Data and earlier results

- **Measurement record.** The [retained JSON](../bench/pyperformance/results/alpha3-vs-release-candidate-2026-11-02.json)
  holds each benchmark's arguments, commands and hashes. It measured the release candidate, main
  `ec442a20`, whose code the alpha.4 tag shares. Its alpha.4 counts leave out a stack-bounds lookup
  of about 100,000 instructions that only Valgrind triggers.
- **Earlier results.** The 2026-10-16 wall-time comparison with CPython and the October regex
  reruns are on [this page as of alpha.4](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/docs/pyperformance.md);
  their raw samples stay in [`docs/benchmarks/`](benchmarks/).
- **Timing on your machine.** `make bench-pyperformance` times CPython, the JIT and AOT; see the
  [port notes](../bench/pyperformance/README.md#run).
