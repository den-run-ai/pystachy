# CPython support surface

Pystachy's fast core is concrete values, predictable storage and typed operations. More
Python compatibility can build on that core, but the same syntax can also select boxed
storage, dynamic dispatch, suspended frames or exception unwinding. These diagrams show
what to preserve, where to measure costs, and which CPython behaviors remain gaps.

**Recommendation:** preserve concrete typed execution as the performance baseline. Keep
supported generators, exceptions and class features; reduce the machinery they require.
Keep dynamic `Any` and promoting ints experimental and opt-in while their correctness and
application-cost gates remain open, and keep their bookkeeping out of code that cannot
observe it. The useful boundary is the representation and operation, not a blanket ban on
a Python syntax family.

**Snapshot:** 28 October 2026 (Pacific), main
[`9b50a385`](https://github.com/den-run-ai/pystachy/commit/9b50a3851ed66c792c07f4c7cbaabd6af04b6d8e),
before the v0.1.0-alpha.4 release. The first version of this guide described main
[`f5a09d4`](https://github.com/den-run-ai/pystachy/commit/f5a09d4223139d7255e31051be97fc509e1ca1fe)
(v0.1.0-alpha.3, 23 October).
This is an engineering guide to the existing surface, not a new language mode or a change
to the support policy. The [language reference](language.md),
[compatibility reference](language/compatibility.md), [dynamic `Any` contract](dynamic-any.md)
and [promoting ints](python-int.md) define the exact supported forms. Issue status below was
checked for this snapshot; measurements linked below retain their own revisions. No new
timings were collected for this guide.

This snapshot includes [#981's promoting-int identity repair](https://github.com/den-run-ai/pystachy/pull/981).
The identity-scope [#973](https://github.com/den-run-ai/pystachy/pull/973) and scalar dict-hash
[#980](https://github.com/den-run-ai/pystachy/pull/980) results below describe open candidates,
not code in this snapshot. Follow the [release tracker](https://github.com/den-run-ai/pystachy/issues/976)
for their integration and final release gates; this guide does not declare alpha.4 ready.

## Reading the colors

| Label | Meaning | Engineering guidance |
|---|---|---|
| **G / green — KEEP** | Supported paths with concrete native representations or direct lowering | Preserve these paths and their performance when extending compatibility. |
| **Y / yellow — BOUND** | Supported features with restrictions or workload-dependent costs | Keep the feature; measure execution, memory, compilation and IR separately. |
| **Y / yellow — PROTO** | Experimental implementation with its own bounded contract | Evaluate the named APIs and consumers; support and cost gates are still open. |
| **R / red — OUT** | The named behavior has no native implementation/contract | Use a supported form or explicit interop; assess an extension against a real consumer. This is not a correctness-bug or removal label. |
| **R / red — FIX** | A known accepted-program correctness gap | Repair the result, effects or first exception before relying on that behavior. A compile-time rejection is a different boundary. |

Green is a design target, **not a promise that every program beats CPython**. Yellow does
not mean a feature is experimental unless it says **PROTO**, and red does not mean its
entire enclosing feature should be removed. The areas are schematic, not coverage percentages.
Read **support status**, **representation** and **measured cost** separately. A yellow
operation can outperform CPython; a green operation can still have high algorithmic cost.
The red examples are not an exhaustive inventory of deviations.

## 1. The native subset to preserve

![Nested support map: a green concrete native core inside a yellow bounded Pystachy surface, with local red correctness gaps and a separate red region for unavailable native CPython features.](images/support-surface.svg)

The green region includes the compiler's own style of code: typed functions, inferred
specializations, concrete fields, numeric loops and homogeneous containers. Strings,
dictionaries, classes, generators and exceptions are useful parts of the supported language;
their broader contracts need more machinery than a scalar loop.

The core classification follows the [typed-IR fast paths](typed-ir.md#optimizations)
and concrete storage layouts. The [microGPT snapshot](../bench/microgpt/README.md#measured-snapshot)
and [integer-list memory measurement](performance.md#start-up-and-memory) are examples
of measured consumers of those paths, at the revisions recorded in their reports.

The core still has [numeric domain limits](language/compatibility.md#numbers): in a module
that does not opt in to promoting ints, an integer overflow raises `OverflowError` instead
of producing CPython's arbitrary-precision result (a masked product such as
`(k * 0xCC9E2D51) & 0xFFFFFFFF` keeps CPython's result), and unboxed NaNs lack CPython's
object-identity behavior in container membership/comparisons. Green does not establish
CPython equivalence even when every operand has a concrete type.

Two per-module **experimental opt-ins** extend this surface, and a module cannot take both:

- `# pystachy: python-int` gives the module CPython's `int` ([promoting ints](python-int.md)).
  A value that fits stays an inline 64-bit word; a larger one is an immutable digit array.
  Other modules keep checked 64-bit ints, so a value past 64 bits raises `OverflowError` at
  the [documented boundaries](python-int.md#64-bit-boundaries) where CPython continues.
  Explicit [`mpz`](mpz.md) values are a separate arbitrary-precision API.
- `# pystachy: dynamic-any` makes `Any` a runtime-typed value ([dynamic `Any`](dynamic-any.md)).
  A module without the opt-in comment uses `Any` for concrete inference/specialization.

The boundary is not simply whether the hot function contains an `Any` annotation. At this
snapshot, a program in which any module opts in to dynamic `Any` tracks numeric identity in
every module's typed code, and gives every module's typed dictionaries Python's hash/probe
scheme ([section 4](#4-where-compatibility-adds-cost)). A typed loop that only imports
`tomllib` measured 9.6× slower than alpha.3 before
[#974](https://github.com/den-run-ai/pystachy/pull/974) and 1.84× slower with it; the draft
[#973](https://github.com/den-run-ai/pystachy/pull/973), which tracks identity only where it
can be observed, measured within alpha.3's range ([#969](https://github.com/den-run-ai/pystachy/issues/969),
[identity-scope report](reports/identity-scope-performance-2026-10-28.md)).

Preserve programs that already compile correctly. This map does not propose removing
generators, exceptions, unions or other accepted features to make the compiler smaller;
see the compatibility rule in [AGENTS.md](../AGENTS.md#start-with-the-current-tree).

## 2. Syntax is only the first layer

| Python syntax or construct | Label | Current native surface and the important boundary |
|---|---|---|
| Arithmetic, boolean expressions, `if`, `while`, `for`, `break`, `continue`, `return` | **G KEEP** for concrete operands; **Y PROTO** for promoting ints | Checked 64-bit integers by default, and native floats/bools; changing operands to unions or `Any` changes lowering. CPython's arbitrary-precision `int` is a per-module opt-in ([promoting ints](python-int.md)); `complex` is **R OUT**. |
| `def`, direct calls, keyword/default arguments, templates | **G KEEP** for known signatures | Inference specializes supported unannotated functions. Unrestricted runtime argument expansion and arbitrary builtin function values are outside this contract; see [calls and templates](language/typing.md#function-and-method-templates). |
| List/dict/set displays, comprehensions, indexing and slicing | **G KEEP** for concrete supported types; **Y BOUND** for mixed storage | Syntax is supported; element/key types determine layout, hashing, boxing and callbacks. Scalar-union locals and containers have different costs. |
| Assignment, unpacking, `:=`, closures, `global`, `nonlocal` | **G KEEP** within the static contract; **Y PROTO** for dynamic identity tracking | These forms are supported. Dynamic numeric identity can add box slots/snapshots, also in typed modules of a program that uses dynamic `Any`. #981 extends companions to promoting-int bindings, calls, fields, optionals, closures and defaults while values fit int64. Remaining container/generator identity boundaries are **R FIX**, not reasons to remove assignment syntax. |
| Strings, bytes, f-strings, formatting | **Y BOUND** | Supported operations have different copying, Unicode and formatting limits. A read of an accumulating string can force a later append to copy; use the [performance contract](performance.md#costs-to-watch). `bytearray`, `memoryview` and binary files are **R OUT**. |
| Classes, dataclasses, properties, single inheritance | **G KEEP** for concrete fields/direct methods; **Y BOUND** for broader dispatch | Supported hierarchy and reflection forms have explicit limits. Multiple inheritance, general metaclasses and runtime-named attribute-value lookup remain **R OUT**. |
| Generator expressions and `yield` / `yield from` | **G KEEP** for direct consumer lowering; **Y BOUND** for suspended generators | A direct reduction can avoid a general generator object. A stored generator, delegation, `send`, `throw` and `close` need frames and cleanup; see the [semantic paths](#3-generators-exceptions-and-the-object-model). |
| `try` / `except` / `else` / `finally`, `raise`, `with` | **Y BOUND**, supported | Local handlers and cross-function unwinding have different costs. `except*`, exception groups and full traceback APIs remain **R OUT**. |
| `import`, packages and module initialization | **Y BOUND** | Sources are resolved at compilation; supported Python-module initialization runs on first executed import. This does not supply arbitrary runtime module discovery or CPython extension compatibility; see [module rules](language/modules.md). |
| `match`, native `async def` / `await` / `async for` / `async with` | **R OUT** | Not part of the supported native language. Concurrency hosted by CPython through an extension is a separate [interop path](concurrency.md). |

The [execution reference](language/semantics.md) describes the supported statements,
expressions, generators and object protocols. A recognized or unused piece of syntax
does not establish that a program needing it can execute natively.
Likewise, an import count is not an API-coverage score: native library implementations,
adapted ports and calls into embedded CPython are separate support paths. Check the
[library API inventory](../lib/README.md) and [explicit CPython bridge](ffi.md).

## 3. Generators, exceptions and the object model

![Three rows compare direct iteration with suspended generators, local handlers with unwinding, and concrete fields with hierarchy dispatch. Separate red boxes identify unavailable APIs and accepted deviations; generator yield channels that cannot become Any values are rejected at compile time and labelled separately.](images/support-semantics.svg)

Arrows connect **supported paths with additional implementation obligations**. The red
column records separate boundaries, not the next stage of execution. In particular:

- **Generators:** functions and methods that yield, delegation, and the documented
  `send` / `throw` / `close` forms already work. Real generators use LLVM coroutine
  operations in the [typed IR](typed-ir.md#instructions-and-control-flow). Their frames,
  live references, resumption and cleanup need validation. Some consumers materialize
  inputs; dropped suspended generators are not generally closed. Through dynamic `Any`,
  ranges, builtin and user iterators and generators with boxable yields iterate lazily
  and share their state ([iteration](dynamic-any.md#iteration),
  [#951](https://github.com/den-run-ai/pystachy/pull/951)). An object that defines only
  `__getitem__` still raises `TypeError` when iterated through `Any`, where CPython iterates
  it by index (**R FIX**, [#773](https://github.com/den-run-ai/pystachy/issues/773)), and
  `send` / `throw` / `close` through `Any` are not provided. A generator whose yields
  cannot become `Any` values (aliased typed mutable containers) is rejected at compile
  time where it would become one: a compilation restriction, not an accepted-program gap.
- **Exceptions:** keep ordinary exceptions and cleanup. Local raises can branch to a
  handler; covered calls that may raise lower to LLVM `invoke` and native unwinding.
  Repeated cross-function throws are a runtime cost, not an unsupported construct.
  A call that succeeds on a particular run can still need exceptional edges and cleanup
  in its IR. A local raise can still construct an exception; green does not mean zero cost.
  See [exception lowering](typed-ir.md#exception-lowering) and
  [runtime deviations](language/compatibility.md#errors-and-control-flow).
- **Objects:** known fields and direct calls retain typed layouts. Single inheritance,
  overrides, properties and supported reflection are implemented, with class analysis
  and dispatch costs. Arbitrary runtime attribute names returning arbitrary values,
  dynamic attribute hooks and general metaclasses require a larger object model than
  the shipped one; see [reflection](language/semantics.md#reflection).

## 4. Where compatibility adds cost

![Representation graph separates native, closed-union and experimental Any storage, their execution costs, and compiler/IR pressure in the shared pipeline. Recursive JSON uses closed union boxes, not dynamic Any; an imported opt-in module can activate typed identity work.](images/support-costs.svg)

All three paths compile through typed IR and LLVM in both JIT and AOT. Dynamic `Any` is
not an interpreter fallback or a tracing JIT. Narrowing can recover a typed payload
operation, but does not transparently change an aliased container's layout, remove its
boxes, or solve identity across every typed boundary. Promoting ints, not drawn in the
figure, are a further representation of the same integer syntax (table below).

The [recursive JSON prototype](json-prototype.md#values-and-ownership) is a closed recursive
union representation, separate from dynamic `Any`; it does not require the `dynamic-any`
pragma. Their boxes and dispatch contracts differ. JSON scanning/copying costs can affect
both paths, so more dynamic-type specialization is not automatically the remedy.

| Added surface | Label and cost dimension | Current mechanism, evidence and boundary |
|---|---|---|
| Closed scalar/value unions | **Y BOUND — execution / heap** | Numeric locals can use split tag/payload slots, while union-valued container items can still allocate boxes. [Union costs](union-value-costs.md), [typed-IR optimizations](typed-ir.md#optimizations), [#758](https://github.com/den-run-ai/pystachy/issues/758). Keep concrete containers for homogeneous hot data where the program's semantics permit it. |
| Promoting ints (`python-int` opt-in) | **Y PROTO — execution / heap / IR** | Two-word values: inline checked 64-bit paths while values fit, runtime calls and immutable digit arrays past 64 bits. Recorded 64-bit loops match checked int64 (`lcg32`), values crossing 2⁶³ stay inline where they fit, and big values ran within 0.83–1.31× of CPython ([measurements](python-int.md#measurements)). Values narrow at the [64-bit boundaries](python-int.md#64-bit-boundaries), raising `OverflowError` where CPython continues; containers of ints hold 64-bit ints in a program that uses dynamic `Any`. [#907](https://github.com/den-run-ai/pystachy/issues/907). |
| Dynamic `Any` values, heterogeneous records and JSON/TOML | **Y PROTO — execution / heap** | Runtime type/payload boxes, boxed collection items, hashing, dispatch and GC enable useful mixed data. Narrowed payload operations can avoid generic arithmetic; this does not make every dynamic pipeline fast. [Representation and measurements](dynamic-any.md#representation), [#780](https://github.com/den-run-ai/pystachy/issues/780). |
| Numeric identity across dynamic and typed code | **Y PROTO — execution / IR; R FIX — parity** | Box provenance, snapshots and joins preserve copies, globals, closure cells, known-dynamic displays, typed parameters/defaults/returns, instance fields, class attributes and `list[int]`/`list[float]` items. Scalar-only proofs and lazy field sharing avoid some boxing. In a program where any module opts in, every module tracks identity: numeric fields gain companion slots and functions gain box slots and companion arguments ([#969](https://github.com/den-run-ai/pystachy/issues/969)). [#981](https://github.com/den-run-ai/pystachy/pull/981) extends companions to promoting-int bindings, calls, fields, optionals, closures and defaults: the companion carries the int64 box while the value fits and is null for wider values. Bookkeeping does not narrow or reject wide typed values; an actual wide crossing into `Any` still raises `OverflowError`, including field reads and dynamic-list displays. Typed tuple/dict/set items, optional/union list items, typed numeric generator yields and some constant folds remain gaps. [Identity contract](dynamic-any.md#representation), [#858](https://github.com/den-run-ai/pystachy/issues/858). |
| Typed dictionaries in a program that uses dynamic `Any` | **Y PROTO — execution** | So that dynamic comparisons can look keys up across layouts, every module's typed dicts take Python's hash/probe scheme (the `!` key kind of `gen_key_kind` in `src/pystachy_compiler/containers.py`), whose str and int key hashes `runtime.c` computes out of line. The adapted [`json_loads` benchmark](reports/json-loads-performance-2026-10-28.md) discards its `json.loads()` results, so its timed loop runs json's typed decoder in such a program; its AOT loop remained slower than alpha.3 in all seven pairs after #974. Candidate [#980](https://github.com/den-run-ai/pystachy/pull/980) inlines compatible scalar hashes and guarded lookup without changing hashes, table layout or probe order; it retains the program-wide policy and recovers only part of the measured instruction excess ([section 5](#5-measured-examples-with-their-limits)). Typed lookups also keep generic out-of-line entry points ([#894](https://github.com/den-run-ai/pystachy/issues/894)). |
| Cross-type comparisons through `Any` | **R FIX — parity; Y PROTO — compiler work** | Guarded concrete adapters now execute many previously skipped bodies, including differently typed builtin container fields. An unsupported body/field shape can still fall back without executing the method. [Deviations](dynamic-any.md#deviations), [#803](https://github.com/den-run-ai/pystachy/issues/803). Fix the missing semantics before treating this as stable. |
| Typed container ↔ `Any` crossings and generator channels | **Y PROTO — compile-time restrictions** | Incompatible mutable layouts, and generator yield channels that hold them, are rejected rather than copied or reinterpreted. The dynamic-`Any` opt-in manifest lists four programs for JIT and AOT (eight entries, [#777](https://github.com/den-run-ai/pystachy/issues/777), [#782](https://github.com/den-run-ai/pystachy/issues/782)); its other 200 entries cover 100 programs whose entry module already opts in to promoting ints, which cannot also opt in to dynamic `Any` ([#907](https://github.com/den-run-ai/pystachy/issues/907)). [Exact exception manifest](../tools/dynany_optin_exceptions.json). This is separate from an object with only `__getitem__` raising `TypeError` when iterated through `Any` (**R FIX**, [#773](https://github.com/den-run-ai/pystachy/issues/773)). |
| Larger class hierarchies | **Y BOUND — compiler work / IR** | Comparison emission and specialization have already been reduced; residual class-pair analysis remains separate from field-error-message IR growth. [#625](https://github.com/den-run-ai/pystachy/issues/625), [#786](https://github.com/den-run-ai/pystachy/issues/786). Do not describe the old quadratic emitted dispatcher as the current implementation. |
| More dynamic classes and operation keys | **Y PROTO — compiler work / IR / execution** | Class-id switches have replaced the old linear field-dispatch chain. Duplicate method lookup, classes × attributes IR, dispatcher regeneration and deterministic cost guards remain. [#799](https://github.com/den-run-ai/pystachy/issues/799). |
| Speculation, widening and retries | **Y PROTO — compiler work / state safety** | Retries retain fresh compiler instances; the unsound catch-and-continue experiment was not merged. State checks and concrete leak fixes have landed, but complete semantic rollback and cheaper safe retries remain work. [#801](https://github.com/den-run-ai/pystachy/issues/801), [#767](https://github.com/den-run-ai/pystachy/issues/767). |
| Deep dynamic list/dict displays | **Y PROTO — compiler work** | Memoized dry traversal removed the exponential timeout. Residual superlinear work and deterministic scaling bounds remain; the historical timeout is not today's behavior. [#781](https://github.com/den-run-ai/pystachy/issues/781). |
| Text, regex and JSON scanning | **Y BOUND / PROTO per API — execution / heap** | Prefix copying, per-character scanning and regex miss paths can dominate even with static types. These are independent of type-dispatch optimization. [String costs](performance.md#costs-to-watch), [JSON prototype](json-prototype.md), [#861](https://github.com/den-run-ai/pystachy/issues/861), [#862](https://github.com/den-run-ai/pystachy/issues/862), [#345](https://github.com/den-run-ai/pystachy/issues/345). The adapted [`json_repair`](../ports/json_repair/PORT.md) port is merged; its bounded accumulator removes the measured repeated-prefix bottleneck, with recorded PyPy and CPython-memory tradeoffs ([measurements](../bench/json_repair/ACCUMULATOR.md)). |
| Long-lived allocation and caches | **Y BOUND — retained heap / RSS** | Conservative, batched collection can retain more memory despite fast scalar execution. A short checksum/timing run does not prove service-lifetime acceptance. [Memory behavior](performance.md#start-up-and-memory), [#202](https://github.com/den-run-ai/pystachy/issues/202), [#615](https://github.com/den-run-ai/pystachy/issues/615). |

The sharpest boundaries are **concrete versus boxed storage**, **known versus dynamic
dispatch**, **direct iteration versus suspended state**, and **ordinary control flow
versus repeated unwinding**. The last two are supported capabilities to retain; the
red comparison/identity cases are correctness work, not performance trade-offs to accept.

## 5. Measured examples, with their limits

These are **historical measurements**, not a fresh ranking of the snapshot above. Each row
compares the same workload within its own report; do not combine ratios across rows.
The linked reports give environment and validation details; sampling differs by experiment.

| Boundary | Recorded result | What it establishes |
|---|---|---|
| Useful concrete workload | At `d3fbfc6f`, adapted microGPT's 100-step training phase took **15.220 s in adapted CPython vs 0.896 s in AOT** (17.0×); AOT build was separately **1.802 s**. [Report](../bench/microgpt/README.md#measured-snapshot). | A concrete native consumer is worth protecting. This is an adapted application, a phase timing and a historical compiler, not unrestricted Python or end-to-end compile-plus-run speed. |
| Concrete vs union container | At `2438e7e0`, one million integers in `list[int]` vs `list[int \| str]`: construction **9.197 vs 19.043 ms**, scan **0.775 vs 2.392 ms** (process CPU, excluding startup); peak managed heap **13.0 vs 33.1 MiB** from separate runs. [Report](union-value-costs.md#boxing-measurement). | Identical integer payloads can incur extra allocation and indirection solely from storage. Heap peak is not retained live memory or RSS. |
| Narrowed vs generic dynamic arithmetic | At `bc79f24c`, summing a million items took **1.1 ms typed**, **3.2 ms with narrowed Any items**, **17.8 ms with an Any accumulator** (processing CPU); CPython's generic case took **30.5 ms**. [Report](dynamic-any.md#measurements). | Yellow can beat CPython while remaining much slower than the native core. Payload narrowing avoids arithmetic dispatch without removing the container's boxes. Later boxing/identity changes mean these are not current-main ratios. |
| Compiler work vs emitted IR | At `554f3d1 → 570eb4e`, the ordinary-class comparison with 30 subclasses and `other: object` went from **962 → 62 method instances**, **197,808 → 26,898 IR lines**, and AOT build **32.4 → 1.9 s**. [#792 measurements](https://github.com/den-run-ai/pystachy/pull/792). | Sharing specialization can preserve the feature while reducing compiler/backend cost. Quadratic frontend class-pair analysis remains ([#625](https://github.com/den-run-ai/pystachy/issues/625)); smaller IR alone proves no execution-speed gain. |
| Typed code beside an opt-in import | At main `5bd492b3`, a 30-million-step typed `Counter` loop that also imports `tomllib` took **215.6 ms** AOT against alpha.3's **22.4 ms** (9.6×); with #974's changes **41.3 ms** (1.84×), with draft #973 **22.4 ms** (medians of nine CPU-pinned runs). [Report](reports/identity-scope-performance-2026-10-28.md). | A program-wide policy taxes typed code that cannot observe it, and scoping it recovered that cost on this workload. #981 repairs the promoting-int correctness blocker recorded in that historical report. #973 remains a candidate outside this snapshot; its newer combined-source results also overlap alpha.3's range. This is not a JSON, JIT start-up or application measurement. |
| Compatible hashing in typed JSON decoding | Candidate [#980](https://github.com/den-run-ai/pystachy/pull/980) at `86cedeec`, and the combined [#973](https://github.com/den-run-ai/pystachy/pull/973) source at `9fd73f34`, record **1,405.530M → 1,351.341M instructions** versus main `5b49dcfa`; alpha.3 records **1,300.339M** (300-loop callgrind workload). | Removes **51.5%** of main's excess, but remains **3.92%** above alpha.3. Separate 2,000-loop paired timing medians for the combined candidate remain **+3.12% AOT / +5.68% warm JIT** versus alpha.3, with overlapping shared-host ranges. Instruction counts establish partial recovery; small timing differences are inconclusive. These are candidate results, not a merged release guarantee. |
| Promoting ints at 64-bit width | Recorded 26 October 2026 with `bench/integers` (AOT, medians of five): `lcg32` took **0.005 s** with promoting ints and with checked int64 (151× and 152× CPython's speed); `cross64`, whose values cross 2⁶³, took **0.174 s** against `mpz`'s **0.419 s**. [Measurements](python-int.md#measurements). | The opt-in's inline paths keep 64-bit work at checked-int64 speed on these kernels. They do not measure programs that mix promoting ints with dynamic `Any` or cross many 64-bit boundaries. |
| Runtime support that plain programs do not use | From `5bd492b3` to `9b0cedc9`, pruning unreachable promoting-int and dynamic-identity runtime paths shrank four plain executables by **12.6–29.3%** (`print(1)`: 41,416 → 29,264 bytes) and cut the `spectral` and `richards` builds by **19.3%** and **17.6%**. [Report](reports/aot-plain-runtime-2026-10-28.md). | Opt-in features need not cost programs that do not opt in. AOT still optimizes the runtime with each program ([#706](https://github.com/den-run-ai/pystachy/issues/706)); no execution regression was confirmed. |

No matched measurement here establishes that all generators or exceptions are slow.
Their yellow classification describes machinery and workload sensitivity. Use the maintained
`exception_local` / `exception_unwind` [kernels](extended-performance.md) to compare throw
frequency and call boundaries; measure a real generator consumer before changing its lowering.

## 6. What to preserve, optimize or defer

This is an engineering recommendation within the existing support policy. The linked
trackers own implementation scope and promotion decisions.

| Decision | Surface | Evidence required for a change |
|---|---|---|
| **Preserve** | Concrete storage, typed calls, direct loops and narrowing fast paths | Correctness plus typed controls for execution, allocations and compiler cost, including programs importing opt-in modules: for example, a deterministic check that such an import leaves a typed class's layout and box calls unchanged (#969). |
| **Keep and optimize** | Supported generators, exceptions, classes and closed unions | A demonstrated consumer cost; retain effects, cleanup, aliasing and first errors. Prefer shared lowering/helpers over removing semantics. |
| **Repair before promotion** | Remaining accepted comparison, container/generator identity and `__getitem__`-only iteration gaps inside dynamic `Any` | CPython parity for the affected contract and negative controls. Preserve #981's promoting-int companion repair; wide values still have a documented `Any` boundary. #108 keeps stable opt-in separate from default-on, and #907 keeps the promoting-int prototype separate from a default switch with its own cost budget. |
| **Contain implementation cost** | Union-item boxing, Any bookkeeping, dispatch generation, class-pair analysis, speculative retries, and opt-in policies applied to a whole program (identity tracking, Python-hash dictionaries) | Allocation counts, separate frontend/backend timing, raw/optimized IR and scaling bounds. Scope a program-wide policy to the code that can observe it, with a safe fallback, as the draft #973 does for identity. Preserve verified reset/ownership boundaries (#767); the rejected #801 partial-rollback approach is not a safe shortcut. |
| **Shrink boundaries** | Promoting-int 64-bit boundaries | CPython differential tests and GC stress for each boundary removed, with the int64 fast path unchanged. Until promotion is the default (#907), an `OverflowError` can surface at a boundary far from the arithmetic that grew the value. |
| **Defer expansion until justified** | Unavailable general object/runtime facilities | A concrete consumer and an explicit contract/cost evaluation. Red OUT is not a request to remove already-supported features. |

## 7. Compatibility payoff, correctness and evidence

![Ordinal bubble map of nine representative paths. Horizontal position is implementation complexity; vertical position is runtime CPU/memory overhead excluding compilation. Circle area estimates compatibility payoff. Separate outlines identify bounded contracts or known dynamic-Any gaps, and M/S badges distinguish historical measurements from structural evidence.](images/support-payoff.svg)

The bubble map adds **compatibility payoff** to complexity versus runtime cost. The
two circle sizes mean medium or large estimated utility across useful application
patterns. They are engineering judgments, not counts of unchanged applications, working
APIs, import successes or annotations removed. A larger circle is not a measured multiple
of a smaller one. Empty cells mean no example is plotted, not that no feature belongs there.
Positions within a low/medium/high cell only separate labels. The placements and payoff
sizes are the 23 October estimates named in the figure's footer: this refresh did not
re-estimate them, and promoting ints are not plotted ([section 4](#4-where-compatibility-adds-cost)
covers their costs).

**B** denotes an implemented, documented subset with limits; it does not certify full
CPython parity. **GAP** identifies accepted-program deviations in the associated dynamic
contract. On H/I it refers to remaining comparison, identity and iteration boundaries
([#803](https://github.com/den-run-ai/pystachy/issues/803),
[#858](https://github.com/den-run-ai/pystachy/issues/858),
[#773](https://github.com/den-run-ai/pystachy/issues/773)), not a failed checksum in the
illustrated numeric scan. Correctness remains a gate regardless of estimated payoff.

**M** means a linked historical report contains matched cost measurements for that path;
**S** means structural source/test evidence without a matched cost sample here. M does
not validate the estimated complexity bin or payoff size. Neither badge establishes a
current-main performance bound. All measurements retain their original revisions.

| Key / path | Estimated payoff and consumer | Impact scope | Cost evidence / boundary |
|---|---|---|---|
| **A — Native typed core** | **Large:** numeric/application kernels | Ordinary typed code | **M:** adapted [microGPT](../bench/microgpt/README.md#measured-snapshot) and concrete [list storage](union-value-costs.md#boxing-measurement); int64/NaN limits still apply. |
| **B — Numeric-union locals** | **Medium:** mixed numeric functions | Ordinary typed code | **S:** split tag/payload [IR representation](typed-ir.md#optimizations); no matched timing sample is assigned to this bubble. |
| **C — Boxed union items** | **Medium:** heterogeneous sequences | Ordinary typed code | **M:** [one-million-item comparison](union-value-costs.md#boxing-measurement) at `2438e7e0`; peak heap is not retained live memory. |
| **D — Generator frames** | **Medium:** lazy/stateful APIs | Supported native generators | **S:** [yield/resumption/cleanup contract](language/semantics.md#generators); no blanket measured slowdown claim. |
| **E — Successful cleanup paths** | **Large:** resource/error handling | Ordinary typed code | **S:** [exception lowering](typed-ir.md#exception-lowering); successful calls can retain exceptional edges without actually unwinding. |
| **F — Repeated unwinding** | **Large:** same error semantics as E | Frequently throwing call paths | **S:** [local versus cross-function mechanism](performance.md#costs-to-watch); throw frequency changes cost, not compatibility payoff. |
| **G — Recursive JSON** | **Large:** input-selected nested values | Closed-union native prototype | **S:** [JSON API and representation](json-prototype.md#values-and-ownership); this is separate from dynamic Any and has codec/type-graph limits. |
| **H — Any, narrowed payloads** | **Large, potential:** mixed-data processing | Opt-in modules plus typed crossings | **M:** [dynamic scan](dynamic-any.md#measurements) at `bc79f24c`; remaining contract gaps and application/retention acceptance stay open. |
| **I — Any, generic arithmetic** | **Large, potential:** same mixed-data reach as H | Opt-in modules plus typed crossings | **M:** same [benchmark report](dynamic-any.md#measurements), with an Any accumulator; generic addition dispatches and boxes. |

E/F and H/I are alternative execution scenarios for overlapping semantics; their payoff
is not additive. G/H/I do not establish unchanged third-party package support. The map
contains selected implemented paths, not design estimates for unavailable native async,
general metaclasses or multiple inheritance, whose runtime cost is unmeasured.

The remaining dimensions should stay explicit instead of being folded into one score:

| Dimension | Representation | What to check |
|---|---|---|
| Compatibility payoff | Ordinal circle area | Useful consumers, executed APIs and avoided adaptations; estimate broad reach separately from verified consumers. |
| Correctness boundary | B / GAP outline | Results, effects, first exceptions, aliases and identity within the stated contract. |
| Impact scope | Companion-table scope | Ordinary typed code, a native prototype, or opt-in modules including imported-module and typed-boundary effects. |
| Compilation scaling | Separate view below | Frontend work/retries, raw/optimized IR, LLVM time and binary size. |
| Memory behavior | Separate allocation/heap/RSS observations | Allocation traffic, peak managed heap, peak RSS and repeated-use retained live memory are different quantities. |
| Evidence confidence | M / S badge plus revision | Historical matched measurements versus structural evidence; payoff estimates remain estimates in either case. |

## 8. Compilation scaling is a separate view

![Three independent zero-based bar panels reproduce historical PR 792 results: method instances 962 to 62, LLVM IR lines 197808 to 26898, and AOT build 32.4 to 1.9 seconds. The panels have different units and scales; these are not current-main timings or runtime-speed measurements.](images/support-compilation.svg)

The historical [#792 experiment](https://github.com/den-run-ai/pystachy/pull/792) uses an
ordinary base class whose comparison takes `other: object`, 30 subclasses and 40 comparison
sites, comparing `554f3d1` with `570eb4e`. LLVM was 18.1.3; AOT builds used one CPU.
The bars reproduce reported values; no new timing or confidence interval is implied.
Each panel starts at zero and has its own units and scale. Sharing specialization reduced
generated work while retaining the feature; this does not establish execution speed or
whole-compiler linear scaling.

| Remaining pressure | Measure separately | Correctness boundary |
|---|---|---|
| Class-pair analysis ([#625](https://github.com/den-run-ai/pystachy/issues/625)) | Frontend CPU and pair counts as classes/sites grow | Preserve subclass/reflected-method priority and first errors. |
| Field-error and dispatcher IR ([#786](https://github.com/den-run-ai/pystachy/issues/786), [#799](https://github.com/den-run-ai/pystachy/issues/799)) | Raw/optimized IR, LLVM CPU and code size as classes/fields grow | Preserve concrete error names and dynamic fallbacks. |
| Nested displays ([#781](https://github.com/den-run-ai/pystachy/issues/781)) | Traversal counts and frontend CPU as depth grows | Retain the fixed deep-nesting acceptance; the old exponential timeout is historical. |
| Safe retries ([#801](https://github.com/den-run-ai/pystachy/issues/801), [#767](https://github.com/den-run-ai/pystachy/issues/767)) | Restart counts and frontend CPU, separately from emitted IR | Preserve reset/ownership boundaries and existing bounded adapter controls; partial rollback was unsound. |
| AOT runtime re-optimization ([#706](https://github.com/den-run-ai/pystachy/issues/706)) | Build time and executable size per program, separately from execution | Keep runtime paths that plain programs never reach out of their executables ([pruning report](reports/aot-plain-runtime-2026-10-28.md)); opt-in programs keep the paths they use. |

For memory, the [union report](union-value-costs.md#boxing-measurement) records allocation
representation and peak heap, and the [dynamic report](dynamic-any.md#measurements) also
records peak RSS. These short processes do not establish service-lifetime retention.
Use repeated calls, explicit cache/input bounds and post-collection live-memory evidence
for [#202](https://github.com/den-run-ai/pystachy/issues/202); keep its acceptance separate
from the bubble map and from fast scalar throughput.

## Using the map

For a performance-sensitive component, start with the concrete representation that fits
its data. Keep mixed records or dynamic dispatch where needed, then cross into concrete
numeric kernels only where conversions, aliases and identity satisfy the documented
contract. Removing Python semantics or silently copying mutable values is not a fast path.

Before calling a larger surface fast enough, establish CPython output/effects first,
then measure warmed execution, allocations/retention, frontend time, LLVM time and IR/binary
size separately. Check typed-mode controls as well as the extension. The maintained
[performance guide](performance.md), [extended benchmark guide](extended-performance.md)
and [verification guide](testing.md) describe those checks. Published compute and
application results are workload evidence, not a universal green/yellow threshold.

The `Any` promotion tracker [#108](https://github.com/den-run-ai/pystachy/issues/108)
keeps **stable bounded opt-in** separate from **default-on**, and the promoting-int tracker
[#907](https://github.com/den-run-ai/pystachy/issues/907) keeps its prototype separate from
a default switch with its own cost budget. This map makes neither promotion: correctness
gaps, corpus exceptions, whole-import-graph behavior and application/retained-memory
acceptance still matter.

When updating this page, change the affected SVG labels and tables together, recheck the
linked issue's remaining scope, and retain the distinction between an unavailable feature,
an intentional restriction, a known accepted deviation and a measured cost. The SVGs are
editable vector sources in [images/](images/); labels and the tables carry the meaning
without relying on color alone.
