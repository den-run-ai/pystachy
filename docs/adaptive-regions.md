# Profile-first native call regions

This experiment profiles ordinary CPython workloads before selecting a supported
hot call chain. It compares the existing adaptive leaf wrapper, a guarded native
caller including its helpers, and the same region compiled with types known in
advance. The application driver stays in CPython in every mode.

This extends the [adaptive specialization prototype](adaptive.md). It evaluates
whether moving a call boundary improves an application, and how much useful code
fits the prototype's conservative pure numeric policy. It does not add general
Python compilation, caller-context cloning, or LLVM profile-guided optimization.

## Profile before compiling

From the repository root, run the profile-only controller:

```sh
python3 tools/adaptive_profile.py \
    --iterations 24 --samples 3 --numeric-inner 4096 \
    --json build/adaptive-profile.json
```

This command does not require LLVM or build native variants. It runs three small
applications from `examples/adaptive/workloads.py`:

| Workload | Original Python code exercised | Main limitation to inspect |
|---|---|---|
| Event routing | Existing `examples/route/route.py` router with a generated event stream | Strings, collections and library calls |
| Text processing | CPython `re` and `textwrap`, with a normalization driver | Objects, methods and library calls |
| Numeric computation | A synthetic scalar batch calling a numeric helper | Whether supported computation amortizes boundaries |

These are feasibility workloads, not a sample of production applications or a
measurement of general Python compatibility. Their drivers include unsupported
Python orchestration as well as candidate kernels.

The report separates three passes:

1. `sys.setprofile` records exact argument types per function and caller site,
   including separate steady, unseen-input and shifted-distribution phases.
2. `cProfile` records self and cumulative hotness in another execution.
3. Uninstrumented executions record application wall time, checking outputs
   against the type-collection pass.

Function identifiers include source location and qualified name. Caller sites
also include the caller's bytecode offset. No argument values, representations
or container contents are written to the report. Function, caller-site and
signature tables are bounded; dropped calls remain visible in coverage counts,
and top-signature coverage is marked as a lower bound when signatures overflow.

Eligibility checks use the adaptive wrapper's source and purity policy, including
directly named transitive helpers. They do not compile candidates. An eligible
AST is neither proof of native compilation nor a count of all language features
supported by Pystachy. Exact scalar types also say nothing about integer bounds,
float finiteness or intermediate overflow.

Region selection uses steady-phase cumulative hotness among eligible functions.
Per-function cumulative times overlap and must not be added to estimate coverage.
The report separately presents self-time coverage, including a denominator that
accounts for profiled native/builtin work. Profiling perturbs execution, so its
hotness times are selection evidence rather than speedup measurements.

## Compile one selected region

Use Linux x86-64, CPython 3.12+ with the GIL and the LLVM toolchain in
[installation](install.md). The comparison controller reruns profiling before
compiling; it currently implements the `numeric_batch` candidate and fails if
profiling selects another region:

```sh
python3 tools/adaptive_regions.py \
    --profile-iterations 24 --inner 4096 --batches 24 --samples 7 \
    --json build/adaptive-regions.json
```

`--compiler 'python3 /path/to/pystachy.py'` overrides the compiler command. Use
`--inner 64 --batches 12 --samples 2 --profile-iterations 4` for a small correctness
run. The batch count must be at least 12 so both common signatures can warm up.

| Mode | Boundary and information available |
|---|---|
| CPython | Original numeric batch and helper |
| Adaptive leaf | Python batch calls the existing adaptive numeric helper wrapper |
| Adaptive region | One adaptive boundary encloses the native batch and its helper |
| Static region | Entry types supplied in advance; identical generated source, compiler and extension ABI |

The static mode retains Python boundary guards and fallback for held-out inputs;
it has no type learning or runtime compilation path. The controller asserts that
its sources exactly match the adaptive region's generated typed sources. Helpers
remain unannotated: ordinary Pystachy inference specializes them from the typed
entry. This comparison measures boundary placement and runtime discovery cost,
not a new optimizer advantage over statically specialized code.

Every timed application includes Python orchestration and output construction.
Oracle computation and output equality checks run outside the measured interval.
The output records each result's exact scalar type as well as value. Performance
samples run with tracing and profiling disabled, rotate execution order, and
must show actual native dispatch. No timing thresholds are used for correctness.

## Measured feasibility result

The [checked report](benchmarks/adaptive-regions-2026-10-14.json) retains every
timing sample, per-workload coverage, the function eligibility inventory and the
selected functions' full type distributions. The controller emits additional
caller-site detail for all functions. This run used an AMD EPYC 9V74, CPython
3.13.16 and LLVM 18.1.3, with 24 batches of 4,096–4,098 helper calls and medians
of seven uninstrumented whole-application samples. These small workloads run on
a shared host; the numbers are feasibility evidence, not general Python claims.

With populated compiler caches, warm times were:

| Input phase | CPython | Adaptive leaf | Adaptive region | Static region |
|---|---:|---:|---:|---:|
| Mostly integers | 6.22 ms | 220 ms | 0.183 ms | 0.150 ms |
| Unseen bool/large-int inputs | 6.24 ms | 202 ms | 3.29 ms | 3.28 ms |
| Mostly floats | 6.20 ms | 211 ms | 0.208 ms | 0.170 ms |

The short leaf loses heavily to repeated guards and conversions. Moving its
caller loop into the same native region removes those repeated boundaries:
seven steady samples made 688,296 native leaf calls versus 168 native region
calls. The region is about 34× faster than CPython on the supported phase, while
the static version remains faster. This is boundary-placement benefit, without
evidence of an additional profile-guided code-generation gain or newly discovered
signature coverage. Native inlining is not separately isolated by this experiment.

| Region startup measurement | Fresh compiler cache | Populated compiler cache |
|---|---:|---:|
| Wrapper setup plus first whole application | 3.56 s | 0.773 s |
| Profiling, setup and first application | 5.22 s | 2.43 s |

Profiling all workloads/phases took 1.66 s. Compile-only payback was an estimated
571 applications with a fresh compiler cache, or 128 with a populated one;
profiling adds further cost. The leaf had no payback. The two compiled signatures
totalled about 85 kB of extension artifacts per mode, including runtime and glue.

Only `numeric_step` and `numeric_batch` passed the adaptive AST policy. Event
routing and text processing had zero eligible call regions under this policy.
Their string/object/library work remains a boundary-coverage limitation of this
adaptive prototype; broader statically compiled Pystachy already supports more
of these workloads. Numeric calls dominate the aggregate coverage denominator,
so the per-application results are necessary to interpret it.

Steady numeric signatures have 75% top-one and 100% top-two coverage. The
callee-wide and caller-site-conditioned choices cover exactly the same calls at
budgets of one or two compiled bodies. The one-body phase-shift probe retains
Python fallback for later floats after its integer version consumes the budget.
This supports continuing selective region experiments and measuring a broader
application corpus before investing in caller cloning or a general PIC system.

## Report contents

The JSON report includes:

- Steady inputs, unseen inputs including booleans and large integers, and a
  shift from mostly integers toward floats.
- First-application wall time, synchronous compilation/import time, and separate
  profile-plus-first-application totals for the adaptive modes.
- Isolated fresh compiler caches and caches populated by a prior leaf build.
  These describe `PYSTACHY_CACHE`, not OS cache state; cache-priming cost is
  reported separately.
- Warm whole-application samples, native/fallback counts, generated source bytes
  and extension artifact bytes. Artifact size includes runtime and ABI glue.
- Estimated applications needed to amortize compilation from measured
  whole-application savings; no payback is reported when a mode saves no time.

## API and guards

The selected call graph can be expressed without annotating the original code:

```python
from tools.adaptive import specialize

def numeric_step(x, i):
    return x + (i % 7) * 3

@specialize(warmup=3, max_variants=2,
            helpers={"numeric_step": numeric_step})
def numeric_batch(x, n):
    for i in range(n):
        x = numeric_step(x, i)
    return x

numeric_batch(3, 4096)
numeric_batch(0.5, 4096)
report = numeric_batch.adaptive_stats()
```

The mapping names the bindings used by callers. Every reachable helper must be
an ordinary Python function, and every member must pass source/code matching and
the same pure scalar AST checks. Calls must directly name supplied helpers, use
all positional arguments and form an acyclic graph. The wrapper rejects local
shadowing, callbacks, keyword helper calls, recursion and closures. Helpers are
renamed privately in the generated module; the original functions are retained.

Each native entry checks every member's code identity, each caller's helper
binding, and any builtin `range` binding using that function's own namespace.
Rebinding a helper or replacing its code therefore routes the call to ordinary
Python before native code starts. Calls under tracing/profiling, from other
threads, or with unsupported scalar inputs also use Python.

Checked native overflow and division errors can replay the original region.
Replay is permitted only because the entire transitive graph is verified pure;
allowing arbitrary helper effects would make replay incorrect. As with the leaf
prototype, the contract covers values and scalar types, not Python object
identity or preservation of native calls as Python frames.

## Profile admission and fixed budgets

`max_profiles` bounds replaceable signature counters independently of
`max_variants`, which bounds lifetime compilation attempts, including failures.
The profile table defaults to `max(8, max_variants)`. When full, it replaces the
least frequent resident signature and resets that signature's warmup count. This
lets a later hot signature warm up after rare signatures arrived first. Reported
signature counts describe calls since admission, not historical totals.

Profile eviction does not evict native variants or replenish compilation
attempts. A one-variant budget that compiles integers first leaves a later float
phase in Python; the controller explicitly checks this case. There is no claim
of adaptive variant replacement or recompilation after the budget is exhausted.

An integer/float helper already fits the default two-variant cache. Compiling
its caller and helpers together can remove repeated Python/native boundaries,
but that result alone demonstrates no additional type-discovery benefit.
