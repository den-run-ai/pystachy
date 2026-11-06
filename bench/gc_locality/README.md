# Collector locality research workloads

These programs complement [the allocator suite](../allocator/README.md) with a
stable pointer graph, escaping scalar records, and writes to long-lived containers.
They run unchanged under CPython or as native Pystachy programs. Each emits one
deterministic checksum line and checks the final reachable data. Suggested arguments
are starting points; scale them to keep runs long enough to measure on your machine.

| Program | Suggested arguments | Purpose |
| --- | --- | --- |
| `graph.py` | `30 30000` | A permuted live graph remains reachable while linked chains come and go; exercises marking locality. |
| `reverse_chain.py` | `30 30000 reverse` | Single-root chain follows reverse allocation order; adversary for ascending chunk scans that must revisit newly marked lower slots. |
| `reverse_chain.py` | `30 30000 forward` | Same retained size and atomic churn, with forward allocation order as a separate control. |
| `scalars.py` | `40 100000 aligned` | Eight-field scalar records escape through lists; synthetic aligned integers exercise conservative candidate checks. |
| `scalars.py` | `40 100000 small` | Same allocation pattern with small integers; control for address-shaped payloads. |
| `stores.py` | `100 20000` | Object fields, list slots, and dictionary values change while older containers retain references. |

The scalar `aligned` case uses fixed integers that resemble virtual addresses; it
is not a proof of false retention or an actual interior-pointer correctness test.
Use the runtime probes for those properties. The workloads do not measure pause
percentiles or prove a win for application workloads.

The [2026-11-06 evaluation](results/2026-11-06.md) includes an isolated scalar
allocation control, the combined experimental runtime, negative results, raw
samples and source/binary identities. The isolated change is promising on the
scalar workloads; these experiments establish no self-compilation speedup.

## What the runtime experiments change

`pys_new` already requires the compiler's `ref_free` proof: fixed tuples or class
layouts containing only native `int`, `float` and `bool`, without hidden reference
fields. This branch routes surviving allocations through existing atomic storage
in both JIT and AOT. It does not broaden that proof. Large scalar allocations also
enter the existing atomic-large pressure accounting; workloads using them can
change collection cadence as well as scanning cost. The scalar benchmark's records
are small, and the matched runs had equal collection counts.

`PYSTACHY_GC_MARK=block` instead experiments with tracing order. It queues scanned
small-object chunks, records pending slots in a bitmap with a word summary, and
scans discovered runs in address order. It never scans unmarked neighboring
objects. Backward discoveries and edges to an already-drained chunk create more
work until the queue reaches a fixed point. Large arrays retain sliced tracing.
This is a nonmoving, stop-the-world experiment. The default object mode still
contains shared dispatch/profile checks: it is **not** an isolated scalar patch.
Keep that distinction when interpreting results or choosing changes to promote.

Pystachy's existing collector already has allocation pools, atomic classes, page
reuse, interior-pointer recognition and tracing prefetches. The chunk worklist is
an independently written implementation inspired by the locality argument in
[Go's Green Tea article](https://go.dev/blog/greenteagc), not a port or measurement
of Go's collector. Its queue and bitmap costs can outweigh locality gains.

[Julia's sticky generations](https://docs.julialang.org/en/v1.14-dev/devdocs/gc/)
offer another way to avoid repeated tracing, but need complete old-to-young write
barriers across generated field stores, runtime containers and bulk copies.
[MMTk's plan matrix](https://www.mmtk.io/status) and
[Julia's binding](https://docs.julialang.org/en/v1.14-dev/devdocs/gc-mmtk/) illustrate
the integration work: roots, object boundaries, interior pointers, FFI ownership,
weak references and safepoints need explicit contracts. Moving plans additionally
need reference updates or suitable pinning. Immix/StickyImmix, LXR and
[Whippet](https://github.com/wingo/whippet) were not benchmarked in this experiment;
these results do not rank them.

For phase arenas, the compiler already clears each function's typed-IR blocks and
auxiliary containers immediately after lowering (`src/pystachy_compiler/program.py`),
while retaining emitted LLVM text and effect summaries. That drops references; it
does not prove immediate reclamation or ownership of shared metadata. An arena
experiment needs a demonstrable additional lifetime benefit.

## Build first, measure separately

Build each compiler and each AOT workload outside the measurement run. Record the
compiler source revision and any local patch, then check the checksum with pinned
CPython 3.13.16 at the same arguments. Use the same `MODE` when comparing scalar
variants. Keep the GC minimum and input sizes equal across a comparison. The
existing `bench/allocator/run.py` remains the convenient AOT/JIT build-and-run
controller; the generic controller here accepts **already-built commands**, including
the native compiler's self-frontend, and hashes large file outputs without loading
them into memory.

Create a JSON config (paths are relative to the directory from which the controller
is invoked; command arguments and `inputs` are relative to each variant's `cwd`):

```json
{
  "name": "self_frontend",
  "cwd": "/absolute/path/to/one/shared/input/checkout",
  "address_space_mib": 2048,
  "inputs": ["pystachy.py", "runtime.c", "src/pystachy_compiler/lowering.py", "src/pystachy_compiler/lower_module.py"],
  "env": {
    "PYSTACHY_HOME": "/absolute/path/to/one/shared/input/checkout",
    "PYSTACHY_GC": "stats",
    "PYSTACHY_GC_MIN": "32"
  },
  "notes": "Source revision, patch identity, toolchain, other jobs, and input coverage.",
  "variants": [
    {
      "name": "baseline",
      "argv": ["/absolute/path/to/baseline/pystachy", "ir", "pystachy.py", "-o", "{output}"]
    },
    {
      "name": "prototype",
      "argv": ["/absolute/path/to/prototype/pystachy", "ir", "pystachy.py", "-o", "{output}"],
      "env": {}
    }
  ]
}
```

Per-variant `env`, `cwd`, `inputs`, and extra descriptive fields such as
`source_revision` are preserved in the report. Put any prototype opt-in in that
variant's `env`. Inherited `PYSTACHY_*`, `LD_PRELOAD`, `PYTHONPATH`, and `PYTHONHOME`
are removed: specify all needed settings in the config, including `PYSTACHY_LLVM`
if the chosen command invokes LLVM. For frontend comparisons, use identical source
and library inputs and a shared input path so emitted IR hashes can match; a shared
home is valid only when its runtime/library content is intended for both runs.
The compiler executable SHA is recorded independently of the input checkout.
Relative or empty `PATH` entries are resolved against the variant's `cwd`, matching
the child process's executable lookup.
List every consumed input or describe a pinned clean source tree in `notes`; the
four example `inputs` above alone do not cover the compiler's complete imports.

Optional `address_space_mib` is a positive integer in the common config or a
per-variant override. The controller sets both soft and hard Linux `RLIMIT_AS`
limits in the child before execution and records the selected limit in each
variant. It rejects limits above an inherited hard limit. Omitting the setting
preserves inherited limits. This caps each process's virtual address space,
including libraries and mappings; it is not a cap on RSS or only the GC heap.
Use the same cap across variants for a matched comparison, for example 2048 MiB
with `PYSTACHY_GC_MIN=32`, and continue to report observed peak RSS separately.

For an AOT program, replace each `argv` with its corresponding binary and identical
arguments, for example `["/path/to/baseline-graph", "30", "30000"]`, and include
`bench/gc_locality/graph.py` as an input. Omit `{output}` in every variant for a
stdout-only comparison. The controller does not run a shell.

```sh
python3 -I bench/gc_locality/run.py --config build/gc-config.json \
  --cpu 3 --rounds 5 --warmups 1 --json build/gc-results.json
```

Choose a CPU in the process's allowed affinity. All runs, including the untimed
warmup round, validate return status, exact stdout SHA-256, and output-file SHA-256
when `{output}` is present. Each round rotates variant order. A failed comparison
stops with a nonzero exit status and retains partial evidence in JSON. Output files
are temporary and removed after hashing. A warmup is excluded from reported medians;
its wall/CPU/RSS samples remain in the report for inspection.

The report records command arrays, explicit environment, executable and requested
input hashes, checkout revision and dirty status, CPU affinity/model, OS/Python,
host load before/after, each sample, and medians. Linux `wait4` reports process user
CPU, system CPU, peak RSS in KiB, and page faults. Runtime `gc:` statistics retain
collection count, elapsed collection milliseconds, heap peak, and last live bytes
(reported in MiB). Elapsed collection time is not a separate GC CPU measurement.
If a command reports several collectors, raw reports are retained without combining
them into a misleading median. `PYSTACHY_GC=profile` additionally records structured
`gc phases:` timings and `gc work:` counts in each sample's `gc_profile`, without
changing the headline summary fields. Collect these diagnostics in a separate run;
use `PYSTACHY_GC=stats` for headline timings because profiling adds hot-path work.

Compare elapsed time **and** peak RSS at a fixed memory policy, with GC time and
collection counts explaining the result. The configured GC minimum is a pacing
setting, not a hard RSS budget. Shared-host measurements are advisory; repeat noisy
cases on an idle machine. No timing threshold is a correctness gate. The native
self-frontend exercises Pystachy's compiler, but does not include LLVM optimization
or code generation for a complete self-build.

Controller regression tests use tiny synthetic child processes, with no native builds
or performance thresholds:

```sh
python3 -m unittest discover -s bench/gc_locality -p test_run.py
```
