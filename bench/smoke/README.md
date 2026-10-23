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
The general `fannkuch` and `nbody` proxies are replaced by these more relevant cases.

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
loops are long enough to exercise the existing 5 ms warning floor. The paired harness
records timing; peak RSS and retained-memory costs require separate measurements.

`graph_copy` retains the graph-processing workload that exposed #821's historical
regression, tracked in #780. Its `jit_loop_s` and `aot_loop_s` use `process_time_ns`
around deep-copy plus checksum processing; the other cases use `perf_counter` wall time.
Each result records `loop_clock` so these clocks remain distinguishable. Whole-process
times still include graph construction and startup. The original `graph` mode retains
its checksum/construction-nanoseconds/processing-nanoseconds output for historical replay.
