# Adaptive specialization prototype

`tools/adaptive.py` is an opt-in experiment in running unannotated numeric
functions through Pystachy's existing typed IR and CPython extension backend.
The surrounding application runs in CPython. Observed argument types select
compiled implementations; runtime guards decide whether each call can use them.

This is a function-entry prototype of type feedback and guarded specialization.
It can include an explicitly supplied pure helper call graph behind one native
boundary. A separate profile-only tool records function and caller-site types
before selecting a region; the runtime cache still dispatches on function-entry
signatures. It does not implement machine-code polymorphic inline caches,
caller-context cloning, or a general dynamic Python runtime. See the
[profile-first region experiment](adaptive-regions.md) for that workflow and its
matched static baseline.

## Try it

Use Linux x86-64, CPython 3.12+ with the GIL and the LLVM toolchain described in
[installation](install.md). From the repository root:

```sh
python3 examples/adaptive/demo.py
```

The example has no parameter or return annotations:

```python
from tools.adaptive import specialize

@specialize(warmup=3, max_variants=2)
def weighted_sum(x, n):
    total = x
    for i in range(n):
        total += (i % 17) * x
    return total

weighted_sum(3, 200_000)       # observes an int/int signature
weighted_sum(0.5, 200_000)     # observes a float/int signature
```

After warmup for each signature, the wrapper generates a typed version, builds
it with `pystachy ext`, and loads it into the host. `max_variants` bounds lifetime
compilation attempts, including failed attempts. A separate replaceable profile
table, bounded by `max_profiles` (default `max(8, max_variants)`), lets later hot
signatures warm up even when rare signatures arrive first. Profile eviction
does not replenish the compilation budget or evict compiled versions. The
original function is available as
`weighted_sum.__wrapped__`; diagnostics are available through
`weighted_sum.adaptive_stats()`.

The demo checks results against the original function, prints cold and warm
timings for both signatures, and exercises fallback with a boolean and a large
integer. It fails if the two native versions were not built, so a fallback-only
run cannot masquerade as native benchmark evidence. Warm timings include the
wrapper's guards and the extension's argument/result conversions. Cold timings
include three calls and synchronous compilation; the compiler's runtime cache
may already be populated. Compilation is not persisted across host processes.

One local run on an AMD EPYC 9V74, CPython 3.13.16 and LLVM 18.1.3, with
200,000 loop iterations and the median of five warm calls, gave:

| Argument types | CPython | Adaptive, including dispatch | Warm speedup | First three calls, including compilation |
|---|---:|---:|---:|---:|
| `int, int` | 10.44 ms | 0.214 ms | 48.8× | 0.428 s |
| `float, int` | 10.13 ms | 0.169 ms | 59.9× | 0.380 s |

Both native signatures were built, ten calls used native code, and the six warmup
calls plus two unsupported inputs used CPython. The runtime cache was already
populated. These numbers describe this small compute kernel on a shared host,
not general Python application performance; short-lived workloads may lose to
compilation cost.

## Comparison with existing Pystachy

The first table compares only with CPython. Pystachy already specializes
unannotated functions when a caller's argument types are known statically. This
prototype discovers those types at a CPython boundary and compiles them through
the existing AOT extension pipeline. It does not supply branch frequencies or
other profile data to LLVM's optimizer.

Run the matched comparison from the repository root:

```sh
python3 tools/adaptive_bench.py --json build/adaptive-comparison.json
```

The controller checks five modes against CPython, with the same function body and
varying runtime inputs. A direct extension uses the identical generated typed
source and ABI, removing only the adaptive wrapper. The standalone JIT and AOT
programs keep the kernel unannotated; argument conversions from `sys.argv` give
the ordinary compiler enough information for static template specialization.

On the same host and toolchain, 200,000 base iterations and the median of seven
checked samples gave these warm times:

| Argument types | CPython | Adaptive AOT extension | Direct AOT extension | Existing JIT | Existing AOT |
|---|---:|---:|---:|---:|---:|
| `int, int` | 8.40 ms | 0.219 ms | 0.201 ms | 0.380 ms | 0.202 ms |
| `float, int` | 9.35 ms | 0.199 ms | 0.166 ms | 1.171 ms | 0.169 ms |

All fourteen adaptive samples used native code. Every result's type and value
matched the CPython oracle. Each sample varies `x` and `n`, and the compiled
driver retains a live compute loop between its timer calls. Printing and result
checks are outside the warm timings. The JSON report includes every sample and
separate compilation, import and process times. CLI JIT runtime setup is primed
once; these setup costs are process-cold, not cache-cold.

The matched extension is the best comparison for the wrapper: adaptive dispatch
was about 9–20% slower in this run. Standalone AOT was also slightly faster. The
advantage over this kernel's existing JIT reflects backend differences: JIT uses
a precompiled runtime object, while AOT and extensions can optimize across the
runtime boundary. This experiment demonstrates near-AOT execution inside a
CPython application with runtime type discovery and fallback. It provides no
evidence of a new optimization gain over statically specialized AOT code.
For very short functions, guard and conversion overhead can also outweigh the
benefit over CPython.

## Initial scope and correctness

The prototype accepts a deliberately small, side-effect-free numeric subset:
local scalar computation, branches, and loops over builtin `range`. It requires
source that can be checked against the original function's code. Direct calls
to ordinary helpers explicitly supplied in `helpers={name: function}` are allowed
when the entire reachable call graph passes the same checks and is acyclic.
Closures, arbitrary external calls, mutable containers, attributes and global
state are outside this experiment. Unsupported functions keep running in CPython.

Native dispatch requires exact supported scalar types and representable inputs.
Booleans, subclasses, large integers, non-finite floats and unsupported call shapes
use the original function. Calls under tracing/profiling or from another thread
also use CPython, because the extension
runtime belongs to the thread that imported it. Changes to any member's code,
the helper bindings used by each caller, or its builtin `range` binding invalidate
the native path. Helpers are privately renamed in generated source; the ordinary
Python functions and their namespaces remain available for fallback.

The native runtime uses checked signed 64-bit integers. An intermediate overflow
can occur even when the arguments fit. The verified purity restriction lets the
wrapper discard that native attempt and evaluate the original function with
CPython's arbitrary-precision arithmetic. This replay would be incorrect for a
function that had already performed visible side effects; those functions are
excluded. Compiler failures are recorded and attempts are bounded.

The experiment checks scalar values and types. Native return values are boxed
again, so Python object identity is outside its contract, including returning an
input float or the same constant object. It does not preserve native call frames
as Python frames.

Profiling observations are not a proof that other types will never occur. The
generated version must pass Pystachy's static checks, and the wrapper keeps the
original function for calls outside its assumptions. The first useful question
is whether compilation and dispatch costs amortize on supported compute kernels.
Supporting arbitrary Python requires substantially more representation,
interoperability and deoptimization machinery.

## Validation

```sh
make test-adaptive
PYSTACHY_ADAPTIVE_REQUIRE_NATIVE=1 make test-adaptive
make bench-adaptive-check
```

The first command runs guard and fallback tests, with native tests when a suitable
toolchain is available. The second requires native compilation and dispatch;
CI uses this mode. There are no timing thresholds in CI.
`bench-adaptive-check` runs a small checked workload through all five comparison
modes and requires actual adaptive native calls.

## Background

- [Polymorphic inline caches](https://bibliography.selflanguage.org/pics.html):
  a small type-to-target cache also supplies feedback for optimization.
- [Selective specialization](https://projectsweb.cs.washington.edu/research/projects/cecil/www/Papers/specialize-pldi.html):
  choose profitable compiled versions while controlling code growth.
- [PEP 659](https://peps.python.org/pep-0659/): small adaptive specializations and
  cheap recovery in CPython.
- [Annotation porting experiment #264](https://github.com/den-run-ai/pystachy/issues/264):
  the earlier source-rewriting experiment, which measured a different approach.
