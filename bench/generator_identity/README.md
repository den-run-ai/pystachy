# Numeric generator identity costs

`score.py` streams deterministic rewards for synthetic trajectory errors, then
accumulates a total, second moment and threshold count. Its `typed` mode consumes
raw float yields; `observed` passes the generator through `Any`, so each yielded
object becomes observable. The `typed-alias` and `observed-alias` controls repeatedly
yield one source number. All modes remain executable with CPython.

From the repository root:

```sh
python3.13 bench/generator_identity/score.py typed 100000 5
./pystachy build bench/generator_identity/score.py -o /tmp/generator-score
/tmp/generator-score typed 100000 5
/tmp/generator-score observed 100000 5
/tmp/generator-score typed-alias 100000 5
/tmp/generator-score observed-alias 100000 5
```

Each output line contains a checksum and the in-process duration in seconds.
Compare checksums with CPython before interpreting timings. Use separate processes,
interleave baseline/candidate order, and report build, whole-process JIT startup
and steady execution separately. The fresh-expression control must not be used to
claim that yielding an existing local or copying a default avoids boxing.

For deterministic allocation counts, build separate AOT binaries with
`PYSTACHY_CFLAGS=-DPYSTACHY_PROFILE_DATA` and private `PYSTACHY_CACHE` directories.
The `pystachy-data` stderr record reports C allocation requests, requested bytes and
managed-heap peak. These counters exclude foreign allocations and are not live
memory or RSS. Keep their instrumented timings separate from ordinary timings.
Ordinary no-Any and isolated nontracking generator IR are structural controls.

## Allocation qualification

Linux x86-64, CPython 3.13.16, LLVM 18.1.3; one instrumented AOT process per row,
three repetitions of 20,000 scores. Every checksum matched CPython. The baseline
is main `5f81cc25`; the eager implementation is `e0f17211` (the initial #1486).
The companion implementation uses the code accompanying this workload.

| Consumer | Main allocation requests | Eager yields | Nullable companions |
| --- | ---: | ---: | ---: |
| Typed, fresh expression | 21 | 60,021 | 21 |
| Any, fresh expression | 60,027 | 60,027 | 60,027 |
| Typed, repeated source alias | 21 | 24 | 24 |
| Any, repeated source alias | 60,027 | 30 | 30 |

Fresh typed consumption returns to the baseline allocation count; actual dynamic
observers still materialize objects. Repeated source aliases need one canonical
box per generator invocation. Main's repeated-Any case allocates new boxes because
it loses the source identity; it is a negative control, not equivalent semantics.
For the typed fresh case, managed-heap peaks were 393,216 / 1,310,720 / 393,216
bytes, respectively. Requested bytes include coroutine storage and formatted output
and are not a reachable-memory census.

Five interleaved uninstrumented processes per mode, each with five samples of
200,000 scores, were pinned to one CPU during other qualification work. Median
in-process AOT durations (main / eager / companion) were 11.37 / 12.81 / 9.80 ms
for typed fresh scores and 12.57 / 12.24 / 12.89 ms for actual Any observation.
These shared-host timings establish no general speedup. Warm CPython-hosted AOT
builds took 1.79 / 1.71 / 1.79 s; whole-process CPython-hosted JIT runs of 20,000
scores took 0.258 / 0.267 / 0.315 s. Startup is distinct from steady execution and
remains a cost to qualify; instrumented durations were excluded.

Reproduce each row by building the three source revisions with the flags above,
then running the corresponding mode with arguments `20000 3`. The structural
`tools/test_typed_generator_identity.py` control checks that a fresh-expression
producer has no numeric boxing calls and fails when eager boxing is restored.
