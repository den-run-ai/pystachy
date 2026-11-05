# Bootstrap pipeline experiment

This research builds on the [compiler-parallelism experiment](../compiler_parallel/README.md).
It measures a complete hosted-to-native bootstrap, including two native executable
builds and three independent compiler/runtime IR witnesses. The ordinary `make`
bootstrap, compiler defaults and CI matrix are unchanged.

## Measurements and recommendation

The preferred next candidate retains the original backend: keep build IR, build
the temporary first compiler at O0, reuse C-runtime bitcode, and allow two controller
jobs with one slot per build. One exploratory run took **139.527 seconds**, 41.1%
less than the two-run baseline median, and produced a final compiler **byte-identical
to both baseline binaries** (`f22ac677341a10eecda4356b66329d51277ec9eea17cd4bf06e8c2c29d689502`).
Repeat this candidate before adopting it as a default.

All seven bootstraps passed the compiler and runtime IR fixed points and built both
native executables. Measurements used Linux x86-64, AMD EPYC 9V74, an eight-CPU
cgroup quota, an 8 GiB memory limit, CPython 3.13.16 and LLVM 18.1.3. Each run started
with a fresh private runtime cache. Compiler/library source inventory
`8a210360088f96bd19c0a05bec43c00c8985e7cc426d95438e6c1cc045db9c30`
and tool identities match across runs; recorded Git states differ only through
documentation/test work. See [raw reports](results/linux-llvm18.json),
[summary](results/summary.csv) and [compiler execution witness](results/compiler-witness.json).

| Variant | Runs | Wall seconds | Child CPU seconds | Wall reduction |
|---|---:|---:|---:|---:|
| Serial baseline, both stages O2 | 2 | 236.859 | 236.390 | — |
| Retained IR only, serial O2 | 1 | 194.263 | 193.899 | 18.0% |
| **Retained IR + O0 first stage + C cache; original backend, two jobs** | **1** | **139.527** | **139.887** | **41.1%** |
| Retained IR + O1 first stage + C cache + four LTO partitions | 1 | 153.873 | 197.286 | 35.0% |
| Retained IR + O0 first stage + C cache + four LTO partitions | 2 | 123.301 | 148.980 | 47.9% |

Two-run rows show medians; single-run rows are exploratory observations. Baseline
wall samples were 231.939/241.779 seconds; O0/LTO4 samples were 123.400/123.202
seconds. The latter combination reduced median wall time by 47.9% and child CPU
by 37.0%. This combines less repeated work, a cheaper temporary compiler, cache
reuse and backend scheduling; it is not an isolated threading speedup. The retained-IR
control isolates duplicate frontend work, but has only one sample. Full bootstrap
runs were not CPU-pinned, and shared-host noise and an unflushed OS page cache remain.

LTO4 changes the final compiler. Five interleaved pairs of `ir pystachy.py`, pinned
to CPU 0, produced matching IR but CPU medians of 5.658 seconds for the original
backend and 5.905 seconds for LTO4: **4.4% slower** in this small witness. Ranges
overlap (5.528–6.132 versus 5.660–6.287 seconds), so this is a performance concern
requiring more evidence, not a stable regression estimate. LTO4's final binary is
5,522,280 bytes versus 5,242,632 bytes for the original backend. The original-backend
candidate avoids this particular code-generation change and is the recommended
follow-up despite its longer bootstrap.

The largest per-command `wait4` RSS was about 909–921 MiB across these runs.
This does not measure aggregate peak memory when commands overlap.

The original-backend candidate's final native build took 83.56 seconds: program
LLVM optimization took 36.89 seconds, code generation 27.42, and the frontend 9.25.
Typed-IR optimization occupied 0.90 seconds **within** that frontend total. This
supports prioritizing duplicate work and backend cost over function-pass workers
for this self-build. It does not establish the same ranking for other programs.

## Implementation

| Change | Contract |
|---|---|
| Retain build IR | `build FILE.py --emit-ir FILE.ll` atomically publishes the exact frontend IR after successful linking. The witness excludes the build-only `pys_plain` addition. Existing source/output aliases are rejected. |
| Remove duplicate work | The first two builds supply stage-1/stage-2 witnesses; stage 2 separately emits stage-3 IR. Five compiler frontend traversals become three. Both native binaries are still actually compiled. |
| Bounded scheduling | The controller runs independent runtime witnesses alongside eligible builds. Each build reserves its full LLVM/driver budget; witnesses each reserve one slot. Stage 2 still waits for stage 1. |
| Temporary compiler tier | `PYSTACHY_AOT_OPT=0/1/2` selects program LLVM optimization/codegen for `build`, retaining late allocator inlining. The controller applies the chosen tier only to the temporary first compiler; final output uses level 2. |
| Independent C bitcode | `PYSTACHY_RUNTIME_C_CACHE=1` reuses C-runtime bitcode across Pystachy producers. Captured preprocessing includes headers and target macros; tool identities and compile recipe also enter the key. Runtime Python remains compiler-dependent. |

The C cache is limited to Linux with default C flags. Custom flags and sanitizers
retain the existing path. A semantic use of the temporary source path falls back
instead of rewriting C strings. Concurrent misses may duplicate compilation;
private files and atomic publication prevent partial entries. No cache eviction
policy or cross-machine cache transport is provided by this prototype.
Explicit `PYSTACHY_CFLAGS` retain their existing precedence over Clang's codegen
flags; the controller clears inherited settings so its recorded tiers are effective.

## Reproduce

Use CPython 3.13.16 and matching Linux LLVM/Clang/LLD 18.1.3. From a clean checkout:

```sh
python3 tools/bootstrap_pipeline.py --variant baseline --timing \
  --output /tmp/pystachy-bootstrap
python3 tools/bootstrap_pipeline.py --variant retained-ir --timing \
  --output /tmp/pystachy-bootstrap
python3 tools/bootstrap_pipeline.py --variant optimized --jobs 2 --build-jobs 1 \
  --partitions 0 --stage1-opt 0 --runtime-c-cache --timing \
  --output /tmp/pystachy-bootstrap
# Separate backend experiment; assess the rebuilt compiler's execution speed too.
python3 tools/bootstrap_pipeline.py --variant optimized --jobs 4 --build-jobs 4 \
  --partitions 4 --stage1-opt 0 --runtime-c-cache --timing \
  --output /tmp/pystachy-bootstrap
```

`--output` is a parent directory: each invocation creates a fresh private run and
runtime cache underneath it. It prints the final `report.json` path, including on
failure. `--llvm` and `--python` select explicit toolchains. The controller removes
inherited `PYSTACHY_*` settings before applying its recorded options. Do not edit
compiler or library sources during a run, or run other heavy tasks alongside it.

Compare the baseline and retained-IR variants with identical tiers and budgets to
isolate redundant frontend work. Compare other options separately before drawing
attribution from the combined variant. An O0/O1 first compiler can execute more
slowly, so its own build time alone is not an acceptance metric. Four codegen
partitions change generated code and can increase memory or reduce execution speed.

Reports contain source, tool and harness hashes, Git state, commands, exit statuses,
logs, output hashes, CPU/affinity/quota/load, and timings. `wall_seconds` covers
controller setup, scheduled work and final verification; their separate timings
are also recorded. CPU is the sum for child command trees, excluding controller
work. `largest_command_max_rss_bytes` is the maximum `wait4` value for one command,
not aggregate memory for concurrent jobs. The operating-system page cache is not
flushed. Stage timers nested inside command logs must not be added twice.

## Validation

On the same compiler-source inventory as the measurements:

- `make check-fast lint` passed, including 10 scheduler controls; workflow-limit
  controls passed all 14 cases. No CI jobs were added.
- Real LLVM driver controls passed under the rebuilt-native compiler:
  10 driver tests and five C-cache tests, including all optional integrations.
- `tools/check_compiler_parallel.py --compiler "$compiler" --lto` passed four
  failure-order cases, snapshot parity and six native build variants, each checked
  against CPython with ordinary and every-allocation GC.
- `PYSTACHY_HOME="$PWD" PYSTACHY_JOBS=2 tools/irsame.sh "$parent_compiler" "$compiler"`
  passed all 4,238 IR/diagnostic/status comparisons against the #1089 compiler.
  A common home is valid here because runtime/library inputs are byte-identical.
- The compiler execution comparator's negative control rejects a successful exit
  that fails to write fresh IR, instead of accepting a previous invocation's file.
- `make test-cache` passed 66 native and 68 hosted assertions, including forced
  termination and recovery. For this sandbox's mismatched PID namespaces, a local
  `ps` adapter mapped only the suite's `comm`/`ppid` queries through `/proc`'s
  `NSpid` field; a control confirmed its parent lookup against `os.getppid()`.
  The repository test script and its assertions were unchanged.

Full local `make verify` and macOS were not run; PR CI is separate from this local
evidence. These remain research results, not merge-readiness certification.

The controller fails on any unsuccessful command, missing/empty/mismatched witness,
or changed source inventory. Each run independently generates three compiler IR
witnesses and three runtime IR witnesses. Retaining an IR artifact does not replace
either native executable build with a cached binary.

Unit controls use a deliberately fallible compiler to check producer identities,
worker budgets, real overlap, missing/mismatched outputs, source mutation, timeouts,
launch-time cancellation and descendant cleanup. Driver integration controls exercise
ordinary/LTO builds at all three tiers against a CPython oracle; cache controls count
actual C compilations across producer changes, header changes and failed builds.
The optional real-tool tests require the environment variables documented in their
test modules. They are distinct from the lightweight checks in `make check-fast`.

After selecting a rebuilt compiler from a completed run:

```sh
PYSTACHY_TEST_LLVM="$PYSTACHY_LLVM" PYSTACHY_TEST_COMPILER="$compiler" \
  python3 -m unittest discover -s tools -p test_self_build_driver.py
PYSTACHY_CACHE_TEST_LLVM="$PYSTACHY_LLVM" PYSTACHY_CACHE_TEST_COMPILER="$compiler" \
  python3 -m unittest discover -s tools -p test_runtime_c_cache.py
```

## Limits and next boundaries

This does not parallelize whole-module LLVM optimization, semantic discovery or
typed-IR passes. It does not overlap the entire cold runtime build with the program
frontend. That needs an earlier isolated runtime-preparation boundary and preserved
diagnostic ordering; launching duplicate builds without a rendezvous is not enough.

Full-LTO partitions still follow serial LLVM optimization. Module/SCC partitioning,
ThinLTO, remote backend workers and shared artifact caches need stable symbol/import
ownership and correct handling of the late allocator-inlining phase. Independent
architecture/test jobs can already be distributed; doing so does not remove the
stage-1-to-stage-2 dependency of one bootstrap. No general shared-heap threading or
language-level concurrency feature is introduced here.

The separate historical-regression question needs a frozen input compared across
old/new compiler executables on one host. These variants compare the same source
checkpoint and do not establish a recent main-branch regression.
