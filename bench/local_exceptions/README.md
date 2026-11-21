# Locally caught container errors

This workload isolates EAFP (`try` the operation, catch a missing item) in typed
dictionary and list reads, with all hits, all misses and 50% misses. A word-count
consumer uses `counts[word] += 1` and inserts on `KeyError`; each batch contains
256 distinct strings repeated twice. `list.index()` and `int()` failures are
controls for runtime errors outside the optimized lookup operations.

## Reproduce

Build baseline and candidate compilers in separate checkouts using the same pinned
CPython and LLVM toolchain. Preserve their compiler/runtime fixed-point evidence.
Choose an available CPU from `os.sched_getaffinity(0)` and run this independently
of other builds/tests:

```sh
python3.13 bench/local_exceptions/run.py \
  --baseline ../pystachy-before --candidate . --python python3.13 \
  --llvm /usr/lib/llvm-18/bin --cpu 0 --repeats 1000 --samples 7 \
  --output build/local-exceptions/results.json
```

Use `--repeats 10 --samples 1` first to calibrate. Each batch performs 512
operations. Hit-only cases use 100 times as many repeats by default
(`--hit-multiplier`) so their very short native loops are measurable. The runner
builds the same workload with each native compiler,
checks all variants against CPython before measurement, then rotates their
execution order every sample. Every timed checksum must also match. It records
raw timings, medians, source/compiler/executable hashes, compiler source manifests,
build commands, platform, affinity and host load. Run from a stable source tree;
changes during measurement invalidate the result.

Times come from `perf_counter()` inside each fresh workload process. They exclude
process startup, command-line parsing, shared input construction and AOT compilation.
They include per-function container construction, dictionary resets and garbage
collection. The word-count case includes its final sum/length validation. These
are bounded workloads, not whole-application or JIT startup claims. Peak memory
is not measured, and timing differences whose sample ranges overlap are inconclusive.

## Recorded results

[2026-11-11 results](results/2026-11-11/README.md) include baseline/candidate
source identities, raw samples, validation and the dictionary hit-path tradeoff.
