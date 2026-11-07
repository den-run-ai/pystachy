# Runtime subset benchmarks

These workloads compare the native C helpers with their `runtime.py` replacements
and exercise the compiler's forward-range list-bounds proof. Both versions use
the same workload source, inputs and LLVM toolchain. See [the runtime
guide](../../docs/runtime-in-subset.md) for the ABI and storage contracts, and
[PR #1123](https://github.com/den-run-ai/pystachy/pull/1123) for the migration's
review and validation history.

## Run the paired comparison

Use two clean checkouts with freshly built native `./pystachy` compilers. Build
them separately before timing, and keep other builds and heavy tests off the
host during the measurement. The recorded run uses CPython 3.13.16 and LLVM
18.1.3 on Linux x86-64. `PYSTACHY_LLVM` is mandatory so both builds and runs use
the intended matching toolchain.

From the candidate checkout, after building both checkouts:

```sh
export PYSTACHY_LLVM=/path/to/llvm-18/bin
BENCH_BASELINE=../baseline
BENCH_CPU=8  # choose an allowed CPU on this host
taskset -c "$BENCH_CPU" python3.13 bench/runtime_subset/compare.py \
  --before "$BENCH_BASELINE" --after . --pairs 7 \
  --json /tmp/runtime-subset-result.json
```

Use `--cases scalar range power` to select workloads or `--scale N` to multiply
their iteration counts. The defaults keep the small kernels long enough to
measure without launch time:

| Case | Default iterations | Work measured |
|---|---:|---|
| `scalar` | 120,000,000 | `degrees`, `radians`, and `isclose` with varying operands |
| `range` | 60,000,000 | Positive/negative range lengths and membership |
| `power` | 60,000,000 | Checked integer powers with varying bases and exponents |
| `sum-float` | 5,000 | Compensated float-list sum with a varying float start |
| `sum-int` | 5,000 | Compensated float-list sum with a varying integer start |
| `reduction` | 5,000 | Indexed absolute-value reduction from index one |
| `ascii` | 5,000 | ASCII-only representation and escape processing |
| `unicode` | 5,000 | Mixed-width Unicode representation and escape processing |

List/text construction happens before the measured region. Escape inputs vary
each iteration, and the changing prefix contributes to the checksum. Reduction
inputs are exactly representable so each varying start remains observable.

The controller builds both AOT executables, warms each mode/case, and alternates
before/after order between pairs. Ratios use each program's internal kernel
timer; compilation and process launch are excluded. Wall times are also retained.
Every native output checksum must exactly equal CPython's checksum. This is a
timing guard, not a replacement for the full-output and edge-case regression tests.

Reports start with `complete: false` and become complete only after every
requested case finishes. Failed or interrupted reports must not be presented as
completed comparisons. Source/compiler hashes, toolchain, affinity, checksums,
individual paired samples, build outputs and GC observations are retained.

## Recorded comparison

The [complete report](benchmark.json) compares baseline `f7103067545b43cdcd8ce20dc66b1571425b3a8d`
with the integrated migration and bounds optimization. The final native compiler
was freshly bootstrapped; the report records the measured source identities and
hashes. Later additions of this README and result files do not change those inputs.

| Workload | AOT after / C | JIT after / C |
|---|---:|---:|
| `scalar` | 0.997 | 0.976 |
| `range` | 0.923 | 0.947 |
| `power` | 1.039 | 1.003 |
| `sum-float` | 1.018 | 1.037 |
| `sum-int` | 1.011 | 1.020 |
| `reduction` | 1.008 | 0.239 |
| `ascii` | 0.264 | 0.252 |
| `unicode` | 0.631 | 0.621 |

Ratios are **after / before**; lower is faster. These are medians of seven
alternating pairs pinned to CPU 8 on a shared host. They describe these workloads
and this toolchain, not a universal parity or statistical-significance claim.
Individual samples and their variation are available in the report.

The combined benchmark executable changes from **114,024 to 114,552 bytes** (**+528 bytes; +0.46%**). Numeric/scalar workloads report the same **0.4 MiB** managed-heap peak; float-list reductions report **0.6 MiB** in both versions. The ASCII workload reports **38.0 → 34.4 MiB**, and Unicode **6.1 → 6.0 MiB**.

GC observations come from one separate AOT process per case/version. They cover
the entire program, including input setup, and report managed-heap peaks rounded
to 0.1 MiB. They do not measure RSS, JIT memory or allocation counts. Numeric
helpers preserve their successful-path allocation-free implementations; the ASCII
helper fills one exact-sized string instead of growing an intermediate buffer.

## Independent numeric contract

```sh
python3.13 bench/runtime_subset/numeric_contract.py \
  --before "$BENCH_BASELINE" --after . --compiler ./pystachy \
  --seed 1123 --random-ranges 20000 --json /tmp/runtime-numeric-contract.json
```

The [recorded result](numeric-contract.json) checks 21,352 range lengths,
106,760 memberships and 9,669 integer-power results/errors against the original C
helpers and independent CPython oracles. It exercises signed 64-bit extremes,
unsigned range-count patterns, checked overflow and negative-exponent errors.

The probe extracts the actual compiled runtime functions and links a small
exception shim. Its 137,781 checks establish native values and error text; they
do not test the complete runtime unwinder, GC, or performance. Full-runtime JIT,
AOT, GC-stress and sanitizer regressions are separate validation linked from the PR.
