# Compiler optimization follow-up

Linux x86-64, 2026-11-06. This continues the [original host and worker experiment](README.md)
in draft PR #1091. It implements the allocator-routing fix, makes the receiver
overlay portable between mypyc and native Pystachy, and measures complete
bootstraps with bounded LLVM workers. Early splitting remains opt-in.

[Published revision equivalents](PUBLISHED_REVISIONS.md) map the local commit
IDs retained in the measurements to publicly checkable commits with identical trees.

## Decisions

- Use an actual allocator declaration to select the allocator-specific backend.
  The previous substring test matched LLVM text embedded in compiler strings.
- Retain the ordinary whole-module O2 final compiler by default. Splitting only
  the temporary compiler offers a modest gain after #1090's cheap-stage-1 work.
- Offer splitting of both bootstrap builds as an explicit development experiment;
  measure the resulting compiler's execution speed as well as build latency.
- Keep the fast mypyc receiver types in a preparation overlay that also self-hosts
  natively. This does not establish complete native mypy or mypyc support.
- Give local workers owned process groups, bounded cleanup, fail-fast scheduling,
  and explicit optimization levels before adding remote execution.

## Allocator routing: remove the false positive at its source

The frozen compiler IR contains three `@pys_new(` substrings, all inside LLVM
string constants. There is no allocator declaration or call in this input even
before LLVM optimization. The old driver therefore selected a separate
optimization, late-inline and code-generation pipeline unnecessarily. The earlier
report's observation that O2 output had no allocator was correct, but it did not
identify this earlier cause.

`lower_module.uses_new_allocator()` now obtains the exact declaration line from
the compiler's runtime-declaration producer. Genuine allocator users retain the
existing late-inline contract. The false-positive case returns to the driver's
ordinary combined optimization/code-generation path, avoiding both the late pass
and intermediate bitcode round trips. Tests cover embedded text, the actual
producer, declaration placement, and function/call-site `alwaysinline` behavior.

The paired frozen-input replay is recorded in
[allocator-routing.json](results/allocator-routing.json). Both routes must
produce byte-identical objects and executables. This is one paired timing
observation; equality is a stronger conclusion here than timing repeatability.
The ordinary route took 64.61 s versus 64.24 s for the staged route (64.58 versus
64.20 CPU-s). The separate late-inline command took 3.03 s, but these end-to-end
measurements do **not** establish a net speedup from returning to ordinary
codegen. Removing a timed stage is not automatically an equal wall-time saving.

An initially considered shortcut based only on the absence of the `pys_new`
symbol was rejected: other `alwaysinline` functions or call sites can still make
the late pass meaningful. No general symbol-absence shortcut was added.

## Complete bootstrap measurements

Every successful run performs two real native compiler builds, retains the first
two compiler IR witnesses, independently emits the final compiler witness, and
checks three runtime witnesses. Fresh caches, the same source, the same LLVM
tools, and CPU affinity 0-3 are used for every policy. Timings include controllers,
runtime preparation, linking, cache trust waits, and all six witnesses. Total CPU
and sampled aggregate process-tree RSS accompany wall time.
Split profiles also perform timed tiny builds to prepare the runtime; their cost
is included and their commands are recorded.

The initial one-run policy probes are preserved in
[bootstrap-stage1-probes.json](results/bootstrap-stage1-probes.json):

| Temporary compiler / final backend | Full bootstrap | Total CPU | Peak aggregate RSS |
|---|---:|---:|---:|
| Ordinary O0 / ordinary O2 | 134.94 s | 136.02 CPU-s | 924 MiB |
| Split four ways at O0 / ordinary O2 | 130.12 s | 149.06 CPU-s | 924 MiB |
| Split four ways at O2 / ordinary O2 | 135.25 s | 184.26 CPU-s | 1,485 MiB |

All three final executables are byte-identical. Splitting the cheap temporary
compiler saved only 3.6% in this single observation; optimizing that split
temporary compiler more heavily erased the saving. Backend-only speedups cannot
be applied directly to an already optimized complete bootstrap.

The [repeated complete-bootstrap experiment](results/bootstrap-fast.json) has
three interleaved runs per policy:

| Bootstrap policy | Median wall time (range) | Median total CPU | Median peak aggregate RSS |
|---|---:|---:|---:|
| Ordinary O0 temporary / ordinary O2 final | 133.44 s (132.66-133.56) | 134.44 CPU-s | 924 MiB |
| Split-four O0 temporary / split-four O2 final, overlap | 79.70 s (79.06-80.67) | 134.00 CPU-s | 934 MiB |

That is **40.3% less complete-bootstrap time, or 1.67x speedup**. Total CPU is
nearly unchanged and sampled aggregate RSS is about 1% higher. The improvement
combines changed optimization scope, overlap and parallel scheduling; the original
identical-partition experiment remains the measurement of scheduling alone.
All six bootstraps pass all six IR witnesses. Repeated executable bytes are
identical within each policy; the split and ordinary final executables differ,
as expected from their different optimization scope. They are 4,892,096 and
5,242,672 bytes, respectively.
The second compiler build accounts for most of the saving: its median step time
falls from 82.89 to 31.73 s; the first build changes from 44.69 to 41.45 s.
Both policies already contain the allocator-routing correction, so its possible
effect cannot be added again. Whole-bootstrap peak RSS can also hide increased
memory in a smaller phase; the original identical-partition measurements remain
the evidence for backend-worker memory growth.

The seeded order happened to put the split policy first in all three pairs; this
is interleaved, not counterbalanced. Commit metadata spans `91abd724` and the
evidence-only `c20ed941`, while all 145 compiler/runtime/library source hashes,
tool identities and four harness hashes are identical. All 18 compiler and all
18 runtime witnesses agree across policies as well as within each bootstrap.

The [generated-compiler comparison](results/bootstrap-fast-quality.json) uses
five interleaved fresh processes on CPU 0, with the frozen `c20ed941` compiler,
JSON-repair and runtime inputs, before the later allocator-helper relocation.
It also includes a fresh compatible mypyc host built from that same frozen
compiler source; host preparation is recorded
separately in [current-host-preparation.json](results/current-host-preparation.json).

| Prepared compiler host | Self frontend (range) | JSON-repair frontend | Runtime frontend | Self peak RSS |
|---|---:|---:|---:|---:|
| Ordinary native | 5.811 s (5.751-6.224) | 0.259 s | 0.070 s | 905.7 MiB |
| Split native | 6.587 s (6.432-6.778) | 0.288 s | 0.078 s | 897.5 MiB |
| Compatible mypyc, GCC 13.3 O2 | 7.354 s (7.258-7.723) | 0.413 s | 0.136 s | 645.7 MiB |

All **45/45** measured outputs match. The split compiler's self-frontend median
is **13.3% slower**, supporting its use as an explicit development profile while
retaining whole-module O2 for the default final compiler. Ordinary native is
1.27x the compatible mypyc host and uses about 40% more peak RSS on this input.
All 48 mypyc compiler modules load as extensions. These are frontend times,
including startup and IR writing, with preparation and the LLVM backend excluded.

This mypyc host used GCC 13.3 O2, with 22.52 s C generation and 107.13 s C
compilation/linking in one serialized preparation. The earlier portable-versus-
prior overlay pair used Clang 18 O2; their timings must not be combined into a
source-regression or C-toolchain ranking. The small-input RSS floor described in
the original report also applies here.

## LLVM inlining policy: useful headroom, still exploratory

[optimization-tiers.json](results/optimization-tiers.json) uses the original frozen
linked bitcode, one backend build per policy, then five interleaved self-frontend
executions per resulting compiler, pinned to CPU 0. Code generation remains O2.
All eight build witnesses and all twenty measured frontend outputs match exactly.

| LLVM IR optimization policy | Backend | CPU | Sampled peak aggregate RSS | Generated compiler self frontend, median | Executable bytes |
|---|---:|---:|---:|---:|---:|
| O2 | 67.74 s | 67.71 CPU-s | 536 MiB | 5.923 s | 5,242,632 |
| O1 | 57.04 s | 57.01 CPU-s | 526 MiB | 6.128 s | 5,189,912 |
| O2, inline threshold 0 | 36.63 s | 36.59 CPU-s | 350 MiB | 6.717 s | 3,714,520 |
| O2, inline threshold 75 | 46.10 s | 46.09 CPU-s | 408 MiB | 6.072 s | 4,102,680 |

Threshold 75 used about 32% less backend time and produced a roughly 22% smaller
compiler in this probe. Its self-frontend median was 2.5% slower, with overlapping
ranges (5.57-6.60 s versus 5.59-6.79 s). Threshold 0 made a clearer performance
tradeoff: roughly 46% less backend time and a 13% slower median. Backend timings
have only one observation per policy, and these are not complete bootstraps or
application-throughput studies. No new default inlining threshold is justified.

## Receiver typing compatible with both hosts

The preparation overlay still annotates 1,189 helper receivers in 27 modules.
The portable spelling combines a type-only concrete `Gen` import with a runtime
`Any` alias after that block. Three existing non-None invariants use type-only
assertions instead of runtime `typing.cast` expressions. This avoids import
cycles, retains mypyc's static receiver access, and preserves Pystachy's call-site
specialization. Compiler algorithms are unchanged.

Two native generations now compile this overlay and reproduce compiler, overlay,
and runtime IR witnesses. Across five interleaved frontend samples on each of four
frozen inputs, the prior and compatible mypyc hosts produce 40/40 identical
outputs. All 48 compiler modules in each host load as compiled extensions.
Self-frontend medians are 7.403 s for the prior overlay and 7.149 s for the
compatible overlay; ranges overlap. This preserves the typed host's performance,
without establishing an additional speedup. Preparation remains outside frontend
timing.
This receiver-only experiment uses the `30ea5f7` snapshot, whose compiler sources
are unchanged from #1090, with Clang 18.1.3 O2 for mypyc C compilation and CPU 8
for frontend timings.
See the [receiver-specific explanation](receiver_compatibility.md),
[raw evidence](results/receiver-compatible.json), and
[portable overlay](results/receiver-compatible-overlay.diff).

The overlay source itself differs from the ordinary source, and their raw IR is
not required to match. The fixed-point checks compare producers on the same
input. This is a compatible research preparation method, not a wholesale
production receiver-typing migration or a completed mypy port. The existing
component-level support and first-failure probes in the original report remain
the evidence for Pystachy compiling mypy/mypyc components.

## Worker and bootstrap contracts

`backend_workers.py` owns subprocess groups, stops queued work on failure,
handles termination during process creation, and escalates cleanup after a
bounded grace period. Reports retain failed, cancelled and timed-out command
output. Jobs expose O0-O3, defaulting to O2, and continue to bind input, tool,
settings and result hashes. Stale results are removed before replay and results
are merged in deterministic partition order. Nested controllers inherit ownership
instead of creating unmanaged detached subprocess trees.

The bootstrap reserves each build's worker budget before scheduling independent
witnesses. `--stage1-split` and `--stage2-split` are explicit research controls;
`--runtime-overlap` overlaps whole-runtime preparation with the program frontend.
Output paths are checked against sources and producers, publication is atomic,
and source/producer identities are rechecked. Runtime-cache selection requires
one unambiguous prepared artifact rather than choosing the newest file.

Remaining scaling limits are substantial: LLVM partition imbalance, lost
cross-partition optimization, serial splitting/linking, total CPU and memory cost,
and source-loading/inference cost. Finalized function optimization remains only
about half a second on the original native frontend workload. Remote transport,
queue accounting, shared-cache deduplication, retry policy, complete target/sysroot/
shared-library identity, cross-host compatibility and a fleet-wide CPU-plus-memory
budget remain unfinished. Local detached replay is not remote-fleet validation.

## Reproduction and validation

Use CPython 3.13.16 and LLVM/Clang/LLD 18.1.3, with the matching LLVM shared-library
directory available to the loader. The snapshot used by both new backend probes
is a retained output of `self_pipeline.py`; its linked bitcode SHA-256 is
`3126c90b8bb6e2f841e1752ce7e1d786f3b7ddc40f160a07a4cf080789fbcdb1`.
Each command requires a new work directory. Raw reports retain commands, hashes,
tool versions, individual samples and failures. The machine is the same EPYC
9V74 container with eight CPUs of quota and an 8 GiB memory cap; it is not a
dedicated physical benchmark machine.

```sh
taskset -c 0-3 python bench/compiler_host/allocator_routing.py \
  --snapshot "$SNAPSHOT" --llvm "$LLVM" --work "$WORK/allocator" \
  --report "$WORK/allocator.json" --samples 1
python bench/compiler_host/bootstrap_followup.py --llvm "$LLVM" \
  --work "$WORK/bootstrap" --report "$WORK/bootstrap.json" --samples 3 \
  --variant driver-o0 --variant split-both --cpus 0-3
python bench/compiler_host/receiver_compatibility.py --seed "$SEED" \
  --llvm "$LLVM" --input-root "$FROZEN" --work "$WORK/receiver" \
  --report "$WORK/receiver.json" --generations 2
```

For one opt-in development bootstrap rather than the benchmark sweep:

```sh
python tools/bootstrap_pipeline.py --llvm "$LLVM" --variant optimized \
  --jobs 4 --build-jobs 4 --stage1-opt 0 --stage1-split 4 --stage2-split 4 \
  --runtime-overlap --runtime-c-cache --output "$WORK/development"
```

The first split-bootstrap attempt ran inside the driver's two-second cache
publication trust window after a source edit. It correctly failed rather than
using a missing runtime artifact. The research controller now waits for its
inputs to settle; the wait is timed and the production cache rule is unchanged.
[Initial failure](results/bootstrap-initial-failure.json). A subprocess-liveness
test initially confused container PID and mounted `/proc` namespaces; the test
now resolves namespace identities and includes a live-process positive control.

The first full fast-check run caught an LLVM ownership violation: the routing
predicate's declaration text was initially in the driver. The reviewed version
moves recognition into `lower_module.py` and derives its needle from
`runtime_decl(RTSYM["pys_new"])`; the architectural test remains intact. The
repeated performance results above keep their frozen pre-relocation source
identity. Fresh ordinary and split bootstraps and the final validation suite
exercise the reviewed placement separately. The [initial test failure](results/validation-initial-layering-failure.json)
is preserved rather than counted as a pass.

After the relocation, [fresh bootstraps of the reviewed source](results/bootstrap-reviewed.json)
again passed all six witnesses per policy: 133.09 s ordinary and 78.13 s split.
These are one observation each on the changed source, kept separate from the
three-pair frozen-source timing study. Final native executables and a fresh
compatible mypyc host were rebuilt from that reviewed source for the
[completed validation](results/validation-reviewed.json):

| Reviewed-source gate | Result |
|---|---|
| `make check-fast lint`, with real LLVM integration enabled | Passed; 441 unit-test executions, one optional test skipped |
| Research-controller test discovery | 50 test executions passed |
| Actual worker artifacts and integrity controls | Eight jobs and six controls passed; no compiler execution during offline checks |
| Standalone copied worker, isolated Python, outside repository | Exact original object reproduced |
| Ordinary versus split compiler corpus | 4,238 IR/diagnostic/exit-status comparisons identical |
| Ordinary versus compatible mypyc corpus | 4,238 IR/diagnostic/exit-status comparisons identical |
| Nine native cases, JIT and AOT, ordinary and every-allocation GC | 36 execution comparisons passed |
| Allocator IR and LLVM assembly checks | Three programs passed |
| Native / hosted runtime-cache suites | 66 / 68 assertions passed |

Test counts are per invocation; controller tests partly overlap the fast suite.
The [final mypyc provenance check](results/reviewed-host-provenance.json) confirms
all 48 compiler modules are extensions and its prepared sources exactly match
the intended overlay on the reviewed tree. Compiler, source and prepared-host
artifact hashes remained unchanged. The
[worker artifact report](results/worker-artifacts-reviewed.json) retains job/result
bindings and corruption controls. Actual build-tier tests exercise O0/O1/O2 and
two-way LTO, including retained IR and failed-publication behavior.

Full local `make verify`, macOS and actual multi-host execution remain unrun.
The draft stays open for review; no merge is requested.
