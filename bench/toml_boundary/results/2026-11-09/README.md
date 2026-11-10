# Typed TOML namespace state

This compares baseline `c1796654c55d162ff7cad43390c86270acaf91f3` with the
[published implementation](https://github.com/den-run-ai/pystachy/commit/54e32245e89aa8ca193a17bd54e42a90261539cd).
The candidate replaces TOML's private dynamic flag dictionaries with typed
recursive nodes and integer sets. Open callback results, public document
storage, compiler/runtime code and module identity tracking remain unchanged.

The [raw report](report.json) contains commands, samples, source hashes, relevant
environment and toolchain details. The candidate was measured before its commit
was created; [source verification](source-verification.json) matches all 167
recorded source inputs and all five benchmark files to the identical published
Git tree. The report preserves its original checkout status rather than
pretending that the publication preceded the run.

## Workload and execution costs

Linux x86-64, Intel Xeon Platinum 8573C, one allowed CPU (0), CPython 3.13.16 and
LLVM 18.1.3. Both compilers are CPython-hosted and use their own library/runtime
sources and private caches. The consumer parses 16 worker sections with nested
inline tables and arrays of tables, then scores them through concrete
annotations. Each process runs three samples of 100 parses. There are five
alternating baseline/candidate pairs, each checked against CPython and an
independent checksum. These are shared-host measurements for this workload.

The entries below are medians across five processes. In-process durations first
take the median of each process's three samples; correlated samples do not gain
extra statistical weight.

| Cost | Baseline | Typed flags |
|---|---:|---:|
| Hosted frontend IR emission | 2.317 s | 2.161 s |
| Warm AOT build | 13.432 s | 12.350 s |
| Whole-process JIT, compilation included | 5.191 s | 4.841 s |
| Whole-process AOT, three samples | 133.61 ms | 119.66 ms |
| JIT parsing/processing, 100 parses | 56.12 ms | 47.98 ms |
| AOT parsing/processing, 100 parses | 39.65 ms | 35.21 ms |
| First AOT build, empty runtime cache (one observation) | 22.961 s | 22.915 s |
| Executable bytes | 742,360 | 742,008 |

All five paired in-process comparisons improved in both execution modes.
The median of the five *paired speed ratios* is 1.089 for JIT and 1.167 for AOT;
these differ from dividing the separate medians in the table. AOT process
medians span 38.04–45.64 ms before and 32.46–35.69 ms after; JIT spans
49.98–58.55 ms before and 47.11–53.50 ms after. Compile/build ranges overlap, so
their small changes are inconclusive. Cold build has only one observation.
Binary and raw byte sizes include each checkout's own path literals.

## Allocations, retention and emitted operations

A separate counted AOT build executes the same three samples, totaling 300
parses. These are C allocation requests before allocator rounding, not JIT
allocation counts or physical memory traffic. Counts include initialization and
output formatting. The retained-memory diagnostic runs in five independent
processes, after 100 parses, with the input and one document still live.

| Metric | Baseline | Typed flags | Interpretation |
|---|---:|---:|---|
| C allocation requests | 4,273,870 | 3,572,770 | 16.4% fewer |
| C requested bytes | 193,254,261 | 179,776,462 | 7.0% fewer |
| Peak managed-heap bytes | 36,450,304 | 36,450,304 | Unchanged |
| Conservative post-collection live bytes | 143,353 | 143,353 | Identical in all five processes per variant |
| Raw program IR lines | 91,294 | 91,173 | Static footprint |
| Raw C dynamic-helper call sites | 2,024 | 2,000 | Direct `pys_dyn_*` calls |
| Raw generated-dispatcher call sites | 50 | 24 | Direct `dyn.*` calls |
| LLVM-O2 program IR lines | 53,634 | 53,517 | Before runtime linking |
| LLVM-O2 C dynamic-helper call sites | 1,742 | 1,695 | Static calls, not execution counts |

Within this consumer's `Flags` methods and entry construction, C dynamic-helper
calls fall from 25 to 1 and generated dispatcher calls from 26 to 0. The sole
remaining call boxes the integer unpacked from a pending tuple. The hosted
representation test checks the typed node/dictionary/set fields and bounds the
residual call count. Supplying the original parser is a negative control: the
test fails on its `dict[dyn,dyn]` storage.

The collector is conservative. Its live-byte count includes globals, caches,
input and any conservatively retained objects; it is not an ideal object census
or RSS. No reduction in retained or peak memory is claimed. The initial harness
smoke failed because its collection wrapper was not exported for dynamic symbol
lookup. Marking it used/default-visible and exporting the symbol fixed the
diagnostic; the focused native probe also passed under GC stress. The complete
report above is from the corrected harness. macOS execution remains unverified.

## Correctness and scope

Seven TOML fixtures passed JIT and AOT normally and with collection at every
allocation: 28 hosted-compiler/native-program executions, zero failures. They
include upstream data/error cases, recursive flag changes, pending duplicates,
subtree resets, callback errors and invocation order, object aliases, and
same-object NaN membership/equality. Recordings use CPython 3.13.16.

All 19 identity-scope tests and five evidence-harness controls passed. The
ordinary IR/diagnostic audit covered 221 benchmark, generic and typed-JSON
controls: 220 were byte-identical; one had only an independently verified
checkout-path string and its length fields. The [path audit](ordinary-path-audit.json)
contains that complete diff. Lint, runtime-root checks and repository hygiene
passed. Full local verification/bootstrap and the full corpus IR audit were not
run; CI is separate evidence.

Reproduction for the focused executions and controls, using the pinned tools:

```sh
PYSTACHY_JOBS=2 tests/run.sh 'python3.13 -m pystachy' 'jit aot' \
  tests/programs/library/lib_tomllib*.py tests/programs/upstream/upstream_tomllib*.py
PYSTACHY_GC_STRESS_PROGRAM=1 PYSTACHY_JOBS=2 \
  tests/run.sh 'python3.13 -m pystachy' 'jit aot' \
  tests/programs/library/lib_tomllib*.py tests/programs/upstream/upstream_tomllib*.py
python3.13 -m unittest discover -s tools -p test_identity_scope.py
python3.13 -m unittest discover -s tools -p test_toml_boundary.py
```

Use the [runner instructions](../../README.md) with width 16, rounds 100,
samples 3 and processes 5 for the cost report. Short-use and input-size scaling
remain unmeasured here. This result establishes one smaller dynamic computation
and storage boundary; it does not shrink the transitive identity-tracking
closure or establish that every remaining library opt-in is necessary.
