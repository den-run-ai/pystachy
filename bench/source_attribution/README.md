# Python source attribution and data counters prototype

This experiment adds opt-in Python file, function and line tables to Pystachy's
LLVM IR, and measures four existing workloads with the same profiling procedure.
It is a prototype for [#710](https://github.com/den-run-ai/pystachy/issues/710).
The [measured results and validation evidence](results/README.md) include all four
profiles, compiler overhead, raw samples, and known limits. It does not provide
debugger variable inspection or a trace viewer.

## Use source locations

```sh
PYSTACHY_DEBUG_LINES=1 ./pystachy build program.py -o program
PYSTACHY_DEBUG_LINES=1 ./pystachy run program.py
llvm-dwarfdump --verify program
llvm-dwarfdump --debug-line program
valgrind --tool=callgrind --dump-instr=no --dump-line=yes ./program
```

The setting must be exactly `1`. It applies to both the program and the compiled
Python runtime, and participates in runtime-cache identity. C runtime functions
retain their symbols but acquire no C line information from this option. The
program's output and Python semantics are unchanged. Debug-disabled LLVM IR stays
byte-identical for the same source and compilation context; the compiler itself
still has an extra line field on each IR instruction, whose cost is measured.

The implementation captures the existing encoded Python source location when
constructing typed IR. Replacements in the optimization and exception passes
inherit the originating instruction's location. Lowering creates a compile unit,
file records, a subprogram for each Python specialization, and instruction
locations. Imported and nested functions keep their own file and function
identity. Generated entry points and wrappers use line zero, so LLVM can preserve
Python locations when inlining into those callers. Newly synthesized bookkeeping
also uses line zero. Columns, lexical variables, source checksums, and a complete
Python inline-call stack are outside this prototype. A front-end expansion can
retain its originating file and line without becoming a distinct inline frame.

LLVM is free to merge, eliminate, inline, or move optimized instructions. These
are optimized line tables, not an assertion that every Python line has a unique
address. Perf/Callgrind can attribute instructions to Python lines that survive
optimization. The metadata contains the compilation directory; repeating a build
in the same source context is deterministic, while moving the checkout changes
that directory. A future path-remapping option would be needed for byte-identical
debug artifacts across checkout locations.

Debug-node IDs use a numeric offset after the existing metadata IDs. If the
highest existing ID leaves insufficient room in LLVM's unsigned 32-bit range,
the emitter finds a free contiguous gap. Existing metadata, quoted strings and
comments remain unchanged. This repairs the earlier decimal-prefix overflow;
the historical measurements below predate that repair. Sparse IDs and an
existing maximum ID are covered by LLVM assembly regression tests.

The default LLVM 18 Linux ORC JIT was tested with its actual GDB registration
interface. A native callback reads the running process's `__jit_debug_descriptor`,
writes a registered ELF object, and verifies the object's Python line table with
`llvm-dwarfdump`; the disabled-mode control registers no such Python table. This
uses LLVM's existing listener and makes no JIT linker changes. It establishes
registration on that tested toolchain, not compatibility with every debugger,
JIT mode, or operating system. In particular, Pystachy's `PYSTACHY_JIT_CODEGEN=0` MCJIT
fallback and macOS debug registration are not covered by this experiment.

## Optional data counters

```sh
PYSTACHY_DEBUG_LINES=1 PYSTACHY_CFLAGS=-DPYSTACHY_PROFILE_DATA \
  ./pystachy build program.py -o program-counted
./program-counted
```

A counted runtime emits one `pystachy-data: {...}` JSON object on stderr from
`pys_finish`. The schema is version 1. CFLAGS already participates in runtime-cache
identity; ordinary builds compile the counters out. Relaxed atomic increments
avoid introducing counter races in native callbacks. Totals are cumulative over
the process, including initialization and user exit callbacks, ending before
final runtime stream cleanup. The counters are aggregate totals, not per-line
allocation attribution.

| Field | Exact scope |
| --- | --- |
| `c_gc_alloc_calls` | Requests through C `gc_alloc`, the large `gc_raw` path, and the exported slow allocation entry. Small `gc_raw` requests are counted once through `gc_alloc`. |
| `c_gc_requested_bytes` | Sum of those requested sizes, before allocator rounding. This is neither live memory nor resident memory. |
| `c_memcpy_calls`, `c_memcpy_requested_bytes` | Calls and requested byte lengths at the `memcpy` call sites compiled in the `runtime.c` translation unit, including its included C sources. |
| `c_memmove_calls`, `c_memmove_requested_bytes` | The corresponding `memmove` call sites in that translation unit. |
| `gc_collections` | The existing runtime GC collection counter. |
| `gc_peak_heap_bytes` | The existing runtime GC peak managed-heap counter; it is distinct from process peak RSS. |

Allocation requests from foreign allocators and libc are excluded. Copy counts
exclude generated LLVM and `runtime.py` copy intrinsics, ordinary scalar stores,
compiler-generated copies, and copies inside libc or foreign code. Requested
bytes are not physical memory traffic, and may count a request whose actual
movement is optimized away. The JIT's generated fast allocator bypasses C
allocation helpers; use AOT for the reported allocation measurements. These
counters should not be described as a general allocation or copy profiler.

Instrumentation changes execution cost. The runner measures three separately
built variants: ordinary, line tables only, and line tables plus counters. It
collects Callgrind instruction profiles from the line-table variant without
counters. The native timing comparison with the counted variant makes the
instrumentation cost visible rather than treating it as normal performance.

## Reproduce the experiment

Use a clean, bootstrapped native compiler and an independently verified compiler
from the base commit. Required tools are Python, LLVM, GNU time and Valgrind with
Callgrind. The runner is a CPython analysis utility, not part of the self-hosted
compiler. Run from the repository root. Keep other builds and benchmarks stopped.

```sh
PYSTACHY_JOBS=2 make PY=python3
python3 -m unittest discover -s tools -p test_source_lines.py
python3 bench/source_attribution/run.py \
  --baseline-compiler /path/to/base/pystachy \
  --compiler ./pystachy --output build/source-attribution \
  --repetitions 7 --phase build
python3 bench/source_attribution/run.py \
  --baseline-compiler /path/to/base/pystachy \
  --compiler ./pystachy --output build/source-attribution \
  --repetitions 7 --phase measure
```

`--cpu` selects an allowed Linux CPU; by default the lowest allowed CPU is used.
Execution measurements, references and Callgrind are pinned to it. Builds use two
workers and are recorded separately. Each build has its own runtime cache;
`cache_existed_before` identifies whether a reused output directory was already
warm. There is no cache-cold claim for a repeated build in an existing directory.
`--time-tool` and `--valgrind` accept explicit executable paths. If Valgrind is
unavailable, timings and counters can still run, but no source profile is produced.

The runner generates deterministic route events, checks complete deterministic
output/checksum witnesses against CPython (or the base compiler for compiler IR),
warms each binary once, and runs seven rounds with variant order reversed on
alternate rounds. It records wall time, user/system time, peak RSS, executable
sizes and hashes, source/input hashes, tool versions and CPU information. The
compiler workload compares emitted IR hashes in addition to stdout. Smaller
profile inputs keep instrumentation bounded, and their witnesses are checked
again. Callgrind totals include process startup and shutdown. The parser sums
exclusive `Ir` costs, skips inclusive call-edge cost rows, and requires the sum
to equal Callgrind's summary.

| Workload | Native timing input | Counter/Callgrind input |
| --- | --- | --- |
| JSON repair | Existing `bench/json_repair/bench.py`, 2,000 rounds, ten records per round | 100 rounds |
| Routing | Existing `examples/route/route.py`, 200,000 deterministic events, in-memory mode | 2,000 events |
| Numerical scoring | Existing `bench/smoke/ml.py numeric`, 100,000 iterations of a 24-wide projection and softmax | 500 iterations |
| Compiler | Emit IR for `pystachy.py` using the same current source and home directory | Emit IR for `examples/route/route.py` |

A separate frontend comparison runs the base compiler, the new compiler with
locations disabled, and the new compiler with locations enabled against the same
current compiler source. This detects overhead from storing the extra IR field
even when program debug information is disabled. Performance is advisory: there
are no timing thresholds, and CPU affinity does not isolate the host from other
activity. The committed results document the particular execution environment.

## Validation and primary references

`tools/test_source_lines.py` checks absent/zero settings, deterministic repeated
emission, exact debug-stripped IR equality, imported and nested functions,
specialized functions, generated helpers, and quote/exclamation/Unicode paths.
It runs LLVM's optimized verifier, produces a native object, verifies its DWARF,
and checks executable line rows for both the main and imported file. The Linux
JIT test additionally checks the actual registered ELF object, not just IR text
or a filename string embedded in the executable.

- [LLVM source-level debugging](https://llvm.org/docs/SourceLevelDebugging.html):
  metadata, optimized code and source-location behavior.
- [LLVM JIT debugging](https://llvm.org/docs/DebuggingJITedCode.html): the debugger
  registration interface.
- [LLVM 18.1.3 `lli.cpp`](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.3/llvm/tools/lli/lli.cpp):
  the default ORC selection and `runOrcJIT`'s GDB listener registration for its
  RTDyld object layer and debug support setup for JITLink.
- [Callgrind output format](https://valgrind.org/docs/manual/cl-format.html):
  cost positions, compressed identifiers and inclusive call-edge costs.
