# Adaptive specialization prototype

`tools/adaptive.py` is an opt-in experiment in running unannotated numeric
functions through Pystachy's existing typed IR and CPython extension backend.
The surrounding application runs in CPython. Observed argument types select
compiled implementations; runtime guards decide whether each call can use them.

This is a function-boundary prototype of type feedback and guarded specialization.
It does not implement machine-code polymorphic inline caches, call-site profiling,
caller-context cloning, or a general dynamic Python runtime.

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
it with `pystachy ext`, and loads it into the host. The cache retains at most
`max_variants` compiled versions. The original function is available as
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

## Initial scope and correctness

The prototype accepts a deliberately small, side-effect-free numeric subset:
local scalar computation, branches, and loops over builtin `range`. It requires
source that can be checked against the original function's code. Closures,
external function calls, mutable containers, attributes and global state are
outside this first experiment. Unsupported functions keep running in CPython.

Native dispatch requires exact supported scalar types and representable inputs.
Booleans, subclasses, large integers, non-finite floats and unsupported call shapes
use the original function. Calls under tracing/profiling or from another thread
also use CPython, because the extension
runtime belongs to the thread that imported it. Changes to the original code or
the builtin bindings it uses invalidate the native path.

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
```

The first command runs guard and fallback tests, with native tests when a suitable
toolchain is available. The second requires native compilation and dispatch;
CI uses this mode. There are no timing thresholds in CI.

## Background

- [Polymorphic inline caches](https://bibliography.selflanguage.org/pics.html):
  a small type-to-target cache also supplies feedback for optimization.
- [Selective specialization](https://projectsweb.cs.washington.edu/research/projects/cecil/www/Papers/specialize-pldi.html):
  choose profitable compiled versions while controlling code growth.
- [PEP 659](https://peps.python.org/pep-0659/): small adaptive specializations and
  cheap recovery in CPython.
- [Annotation porting experiment #264](https://github.com/den-run-ai/pystachy/issues/264):
  the earlier source-rewriting experiment, which measured a different approach.
