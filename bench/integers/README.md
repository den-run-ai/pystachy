# Integer benchmarks: mpz and int64 against CPython and PyPy

Ten bounded workloads for Pystachy's integer roadmap (#907): CPython-compatible `int` that
promotes past 64 bits. Every later step is measured against these programs. Each workload has:

- **`NAME.py`**, written with ordinary `int`, as CPython and PyPy run it. It starts with
  `# pystachy: python-int`, the opt-in to [promoting ints](../../docs/python-int.md), which
  CPython ignores. Pystachy times it only with `--python-int`. `containers` still raises
  `OverflowError` there: its values past 64 bits reach containers, which keep 64-bit ints for
  now.
- **`NAME_mpz.py`**, the same work with the explicit [`mpz`](../../docs/mpz.md) type.
- **`NAME_i64.py`**, checked 64-bit `int`, only where every value fits (`lcg32`, `collatz`).

| Workload | Integers | Work |
|---|---|---|
| `lcg32` | int64 only | Masked 31-bit LCG and xorshift mix, 3,000,000 steps |
| `collatz` | int64 only | Longest Collatz chain below 100,000 |
| `cross64` | crosses 2^63 and back | Additions just past `INT64_MAX`, then subtraction back below it |
| `arith128` | 64–128 bits | #889's masked recurrence `((x + a) * b) & (2**128 - 1)`, 8,000,000 steps |
| `factorial` | grows to 30,000 bits | 3000! by repeated small multiplications, 300 times |
| `fibadd` | grows to 14,000 bits | Fibonacci(20000) by additions, 150 times |
| `bigmul` | about 20,000 bits | Products and long division of ~6,000-digit values, 600 times |
| `dectext` | 400 and 3,300 bits | Parse and format 128-digit text; 1,000-digit text every 20th step |
| `modpow` | 521 bits | Three-argument `pow` with a 256-bit exponent, 3,000 times (the mpz variant multiplies and reduces in a loop) |
| `containers` | mixed | 1,000,000 small and `2**64 + i` values: list, sort, dict keyed by `v % 1000`, sum |

Each program prints a checksum and then the seconds its timed loop took; startup,
compilation and printing are excluded. The runner refuses to time a workload whose variants
print different checksums, and records each child's peak RSS. A small C launcher forks each
program and reads its peak: Linux's `ru_maxrss` keeps the larger of a process's RSS before and
after its `exec`, so a child forked from the Python runner itself would report at least the
runner's own memory.
`tools/test_bench_integers.py` (Lint CI) runs every variant at a small size under CPython,
with `tools/rt_cpython/mpz_oracle.py` as the mpz module, and checks that they agree, and that
a child's peak RSS leaves out the memory the runner holds.

## Results

Measured 2026-10-26 on main at `a4b2b7d` (after #910) on a shared 4-vCPU Intel Xeon @ 2.10 GHz
cloud VM (Linux 6.18.44 x86-64), LLVM 18.1.3, default optimization and GC, AOT binaries.
CPython is 3.13.16 from uv's python-build-standalone (PGO and LTO), PyPy 8.0.0 (Python 3.11.16).
Every variant printed the same checksum. Each cell is the median of five samples pinned to one
CPU, with variant order alternating between samples; raw samples, peak RSS and arguments are in
[results/linux-x86_64-2026-10-26.json](results/linux-x86_64-2026-10-26.json). Speed relative to
CPython is in parentheses.

| Workload | CPython | PyPy | mpz | int64 |
|---|---:|---:|---:|---:|
| `lcg32` | 0.791 s | 0.009 s (90.0×) | – | 0.005 s (157×) |
| `collatz` | 0.856 s | 0.038 s (22.3×) | – | 0.045 s (19.1×) |
| `cross64` | 0.578 s | 0.341 s (1.70×) | 0.399 s (1.45×) | – |
| `arith128` | 0.728 s | 0.621 s (1.17×) | 0.691 s (1.05×) | – |
| `factorial` | 0.529 s | 0.653 s (0.81×) | 0.708 s (0.75×) | – |
| `fibadd` | 0.966 s | 0.747 s (1.29×) | 1.069 s (0.90×) | – |
| `bigmul` | 0.657 s | 0.381 s (1.73×) | 0.689 s (0.95×) | – |
| `dectext` | 0.710 s | 1.102 s (0.64×) | 0.752 s (0.94×) | – |
| `modpow` | 0.877 s | 0.532 s (1.65×) | 1.015 s (0.86×) | – |
| `containers` | 0.536 s | 0.692 s (0.77×) | 0.628 s (0.85×) | – |

Peak RSS: CPython 11–12 MiB (58 MiB on `containers`), PyPy 57–222 MiB, the mpz binaries 35–37 MiB
(99 MiB on `containers`) and the int64 ones 2 MiB, as they allocate nothing.

What this shows, and does not:

- **int64** loops are where Pystachy's checked ints stand today: 157× and 19× CPython, beside
  PyPy's JIT at 90× and 22×. The roadmap's budget is to keep this speed for promoting ints.
- **mpz**, now with CPython's algorithms (#902–#905), is within 0.75–1.45× of CPython on every
  big-integer workload; an earlier run on the same VM that day gave 0.87–1.34×, so a workload's
  ratio can move by 0.15 between runs. `factorial`, `containers` and `dectext` still allocate a
  wrapper object per value, and `modpow`'s mpz variant multiplies and reduces in a loop where
  CPython runs three-argument `pow` in C.
- These are bounded microbenchmarks on a shared VM, not application results. No GMP comparison,
  JIT (`pystachy run`) timing or compile-time cost is included.

## Reproduce

From the repository root, after `make`:

```sh
python3 bench/integers/run.py --compiler ./pystachy --cpython python3.13 \
  --pypy /path/to/pypy3 --samples 5 --cpu 3 --json build/integers.json
```

`--only NAME...` selects workloads, and `--python-int` adds `NAME.py` built by Pystachy, whose
ints promote in a module that opts in. Its first measurements, of the eight workloads that keep
their values outside containers, are in
[results/linux-x86_64-2026-10-26-python-int.json](results/linux-x86_64-2026-10-26-python-int.json);
with the inline paths for values that fit, in
[results/linux-x86_64-2026-10-26-python-int-fast-paths.json](results/linux-x86_64-2026-10-26-python-int-fast-paths.json);
`modpow`, once three-argument `pow` took every value, in
[results/linux-x86_64-2026-10-26-python-int-modpow.json](results/linux-x86_64-2026-10-26-python-int-modpow.json);
and all of them in [the promoting int guide](../../docs/python-int.md#measurements).

## History

The programs and the runner come from the opt-in source-rewriting prototype of #901, which
measured them on 2026-10-25 at compiler commit `93bc9209`, before the mpz core used CPython's
algorithms (#902–#905); its numbers are in that PR.
