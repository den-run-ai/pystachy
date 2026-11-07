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
runtime IR witnesses. Validation failures occur before publication and preserve
prior outputs. The executable and retained IR are each replaced atomically, but
the pair is not a transaction: a publication failure on the second file can leave
the first replaced. The private bootstrap directories avoid reusing that pair.
The runtime is
prepared through the unchanged driver's tiny-program build, so its overhead is
included. This is a bounded experiment, not a production driver overlap API.

## Three paired bootstrap observations

The [initial pair](results/ordinary-overlap-initial.json) and
[two follow-up pairs](results/ordinary-overlap-followup.json) use CPython 3.13.16,
LLVM 18.1.3, CPU affinity 0–3, fresh private runtime caches, and identical frozen
compiler sources. The bootstrap, self-build and measurement-controller hashes
also match across cohorts. The initial pair runs ordinary then overlap; the two
follow-up pairs run overlap/ordinary and ordinary/overlap. Both cohorts and every
sample are retained. OS caches are not flushed. The outer measurement includes
controller overhead and samples aggregate process-tree RSS (shared pages can be
counted more than once).

Medians across three observations per policy:

| Policy | Wall time | Total CPU | Sampled aggregate peak RSS |
|---|---:|---:|---:|
| Ordinary O0 temporary → O2 final | 129.450 s | 130.419 CPU-s | 920.7 MiB |
| Same backend policy, runtime overlap | 120.867 s | 140.598 CPU-s | 939.2 MiB |

The ratio of medians gives **6.63% less wall time, 7.80% more CPU and 2.01% more
sampled RSS**. The individual paired wall-time reductions are **5.22%, 6.63% and
5.68%**; their median is **5.68%**. CPU increases range from 7.80% to 10.01% across
the pairs. Absolute wall ranges are 123.665–133.002 s ordinary and 116.638–126.054 s
overlap. Timings trend lower across the run sequence, so the paired results matter
alongside the aggregate medians; no sample or cohort was dropped.

The temporary build's median step time falls from 45.520 to 36.664 s; the final
build's median is 78.371 versus 77.348 s. Step medians do not add to the full median
because verification, scheduling and setup are included separately.

All **six complete bootstraps**, **12 actual native builds**, and **36 IR
witnesses** pass. Every temporary executable has the same bytes across both
policies and all repeats, as does every final executable. Compiler and runtime
IR hashes also agree across all six bootstraps. The
[derived summary](results/ordinary-overlap-summary.json) checks these identities
and retains the arithmetic; [six self-build pipeline records](results/ordinary-overlap-pipelines.json)
retain the overlap stages and command details.

This is a measured cold-bootstrap latency improvement on one shared Linux host,
with extra CPU cost. Heavy measurements within this team were serialized; other
sessions can still use the host. It does not establish better throughput on a
saturated machine or a general application-build gain. These inputs and source
revision also differ from the separate main-based compiler optimization
prototypes, so their percentages cannot be added.

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

`--work` must be new. The first cohort used `--samples 1`; the follow-up used
`--samples 2 --variant driver-overlap --variant driver-o0`. The ordinary and
overlap variants keep the same compiler input and controller hashes across both
cohorts. The standalone
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

An independent read-only review found no blocking defect in the intended paired
bootstrap path: pass order/flags match the stripped-environment driver, allocator
routing uses the shared recognizer, worker slots and cleanup remain bounded, and
both temporary and final compiler identities are mandatory. Its publication
wording correction is documented above. The initial published implementation at
`f2a108162e91bdb2b6d67910e694f99bb1e75094` passed all 16 CI jobs, lint,
performance smoke and submission format, including the default Linux/macOS
distribution jobs. Subsequent local commits only clarify documentation and add
the repeated evidence; they do not change compiler or controller code.

Linux x86-64 is locally exercised. macOS, remote workers and cross-host caches
remain outside this prototype. Full local `make verify` has not been run. The
LLVM installation here has no `ld.lld`; existing ThinLTO integration tests are
not claimed as locally rerun. Historical #1091 measurements must be reproduced
from their recorded revisions because the overlap flag's coverage has expanded.
