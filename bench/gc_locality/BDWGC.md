# Optional BDWGC application-runtime experiment

This research overlay compares a restricted Pystachy AOT application runtime with
[Boehm–Demers–Weiser GC 8.2.6](https://github.com/bdwgc/bdwgc/tree/v8.2.6).
It changes no default compiler or runtime source and installs no dependency.
Supply the dependency explicitly and build each application with the same native
compiler used for the native baseline. Compilation is setup; measure the resulting
application process. This is not a complete replacement collector binding.

## Supported contract

The overlay replaces the native allocator and collector together. Native free
lists stay empty, so generated allocation helpers enter the replacement slow path.
The experiment is single-mutator AOT, with one BDWGC marker including that mutator.
The adapter supplies the malloc-backed global-root, prototype and active exception
cleanup tables to BDWGC. BDWGC handles native stack/register and static roots.
Interior pointers are enabled and each allocation reserves an extra byte to retain
Pystachy's one-past-payload pointers.

Atomic allocations preserve the compiler's zeroed-allocation promises explicitly;
BDWGC only guarantees clearing for its scanned allocator. The raw atomic allocator
may omit clearing. Numeric list backing stores keep their atomic representation
through growth, copies and clearing: the adapter queries the actual BDWGC kind
instead of reading the native collector's unused page map. String growth queries
BDWGC's object size. Its size classes differ from the native allocator, and native
large-string page trimming is absent. These integration costs belong to the
measured adapter; a timing result does not isolate collector algorithms.

The following operations exit with status 78 in this overlay:

- Weak references and callbacks, whose native lifecycle is not integrated.
- Managed files and binary files, including explicitly closed files. The native
  file registry relies on native mark bits; silently retaining it would be unsafe.
  Standard input/output streams continue through the normal runtime setup.
- CPython ownership tracking and CPython extension embedding.
- JIT execution, whose signal-handler ownership has not been integrated.
- `PYSTACHY_GC_MIN` and `PYSTACHY_GC_MARK`, which specify native collector policies.

Do not rank workloads that take an unsupported path. File-based JSON wrappers
need to be excluded or rewritten as separately identified in-memory inputs before
comparison. A wrapper rewrite must be applied equally to every collector.

The relevant public allocation, interior-pointer, incremental, event and statistics
contracts are in [gc.h](https://github.com/bdwgc/bdwgc/blob/v8.2.6/include/gc.h).
The extra-root and allocation-kind APIs are in
[gc_mark.h](https://github.com/bdwgc/bdwgc/blob/v8.2.6/include/gc_mark.h).

## Dependency and overlay

The initial experiment used Ubuntu package `libgc-dev` version
`1:8.2.6-1build1` for amd64. Its archive is available from the
[2024-11-01 Ubuntu snapshot](https://snapshot.ubuntu.com/ubuntu/20241101T000000Z/pool/main/libg/libgc/libgc-dev_8.2.6-1build1_amd64.deb),
with SHA-256:

```
e5d9a3129688bcf6722c381561aeef1c938e7a70bcade830c04c04e55cfa0744
```

Verify the archive, then extract with `dpkg-deb --extract` into a private directory.
There is no need to install it system-wide. The static library avoids resolving a
different runtime library through the host's dynamic linker. Review the package's
copyright notices before redistributing dependency bytes; this branch includes
only original adapter code.

For example, with a verified extraction in `/tmp/bdwgc`:

```sh
python3 -I bench/gc_locality/bdwgc_overlay.py \
  --source /absolute/pystachy-checkout \
  --output /tmp/pystachy-bdwgc \
  --include /tmp/bdwgc/usr/include \
  --library /tmp/bdwgc/usr/lib/x86_64-linux-gnu/libgc.a
```

The output directory must be new and outside the source checkout. It holds an
adapted `runtime.c`, symlinks to the other source inputs, a private runtime-cache
path, and `bdwgc-manifest.json`. The manifest hashes the original runtime, adapter,
public headers and library. Those identities are also embedded in the generated
runtime bytes so the existing runtime-cache key changes with the dependency.
Keep the source checkout and dependency unchanged while building and testing.
Record the compiler executable and toolchain identities separately.
The output path is resolved before the containment check, including symlinked
ancestors; existing directories and dangling output symlinks are rejected.
`test_bdwgc_overlay.py` checks those cases using temporary files and placeholder
dependency metadata, without a compiler or installed collector.

Use the manifest's `PYSTACHY_HOME`, `PYSTACHY_CACHE`, and `PYSTACHY_CFLAGS` values
when building. Do not use `pystachy run`: build AOT executables and launch them in
fresh processes. Sanitize inherited `PYSTACHY_*` and `GC_*` variables before
applying each explicitly recorded configuration. Keep native-only policy variables
out of the BDWGC variants. A library filename in `PYSTACHY_CFLAGS` can produce a
harmless unused-linker-input warning during the C-to-IR compilation; the same flag
is needed by the final AOT link.

## Collector policies and capability checks

`PYSTACHY_BDWGC_MODE=default` selects the normal nonincremental collector.
`incremental` calls `GC_enable_incremental`. `generational` also sets
`GC_TIME_UNLIMITED`, selecting the generational component without incremental
pause budgeting as documented in `gc.h`. These are single-mutator configurations,
not concurrent mutator execution.

Before initialization, the adapter calls `GC_set_manual_vdb_allowed(0)`. Some
BDWGC builds default to manual dirty-page tracking, which requires write barriers
that Pystachy does not emit. Incremental/generational requests must instead enable
automatic tracking; a disabled or unavailable incremental facility is rejected.
Libraries built without the required public configuration APIs fail to link.

The initial automatic incremental selection emitted an upstream warning that
opening `/proc/self/pagemap` or `/proc/self/clear_refs` failed. Although the API
reported incremental mode enabled afterward, that observation alone is insufficient
for a clean comparison. The adapter preserves such capability diagnostics and
exits 78; these automatic-selection samples are blocked and excluded.

BDWGC also documents `GC_USE_GETWRITEWATCH=0` as an explicit choice of protecting
pages and catching memory faults instead of trying Linux soft-dirty bits. This is
a separate configuration and must retain that environment setting in its evidence.
The pinned [environment reference](https://github.com/bdwgc/bdwgc/blob/v8.2.6/doc/README.environment)
and [virtual dirty-bit implementation](https://github.com/bdwgc/bdwgc/blob/v8.2.6/os_dep.c)
describe that selection and its ordinary fallback path. The adapter does not change
kernel interfaces or permissions. Validate this configuration's retained-object
mutations and normal AOT runtime initialization before including its timings.

For a predeclared heap-sizing sensitivity, `GC_INITIAL_HEAP_SIZE=33554432` requests
a 32 MiB initial heap. This is a documented runtime environment variable, parsed in
[misc.c](https://github.com/bdwgc/bdwgc/blob/v8.2.6/misc.c). It is not equivalent to the
native collector's 32 MiB collection threshold. Label the two BDWGC policies
separately; use the same process memory cap and report actual peak RSS and output
checks. Do not select a different policy for each workload after observing timings.

`PYSTACHY_GC=stats` or `profile` emits a separate `bdwgc:` diagnostic. It records
actual version/mode, incremental flag, protection-needs mask, marker count,
collection count, stopped-world event time, heap size, free bytes and cumulative
allocated bytes. `stopped_world_ms` excludes work outside those event intervals;
it is neither total collector CPU time nor all collector elapsed time. The
protection-needs mask alone does not establish which tracking mode initialized.
Compare application elapsed time and process RSS directly. Keep BDWGC diagnostics
separate from the native `gc:` schema.

## Integration probe

`bdwgc_probe.c` tests allocation clearing, numeric/scanned list representation,
large string growth and aliases, explicit roots in malloc-backed tables,
one-past pointers, scanned object edges, old-to-new mutations, and eventual
reclamation after live table counts are cleared. It uses BDWGC disappearing links
only as an observation mechanism for the C probe; Pystachy's language weak-reference
API remains unsupported. Allocation and mutation happen in separate stack frames
from the garbage churn. The probe enters through ordinary `pys_init` to exercise
AOT signal setup as well as collector initialization.
The probe first permits manual tracking to simulate a `MANUAL_VDB` build's default,
then asserts that the adapter disables it during initialization.

Build it with the same compiler, LLVM and library used for the application variants:

```sh
/absolute/native-pystachy rt runtime.py -o /tmp/bdwgc-runtime-py.ll
clang -O2 -fexceptions -S -emit-llvm \
  -I/tmp/bdwgc/usr/include \
  -DPYSTACHY_GC_RUNTIME='"/tmp/pystachy-bdwgc/runtime.c"' \
  bench/gc_locality/bdwgc_probe.c -o /tmp/bdwgc-probe.ll
llvm-link /tmp/bdwgc-runtime-py.ll /tmp/bdwgc-probe.ll -o /tmp/bdwgc-probe.bc
clang -O2 /tmp/bdwgc-probe.bc /tmp/bdwgc/usr/lib/x86_64-linux-gnu/libgc.a \
  -lm -ldl -pthread -o /tmp/bdwgc-probe
PYSTACHY_GC=stats /tmp/bdwgc-probe
```

Success prints `bdwgc contract ok`. Arguments `weakref`, `file`, `track`, and
`extension` exercise explicit unsupported-path rejections. Unknown collector modes,
native-only pacing, and JIT configuration must also reject. Probe results are
correctness evidence, not a realistic workload score or full runtime verification.

The [initial 2026-11-06 checks](results/2026-11-06/bdwgc-contract.json) used LLVM
18.1.3 and the pinned static library. Default, default with a 32 MiB initial heap,
default under forced collection stress, explicit page-protection incremental and
explicit page-protection generational configurations all passed. The two automatic
incremental selections and seven unsupported-path/configuration checks exited 78
as expected. Both explicit page-protection configurations reported incremental=1,
protection=1 and one marker, without the soft-dirty capability warnings. This
establishes the tested AOT contract for these modes; it does not establish their
performance on application workloads. The fresh runtime.py IR, compiler binary,
source files, probe binary and dependency identities accompany the result.
These initial results retain their original source identities and are superseded
for the adapter by the manual-tracking safety update; they are not rewritten.

The [post-review manual-VDB checks](results/2026-11-06/bdwgc-contract-manual-vdb.json)
rebuild the overlay and probe with the guard above. Default, 32 MiB initial heap,
explicit page-protection incremental and explicit page-protection generational
modes pass with the simulated manual-enabled precondition. Both automatic
soft-dirty selections reject with status 78, as do two negative controls that
set `GC_DISABLE_INCREMENTAL=1`. Fresh runtime.py IR is byte-identical to the
previous probe's IR. These checks use the following identities; the result also
records compiler, dependency, full source, manifest and build-command identities.

| Input/output | SHA-256 |
|---|---|
| Adapter source | `da765410982de0083f820d38bb2bd635898aea0e94cbe65f6cc4372ba665b546` |
| Generated runtime | `03649f06d682e1374184bd7ddecf04e1b16c8169d1ebff1bb53e9b383d4f5d50` |
| Probe executable | `9c543262dc077d96318c20c2f929210099aa2008edc9139234b0db9488a3d26d` |

## Why BDWGC first; requirements for broader bindings

BDWGC offers a bounded conservative, nonmoving experiment through its C allocation
API. Compiler-proved atomic allocations are already useful to this backend without
changing the language's reference representation. The restricted adapter is a
measurement vehicle, not a recommendation to adopt this dependency by default.

[MMTk's current integration guide](https://docs.mmtk.io/portingguide/prefix.html)
and [repository](https://github.com/mmtk/mmtk-core) require a VM binding: MMTk calls
back through `VMBinding`, while the VM uses its memory-manager API. A Pystachy binding
needs object boundaries and sizes, accurate reference-slot scanning, roots, safepoint
coordination, and the barriers/movement or pinning contracts of the selected plan.
Its existing raw/interior pointers and C resources make that a separate runtime and
compiler project. A collector name in MMTk's plan list does not establish that a
particular Pystachy binding can safely run it.

[Whippet](https://github.com/wingo/whippet) is an embed-only C library with a common
API, multiple tracing/allocation implementations, optional conservative roots for
some collectors, pinning, finalization, ephemerons and compiler/JIT fast paths. Its
README reports Guile feature completeness as of October 2025 while listing further
platform testing. A direct binding would still have to implement Pystachy's roots,
object tracing, barriers, safepoints and resource semantics. Reusing C and keeping
the interface small do not remove those requirements. Neither MMTk nor Whippet was
built or benchmarked in this bounded BDWGC experiment.
