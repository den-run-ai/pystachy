# Bounded process worker measurements

Linux x86-64, LLVM 18.1.3, CPython 3.13.16, eight-CPU quota. Each local
scheduler policy used the same four-core affinity set (CPUs 0-3), identical work,
and three interleaved samples. This was a shared host. Resource measurements are
whole process-tree observations; memory is sampled and can miss brief peaks.

| Workload | One worker | Four workers | Wall speedup | Total CPU, 1 / 4 | Aggregate RSS, 1 / 4 |
|---|---:|---:|---:|---:|---:|
| JSON repair, 76,800 records | 1.195 s | 0.566 s | 2.11x | 1.185 / 1.370 CPU-s | 50.3 / 154.0 MiB |
| Byte BPE, 8 independent batches | 0.571 s | 0.250 s | 2.29x | 0.560 / 0.563 CPU-s | 50.3 / 153.7 MiB |
| Compiler backend, same four partitions | 43.413 s | 16.016 s | 2.71x | 47.808 / 47.459 CPU-s | 365.7 / 709.9 MiB |

The compiler comparison holds **all four early-split bitcode inputs fixed**. It
measures scheduling, not ordinary whole-module O2 versus early splitting, and
excludes frontend, runtime preparation and complete bootstrap. Every one of the
nine rebuilt compiler binaries has SHA256 `b354b1ccbebad3f44bbd8a0593ce2c3f92d46c2456d0cdb26b195c91bbea02eb`
and size 4,892,728 bytes. One of those byte-identical executables
reproduced both full compiler and runtime IR witnesses exactly. This does not
establish equal generated-code quality versus ordinary O2 or ThinLTO.

At four workers, warm object-cache backend median is
**3.884 seconds**, including splitting, cache
validation/copies and final linking. Median CPU is
5.172 CPU-seconds. The remaining serial split
still runs: stable partition caching and identities are subsequent work. "Cold"
here means fresh object-cache entries; filesystem/toolchain pages can be warm.

Application timings include the CPython coordinator, fresh native process
startup, file I/O, allocation, parsing, encoding/decoding and, for BPE, model
training inside each process. Compilation and the complete CPython output oracle
are preparation, recorded separately. The JSON workload is eight files x 32
records x 300 rounds. BPE is eight distinct 16-line corpora x 200 encoding/decoding
rounds, with a small 260-token model trained once per job. It reuses #1107's port
at the source hashes in the report. These are batch-throughput observations, not
interactive-request latency or production workload distributions.

All 36 application campaign executions (nine each for coarse JSON, coarse BPE,
tiny JSON and tiny BPE) check every complete job output against adapted CPython.
Each execution has eight jobs. Tiny controls take roughly 58-93 ms per eight-job
batch across worker counts: coordinator/startup/polling overhead dominates. This
does not establish that distributing tiny work is useful compared with keeping
it in one existing process.

## Detached transport pilot

The JSON pilot copied the three worker support modules into **two separate local
endpoint directories**, then transferred the native executable and input bytes
into a fresh job directory on every request. Three cold/warm pairs passed all
48 output checks; every warm response was a verified cache hit.

Two-client median: cold 1.200 s,
warm 0.526 s. The comparable direct two-process
JSON cohort median is 0.754 s, so this pilot shows
transport/identity overhead rather than a remote-execution win. These cohorts
were separate: do not subtract their medians as a controlled network cost.
Only one physical host was available. No SSH network, queueing service, two-host
speedup, fleet-wide admission daemon or remote ThinLTO importing was tested.

A second detached pilot transferred the same four compiler bitcode partitions
to two local endpoints. Each endpoint ran the registered LLVM 18 optimizer and
code generator in a fresh directory. **All eight cold/warm object responses
matched their local counterparts byte for byte**, and the final linked compiler
matched the nine local builds above. One cold/warm pair took 21.292 / 1.138 seconds
for the worker campaign; final linking is recorded separately. The cold run used
40.957 CPU-seconds and 447.0 MiB sampled aggregate RSS; the warm run used
2.258 CPU-seconds and 126.4 MiB. This is protocol correctness evidence with two
in-flight jobs, not a repeated remote speedup comparison or a two-host test.

## Evidence and preparation failures

- [Compiler backend, raw samples and source inventory](backend-matrix.json)
- [Coarse JSON](json-coarse.json), [coarse byte BPE](bpe-coarse.json)
- [Tiny JSON](json-tiny.json), [tiny byte BPE](bpe-tiny.json)
- [Detached JSON endpoints](remote-json.json)
- [Detached compiler backend endpoints](remote-backend.json)
- [Successful native preparation](preparation-final.json)

Initial JSON preparation used the package directory rather than its parent
(`ports`) and then needed `list[Any]` to match the existing recursive JSON value
API. Both failed attempts are retained in [setup](preparation.json) and
[annotation correction](preparation-corrected.json); neither produced a timed
sample. An initial ordinary-object worker probe exposed an unnecessary `ld.lld`
requirement in the inherited harness. The available LLVM18 toolchain lacks LLD;
the worker now requires it only for the LTO mode, with an explicit rejection if
that mode is requested. No mismatched LLVM linker was substituted.

These results do not rerun the mypyc/CPython compiler-host comparison. The source
preparation mismatch identified in #1091 remains a reason for a separate controlled
host comparison. No historical speedups are added to these measurements.

The raw reports identify every measured source file by hash. After timing, a
linker CPU-budget correction capped the optional full-LTO thread setting; the
measured standalone-object path is unchanged. Application manifest validation
was also tightened after its timing runs. These follow-ups have deterministic
regression coverage; the timing sweeps were not repeated for those changes.
