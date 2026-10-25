# Integer benchmarks: python-int, mpz and int64 against CPython and PyPy

These programs compare three Pystachy integer paths with CPython's and PyPy's
builtin `int`:

- **python-int**: the opt-in [promoting integer prototype](../../docs/python-int.md)
  (`# pystachy: python-int`, ordinary `int` syntax). The same source runs
  unchanged on CPython and PyPy, which ignore the comment.
- **mpz**: the explicit [`mpz`](../../docs/mpz.md) type, in `NAME_mpz.py`.
  Its CPython twin (`mpz = int`) prints the same checksum.
- **int64**: default checked `int`, in `NAME_i64.py`, only where every value fits.

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

Each program prints a checksum and then the seconds its timed loop took.
Startup, compilation and printing are excluded.

## Results

Measured 2026-10-25 at compiler commit `93bc9209` on a shared 4-vCPU Intel Xeon
@ 2.10 GHz cloud VM (Linux 6.18.44 x86-64), LLVM 18.1.3, default optimization and GC,
AOT binaries. CPython 3.13.16 was built from the python.org source with
`--enable-optimizations --with-lto`. PyPy is 7.3.23 (Python 3.11.15). Every variant
printed the same checksum. Each cell is the median of five samples, pinned to one
CPU, with variant order alternating between samples; raw samples, peak RSS and
source hashes are in [results/linux-x86_64-2026-10-25.json](results/linux-x86_64-2026-10-25.json).

| Workload | CPython | PyPy | python-int | mpz | int64 |
|---|---:|---:|---:|---:|---:|
| `lcg32` | 0.627 s | 0.008 s | 0.340 s | – | 0.005 s |
| `collatz` | 0.801 s | 0.038 s | 0.655 s | – | 0.043 s |
| `cross64` | 0.443 s | 0.330 s | 0.756 s | 0.407 s | – |
| `arith128` | 0.650 s | 0.550 s | 1.253 s | 0.586 s | – |
| `factorial` | 0.472 s | 0.581 s | 0.676 s | 0.603 s | – |
| `fibadd` | 0.668 s | 0.715 s | 1.194 s | 1.017 s | – |
| `bigmul` | 0.628 s | 0.373 s | 1.173 s | 1.195 s | – |
| `dectext` | 0.725 s | 1.001 s | 3.046 s | 2.163 s | – |
| `modpow` | 0.817 s | 0.529 s | 1.317 s | 1.161 s | – |
| `containers` | 0.472 s | 0.713 s | 1.556 s | 0.692 s | – |

Peak RSS: CPython 12.6 MiB and PyPy 60–186 MiB on the scalar workloads; Pystachy
binaries 26–37 MiB (12.6 MiB for int64, which allocates nothing). On `containers`,
CPython 55 MiB, mpz 99 MiB, python-int 127 MiB, PyPy 226 MiB.

What this shows, and does not:

- **mpz** matches or beats CPython only around 64–128 bits (`cross64` 1.09×,
  `arith128` 1.11×). It is slower for growing and large values: schoolbook
  multiplication (`bigmul` 0.53×, where CPython and PyPy use Karatsuba) and
  quadratic decimal conversion (`dectext` 0.33×) are the largest gaps.
- **python-int** keeps CPython results. On int64-only loops it is 1.2–1.8× faster
  than CPython but 15–72× slower than default int64, because every value is a heap
  wrapper and overflow detection catches `OverflowError`. Promoted values cost up
  to 2.3× the explicit mpz path (`arith128`, `containers`), from wrappers and
  conversions of small operands.
- An earlier prototype demoted every large result by catching `to_int()`'s
  `OverflowError`; measured the same way, `arith128` took 24.3 s, `cross64` 5.7 s
  and `fibadd` 4.2 s before commit `93bc9209` tested the bit length instead.
- **PyPy**'s JIT dominates int64-only loops in CPython-compatible code (80× and 21×
  CPython). Default Pystachy int64, which rejects or raises past 64 bits, is about as
  fast. For large integers PyPy ranges from 0.66× to 1.68× CPython.
- These are bounded microbenchmarks on a shared VM, not application results.
  No GMP comparison, JIT (`pystachy run`) timing or compile-time cost is included.

## Reproduce

From the repository root, after `make`:

```sh
python3 bench/integers/run.py --compiler ./pystachy --cpython python3.13 \
  --pypy /path/to/pypy3 --samples 5 --cpu 3 --json build/integers.json
```

`--only NAME...` selects workloads. The runner builds each Pystachy variant with
`pystachy build`, refuses to time a workload whose variants print different
checksums, and records each child's peak RSS.
