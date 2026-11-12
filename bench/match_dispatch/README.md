# Bounded `match` dispatch

[`workload.py`](workload.py) compares literal routing, fixed tuple patterns and
plain dataclass patterns with equivalent handwritten conditions. Both variants
consume identical typed data and compute an observable integer checksum. The
tuple and dataclass paths include OR patterns, captures, a false-guard fallback
and negative values. Literal routing includes success, failure and unknown codes.

Each workload has a mixed input distribution and a skewed distribution where 99
of each 100 items select one common branch. All input construction, independent
known-answer assertions and one warm-up pass precede the kernel timer. The timed
region contains the loop, dispatch, payload arithmetic and checksum accumulation.
Complete process times also include setup and validation; JIT process times
include compilation and startup.

## Correctness and paired timings

Use the pinned interpreter in `.python-version` and the repository's LLVM
toolchain. Run from the repository root after building the compiler:

```sh
python3 bench/match_dispatch/bench.py --smoke \
  --json build/match-dispatch-smoke.json
python3 bench/match_dispatch/bench.py --samples 7 \
  --keep build/match-dispatch-artifacts \
  --json build/match-dispatch.json
```

`--compiler "python3 -m pystachy"` selects the hosted compiler. `--modes`,
`--kinds` and `--shapes` select a smaller run. `--loops` and `--size` control
work, and `--cpu` chooses an allowed CPU. On Linux the default is the lowest
allowed CPU. `--keep` must name a new directory.

The controller first compares both variants with a CPython oracle and checks
the full output of every run. It then alternates variant order in paired process
samples on one CPU. Reports preserve source hashes, compiler/toolchain identity,
environment, build time, executable size, raw process/kernel timings and paired
ratios. `if / match` above one favors `match`. The `--smoke` report is correctness
evidence only and deliberately contains no speedup summary.

The controller disables the native program cache explicitly while warming its
private runtime cache. Each JIT command therefore compiles the program again.
Unexpected standard error, mismatched checksums/counts and failed commands
invalidate the report. Its negative controls run with:

```sh
python3 -m unittest discover -s bench/match_dispatch -p test_bench.py
```

The default reports steady-state kernel time and complete command time
separately. AOT build time is a single observation including any initial runtime
cache preparation; it is not a paired build-performance comparison. Avoid heavy
parallel jobs while measuring. A small ratio or a span crossing one is not
evidence of a reliable performance advantage on a shared host.

These are original, focused microbenchmarks, not upstream pyperformance scores,
and no measured results are recorded here. The typed dataclass baseline accesses
fields directly, while CPython's `match` still performs its class-pattern
protocol. The comparison describes each language form under the stated static
input contract, rather than general dynamic class matching.

## Optional pyperf process measurements

With `pyperf` installed, use the retained prebuilt executable from the full run:

```sh
python3 -m pyperf command -o build/match-process.json \
  build/match-dispatch-artifacts/dispatch.exe tuple match mixed 10000 4096
python3 -m pyperf command -o build/if-process.json \
  build/match-dispatch-artifacts/dispatch.exe tuple if mixed 10000 4096
python3 -m pyperf compare_to build/if-process.json build/match-process.json
```

These pyperf results measure complete executable invocations, including input
construction and validation. They do not replace the controller's separate
kernel measurements. Choose loop counts that make measured dispatch dominate
startup; preserve pyperf's metadata and heed its stability diagnostics. Use
`--affinity CPU` with the same allowed CPU for both commands when available.

The [command-dispatch example](../../examples/match_dispatch/README.md) shows the
same pattern forms in a small end-to-end consumer. The existing
[`bench-pyperformance-check`](../pyperformance/README.md) remains the broader
adapted pyperformance correctness check.
