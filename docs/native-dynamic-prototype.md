# Python-free dynamic scalar prototype

This experiment runs unannotated scalar functions without CPython. A baseline
AST interpreter and dispatcher are written in Pystachy's typed subset and
compiled to one native executable. Runtime argument tags select hot numeric
caller/helper regions; the self-hosted compiler generates shared native code for
those tags. Compilation failure or an entry guard miss keeps execution working
in the interpreter.

It is isolated under `tools/` and does not change `pystachy run`, the production
compiler, or the runtime's value representation. It is separate from
[PR #374](https://github.com/den-run-ai/pystachy/pull/374), whose original function
and extension boundary require CPython.

## Run the experiment

On Linux x86-64 with LLVM 18 and a bootstrapped native compiler:

```sh
make native-dynamic-check
python3 tools/native_dynamic_check.py --bench --runs 7 \
    --n 20000 --calls 20 --json build/native-dynamic-bench.json
```

The Python script prepares binaries and supplies a reference oracle. Actual
application subprocesses and runtime specialization builds use native binaries
with Python absent from their `PATH`. It checks the compiler and executors are
native executables. `--compiler build/verify/pystachy2` reuses a verified compiler;
`--skip-build` reuses prepared artifacts. CI requires actual loaded
specializations and fallback tests, with no timing thresholds.

The [example](../examples/native_dynamic.py) contains ordinary unannotated
definitions. `mixed_local` changes a local from an integer to a string and still
executes in the baseline, although it cannot be specialized. `weighted_sum`
calls the same helper with either integer or floating-point values.

The prepared host also accepts a plain call plan:

```text
weighted_sum 6 int:3 int:25
weighted_sum 6 float:1.5 int:25
add 2 bool:true bool:false
mixed_local 6 int:4
```

Each line gives a function, repeat count and tagged positional arguments. From
the checkout, put the prepared loader directory on `LD_LIBRARY_PATH` and run:

```sh
build/native-dynamic/host examples/native_dynamic.py plan.txt adaptive \
    /absolute/path/to/pystachy /absolute/path/to/llvm/bin \
    /absolute/path/to/build/native-dynamic
```

Use `baseline` to disable specialization. Optional final arguments are warmup
calls, total loaded variants and total attempts; defaults are `3 2 4`. Results
and diagnostic counters use tab-separated output.

## Execution and specialization

| Component | Contract |
|---|---|
| `native_dynamic_vm.py` | Reuses Pystachy's lexer/parser, validates the whole input, and evaluates tagged `None`, bool, int, float and string values. |
| `native_dynamic_types.py` | Conservatively verifies stable local/return tags for a numeric caller and its direct helpers. |
| `native_dynamic.py` | Counts exact argument-tag tuples, applies entry guards, builds hot variants synchronously, and selects baseline or native execution. |
| `native_dynamic_loader.c` | Loads shared code and passes at most three integers/doubles, a result tag and a scalar result through a small C ABI. |
| `native_dynamic_check.py` | Builds the experiment, checks results, and reports cold setup separately from warm execution. |

The dispatcher freezes one source snapshot and its AST. Input code can contain
pure function definitions and inert docstrings. Globals, imports, closures,
containers, attributes, callbacks, effects, defaults and keyword calls are
rejected before execution. Compiler runtime and generated ABI symbol prefixes
are reserved. There is no runtime rebinding or module mutation.

The baseline supports assignments, branches, `while`, `for ... in range`, loop
control/else, return, direct calls, short-circuit expressions and scalar
arithmetic. Builtins include `len(str)`, `abs(number)`, `bool(scalar)`,
`int(number)`, `float(number)` and `str(scalar)`. Floor division, modulo and
bitwise operators require integer operands. Annotations are inert metadata in
the baseline; native regions must be unannotated.

Integers use checked signed 64-bit arithmetic rather than arbitrary precision.
Strings follow Pystachy's byte-string semantics. The reusable `Program` API
provides step/depth limits; the CLI disables its step limit so specialization
does not change that policy. Baseline recursion is limited to 128 frames;
recursive regions are not specialized.

Only finite int/float inputs with at most three arguments can enter native code.
Bool, string, `None`, non-finite float and other signatures run in the baseline.
All numeric tuples are counted in a finite domain (at most 15 per function), so
rare first-seen types cannot exclude a later hot tuple from observation. Loaded
images and attempts have separate global budgets. Failed or rejected signatures
are attempted once. Helper calls compile inside the selected outer region using
existing template specialization; helper hotness does not independently trigger
native compilation.

Generated source uses the existing internal `rt` mode to expose a scalar C entry
and result setters. It links ordinary runtime bitcode and a tiny image helper,
without `pyext.c`, `pyembed.c` or libpython. Each image owns its heap and exception
state; internalizing its symbols prevents interposition with the host or another
image. Scalar results cross by value.

The generated entry catches native exceptions and reports failure before any
exception crosses the C boundary. The verified pure region then replays in the
baseline, producing its result or error. This covers checked overflow and zero
division. Effectful code would require recovery at the correct execution point;
whole-function replay is only valid under the purity restriction.

## Measurement and limits

The benchmark compares the native interpreter, warmed runtime specialization,
and static Pystachy AOT for the same caller/helper chain. A `batch(n, count)`
region varies each `sumsq` input and consumes every result in a checksum. Static
execution receives runtime inputs and keeps this loop inside the timed region.
Warm computation, process wall time, runtime compilation and preparation/build
costs are reported separately with raw samples.

An initial [seven-round run](benchmarks/native-dynamic-2026-10-14-aad4f1c.json)
on AMD EPYC 9V74 / LLVM 18.1.3 used `n=20000`, 20 varying helper chains, matching
checksums, and one timed batch per sample:

| Mode | Median warm batch |
|---|---:|
| Native AST baseline | 389.3 ms |
| Runtime-generated specialization | 0.234 ms |
| Static Pystachy AOT | 0.163 ms |

Runtime compilation took a median 0.275 s per variant, separate from warm timing.
Every adaptive round entered the loaded specialization. The optimized static IR
keeps the batch loop between clock calls. Adaptive is about 44% slower than static
on this small native batch; this comparison includes dispatcher, scalar packing,
private image runtime and exception recovery, so it does not isolate guard cost.
The interpreter comparison measures this deliberately simple baseline, not
CPython. These are advisory shared-host results for one numeric region, not a
general speedup claim.

This establishes a Python-free fallback and runtime type discovery for supported
calls. It does not test a new optimizer, an embedded ORC session, machine-code
inline caches, mid-function deoptimization or general Python compatibility.
Short calls can be dominated by dispatch and scalar packing. The baseline
allocates tagged objects and interprets AST nodes, so it is expected to be much
slower than specialized machine code.

The loader is single-threaded. Compilation is synchronous and variants are not
persisted across processes. Images and their private runtime heaps stay loaded
until process exit, bounded by the global variant budget; generated build files
are removed on normal exit. This experimental ABI uses internal compiler
facilities and is not a supported public native-export interface.
