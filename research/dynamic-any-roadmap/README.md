# Dynamic `Any`: a proposal to make it robust and make it scale (2026-10-21)

A proposal, with the measurements behind it, for the dynamic `Any` that #761 merged, #790
extended and #795 now ships `tomllib` with. It maps the reference systems (Julia, V8, Dart, PyPy,
CPython, Truffle, .NET, Go, mypyc, gradual typing research) onto Pystachy's actual architecture
and orders the work by what was measured. Nothing here changes the compiler, the runtime or
`lib/`: the two patches in `patches/` are measurement experiments, not proposed code.

Measured at main **`1cf6a676`** (the merge of #795), built with `make PY=/usr/bin/python3.13`
(fixed points: 635,685 lines of compiler IR, 18,709 of runtime IR), CPython 3.13.16, clang/LLVM
18.1.3, on a shared 4-vCPU Linux container. The same measurements at `3d48ce8c` (the merge of
#790), before #794 and #795, gave the same instruction counts, IR sizes and findings. Instruction
counts come from callgrind and do not depend on the host's load; timings are medians of
interleaved, core-pinned processes, and on this host differences under about 20% are noise.
Measurements cited from issues keep their own revisions.

## Summary

1. **Pystachy is a closed world whose classes never change.** Both `build` and `run` compile the
   whole program before it runs (`run` hands it to `lli`; there is no tiering, profiling or code
   loading, #707/#704/#104), and a class's fields and methods are fixed. So a test of a box's
   `DynType` is a *complete* guard: unlike V8's maps or CPython's type version tags, nothing can
   invalidate it, and no deoptimization is ever needed. Every specialization can be a diamond
   whose other branch is the generic path, chosen before any effect, as #108 requires.
2. **Which references transfer.** Julia (inference, union splitting, unboxed representations)
   and Dart's AOT (closed-world type flow analysis, a global dispatch table, call-site state kept
   as data) transfer directly. PyPy's storage strategies transfer to `list[Any]` and
   `dict[Any, Any]`. CPython supplies type slots, a "str keys only" dict mode and PEP 659's
   cheap-guard-plus-fallback shape. V8 transfers only as *offline* feedback (profiles, as
   `tools/re_specialize.py` already does for regexes) and as its small-integer tagging; its
   hidden classes are already Pystachy's fixed class layouts.
3. **Order the work by the measurements, not by the references.** On the dynamic-heavy pipeline
   of #780, `Any`-keyed dict lookups and hashing take about half of the instructions, box
   allocation and collection a quarter, dispatchers and boxing a tenth. So: a semantics harness
   first (robustness), then the data path (boxes, `Any`-keyed dicts), then dispatch structure,
   then compile-time passes, and guarded speculation last, under #392's reopen criteria.
4. **Five cheap steps with measured or well-bounded payoff:**
   - a differential and metamorphic fuzzer for `Any` operations, and #784's opt-in sweep as a CI
     check (a 450-expression sample already finds one undocumented mismatch class);
   - `Any` boxes, and closed-union boxes, in exact 16-byte slots: today each 16-byte box takes a
     24-byte slot, and the experiment cut the time to build a million boxed values by 26% to 43%
     and `generic`'s heap peak from 55.2 to 39.1 MiB;
   - dispatchers that `switch` on the dense class id every `DynType` already holds, instead of a
     chain of pointer comparisons: reading a field of the 128th boxed class drops from 493 to
     108 instructions, about its cost with 2 boxed classes (104 to 106);
   - field reads and writes through `Any` driven by the reflection records' field tables, so
     dispatcher code stops growing as classes × attributes (14 IR lines per pair today: 55% of a
     64-class, 32-field probe, and enough to push programs past the JIT's 20,000-line inlining
     threshold);
   - the `Any`-keyed dict fast paths of #780, plus constant boxes for literal keys.

## 1. Where dynamic `Any` stands at `1cf6a676`

**Representation.** An `Any` value is a pointer to an immutable 16-byte box
`{DynType *t, payload}` ([runtime.c#L3204-L3256][rt-dyn]). The `DynType` holds the kind, the
payload's layout descriptor, `type(x).__name__`, the class's dense id (`cls`, the `O<id>` of
descriptors; -1 for builtin and function types), its base and flags. `None`, `True`, `False` and
the ints from -5 to 256 are constant boxes; other numbers allocate. Containers of `Any` values
hold boxes (`LA`, `DAA`, `VA`). Typed mutable containers never become `Any` values (#777).

**Dispatch.** Operations on the program's classes go through dispatchers, one function per
operation key (`get.<a>`, `set.<a>`, `call.<m>.<n>`, `has.<m>.<n>`, `callv.<n>`, `op<k>`, ...),
that the compiler writes once the boxed classes are known and recompiles, all of them, while
compiling them boxes more classes ([dynamic.py#L1403-L1418][dispatchers],
[program.py#L1126-L1128][fixpoint]). Each tests the box's `DynType` against every boxed class
that supports the operation, one pointer comparison after another
([dynamic.py#L1085-L1128][body]), then falls back to `runtime.c`'s generic helpers. The runtime
reaches the program's own `__eq__`, ordering, hash, `repr` and #790's cross-type comparison
helpers through `pys_obj_eq`/`pys_obj_cmp`/`pys_obj_repr`, whose class-id argument also encodes
the operation (`-1 - id`, op codes 1 to 6). So a dynamic operation's semantics live in four
places: the compiler's dispatchers, the runtime's generic helpers, the program's `@o.*` helpers
and the descriptor walks of containers.

**Measured costs** (method under [Reproduce](#reproduce)):

| # | Measurement | Result |
|---|---|---|
| M1 | Instructions per `obj.f0` read through `Any` (the sum it feeds allocates a box each time), receiver of the last class in the chain | 106 with 2 boxed classes, 155 with 16, **493 with 128**: about 3 more per class ahead of it in the chain |
| M2 | Dispatcher IR, 64 classes × 32 shared field names | 34 dispatchers, **29,240 of the program's 53,179 IR lines** (about 14 per class and attribute). At 32 × 32 they are 14,904 of 27,035 lines: the other 12,131 alone stay under `PYSTACHY_JIT_INLINE`'s 20,000, so the dispatchers make `run` skip inlining for the whole program ([driver.py#L741-L751][inline]) |
| M3 | Heap slot of a box | 24 bytes for 16 of payload, for `Any` boxes and closed-union boxes (`pys_ubox`) alike: the collector adds one byte of slack to every request ([runtime.c#L193][cls], [#L396-L402][alloc]) |
| M4 | Compile time with K comparison methods whose body does not compile for an `Any` operand (300 other functions; `pystachy ir`, best of 5) | K = 0, 1, 4, 16: **65, 104, 234, 824 ms**; each declined method costs one more whole-program pass ([driver.py#L71-L103][passes]) |
| M5 | `x.m(f(i))` through `Any` | two class dispatches, `dyn.has.m.1` then `dyn.call.m.1` (or `dyn.callv.1` for a field), per call ([dynamic.py#L1448-L1479][method]) |
| M6 | `a: Any = 1000`, `b: Any = int("1000")`, `print(a is b, id(a) == id(b))` | Pystachy `True False` in JIT and AOT; CPython `False False`. `is` compares ints by value ([dynamic.py#L936-L952][ident]) while `id()` gives the box's address ([runtime.c#L3659][id]) |
| M7 | Seeded differential fuzz, 3 × 150 expressions over 37 values, 21 binary operators and 11 unary operators and builtins, JIT | one undocumented mismatch class: a `**` `TypeError` says `for **:` where CPython says `for ** or pow():` ([runtime.c#L3385-L3388][dops]); the rest are documented (`%` of an `Any` str, 64-bit overflow) or not comparable (str hashes, which CPython randomizes) |
| M8 | In-place operators on `Any` values that do not support them (`probes/opmsg.py`), JIT and AOT | every one names the binary operator: `for +:` where CPython says `for +=:`, `for **:` for `**=`. `pys_dyn_inplace` falls back to `pys_dyn_binop`, whose message knows only the binary symbol ([runtime.c#L3454-L3470][inplace]) |

From #780 and #784 (compiler `ad19255e`): on 100,000 mixed JSONL events, AOT processing takes 1.6×
CPython's time; about half of its instructions are `Any`-keyed dict lookups and hashing, a quarter
box allocation and collection, and a tenth dispatchers and boxing. A five-line `dlook` fast path
for two boxed strs removed 16% of the instructions. `tomllib`, whose scanner is typed and whose
results are `Any`, parses 2.0× as fast as CPython runs it, at 2.5× CPython's peak RSS.

**Robustness record.** #772 (silent wrong comparisons through `Any`) and #781 (compile time
doubling with display depth) were found by probes after #761 merged, not by its tests, and fixed
in #790; 5 of #782's 15 opt-in regressions remain, and #790 notes compile time still grows faster
than linearly with display depth. M6, M7 and M8 are three more findings of the same kind.

## 2. What transfers, and what does not

| Reference | Idea | Fit for Pystachy | Item |
|---|---|---|---|
| Julia | inference through bodies; specialization per argument types | templates already specialize unannotated functions; `dyn` is Julia's `Any`. Missing: refining `dyn` at sites (union splitting) and unboxed results of dispatch | C4 |
| Julia | inline unions, unboxing ([isbits unions][julia-unions], [union splitting][julia-split]) | closed unions exist; #742's `unionslots` splits numeric-union locals into tag and payload slots | B3 |
| Dart AOT | closed-world type flow analysis, a global dispatch table indexed by class id and selector offset ([generator][dart-table]), switchable calls whose state, a stub and its cache, the runtime updates ([Dart VM][dart-vm]) | the closest architecture: Pystachy is a closed world too | C1-C4, D2 |
| PyPy | [storage strategies][pypy-strategies]: homogeneous unboxed storage that changes representation in place on the first foreign store | only code whose static type is `list[Any]` or `dict[Any, Any]` reads these containers, so code for other types is untouched | B5 |
| CPython | type slots; [PEP 659][pep659] specialization with a cheap guard and a generic fallback; dicts with only str keys; small-int cache | slots give one definition per operation (A2); the str-keys mode is B2; the small-int cache is already copied (-5 to 256) | A2, B2, D1 |
| Truffle | [DSL specializations][truffle-dsl] with guards and a generic fallback | a declarative table of each operation's cases drives the fuzzer's coverage and the compiler's fast paths; partial evaluation does not apply | A1, A2 |
| V8 | hidden classes and transitions | already Pystachy's fixed class layouts: nothing to add | non-goal |
| V8 | inline caches, feedback, speculation, deoptimization | no online compilation, and guards cannot be invalidated: use offline profiles and diamonds instead | D1, D2 |
| V8, mypyc, OCaml | small integers tagged in the pointer ([mypyc][mypyc-int]) | fits the conservative, non-moving collector; V8's pointer compression does not (the C runtime and every container slot hold full 64-bit pointers) | B4 |
| .NET, HotSpot | [guarded devirtualization][dotnet-gdv]: a profile's dominant type tested, its target inlined, the virtual call as fallback | exactly D1's shape | D1 |
| Go | interface values `{itab, data}`; escape analysis keeps conversions off the heap | #488's tables; B3 | A2, B3 |
| Gradual typing | proxies, transient checks, [monotonic references][monotonic] for typed mutable data seen through a dynamic type | the typed-container crossing of #777 and #487's item 6 is this problem | A4 |
| LuaJIT, SBCL, Chez | a tracing JIT and NaN-boxing (LuaJIT), compilation at run time (SBCL, Chez) | need code generation at run time; NaN-boxing cannot hold 64-bit ints unboxed | non-goal |

Where this proposal departs from the general advice in the research it builds on:

- **"Start with small inline caches."** For a selector known at compile time, a `switch` on a dense
  class id (C1) or a table (C2, C3) does an inline cache's job with no mutable state and no miss
  handler, and the measured dispatch share is about a tenth. Caches pay off where the selector is
  itself a run-time value: `getattr(o, name)`, `setattr` and `__dict__` access (D2).
- **"Before full frame deoptimization."** Not needed at all here: guards are complete and the
  fallback is the generic path, selected before any effect. Deoptimization becomes relevant only
  with online speculative compilation, which #392 parks.
- **"LLVM supplies GC integration and stack maps."** Those serve precise or moving collectors.
  Pystachy's collector is conservative and non-moving by design, which is what makes box
  elimination (B3) and tagging (B4) cheap: no stack map has to learn which slots hold pointers.
- **"GC is workload-dependent."** For `Any`, the lever is fewer and smaller allocations (B1-B5).
  A generational mode with sticky mark bits (compatible with conservative roots) is the GC-side
  option only if allocation still dominates afterwards.

## 3. Principles

- **Never reject or change a program that compiles today** (#409): a program without the comment
  keeps its IR (`make irsame`), and opting in rejects nothing that compiles without it (A1's sweep).
- **Complete guards, generic fallbacks.** Every fast path tests the `DynType` (or the class id) and
  falls back to the generic path; no analysis result is ever a reason to reject a program.
- **One definition per (type, operation), many entry points** (A2): typed code, dispatchers,
  container searches and dict lookups must reach the same per-class code.
- **Python type identity is not layout** (#487): `type(x)` identity (the reflection record) and the
  payload's layout (the descriptor) are separate words of a `DynType`.
- **Pay only where used:** records, tables and slots only for classes whose values reach `Any`
  storage, as reflection records are emitted today ([internals.md#reflection][refl]).
- **Evidence before speculation:** deterministic counters (instructions, boxes, dispatches) as
  guards, as `make re-probe` and `make eqprobe` do, then paired timings.

## 4. Proposal

### A. Robustness: make the semantics hard to break

**A1. A conformance harness for `Any`.**
- A seeded differential fuzzer (`make dyn-fuzz`, as `make re-fuzz` is for `lib/re`) over a value
  pool (int boundaries, `-0.0`, NaN, inf, bool, None, str, list, dict, tuple, objects whose
  dunders are defined, missing, reflected, inherited, or mutate the container mid-operation, #554)
  and every operation `docs/dynamic-any.md` lists, with CPython as oracle. `probes/gen_fuzz.py`
  is a 38-line seed of it.
- A **metamorphic** oracle that needs no CPython: the same expression compiled with concrete
  annotations and through `Any` must agree. #772's bugs were exactly typed and dynamic paths
  disagreeing.
- Cross-operation invariants: `a is b` iff `id(a) == id(b)` while both live (M6 fails it);
  `a == b` implies `hash(a) == hash(b)`; `x in [y]` iff `x is y or x == y`; `sorted()` agrees
  with `<`; JIT and AOT agree.
- #784's opt-in corpus sweep (`tools/optin_sweep.py`, `optin_recheck.py`) as a CI check with a
  documented exception list, as #782's acceptance asks.

Gate: the fuzzer is a `make verify` group with a fixed seed budget, as `re-fuzz` is; the sweep's
exception list only shrinks.

**A2. One definition per operation: slots in the `DynType`.** Give each boxed class's `DynType`
a constant slot table (CPython's `tp_*`, Go's itab, #488's tables): `eq`, `ne`, `cmp`, `hash`,
`repr`, `str`, `format`, `truth`, `len`, `iter`, `next`, `getitem`, `setitem`, `delitem`,
`contains`, `call`, each a boxed entry compiled once per class, or null for "not defined".
`pys_dyn_eq`, the container searches, dict lookups and sorting call through the slot; the
compiler's dispatchers keep direct (inlinable) calls to the same entries. This retires the
`-1 - id` operation encoding for `Any` values and the shared runtime library's stand-ins for those
paths, since the pointers are the program's data. Converge the `DynType` with the class's
reflection record (`@pys.refl.c.<Class>`), as internals' extension path already plans: one
per-class table format for #487, #488, #489 and `Any`.

Gate: `make irsame` unchanged without the comment; every `dynany_*` test, also under
`PYSTACHY_GC_STRESS_PROGRAM=1`; `make eqprobe`'s comparison counts unchanged.

**A3. One generic boxed calling convention** (#108's "one generic boxed entry"). Per function,
method, bound method, class and builtin that can become an `Any` value, one entry taking the
callee, an argument vector of boxes and keyword names, binding them by the callee's signature
(defaults, keyword-only, `*args`, `**kwargs`) and calling the typed body, unboxing per annotation
(CPython's [vectorcall][pep590] is the model). `callv.<n>`, `call.<m>.<n>` and `has.<m>.<n>`
become a lookup plus this call: one class dispatch per method call instead of two (M5), keyword
arguments and builtins as values (#774), and CPython's arity messages from one binder instead of
`gen_dyn_arity`'s copy of `arity`'s wording.

**A4. Typed containers that cross into `Any`** (#777, #487 item 6). The gradual-typing literature
names the three choices: guarded proxies, transient checks, and monotonic references, where a
heap cell keeps its precise type and dynamic writes are checked against it. In order:
1. *Allocation-site selection* (#487's option b): give `list[Any]`/`dict[Any, Any]` storage to an
   allocation whose value flows into `Any` storage and that no annotation types (displays held in
   locals, `cont[k] = {}`, empty displays an `Any` parameter receives). Within one function this is
   the recompilation `gen_dyn_widen` already performs for scalars.
2. In an opted-in module, a `dict[str, Any]` annotation gets `dict[Any, Any]`'s layout, with str
   keys checked where typed code stores them (#777's second direction).
3. *Descriptor views* for the rest: box a `list[int]` with a `DynType` whose descriptor is `Li`.
   The runtime's walks already follow descriptors, so reads, `repr`, `==`, sorting and searching
   work unchanged; a store through `Any` writes an int in place, and any other value raises
   `TypeError`, a documented deviation, never a copy. This is a monotonic reference; #108 decides
   whether that deviation is acceptable or whether such crossings stay compile-time errors. Here
   `isinstance(x, list)` proves a list, not `list[Any]`'s layout: narrowing to `list[Any]` must
   test the `DynType` itself, and other layouts stay on the generic path.

**A5. Compile time that stays linear.**
- Find the comparison methods whose bodies do not compile for an `Any` operand in one pass, not
  one whole-program pass each (M4). After the first such failure the pass's output is discarded
  anyway, so it can catch the error at the `@o.x.<class>` helper, record the method, restore the
  current function as `gen_dry` restores it, and go on compiling the other helpers; any later error
  of that doomed pass ends it too (a real error recurs in the next pass and is reported there).
  The restart then declines every recorded method at once.
- Dispatchers as data (C2, C3) need no recompiling when another class is boxed; until then, recompile
  only the dispatchers whose class set changed.
- The superlinear residue of #781 that #790 records (a 199-deep dict display: 442 ms).

**A6. One identity rule for numbers.** `is` compares ints by value while `id()` gives the box's
address (M6). Choose one rule under which `a is b` holds exactly when `id(a) == id(b)`, and
document it. One that fits B4: value identity for ints in the 63-bit range, whose `id()` is the odd
number `2v + 1` (the tagged word itself, which no aligned address equals), and box identity for
ints beyond it and for floats, as CPython has for its objects. No value-derived id can cover every
64-bit int: there are not enough odd numbers. B3 and B4 depend on this rule, and #487's gate asks
for it to be settled first.

### B. The data path: the measured three quarters

**B1. Boxes in exact 16-byte slots.** Allocate boxes from a 16-byte size class without the slack
byte (a `pys_alloc_box`). The slack byte keeps an object alive through a pointer one past its end,
which loops over arrays form; a box is immutable and read only at offsets 0 and 8, so no code forms
one. The same holds for closed-union boxes (`pys_ubox`, 16 bytes of `{tag, payload}`).
`patches/box-16-byte-slots.diff` approximates this by requesting 15 bytes for both:

| Benchmark and mode | construction, 24 → 16-byte slots | processing | heap peak (one stats run) |
|---|---:|---:|---:|
| `dynany_bench.py generic 1000000` | 24.9 → 18.4 ms | 17.1 → 16.2 ms | 55.2 → 39.1 MiB |
| `dynany_bench.py dyn 1000000` | 26.5 → 17.6 ms | 2.4 → 1.8 ms | 34.1 → 33.1 MiB (no collection) |
| `dynany_bench.py union 1000000` | 28.8 → 17.3 ms | 2.2 → 1.7 ms | 34.1 → 33.1 MiB (no collection) |
| `dynany_bench.py graph 2000` | 6.2 → 5.6 ms | 26.8 → 22.6 ms | 34.2 → 34.2 MiB (no collection) |
| `union_values_bench.py boxed 1000000` | 28.6 → 16.2 ms | 1.6 → 1.3 ms | 33.1 → 33.1 MiB (no collection) |

Medians of 7 interleaved process pairs pinned to one core; every checksum matched. (At `3d48ce8c`,
with `Any` boxes only, the first run gave 21.5 → 15.3, 20.8 → 15.0 and 5.3 → 4.9 ms of
construction.) For 2,000,000 boxed ints (`probes/boxes.py`) the peak fell from 63.2 to 56.1 MiB,
with one collection instead of two. Gate: GC stress on every `dynany_*` and union case, UBSan, a
test that keeps only a box's interior pointer alive across a collection, and `PYSTACHY_GC=stats`
counts in the measurements doc.

**B2. `Any`-keyed dicts** (#780). In order of #780's profile:
- kind-specialized comparison and hashing in `dlook` for two boxed strs or ints (for strs, 16% of
  the pipeline's instructions in #780's experiment) and a one-call hash of a boxed str, instead of
  `hkey` → `hval` → `hcls` → `hitem` → `pys_dyn_hash` ([runtime.c#L2885-L2905][dlook],
  [#L3371-L3382][dynhash]);
- a "keys are all boxed strs" flag on `dict[Any, Any]`, set at creation and cleared by the first
  other key, after which a str probe compares str bytes only, as CPython's dicts with only str keys
  do;
- constant boxes for str literals used as `Any` keys and values (`e["type"]` boxes its literal
  anew at every evaluation today): emitted once, never allocated, and equal by pointer to a key
  stored from the same literal;
- shared key boxes from `json.loads()` once #779 builds `Any` storage (CPython's decoder memoizes
  keys per call).

Gate: #780's acceptance (`1`, `1.0` and `True` one key; NaN keys; objects with `__eq__` and
`__hash__`; a key whose `__eq__` mutates the dict), plus an instruction-count guard on a
pipeline-shaped benchmark.

**B3. Boxes eliminated in locals.** Extend #742's `unionslots` to `dyn` locals: split a local
into its `DynType` and payload slots where its address goes only to its loads and stores, and
make a box only where a value leaves (a call, a return, a heap store), with #742's rule that a
pass never makes more boxes than it removes. Payload pointers stay in stack slots and registers,
which the conservative collector scans, so no root is lost. First targets: numeric accumulators
and `t.calls += 1`-style field updates. Requires A6, since a re-made float box would change `is`.

**B4. Tagged small ints, as a measured prototype** if B1-B3 leave allocation dominant. A `dyn`
word with its low bit set holds a 63-bit int; everything else is a box pointer. `dyn.type` and
`dyn.payload` lower to a select, every `pys_dyn_*` reads the type through one accessor, and ints
outside 63 bits stay boxed. The collector already treats any word that points into an object as a
reference, so a tagged int can at worst retain a block it happens to point into: a cost, never a
safety problem. With A6, `is` and `id()` of ints are already value-based.

**B5. Storage strategies for `list[Any]` and `dict[Any, Any]`** (PyPy). Homogeneous int, float or
str storage, converted in place to boxes on the first store of another type, so a container keeps
its identity and every alias sees the change. Every operation on these two types, in any module
(templates instantiated for them included), then goes through strategy-aware entry points; code
for other types is unchanged. Worth it only after B1-B3, on a workload like #780's.

### C. Dispatch that scales with program size

**C1. `switch` on the class id.** Each `DynType` already holds the class's dense id (word 3; -1 for
builtin and function types). `patches/dispatch-switch-prototype.diff` replaces the chain of
pointer comparisons with one `switch` on it, which LLVM can lower to a jump table:

| Boxed classes | Chain, receiver last | `switch`, receiver last |
|---:|---:|---:|
| 2 | 106 | 104 |
| 16 | 155 | 107 |
| 128 | 493 | 108 |

(instructions per field read; the probes' outputs are identical). Arms are exact-type tests, so
their order never mattered and the change is semantics-preserving. Gate: the dispatchers' IR tests
and `dynany_*` cases, JIT and AOT.

**C2. Fields through tables.** For `get.<a>`/`set.<a>`, look up the receiver's class id in a
per-selector table of field entries (byte offset, assigned-flag offset, descriptor), taken from
the reflection records' field tables ([internals.md#reflection][refl]), then load and box by the
descriptor (`dyn_of` already boxes a slot by its descriptor, [runtime.c#L3560-L3576][dynof]; it
needs `O<id>` for objects). Code becomes constant per selector and data linear in the
(class, field) pairs that reach a site, instead of about 14 IR lines per pair (M2). Properties and
methods keep per-class arms or A2's entries.

**C3. A global dispatch table** when selectors and classes are both many: Dart AOT's single table
indexed by `class id + selector offset`, packed by row displacement, with the entry's selector
checked because an `Any` receiver may lack the selector. Boxing another class adds rows, so no
dispatcher is recompiled.

**C4. Type flow for `Any`** (Dart's type flow analysis, Julia's inference). Compute, over the
closed world, the set of `DynType`s that can reach each `Any` storage location and site. Use it to
prune dispatch to reachable classes, call a singleton directly, split small sets inline (Julia's
union splitting), type a dispatcher's result where every reachable arm agrees (`get.name` returning
`str` unboxed), and emit records and tables only for classes that reach a site. Proven paths also
get precise effects instead of "every effect", which lets the existing list and dict optimizations
work around `Any` code. `dyn` stays the top of the lattice: the analysis never rejects a program.

### D. Speculation, only with evidence (#392)

**D1. Guarded fast paths from profiles.** Record per-site `DynType` histograms under CPython with
`sys.monitoring`, as `tools/re_specialize.py record` does, or from an instrumented build; then
emit `if box.t == dominant: <inlined arm> else: <generic>` (.NET's guarded devirtualization;
profile-guided AOT as GraalVM Native Image does it). No deoptimization and no invalidation are
needed. Reopen criteria are
#392's: a workload, an optimization ordinary AOT cannot economically obtain, paired measurements
including compilation, start-up and memory, and guard/GC/fallback tests.

**D2. Inline caches where the selector is a run-time value:** `getattr(o, name)`, `setattr`, and
`__dict__`-style access (#489). A per-site cache of `{DynType, interned name}` to a field-table
entry is V8's keyed load cache and Dart's switchable-call data, with no code generation.

**D3. Not on this roadmap:** tiered compilation with on-stack replacement or deoptimization (it
needs in-process code loading, #707/#704, and a code cache, #104), NaN-boxing, a moving collector,
hidden-class transitions, and an interpreter tier (#108's candidate B) unless start-up
measurements call for one.

## 5. Order of work

Each step stands alone and has its own gate; numbers name existing issues.

| Step | Items | Why now | Issues |
|---|---|---|---|
| 1 | A1 fuzzer, metamorphic oracle, invariants, opt-in sweep check | finds silent wrong results before users do; M6 to M8 came from probes | #782, #772 |
| 2 | B1 exact box slots; M7's and M8's messages; A6 identity rule | small, measured, independent | new |
| 3 | B2 `Any`-keyed dict fast paths and literal boxes | half of a dynamic-heavy workload | #780 |
| 4 | C1 `switch` dispatch; A5 single restart for declined methods | mechanical; removes O(classes) and O(declines) costs | new |
| 5 | A4 container crossings (allocation-site selection first) | the first failure users of `tomllib`-style code meet | #777, #487 |
| 6 | A2 slots, then A3 boxed calling convention | one definition per operation; keywords and builtins as values | #108, #774 |
| 7 | B3 split `dyn` locals | numeric accumulators and counters | #780, #742 |
| 8 | C2 field tables, C4 type flow | code size and unboxed results at scale | #488, #489 |
| 9 | B4 tagging, B5 strategies, C3 global table, D1, D2 | only if the measurements after steps 1-8 still point there | #392 |

## 6. Risks and non-goals

- **Semantics.** Every fast path must keep CPython's evaluation order and first error, including
  user `__eq__`/`__hash__` mutating the container being searched (#554, #473). B2's fast paths
  apply only to builtin kinds; objects keep the generic path.
- **GC.** B1 relies on no live pointer one past a box's end; B3 and B4 rely on conservative
  scanning of stack slots and registers; B5 changes a container's backing store between atomic and
  scanned memory. Each needs GC stress and a negative control.
- **Identity.** B3 and B4 change which box holds a number; A6 must come first.
- **New `Gen` state.** C4's per-site sets and A5's batched declines are state that `dry()`, `Rejoin`
  and `Frame` must handle; per AGENTS.md, state what speculative compilation may retain.
- **Code size.** D1 duplicates arms; tables and slots keep methods alive. Emit them only for classes
  that reach `Any` storage, and record AOT binary sizes.
- **Non-goals:** changing programs that do not opt in; making `Any` the default for unannotated
  code; online compilation.

## Reproduce

From the repository root after `make PY=/usr/bin/python3.13`, with `D=research/dynamic-any-roadmap`
and a scratch directory `$T`:

```sh
# M1: instructions per Any field read
for C in 2 16 128; do python3 $D/probes/gen_chain.py $C last > $T/chain_$C.py; ./pystachy build $T/chain_$C.py -o $T/chain_$C; done
valgrind --tool=callgrind --callgrind-out-file=/dev/null $T/chain_128 100000   # and 200000: difference / 100000
# C1: copy src/, pystachy.py, runtime.c, runtime.py, pyext.c, pyembed.c and VERSION to $T/proto, link
# lib/ and ryu/, apply patches/dispatch-switch-prototype.diff there, and build with the hosted compiler
python3.13 $T/proto/pystachy.py build $T/chain_128.py -o $T/switch_128
# M5: the two dispatches of a method call whose argument may run code
./pystachy ir $D/probes/mcall.py -o $T/m.ll && grep 'call ptr @dyn\.' $T/m.ll
# M2: dispatcher IR lines
python3 $D/probes/gen_classes.py 64 32 > $T/c64a32.py && ./pystachy ir $T/c64a32.py -o $T/c.ll
awk '/^define internal .*@dyn\./{d=1} d{n++} /^}/{d=0} END{print n}' $T/c.ll
# M3 and B1: copy runtime.c, runtime.py, pyext.c, pyembed.c and VERSION to $T/rt16, link lib/ and ryu/,
# apply patches/box-16-byte-slots.diff there, then (likewise for tools/union_values_bench.py boxed)
./pystachy build tools/dynany_bench.py -o $T/bench24
PYSTACHY_HOME=$T/rt16 ./pystachy build tools/dynany_bench.py -o $T/bench16
python3 $D/probes/interleave.py 7 generic 1000000 $T/bench24 $T/bench16
PYSTACHY_GC=stats $T/bench16 generic 1000000
# M4: one compile pass per declined comparison method (best of 5)
python3 $D/probes/gen_decline.py 16 300 > $T/decline_16.py && time ./pystachy ir $T/decline_16.py -o /dev/null
# M6, M7 and M8
python3.13 $D/probes/ident.py; ./pystachy run $D/probes/ident.py
python3 $D/probes/gen_fuzz.py 1 150 > $T/fuzz1.py && python3.13 $T/fuzz1.py > $T/c.txt; ./pystachy run $T/fuzz1.py > $T/p.txt; diff $T/c.txt $T/p.txt
python3.13 $D/probes/opmsg.py; ./pystachy run $D/probes/opmsg.py
```

## References

- Pystachy: #108 (dynamic-mode contract), #392 (specialization evidence), #487 (boxes and the
  mutation contract), #488 (interface tables), #489 (run-time attribute names), #742 (union slots),
  #761 and #790 (dynamic `Any`), #772, #777-#782 (gaps), #784 (study records).
- Julia: [isbits union optimizations][julia-unions]; [union-splitting][julia-split].
- Dart: [AOT dispatch table generator][dart-table]; [Introduction to Dart VM][dart-vm] (switchable
  calls in AOT).
- C. F. Bolz, L. Diekmann, L. Tratt, [Storage strategies for collections in dynamically typed
  languages][pypy-strategies], OOPSLA 2013.
- [PEP 659][pep659] (specializing adaptive interpreter); [PEP 590][pep590] (vectorcall).
- C. Humer et al., [A domain-specific language for building self-optimizing AST
  interpreters][truffle-dsl], GPCE 2014.
- [.NET guarded devirtualization][dotnet-gdv]; [mypyc object representation][mypyc-int].
- J. Siek et al., [Monotonic references for efficient gradual typing][monotonic], ESOP 2015.

[rt-dyn]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L3204-L3256
[cls]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L193
[alloc]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L396-L402
[dlook]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L2885-L2905
[dynhash]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L3371-L3382
[dops]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L3385-L3388
[dynof]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L3560-L3576
[inplace]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L3454-L3470
[id]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/runtime.c#L3659
[ident]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/src/pystachy_compiler/dynamic.py#L936-L952
[body]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/src/pystachy_compiler/dynamic.py#L1085-L1128
[dispatchers]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/src/pystachy_compiler/dynamic.py#L1403-L1418
[method]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/src/pystachy_compiler/dynamic.py#L1448-L1479
[fixpoint]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/src/pystachy_compiler/program.py#L1126-L1128
[passes]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/src/pystachy_compiler/driver.py#L71-L103
[inline]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/src/pystachy_compiler/driver.py#L741-L751
[refl]: https://github.com/den-run-ai/pystachy/blob/1cf6a676633a5d3e703648d26e3fe328d884b726/docs/internals.md#reflection
[julia-unions]: https://docs.julialang.org/en/v1/devdocs/isbitsunionarrays/
[julia-split]: https://julialang.org/blog/2018/08/union-splitting/
[dart-table]: https://dart.googlesource.com/sdk/+/stable/runtime/vm/compiler/aot/dispatch_table_generator.h
[dart-vm]: https://mrale.ph/dartvm/
[pypy-strategies]: https://tratt.net/laurie/research/pubs/html/bolz_diekmann_tratt__storage_strategies_for_collections_in_dynamically_typed_languages/
[pep659]: https://peps.python.org/pep-0659/
[pep590]: https://peps.python.org/pep-0590/
[truffle-dsl]: https://lafo.ssw.uni-linz.ac.at/pub/papers/2014_GPCE_TruffleDSL.pdf
[dotnet-gdv]: https://github.com/dotnet/runtime/blob/main/docs/design/coreclr/jit/GuardedDevirtualization.md
[mypyc-int]: https://github.com/python/mypy/blob/master/mypyc/doc/dev-intro.md
[monotonic]: https://conf.researchr.org/details/esop-2015/esop-2015-papers/26/Monotonic-References-for-Efficient-Gradual-Typing
