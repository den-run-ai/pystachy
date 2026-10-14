# Online callback identity specialization

This follow-up to [the shlex experiment](stream-online.md) targets an uncertainty
that survives ordinary AOT: which function an erased `Callable` will invoke.
The callback's argument and result types are already known. Its identity comes
from a mutable list at runtime. Knowing that identity lets the compiler inline
its body through the original `bisect_left` search loop.

The workload searches 1,024 text records by field length, with 509 queries per
batch. `lib/bisect.py` is unchanged. This is a text-record indexing workload,
not a repeated scalar arithmetic kernel. It is deliberately controlled; it does
not establish how often this callback distribution occurs in applications.

## Compiler and runtime changes

- The existing online call-site path now accepts one unannotated parameter whose
  inferred type is `Callable`, with an integer result. It still compiles a whole
  function and its ordinary helper chain through typed IR and LLVM.
- After the baseline is compiled, eligible immutable top-level callback
  singletons are registered with the native runtime. Eligibility requires exact
  matching annotated parameter and result types, so replacing an adapter cannot
  remove its argument/result conversions. Generic, variadic and coercing
  callbacks remain generic.
- The runtime observes the **exact Callable object pointer**, not only a code
  address. At call 100, a target with at least 90% share triggers the existing
  synchronous native compiler subprocess and image loader. Closures and bound
  methods retain their environments on the fallback path. There is no source
  rewriting of the callback, search function or standard-library algorithm.
- The child verifies the baseline adapter table and shared singleton identities,
  compiles the same search body for the selected function identity, and imports
  the running host's globals. Arguments execute once; failures and exceptions
  never replay a call. The entry guard runs on every call.

This extends runtime feedback beyond class tags: all named callbacks in the
benchmark have the same `Callable[[Record], int]` signature. The runtime learns
which function is common and passes that information to the normal compiler.
It is callback identity specialization, not a broader dynamic Python executor
or branch-path tracing. Possible callback bodies must already be in the source. A different AOT compiler
could precompile guarded variants of those bodies. This comparison is with
Pystachy's existing generic AOT, not a claim that runtime compilation can do
something that no AOT design could ever do.

The existing limits remain: Linux AOT host, one pointer argument, integer result,
16 sites, one compilation attempt per site, first-window selection, synchronous
compilation and process-lifetime image retention. The callback registry is
bounded to 64 identities; excess identities safely use generic execution.

## Separate runtime-inlining control

`PYSTACHY_ONLINE_INLINE_RUNTIME=1` lets LLVM inspect selected runtime helper
bodies while compiling a loaded image. This is a separate experimental option,
included in the host/child manifest. Default online compilation is unchanged.

The importer uses LLVM's [`available_externally` linkage](https://llvm.org/docs/LangRef.html#linkage-types):
public bodies can inline, while remaining calls still resolve to the host.
The index and integer-division helpers separate their error branches into
exported cold, non-inlined host functions. This allows their hot bodies to
inline without copying exception-message storage.

The importer copies **no runtime data definitions**, including immutable constants and
string hash caches. Bodies referencing data or unsafe private helpers are
excluded. Private helper addresses may not escape. Allocation, GC, exception
state and other rejected operations remain host calls. This restores a subset
of runtime inlining, not full AOT parity. Importing the full runtime would create
incorrect duplicate state.

## Measurement design

`tools/bench_callback_online.py` compares four independently built programs:

| Variant | Information available to the optimized search |
| --- | --- |
| Generic AOT | Erased Callable signature; runtime callback |
| Online, host imports | Callback learned during execution; runtime calls cross the image boundary |
| Online, runtime inlining | Same learned callback; eligible runtime helper bodies also available |
| Concrete AOT control | Named callback given directly to the same search body |

The generic/online fixture contains no concrete search control. The runner
changes only the outer dispatch function to create the concrete control and
asserts that the search AST is unchanged. Host IR inspection requires exactly
one generic search body and a runtime observer; loaded-image inspection records
the generated native entry. Ordinary pre-execution ORC JIT controls are separate.

Every fresh measured process executes 200 cold, 50,000 warm, 40 distribution-shift
and 50,000 recovery calls. Changed callbacks include a second named function and
a closure. Each online process should install once, with 100,108 loaded calls
and 132 fallbacks (99 warmup plus 33 changed callbacks). Timed calls check exact
phase checksums. Separate untimed runs compare 2,036 individual search positions
with CPython, spanning generic, loaded, changed-target and recovery execution.

The normal compiler runtime-bitcode cache is populated by the host builds;
these are fresh application processes and fresh specialization images, not
empty compiler-cache measurements.

Samples rotate variant order and pin one CPU. Whole-process wall and inclusive
CPU include the compiler subprocess. Phase clocks separate warm execution;
compilation and loading have independent runtime counters. The estimated
compile-cost break-even assumes the measured stationary primary-only warm
rate; it is not a universal workload threshold. Exact inputs, source/binary
hashes, commands, output and raw samples are retained in the measurement report.

## Reproduction

```sh
export PYSTACHY_LLVM=/path/to/llvm/bin
make
make callback-online-check
python3 tools/bench_callback_online.py \
  --compiler "$PWD/pystachy" --online-compiler "$PWD/pystachy" \
  --output build/callback-online-results.json
python3 tools/bench_stream_online.py \
  --compiler "$PWD/pystachy" --online-compiler "$PWD/pystachy" \
  --output build/shlex-runtime-inline-results.json
```

The callback fixture requires no closed/reference-union flags. Use
`PYSTACHY_ONLINE=1 PYSTACHY_FEEDBACK_FUNCTION=search` when building its online host,
and set `PYSTACHY_ONLINE_COMPILER` to the same native compiler path at build and
execution. The runtime-inlining option must likewise match at both times.

## Results and validation

Validation:

- Full native JIT/AOT corpus: **2,859 passed, zero failures** after the final
  runtime changes.
- Final compiler IR agrees across hosted and two native compiler generations:
  **394,644 lines**. Runtime IR fixed point: **10,996 lines**.
- Ten callback integration cases exercised with hosted/native host compilation
  and a native child, with runtime imports and runtime inlining: 40 passing
  executions. This includes exact `bisect_left`/`bisect_right` positions, callback
  changes, closures, bound methods, generic adapter contracts, late registration,
  source mismatch, exceptions without replay, live globals and GC stress.
- Eight existing stream-online integration tests passed; six import safety tests
  passed, including LLVM verification and proof that a helper actually inlines.
- All **339 runtime signatures/effects** agree. Strict C warnings, Ruff and
  whitespace checks pass. CI includes both callback online modes and import tests.

[Raw callback measurements](benchmarks/callback-online.json): seven rotated,
CPU-pinned samples on Linux x86-64 / LLVM 18.1.3, after local verification jobs
finished. Times are median seconds:

| Mode | Warm 50,000 batches | Whole process, 100,240 batches |
| --- | ---: | ---: |
| Generic AOT | 0.597 | 1.193 |
| Online, host imports | 1.572 | 3.164 |
| Online, runtime inlining | **0.334** | **0.992** |
| Concrete AOT control | 0.332 | 0.668 |
| Ordinary generic ORC JIT | 1.175 | 2.450 |
| Ordinary concrete ORC JIT | 1.126 | 2.367 |

The paired generic/online-inline ratio is **1.79× warm** (range 1.59–2.00)
and **1.19× whole-process** (1.14–1.25). All seven whole-process pairs favored
the online-inline variant, including its synchronous compilation cost. These
ratios are medians of paired ratios, not ratios of the table's medians. The
three ordinary JIT controls still retain runtime call boundaries; their small
concrete gain is not evidence against the AOT headroom.

Online-inline compilation cost was median **0.327 s**; its stationary warm-rate
estimate pays back compilation/loading after about **63,007 batch calls**
(each batch contains 509 searches), in addition to the first 99 warmup calls.
The host-import-only online mode had no payback and was substantially slower.
The concrete AOT control remains faster overall because it pays no runtime
compilation cost.

Every timed online process recorded exactly **100,240 calls, one installation,
100,108 loaded calls and 132 fallbacks**. Each separate exact-position check
validated 2,036 positions including loaded execution, named-target changes,
closure fallback and recovery. Source and compiler hashes remained unchanged.

Native inspection explains the result: the generic AOT search retains an
indirect callback, and the loaded specialized search has none. The
host-import-only image still calls `pys_floordiv` and `pys_list_get` inside the
binary-search loop. The runtime-inline image has neither call: it contains the
index/length operations directly and imports the host's cold error functions.
The concrete AOT phase loop still repeats the 509-query search each batch;
its result was not hoisted out of the measurement loop.

### Rechecking the shlex boundary

The [paired shlex control](benchmarks/shlex-runtime-inline.json) uses the same
final compiler and five rotated, CPU-pinned samples. Each process parses the
original 9,440-byte, 544-token input 8,240 times, including the stream change.
Median seconds:

| Mode | Warm 4,000 parses | Whole process, 8,240 parses |
| --- | ---: | ---: |
| Generic AOT | 2.153 | 4.421 |
| Online, host imports | 2.833 | 6.269 |
| Online, runtime inlining | 2.652 | 6.270 |
| Concrete AOT control | 2.053 | 4.288 |

Runtime inlining improves warm execution over host-import-only online code by
a paired median **1.09×** (range 1.04–1.18). The whole-process ratio is only
**1.03×** (0.95–1.09), with compilation rising from median 0.385 s to 0.686 s.
Online-inline remains slower than generic AOT in every pair: generic/online-inline
is **0.80× warm** and **0.71× whole-process**. Concrete AOT provides no consistent
warm advantage: paired generic/concrete median **1.00×**, range 0.98–1.16.

Native inspection confirms that selected runtime calls disappear, including
all 12 static `pys_eq` call sites, while allocation and many string operations
still resolve to the host. Both images define only the three online entry
exports and no runtime storage. Every timed online process installs once and
records 8,111 loaded calls and 129 fallbacks; checksums match CPython and source
hashes remain stable. The raw report also contains one ordinary JIT control per
variant, which is insufficient for a timing-distribution claim.

This isolates a measurable benefit from this subset of runtime inlining; it
does not explain the entire shlex slowdown or restore whole-program AOT parity.
The original workload still offers little useful specialization headroom.

The callback result is positive for one controlled stdlib workload and this
bounded online tier. It does not establish general Python compatibility, arbitrary
unsupported-type execution, production callback skew or a universal speedup.
