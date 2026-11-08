# Compiler completion dogfood

`compiler_batch.py` is an optional CPython coordinator for independent compiler
IR/AOT jobs. It drains diagnostic pipes while compilers run, bounds admitted jobs
and diagnostic bytes, writes large artifacts directly to files, and delivers
at most one 4096-byte ASCII JSON completion record at a time. Completed jobs still
occupy their admission slot until the record is acknowledged. Every child has a
private process group; failure/deadline cleanup kills owned groups and reaps direct
children. Admission allows one or two compiler jobs. The per-job timeout must be
finite, positive and at most 900 seconds (default 120), including completion
acknowledgment. Invalid CLI limits fail before validation work or output creation.
Record construction, transfer and decoding count toward the deadline. The
coordinator rechecks all active jobs after constructing records and immediately
before accepting an acknowledgment or admitting queued work. Synchronous work
such as artifact hashing can delay noticing a timeout, but cannot turn an expired
completion into success.
During `run_batch`, SIGINT/SIGTERM request cancellation at safe points,
including immediately after each child is registered. Cleanup finishes before
`SystemExit(128 + signal number)` propagates (130 for SIGINT, 143 for SIGTERM);
repeated signals cannot interrupt cleanup. This POSIX coordinator runs on the
main thread and restores the caller's signal handlers on return or failure.
Workers and the persistent handler must stay in their assigned process groups.
SIGKILL, descendants that create another session/group, and the benchmark's
separate CPython/AOT validation subprocesses are outside this cancellation scope.

After the final acknowledgment, the coordinator closes handler stdin and keeps
both output pipes nonblocking until EOF and child exit. Handler stderr shares one
`diagnostic_limit` budget across acknowledgments and shutdown; trailing stdout
remains bounded to 4096 bytes. Extra output, diagnostics and nonzero exits fail the
batch. Shutdown has a separate deadline of `min(timeout, 5)` seconds, including
handlers that close their output pipes before exiting.

`record_worker.py` is a persistent consumer compiled without source changes by
Pystachy or mypyc. Its context owns each record until copy completion and explicit
acknowledgment. The worker checks identity, status and exact bytes before echoing
the record. This tests the local API inside a real compiler workflow; the pipes,
process lifecycle and scheduler are CPython/OS facilities. It does not implement
a transport backend, native process spawning, or reuse the experimental runtime
changes in #1135. The broader scheduler in #1133 remains a separate draft.

## Run

Use the build and environment setup in [README](README.md). Then:

```sh
./pystachy build examples/comm/record_worker.py -o build/comm/record_worker
python3.13 examples/comm/compiler_batch.py --directory build/comm/batch-native \
  --transport handler --handler-command '["./build/comm/record_worker"]' --samples 5
```

Every directory must be new. The benchmark interleaves serial/direct,
two-worker/direct and two-worker/handler runs after one warmup of each. It checks
IR byte equality, compiler statuses/diagnostics, and AOT output against CPython.
Use `--transport comm` to handle records inside the CPython coordinator, or supply
a CPython/mypyc handler command. `--compiler-command` accepts a JSON argv to test
a hosted compiler. The report records all samples, completion order, admission,
source/binary hashes, affinity and relevant environment settings.

Before measurement, a fresh hosted loader process resolves each workload's imports
without executing workload code. The input manifest groups file hashes, per-workload
resolution probes and relevant environment settings. It includes untracked and
ignored transitive imports, packages, relative and namespace imports, and the
ordered source-directory/`PYSTACHY_PATH`/compiler-library search path. The same
capture runs after measurement; differences in source bytes, resolved symlinks,
search choices or environment settings reject the report. Existing compiler diagnostics
are retained when import discovery fails.

The native or hosted compiler under test must use this checkout's loader semantics;
this preflight does not introspect an unrelated compiler binary. Direct native,
`python FILE.py` and `python -m pystachy` commands use the driver's library-home
rules. Set `PYSTACHY_HOME` explicitly for other interpreter or wrapper command
forms, whose effective compiler entry point cannot be inferred safely. A nonempty
`PYTHONSAFEPATH` also requires an explicit home for `python -m pystachy`, because
module lookup can select a compiler on `PYTHONPATH` instead of this checkout. Relative
compiler search paths are resolved from the repository root, where compiler jobs
run. The separate CPython output oracle uses CPython's ordinary import path, so
workloads found only through `PYSTACHY_PATH` also need an appropriate `PYTHONPATH`
for that oracle.

Local API timings are separate from compiler throughput:

```sh
./pystachy build examples/comm/bench_workload.py -o build/comm/bench_workload
python3.13 examples/comm/benchmark.py --native build/comm/bench_workload \
  --library build/comm/libpystachy_comm.so --cpu 0 --report build/comm/local.json
```

These measure 256-byte record ownership/copy/completion, and two-rank float64 sum
with one rank copied back to Python. They are not a NumPy/BLAS or distributed
scoring comparison. All variants call the same C backend; the CPython twin builds
ctypes arrays and copies lists back, while native Pystachy passes native arrays.
Consequently a large local API speedup can mainly reflect bridge overhead.

## mypyc

```sh
python3.13 examples/comm/mypyc_check.py --build-dir build/comm/mypyc \
  --split-wrapper --probe-unchanged-wrapper
```

This optional check requires mypyc and setuptools, verifies extension-module
origins, and checks the same ownership, numerical and record consumers. The
ordinary mode compiles unchanged consumers while interpreting `comm.py` and the
CPython FFI twin. The split mode keeps only the annotation-inspecting `@extern`
declarations interpreted and compiles the rest of the wrapper too.

Compiling the entire unchanged wrapper currently loses annotations consumed by
`ffi.extern`, producing `KeyError: 'return'` during import. The harness records
that failed mode rather than presenting compilation alone as success. Neither
successful mode is Python-free or a native mypyc-to-C communication backend.

## Compatibility and limits

- The custom API's ordinary IEEE additions follow source/rank order. It matches
  an explicit CPython addition loop, not compensated `sum()` for all inputs:
  `[1e16, 1.0, -1e16]` gives `0.0`, whereas CPython 3.13 `sum()` gives `1.0`.
- Handles/tags and native integers are signed 64-bit; this is not Python's
  arbitrary-precision integer model. Views are contiguous owned allocations,
  not Python's general buffer protocol or zero-copy NumPy imports.
- Inputs and destinations remain leased until acknowledgment, even when terminal.
  Cancellation only cancels queued local operations; compiler-process cancellation
  belongs to the coordinator and is tested separately.
- Pystachy currently rejects `readline(size)`. The shared worker uses bounded
  `read(1)` calls instead. Live-pipe validation additionally exposed the native
  text reader waiting for an extra character; the regression requires a complete
  record to be acknowledged while the input pipe stays open.
- Linux x86-64 is the tested platform. Windows/macOS process handling, remote
  transport, device buffers, shared memory and threaded contexts remain untested.

Tests do not impose timing thresholds. Report platform, exact input identity,
cache warmth, compiler build flags, startup and runtime separately; shared-host
small timing differences are inconclusive.

## Measured results — November 7, 2026

Linux x86-64, AMD EPYC 9V74, CPython 3.13.16, LLVM 18.1.3 and mypyc 2.4.0.
Compiler batches used two pinned CPUs; local API samples used one. Each table
entry is a median of five rotated samples after one warmup per variant, with no
other owned builds running. The shared host still produced occasional outliers.
Worker AOT builds are excluded; handler process startup is included in batches.

Each batch compiles the two checked-in harness-generated programs to IR and AOT
(four jobs). Every run validates statuses/diagnostics, exact IR and AOT output
against CPython. Each row has its own interleaved direct baselines:

| Completion handling | Serial direct | Two workers direct | Two workers with feature |
|---|---:|---:|---:|
| [Native persistent worker](results/compiler-native.json) | 604 ms | 312 ms | 346 ms |
| [CPython persistent worker](results/compiler-cpython.json) | 601 ms | 311 ms | 353 ms |
| [mypyc persistent consumer](results/compiler-mypyc.json) | 606 ms | 320 ms | 335 ms |
| [CPython in-process API](results/compiler-inline.json) | 610 ms | 318 ms | 328 ms |

Two workers with completion handling improve elapsed time **1.70–1.86x** versus
serial. The separate handler process adds roughly 5–14% to the direct two-worker
medians here; in-process handling adds 3.4%, within the observed spread. These
samples do not establish an end-to-end advantage for compiling the handler.
Use in-process completion handling for this small-record workflow unless a
separate native consumer is needed for other work.

The [local API benchmark](results/local-api.json), excluding imports/startup:

| Workload | CPython | Pystachy AOT | mypyc consumer |
|---|---:|---:|---:|
| 5,000 owned 256-byte records | 296 ms | 6.62 ms | 299 ms |
| 100 two-rank reductions, 4,096 doubles/rank | 84.5 ms | 4.40 ms | 84.4 ms |
| 20 two-rank reductions, 65,536 doubles/rank | 301 ms | 13.2 ms | 301 ms |

The native bridge is much cheaper (about 45x for the small record calls), but
CPython/mypyc use the ctypes twin and the same C collectives. This is bridge/API
cost, not a claim of a faster collective algorithm or faster numerical scoring.

[Whole-compiler mypyc validation](mypyc_compiler.md) compiles all 55 unchanged
compiler modules and reproduces full self-compiler IR exactly. It also runs
[real IR/AOT batches through the native completion worker](results/compiler-full-mypyc.json).
That compiler was built at `-O0` to bound memory; its timings are compatibility
evidence, not an optimized mypyc performance comparison.

Additional validation: [CPython/JIT/AOT and GC-stress parity plus 300 ASan/UBSan
ownership cycles](results/comm-validation.json), [both mypyc feature modes and
the unchanged-wrapper failure](results/mypyc-feature.json), and a [real compiler
syntax rejection](results/compiler-failure.json). Fresh compiler/runtime fixed
points, 138 I/O differential checks, 35 communication harness controls, six
multi-mode live-pipe tests, file ownership/GC probes, workflow-budget checks and
lint pass. The open-pipe runtime correction is tracked separately in #1151.

Full local repository verification, optimized full-compiler mypyc measurements,
LeakSanitizer and non-Linux execution remain unrun. No draft is merged by this
evaluation. Result files retain all samples and input hashes; the duplicate
after-run hash map is replaced by `inputs_verified_unchanged` only after equality
was checked when preserving reports.
