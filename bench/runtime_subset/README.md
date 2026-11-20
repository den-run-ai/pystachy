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
18.1.3 on Linux x86-64; its CPU model was not recorded. `PYSTACHY_LLVM` is
mandatory so both builds and runs use the intended matching toolchain.

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

## Integer text conversion

`str(int)` and `int(str, base)` moved from `runtime.c` to `runtime.py` after the migration
above. Their workload is [`int_text.py`](int_text.py), a separate source so that
`workload.py` keeps the hash the first report names. `compare.py` selects it for these
cases:

| Case | Default iterations | Work measured |
|---|---:|---|
| `str-int` | 20,000,000 | `str()` of ints of 1 to 19 digits, both signs |
| `str-int-short` | 20,000,000 | `str()` of ints of 1 to 4 digits, both signs |
| `int-str` | 20,000,000 | `int(s, 10)` of the same numbers' decimal digits |
| `int-str-short` | 20,000,000 | `int(s, 10)` of 1 to 4 decimal digits |
| `int-str-hex` | 20,000,000 | `int(s, 16)` of the same numbers' hex digits |
| `int-str-padded` | 20,000,000 | `int(s, 10)` with a space before and a newline after |

The 4,096 numbers and their texts are made before the timed region. Each iteration reads
one of them; `str()` takes a value that also depends on the iteration, and the length and
last byte of its result enter the checksum.

```sh
taskset -c "$BENCH_CPU" python3.13 bench/runtime_subset/compare.py \
  --before "$BENCH_BASELINE" --after . --pairs 7 \
  --cases str-int str-int-short int-str int-str-short int-str-hex int-str-padded \
  --json /tmp/int-text.json
```

The [recorded report](int-text.json) compares baseline
`d35417c967f25ac699bb713f4c796dfaf2c57fac` with
`094d880c35b3c06cb68801bc03c9b2426e555794`, both from clean checkouts with freshly
bootstrapped compilers, on CPython 3.13.16 and LLVM 18.1.3. The host is a shared four-CPU
Linux x86-64 virtual machine (an Intel Xeon whose model the host does not name); the run
was pinned to CPU 2 and the load average was 0.92 when it began.

| Workload | AOT after / C | JIT after / C | AOT ns per iteration, C to after |
|---|---:|---:|---:|
| `str-int` | 0.628 | 0.622 | 55.7 to 34.9 |
| `str-int-short` | 0.455 | 0.427 | 44.5 to 20.5 |
| `int-str` | 0.634 | 0.673 | 42.1 to 26.6 |
| `int-str-short` | 0.744 | 0.797 | 22.1 to 16.4 |
| `int-str-hex` | 0.410 | 0.436 | 57.7 to 23.6 |
| `int-str-padded` | 0.637 | 0.662 | 43.8 to 27.9 |

Ratios are medians of seven alternating pairs, and the times are medians of the kernel
timer divided by the iterations, loop included. Every pair of every case has a ratio below
1; the largest is 0.804 (`int-str-short`, JIT). Collections and managed-heap peaks are
equal in both versions: 23 and 19 collections with a 32.8 and 32.9 MiB peak for the two
`str()` cases, none for the others.

The AOT executable grows from **140,536 to 145,416 bytes** (+4,880; +3.5%), and its text
from 100,945 to 102,313 bytes (`size`). By symbol (`nm -S`), `pys_int_str` grows by 576
bytes and `pys_str_int` by 95; 618 are `pys_str_cat`, which builds the message for a
number past CPython's 4,300 digits and which this program did not link before.

The hex case gains most because the digit's value is selected from its two readings,
digit and letter, where the C helper branched on them. A variant that branched ran the
decimal cases about 6% faster and the hex case about twice as slow as the recorded one.
That comparison was three runs of each variant on the same host and is not in the report.

## List reductions and path joins

`any()` and `all()` of a list of ints or bools, `sum()` of ints from a float start and
`os.path.join`'s step for two parts moved from `runtime.c` to `runtime.py`. Their workload
is [`reductions.py`](reductions.py), which also times `str.join` and the join of a slice:
those two stayed as they were, for the reason below. `compare.py` selects it for these
cases:

| Case | Default iterations | Work measured |
|---|---:|---|
| `ints-any-all` | 400,000 | `any()` of 4,096 ints whose last alone is nonzero, and `all()` of 4,096 ones |
| `ints-any-all-short` | 200,000,000 | `any()` and `all()` of one of eight lists of 0 to 8 ints |
| `ints-sum-float` | 400,000 | `sum(xs, start)` of 4,096 ints from a float start |
| `join` | 800,000 | `", ".join()` of 256 strs of 1 to 3 bytes |
| `join-bytes` | 400,000 | `"".join()` of 1,024 strs of 1 or 2 bytes |
| `join-slice` | 1,200,000 | `"-".join(xs[lo:-1])` of 251 to 255 strs of 2 or 3 bytes |
| `path-join` | 60,000,000 | `os.path.join(a, b)` of 8 first parts and 7 second parts |

The lists and strs are made before the timed region. Each iteration changes one item of a
list it scans or joins, or takes its operands by the iteration, so that no result can be
computed once.

```sh
taskset -c "$BENCH_CPU" python3.13 bench/runtime_subset/compare.py \
  --before "$BENCH_BASELINE" --after . --pairs 7 \
  --cases ints-any-all ints-any-all-short ints-sum-float join join-bytes join-slice path-join \
  --json /tmp/reductions.json
```

The [recorded report](reductions.json) compares
`71aac074336821a03589401cf7fa61db73fce2e3` with
`c1b9fc13aa19ad4d4d48cae76fa8d83da17d218c`, both from clean checkouts with freshly
bootstrapped compilers, on CPython 3.13.16 and LLVM 18.1.3, on the host of the integer text
report. The run was pinned to CPU 2 and the load average was 1.04 when it began.

| Workload | AOT after / before | JIT after / before | AOT ns per iteration, before to after |
|---|---:|---:|---:|
| `ints-any-all` | 0.999 | 1.002 | 2,213 to 2,223 |
| `ints-any-all-short` | 0.898 | 0.942 | 3.64 to 3.23 |
| `ints-sum-float` | 1.001 | 1.001 | 2,111 to 2,112 |
| `join` | 0.997 | 0.999 | 1,198 to 1,195 |
| `join-bytes` | 1.007 | 1.001 | 2,437 to 2,458 |
| `join-slice` | 1.005 | 1.000 | 803 to 817 |
| `path-join` | 0.993 | 1.003 | 21.9 to 21.9 |

Ratios are medians of seven alternating pairs, and the times are medians of the kernel
timer divided by the iterations, loop included. Single pairs range from 0.801 to 1.141
but for one JIT pair of `ints-sum-float` at 1.326, whose other six are 0.986 to 1.012.
Collections and managed-heap peaks are equal in both versions: none for the three cases
of ints, and 30, 15, 36 and 58 collections with a 34.0 MiB peak for `join`, `join-bytes`,
`join-slice` and `path-join`. The AOT executable is 154,840 bytes in both.

### The join that was not moved

`7e438c6486cea16293b6f3ca0735f1b5ba8ce2e3` also moved the join of a slice, giving it and
`str.join` one loop in `runtime.py` that indexes the list from the slice's first item to
its last. The [report of that tree](reductions-shared-join.json), against the same
baseline on the same host (load average 0.51), shows the cost of indexing each item
where `pys_str_join` iterates its list and `runtime.c`'s slice form passes it a view of
the items:

| Workload | AOT shared loop / before | JIT shared loop / before |
|---|---:|---:|
| `join` | 1.266 | 1.268 |
| `join-bytes` | 1.500 | 1.484 |
| `join-slice` | 1.365 | 1.366 |

`str.join` and its slice form are therefore as they were before, and the three join cases
of the first table compare the same code.
