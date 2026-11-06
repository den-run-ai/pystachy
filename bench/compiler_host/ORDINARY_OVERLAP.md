# Whole-runtime overlap with ordinary self-builds

This prototype extends the self-build experiment at `f8127dc25f44af46f34dbae31b64fa2152aa2a7e`
(PR #1091). It changes research controllers and their tests; compiler, runtime,
LLVM optimization defaults, and arbitrary-program driver behavior are unchanged.

`tools/bootstrap_pipeline.py --runtime-overlap` now prepares the whole runtime
concurrently with the frontend in **both** stages, including an ordinary stage.
Previously the flag applied only to selected split/ThinLTO stages. An ordinary
stage retains one LLVM module, the O0 temporary/O2 final policy, and the driver's
allocator routing and late-inlining sequence. The first temporary compiler and
the final compiler must both match the baseline executable bytes.

The controller reserves two outer build slots; each frontend/runtime child has
`PYSTACHY_BUILD_JOBS=1`, and ordinary LLVM optimization/code generation stays serial.
Every bootstrap still builds two compilers and validates three compiler and three
runtime IR witnesses. Failures preserve prior published outputs. The runtime is
prepared through the unchanged driver's tiny-program build, so its overhead is
included. This is a bounded experiment, not a production driver overlap API.

## First paired observation

The [raw first pair](results/ordinary-overlap-initial.json) uses CPython 3.13.16,
LLVM 18.1.3, CPU affinity 0–3, fresh private runtime caches, and the same frozen
compiler sources. OS caches are not flushed. The outer measurement includes
controller overhead and samples aggregate process-tree RSS (shared pages can be
counted more than once).

| Policy | Wall time | Total CPU | Sampled aggregate peak RSS |
|---|---:|---:|---:|
| Ordinary O0 temporary → O2 final | 133.002 s | 134.442 CPU-s | 920.5 MiB |
| Same backend policy, runtime overlap | 126.054 s | 147.901 CPU-s | 939.2 MiB |

This pair observes 5.2% less wall time, 10.0% more CPU and 2.0% more sampled RSS.
Both temporary and final compiler binaries match exactly between policies, and
all 12 IR witnesses pass. It is one paired observation, not a stable speedup
estimate. Other sessions can use this shared host; do not use unrelated native
correctness-build durations as performance evidence.

The prototype must honor the existing two-second cache trust window for recently
written producer executables. Its source/tool hashing, extra controller, and tiny
runtime-preparation builds also cost work. A production driver extraction could
avoid some of that overhead, but has not been implemented or measured here.
Warm-cache benefit is not established by this cold-cache experiment.

## Reproduction

From this checkout, using the pinned development Python and matching LLVM bin
directory (replace the example paths):

```sh
python3 bench/compiler_host/bootstrap_followup.py \
  --llvm /path/to/llvm/bin --cpus 0-3 --samples 3 \
  --variant driver-o0 --variant driver-overlap \
  --work /tmp/ordinary-overlap-runs --report /tmp/ordinary-overlap.json
```

`--work` must be new. The first observation used `--samples 1`. The standalone
`self_pipeline.py --backend ordinary` also supports a serial control by omitting
`--overlap`, retaining the same preparation and backend work. Full-LTO partitions
cannot be combined with this ordinary overlap path.

## Validation and limits

The scheduler tests validate both ordinary-stage routing, all six witnesses,
worker budgets, invalid combinations, source changes, timeouts and cancellation.
Real-LLVM stand-ins rendezvous to prove frontend/runtime overlap and execute the
resulting compiler witnesses. They cover successful publication and a deliberately
wrong runtime witness that must preserve previous outputs. A real allocating
stand-in also covers optimization, late allocator inlining and code generation,
including correct scoping of an explicit inlining threshold.

On local implementation `8d05de94`, the three documented unittest-discovery
commands pass **40 hosted tests**, with four optional LLVM tests skipped. The
ordinary non-allocating and allocating real-LLVM integration tests pass separately.
Ruff and all 11 repository-hygiene tests pass. An initial combined module-mode
unittest command had three helper-import errors; the repository's discovery mode
adds `tools/` to the import path and passes without changing production code.

Linux x86-64 is locally exercised. macOS, remote workers and cross-host caches
remain outside this prototype. Full local `make verify` has not been run. The
LLVM installation here has no `ld.lld`; existing ThinLTO integration tests are
not claimed as locally rerun. Historical #1091 measurements must be reproduced
from their recorded revisions because the overlap flag's coverage has expanded.
