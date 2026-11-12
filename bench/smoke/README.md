# CI performance kernels

`tools/perf_smoke.py` runs these small deterministic algorithms with CPython and both
revisions' native JIT/AOT compilers. Runtime arguments and printed checksums keep the
work observable. Analytical checks run before timing; every measured result must match
CPython. These are core algorithm probes, not full application benchmarks.

| Case | Work measured | Limits |
|---|---|---|
| `autograd` | microGPT-style scalar object DAG, shared nodes, operator dispatch, identity-set traversal, gradient accumulation and allocation | Add/multiply/backward; no full model, optimizer or dataset |
| `numeric` | 24×24 dense matrix-vector projection and stable softmax, varying inputs and weighted output checksum | Typed flat lists; no ndarray views, BLAS, GPU or full nanoGPT |
| `fnmatch` | Cached wildcard hits/misses plus fresh pattern translation and regex compilation | Small routing-like names; no router I/O or application result cache |
| `json` | Actual `json.loads`, nested mixed values, dynamic `Any` traversal, dictionary/list allocation, Unicode and escapes | CPython uses its stdlib, Pystachy its native JSON overlay; no files or encoder |
| `repair_scan` | Single-pass quoted-string/token scanning, slices, membership, escape decoding and list/join assembly; short, malformed, truncated and 2,048-escape inputs | Original scanning probe; does not import json_repair or implement its structural heuristics |
| `copy_int`, `copy_float` | Typed numeric recurrence, local copy and accumulation in a dynamic-Any opt-in module | No observable identity or Any crossing; isolates unwanted boxing of ordinary numeric copies, without measuring retained memory |
| `global_int`, `global_float` | The same recurrences through mutable typed module globals | Retains global-read snapshot costs outside the closed-function proof; no identity observation or Any crossing |
| `graph_copy` | Deep-copy and checksum processing of 4,000 heterogeneous cyclic graphs, including shared nodes and integer identity memo keys | Uses the existing [dynamic-Any graph driver](../../tools/dynany_bench.py); processing CPU time excludes construction and startup; no retained-memory or stdlib `copy.deepcopy` claim |
| `regex_effbot` | Existing adapted pyperformance regex workload | See [pyperformance provenance and adaptations](../pyperformance/README.md) |

The first two cases share `ml.py`, the next three share `text.py`, and the numeric-copy/global
cases share `identity.py`. The graph case uses `tools/dynany_bench.py graph-smoke 4000`.
Compilation is measured once per source file, while every mode has its own execution
samples. This keeps the suite small without mixing unrelated loop timings.

For a quick standalone correctness run, use Python 3.13 or a native compiler:

```sh
python3.13 bench/smoke/ml.py autograd 2
./pystachy run bench/smoke/text.py json 2
python3.13 bench/smoke/identity.py int 100 123
python3.13 tools/dynany_bench.py graph-smoke 3
```

The adapted scalar `Value` implementation retains microGPT's MIT attribution in
`ml.py` and [license](../microgpt/LICENSE). The remaining drivers are original project
code. No model downloads or new dependencies are needed. `regex_effbot` comes from
pyperformance; the **pyperf runner is not used**. Measurement and warning rules are
documented in [testing](../../docs/testing.md#continuous-integration).

Numeric-copy/global cases use six million iterations and a runtime seed of 123 so the native
loops are long enough to exercise the 5 ms warning floor. The paired harness
records timing; peak RSS and retained-memory costs require separate measurements.

`graph_copy` retains the graph-processing workload that exposed #821's historical
regression, tracked in #780. Its `jit_loop_s` and `aot_loop_s` use `process_time_ns`
around deep-copy plus checksum processing; the other cases use `perf_counter` wall time.
Each result records `loop_clock` so these clocks remain distinguishable. Whole-process
times still include graph construction and startup. The original `graph` mode retains
its checksum/construction-nanoseconds/processing-nanoseconds output for historical replay.

The standalone [dynamic iteration driver](../../tools/dynany_iteration_bench.py) exercises
streaming list, range, object and generator iteration through `Any`. It is separate from
`dynany_bench.py` so new protocol calls do not prevent an older compiler from building the
existing graph comparison. Each mode checks the arithmetic checksum and consumed-item
count. Object and generator producers also count every advance and assert that production
stays one item ahead of consumption, detecting accidental eager materialization.

```sh
python3.13 tools/dynany_iteration_bench.py generator 100000
./pystachy build tools/dynany_iteration_bench.py -o build/dynany_iteration_bench
build/dynany_iteration_bench object 100000 smoke
PYSTACHY_GC_STRESS_PROGRAM=1 ./pystachy run tools/dynany_iteration_bench.py generator 20 smoke
```

Replace `generator` or `object` with `list` or `range` for the other modes. Normal output
separates construction and processing CPU nanoseconds; `smoke` prints a deterministic
checksum/count line to stdout and processing CPU seconds to stderr. Use a separate untimed
`PYSTACHY_GC=stats` run for memory evidence.

The maintained unit checks include empty, one-item and multi-item inputs plus a negative
control for eager production. These modes are not default `perf_smoke.py` base/head cases:
the baseline does not support all four paths, so they report no before/after speedup and
set no timing threshold.

## Retained JSON decoder controls

`json_decode.py` retains three deterministic 32-key objects for
[#969](https://github.com/den-run-ai/pystachy/issues/969). `numeric` preserves the
reconstructed `k0:1000` through `k31:1031` payload; `strings` uses short string
values; `mixed` includes numbers, strings, booleans, null, lists and nested objects.
These are **new acceptance controls**, not the lost historical source behind the
approximately 124M-instruction claim. Their counts cannot validate that old number.

```sh
python3.13 bench/smoke/json_decode.py numeric 3000
./pystachy run bench/smoke/json_decode.py mixed 2
./pystachy build bench/smoke/json_decode.py -o build/json_decode
build/json_decode strings 3000
```

The default is `numeric 3000`; `N` counts individual loads. The timed loop discards
results, exercising the typed `JSONValue` decoder inside an opt-in program, as the
adapted pyperformance workload does. A separate untimed load into `Any` prints the
full parsed result to stdout. Compare every stdout byte with CPython; the single
`seconds` line on stderr measures only the loop.

The output check covers the dynamic adapter separately and does not prove each
discarded typed result was inspected; use the differential JSON suite for that
contract. These standalone controls do not expand the default CI performance matrix.

For a paired AOT instruction comparison, build both revisions from clean, identified
checkouts with the same toolchain and input. First clear inherited `PYSTACHY_*`
settings except the intended `PYSTACHY_LLVM`; keep each checkout's library/runtime
and cache separate. Replace the baseline path and choose a CPU allowed by your host:

```sh
JSON_BASE=/absolute/path/to/baseline-checkout
JSON_INPUT="$PWD/bench/smoke/json_decode.py"
JSON_OUT=$(mktemp -d)
JSON_CPU=$(python3 -c 'import os; print(min(os.sched_getaffinity(0)))')
PYSTACHY_HOME="$PWD" PYSTACHY_CACHE="$JSON_OUT/cache-head" \
  ./pystachy build "$JSON_INPUT" -o "$JSON_OUT/head"
(cd "$JSON_BASE" && PYSTACHY_HOME="$JSON_BASE" PYSTACHY_CACHE="$JSON_OUT/cache-base" \
  ./pystachy build "$JSON_INPUT" -o "$JSON_OUT/base")
for JSON_CASE in numeric strings mixed; do
  python3.13 "$JSON_INPUT" "$JSON_CASE" 3000 > "$JSON_OUT/$JSON_CASE.oracle"
  for JSON_REV in base head; do
    taskset -c "$JSON_CPU" valgrind --tool=callgrind --error-exitcode=99 \
      --callgrind-out-file="$JSON_OUT/$JSON_CASE.$JSON_REV.callgrind" \
      "$JSON_OUT/$JSON_REV" "$JSON_CASE" 3000 \
      > "$JSON_OUT/$JSON_CASE.$JSON_REV.out" 2> "$JSON_OUT/$JSON_CASE.$JSON_REV.log"
    cmp "$JSON_OUT/$JSON_CASE.oracle" "$JSON_OUT/$JSON_CASE.$JSON_REV.out"
  done
done
```

Record both commit/tree IDs, input SHA-256, toolchain, CPU, flags and output agreement.
Callgrind totals include process startup, the untimed validation load and printing;
compare identical commands and use per-function attribution to locate the change.
For wall time, run outside Valgrind, warm each side, alternate order over several
pairs and retain ranges; shared-host timing differences can be inconclusive. Check
warm JIT separately and keep compilation/cache setup outside loop-time claims.

Use [the LLVM call inventory](../../docs/performance.md#inspecting-emitted-llvm-calls)
to explain the profile: emit raw IR with each revision, inventory both with the same
`tools/ir_cost_report.py`, then inspect the actual linked/optimized AOT IR where
inlining matters. Static call counts locate candidate work; only the paired executed
profiles establish instruction savings. Retain the broader
[pyperformance JSON workload](../pyperformance/json_loads.py) alongside these controls.

### Actual Any-result decoding

[`json_decode_any32.py`](json_decode_any32.py) uses the **same input bytes** as
`json_decode.py` for `numeric`, `strings` and `mixed`, but every timed load is
assigned to `Any`. Each iteration consumes the dictionary length and a field
(including a nested field for `mixed`); a checksum is checked before the complete
final value is printed. The benchmark unit tests reject a corrupt intermediate
result even when the final result is correct, and keep both fixtures identical.

```sh
python3.13 bench/smoke/json_decode_any32.py numeric 3000
./pystachy run bench/smoke/json_decode_any32.py mixed 2
./pystachy build bench/smoke/json_decode_any32.py -o build/json_decode_any32
build/json_decode_any32 strings 3000
```

The default is `numeric 3000`; counts must be positive. Use the paired procedure
above with `JSON_INPUT` pointing to this file. Both 32-key controls are retained
replacements, not a reconstruction of the unavailable historical 124M input.
Keep the actual alpha.3 tag (`f5a09d42`) separate from the historical post-tag
baseline (`dcdc1a28`) when comparing results.

The standalone [Any-result JSON decoder control](json_decode_any.py) parses a short mixed
object into an `Any` result on every iteration and accumulates an integer field. Its
nested arrays/object, strings, float, bool, null and escaped Unicode exercise the actual
boxed decoder. The full final value and checksum must match CPython before timings are
compared. The document is shorter than 256 bytes, so cursor values remain within the
small-integer cache; this makes extra scanner dispatch visible without large cursor-box
allocation savings masking it. This is distinct from pyperformance's discarded-result
loop, which Pystachy compiles through typed `JSONValue` decoding.

```sh
python3.13 bench/smoke/json_decode_any.py 20
./pystachy run bench/smoke/json_decode_any.py 20
./pystachy build bench/smoke/json_decode_any.py -o build/json_decode_any
build/json_decode_any 20000
valgrind --tool=callgrind --callgrind-out-file=build/json_decode_any.callgrind build/json_decode_any 2000
```

The optional argument is a positive iteration count (default 20,000); stdout is deterministic
and stderr measures the loop, checksum assertion and final stdout print in seconds.
Interleave pinned-core baseline/candidate
runs and keep JIT startup separate. The control is intentionally standalone, not an added
CI timing threshold or an entry in `perf_smoke.py`'s default matrix.

<a id="release-candidate-counts"></a>

### alpha.3 to alpha.4

All eight controls execute fewer instructions under v0.1.0-alpha.4 than under alpha.3, and
every output matches CPython. These are whole-process AOT counts under Callgrind, measured on
2 November 2026 on main `ec442a20`, whose code the alpha.4 tag shares:

| Control | alpha.3 | alpha.4 | Change |
|---|---:|---:|---:|
| Broad (`json_loads.py 300`) | 1,300.4M | 1,296.2M | −0.32% |
| Typed 32-key numeric / strings / mixed | 91.5M / 108.7M / 127.4M | 91.0M / 107.1M / 126.8M | −0.47% / −1.44% / −0.42% |
| Short observed `Any` (`json_decode_any.py 2000`) | 30.0M | 29.9M | −0.29% |
| Observed `Any` 32-key numeric / strings / mixed | 106.8M / 117.0M / 142.8M | 103.1M / 116.7M / 141.1M | −3.50% / −0.27% / −1.14% |

- **The byte scanner's regression is gone.** On an earlier alpha.4 candidate,
  [#1004](https://github.com/den-run-ai/pystachy/pull/1004)'s scanner raised the broad control
  by 9.85%: keys and strings just past the 16-byte scalar prefix paid for a scanner call.
  [#1028](https://github.com/den-run-ai/pystachy/pull/1028) keeps object keys, and the strings
  of texts up to 1 KiB, in a scalar loop; longer string values still use the scanner after
  their first 32 bytes.
- **Work that only Valgrind causes is left out.** Under Valgrind, the runtime's stack-bounds
  lookup ([#1026](https://github.com/den-run-ai/pystachy/pull/1026)) can fall back to glibc's
  parse of `/proc/self/maps`, about 110,000 instructions once per process, which a native run
  never makes.
- **Data.** The [results file](results/json-controls-2026-11-02.json) keeps these counts under
  `release_candidate`, with the earlier candidate's counts, a bisect and per-function
  attribution of #1004's regression, and nine wall-time pairs that could not resolve it.
