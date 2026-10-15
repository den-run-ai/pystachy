<a id="a-typed-ir-for-pystachy"></a>

# Typed intermediate representation

Pystachy's typed IR sits between the type checker and LLVM lowering. It gives control flow,
runtime calls, effects and exception handling explicit representations shared by JIT and AOT.
The implementation lives in the [compiler components](../src/README.md):
[IR records](../src/pystachy_compiler/ir.py),
[verification and effects](../src/pystachy_compiler/ircheck.py),
[optimizations](../src/pystachy_compiler/optimizations.py) and
[LLVM lowering](../src/pystachy_compiler/lowering.py).
The original proposal and measurements are retained in the [historical design](archive/typed-ir-design.md).

<a id="summary"></a>
<a id="1-why"></a>
<a id="11-one-walk-six-jobs"></a>
<a id="12-what-it-costs"></a>
<a id="2-goals-and-non-goals"></a>
<a id="38-the-end-state"></a>

## Status

The IR, effect summaries, list/dict optimizations and table-driven exception lowering are
implemented. Optional values, closures and constructor-inferred class templates are also
implemented; their language rules belong in the [language guide](language.md).

The separation is partial. `Gen` still resolves, types, folds and specializes code while
building IR. Every function instruction is a registered typed operation, including
arithmetic, internal storage, closure pointers and runtime byte accesses. There is no
`raw` instruction or instruction-text builder. Module declarations, constants and ABI
wrappers are serialized by the LLVM backend. This completes instruction coverage for
the current backend; WebAssembly and dynamic `Any` values remain future work.

<a id="4-passes"></a>
<a id="41-the-pipeline"></a>
<a id="42-lexical-resolution"></a>
<a id="43-declarations"></a>
<a id="44-elaboration-typing-folding-and-instantiation"></a>
<a id="46-lowering"></a>
<a id="47-what-in-gen-becomes-what"></a>
<a id="5-how-the-hard-parts-map"></a>
<a id="51-templates"></a>
<a id="52-empty-container-placeholders"></a>
<a id="53-static-folding"></a>
<a id="54-deferred-errors"></a>
<a id="55-definite-assignment"></a>
<a id="56-module-init-defaults-and-none-arguments"></a>

## Pipeline

1. The loader prepares qualified modules; `Flow` marks potentially uninitialized reads.
2. `Gen` collects declarations and builds an `IFn` for each compiled function, including
   template instances, module initializers and generated helpers.
3. Empty-container holes are resolved as their element/key/value types become known.
4. `Gen.effects` computes summaries across the call graph.
5. IR optimization passes run before exception lowering.
6. `Gen.eh_ir` makes exceptional edges explicit where required.
7. `Gen.lower` prints LLVM text; `Gen.program` then releases the function's temporary IR data.

`PYSTACHY_IRCHECK=1` verifies IR before the passes and after transformations. Function effect
summaries remain available after the rest of the function's IR is released.

Module declarations follow the same boundary. Globals retain native types in `Val`
records; `Data` records retain string bytes, callable code/environment references and
exception descriptor references. `lower_module.py` alone selects their LLVM layouts,
GC root tables and entry points. It also owns native C ABI adapters, CPython extension
wrappers and object dispatch tables; these backend stubs do not enter the optimization
IR as opaque instructions. `llvm_abi.py` contains declaration and byte-escaping
serializers shared with runtime ABI checks. The runtime signatures and concrete
C layouts are unchanged.

Static folding and template instantiation remain frontend responsibilities: an unselected
static branch need not be type-checked. The [typing](language/typing.md) and
[module](language/modules.md) references cover those semantics; the IR does not replace them.

<a id="3-the-ir"></a>
<a id="31-data-structures"></a>
<a id="32-types"></a>
<a id="33-operands-and-constants"></a>
<a id="39-an-example"></a>
<a id="57-objects-descriptors-and-the-object-protocol"></a>
<a id="75-classes-as-templates-m2-7"></a>
<a id="76-dynamic-values-m4-9"></a>

## Representation

| Class | Holds |
|---|---|
| `Val` | An operand's spelling (`v`) and canonical static type (`t`) |
| `Ins` | An operation, result type, immediate data, typed operands, result numbers and labels |
| `Blk` | A basic block's label, instruction list and enclosing exception handler |
| `Loop` | Loop shape, sequences and indices used by loop optimizations |
| `Try` | The source-level shape of a try statement; LLVM lowering uses block handler metadata |
| `IFn` | Function signature, parameter indices, entry slots, blocks, loops, handlers and effect summary |

Types are canonical strings, such as `list[int]`, `dict[str,int]`, `opt[str]` and
`union[int,str]`. A closed union is an immutable pointer to a program-wide
type tag and an eight-byte payload slot; `opt[union[...]]` uses null for `None`.
Mixed scalar/list/dict unions store the original container pointer in that slot;
unboxing never copies a container or changes its element storage type.
Truth and string conversion select a typed member operation. Runtime `U` descriptors
describe mixed members for representation/formatting and builtin-value equality.
Equality resolves both operands' descriptors independently, including optional boxes
and nested union payloads; it never guesses container element storage from the first
descriptor character. Original container identity shortcuts shared descendants.
User callbacks are excluded from this paired-descriptor equality path.
Native reference unions keep the original object/file pointer in that payload;
their method calls dispatch by member tag. Narrowing checks the tag before reading
the concrete payload.
An `Ins` uses only the fields its operation needs:

| Field | Meaning |
|---|---|
| `op`, `t` | Operation name from `IROPS` and result type, or an entry slot's type |
| `s`, `k` | Operation-specific text and integer immediates |
| `x` | Runtime operation's static type descriptor where needed |
| `r` | Result/value numbers reserved for lowering |
| `a` | Typed operands in evaluation order |
| `b` | Successor labels, phi predecessors or invoke edges |

Empty operand/result/label lists are shared immutable placeholders until an instruction needs
its own list. `IFn.n` bounds allocated value and label numbers. Object descriptors and
specialized classes are supplied by the frontend; the IR does not turn them into dynamic types.

<a id="34-instructions"></a>
<a id="35-blocks-terminators-and-loops"></a>
<a id="36-checks-and-cold-paths"></a>

## Instructions and control flow

The exact operation table is `IROPS`; its current groups are:

| Purpose | Operations |
|---|---|
| Entry storage | `slot` |
| Internal storage and addressing | `mach.load`, `mach.store`, `mach.addr` |
| Scalar arithmetic, bitwise operations and machine conversions | `scalar.bin`, `scalar.cast`, `scalar.cmp` |
| Native memory access | `mem.load`, `mem.store` |
| Fixed-layout allocation | `alloc.fixed` |
| Fixed tuple slots | `tuple.load`, `tuple.store` |
| Object layout addresses | `field.addr` |
| Container payload conversions | `slot.pack`, `slot.unpack` |
| Fresh empty result layout | `empty.kind` (typed dict/set key kind, or a deferred result hole) |
| Closed union reads | `union.tag`, `union.payload` |
| Numeric promotion and comparison | `num.cast`, `num.cmp`, `int.ucmp` |
| Native reference identity and null tests | `ptr.cmp` |
| Calls | `rt`, `call`, `icall`, `init` |
| Ordinary control flow | `br`, `cbr`, `ret`, `ret.none`, `unreachable` |
| Value joins and checked arithmetic | `phi`, `select`, `ovf` |
| Guards and errors | `check`, `raise` |
| Optimized list reads | `list.len`, `list.load` |
| Exception handling | `landing`, `throw`, `exc.match` |

The operation registry is closed: unknown operations, including `raw`, are rejected.
Operations carry typed operands and finite operators, predicates, flags and metadata;
they never carry an LLVM instruction string. Entry slots lower to `alloca`; LLVM's
`mem2reg` later builds SSA form.

`mem.load` and `mem.store` keep a native value type on both sides of a typed
address (`*int`, `*Box`, and so on). The verifier checks operand counts, matching
address/value/result types, result numbers and absence of unused metadata; runtime
pseudo-types and nested address types are rejected. Lowering selects the existing
native LLVM type (`None` payloads use a null pointer). Variable and parameter slots,
globals, assignment/import flags and native values held in closure cells use these
operations. Internal closure and runtime storage use the machine operations below.
No LLVM instruction text is parsed to construct these operations.

Effects retain the existing address classification: local slots have none, globals
use `rG`/`wG`, known field addresses use `rO`/`wO`, and other addresses conservatively
read/write lists, dictionaries and objects. Canonicalization follows reaching loads
and stores across native and machine operations, including the existing alias and
call barriers, so the representation change preserves dictionary lookup fusion.

`alloc.fixed` allocates a declared class (including specialized classes and custom
exceptions) or a fixed tuple. Its result retains the native type; LLVM lowering alone
chooses the class layout's byte size or the tuple's eight-byte slot count. It uses the
existing zeroed, GC-scanned `pys_alloc` allocation and keeps its `A` effect. Object
initialization, field and tuple stores, stack tuple promotion, and the runtime ABI
retain their existing behavior. The verifier checks the layout type, one result,
runtime declaration and absence of unused operands or metadata. Variable-sized
allocations and closure/cell layouts still use runtime calls.

`tuple.load` and `tuple.store` retain a fixed tuple's type, constant item index and
declared item type while transferring an opaque `%slot`. The verifier checks that the
index selects that member and that load results and store operands are slots. Native
packing and unpacking remain separate typed operations. These instructions replace raw
LLVM in fixed tuple reads and heap/stack construction, preserving the existing layout,
conservative memory effects and dictionary-key canonicalization. Variable-length tuple
reads, tuple traversal and stack-to-heap copies keep their existing paths.

`field.addr` retains a declared class layout, member index and typed address result.
It addresses both fields and assignment flags, including flags inherited inside a
derived layout. The verifier checks the class, index and declared member type.
Field reads and writes use `mem.load`/`mem.store`; existing frontend null and
assignment guards still establish when those accesses are safe. LLVM lowering
alone emits the class GEP. Address canonicalization keeps its existing spelling
and inheritance-aware alias rules; memory effects and emitted LLVM are unchanged.

`slot.pack` preserves a native value's bits in an opaque `%slot` (eight bytes), and
`slot.unpack` recovers the declared native type. Their operands retain that type through
IR passes; only LLVM lowering chooses float bitcasts, boolean extension/truncation or
pointer conversion. Integer slots need no instruction. These pure operations replace
LLVM text in the shared container/optional/union conversion helpers, preserving the
existing representation and allocation behavior. The verifier checks their operand,
result and metadata contracts; it does not prove that a payload was read with its original
type. Container typing and union narrowing still establish that frontend contract.

`union.tag` reads a nonoptional closed union's integer tag. `union.payload` records the
declared member type and reads its opaque `%slot`; `slot.unpack` then recovers the native
value. The existing frontend guards still prove that the box is non-null and holds that
member. The verifier checks operation shape and declared membership, not guard dominance.
These operations preserve the previous LLVM loads and conservative `rL rD rO` effects.
Canonicalization retains the equivalence of repeated reads of the same immutable union
payload, so narrowing a dictionary key still permits the existing lookup fusion. This
extends the representation of existing scalar unions, without adding language support
or runtime specialization.

`num.cast` represents numeric promotion: `bool` to `int` or `float`, and `int` to
`float`. This changes the numeric representation, unlike bit-preserving `slot.pack`.
`num.cmp` compares two `int` or two `float` operands using a source comparison operator
and returns `bool`; floating `!=` remains true for NaN. The verifier checks the finite
operand/result combinations. Both operations are pure and retain typed operands for
canonicalization, including repeated numeric dictionary keys. Numeric truth and the
shared promotion/comparison helpers use these operations, so numeric-union dispatch
can reuse them without new IR or runtime machinery. Exact mixed integer/float comparison
still uses its existing frontend/runtime path; float-to-int checks, overflow checks,
and arithmetic use the scalar operations below.

Loop tests, native integer truth tests and union/class tag dispatch also use `num.cmp`.
`int.ucmp` keeps unsigned `<`, `<=`, `>` and `>=` explicit for bounds checks over native
integer bits; a negative index still fails an unsigned length check. Runtime string
primitives and the exact mixed integer/float result tests share these typed operations.
Both lower to the existing LLVM predicates. Dictionary lookup fusion reads membership
conditions from typed operands, preserving its branch facts and mutation barriers.

`ptr.cmp` retains the native reference operands of identity and null tests, including
boxed optional scalars, optional unions, classes and callables. It permits only `==`
and `!=`, returns `bool` and has no effects. The verifier rejects native scalars and
runtime pseudo-types; lowering selects the existing pointer equality predicate.
Internal closure code/environment pointers and runtime interior pointers use
`scalar.cmp` with the explicit machine pointer type `%ptr`.

`scalar.bin` records integer/boolean arithmetic and bitwise operations, floating
arithmetic and negation, and the existing finite overflow flags. `scalar.cast` records
checked frontend-selected machine conversions; `scalar.cmp` covers machine integer,
floating and pointer predicates. Verifiers reject mismatched operands, unsupported
operators/conversions and extra metadata. These operations are pure; frontend guards
retain responsibility for bounds, overflow and division checks. `select` also checks
its boolean condition and matching result/value types.

`mach.load`, `mach.store` and `mach.addr` cover internal storage and indexed addresses
that have no Python value type: closure code/environment pointers, loop/reduction
temporaries, variable tuple traversal, string headers and bytes. Storage retains native value
types or one of the finite machine types (`%ptr`, `%byte`, `%i32`); addresses carry
explicit operands and indices. String alias/range metadata and in-bounds addressing are finite
choices checked before lowering. These operations preserve the existing effects,
layout and guard order; they do not introduce unchecked Python operations.

Each block ends with one terminator. Branch labels stay within the function, and phi
predecessors must branch to their join. Checked operations share cold error blocks per
function, message and handler. The verifier checks these invariants and number bounds.

<a id="37-effects"></a>
<a id="45-effects"></a>

## Effects

`IROPS` defines fixed operation effects. `RUNTIME` defines runtime signatures and effects;
direct calls and module initializers use their callees' summaries. Summaries are computed
to a fixed point over the compiled call graph. Indirect `Callable` calls conservatively have
all summary effects, as do runtime operations that may invoke user methods for their type.

The solver deduplicates direct call edges and propagates effects through a reverse-edge
worklist. Each summary bit is added at most once per affected function, bounding propagation
by the number of effect bits times the affected reverse edges. On a later analysis, changed
local effects or dependencies invalidate their caller closure; resetting that closure also
removes obsolete effects from cycles. Unaffected summaries are reused. These are compiler
analysis facts for already compiled functions, not runtime type profiles or new language
support. `tools/test_function_summaries.py` compares incremental updates against a full
fixed-point oracle; `tests/summary_worklist.py` also executes the solver natively.

| Letter | Meaning |
|---|---|
| `R` | May raise; includes exception allocation on that path |
| `N` | Never returns; an operation property, omitted from function summaries |
| `A` | Allocates on a returning path and may trigger collection |
| `U` | May run user code; treated conservatively as having all effects |
| `I` | I/O or process/global runtime state |
| `rL`, `wL` | Read/write lists |
| `rD`, `wD` | Read/write dictionaries, sets and frozensets |
| `rO`, `wO` | Read/write object fields or assignment flags |
| `rG`, `wG` | Read/write globals or assignment flags |
| `rF`, `wF` | Read/write files |

`mem.load`/`mem.store` and `mach.load`/`mach.store` classify their addresses directly,
using known field addresses where needed. Effect analysis never parses LLVM text.
Effects describe observable behavior for optimization, not an ownership or alias type system.
`U?` applies only when a static descriptor can contain user classes or custom exceptions.
Allocation-triggered collection can close unreachable files; that unspecified cleanup timing
is represented by `A`, rather than adding file or I/O effects to every allocation.

Each `RUNTIME` entry has the form `result:params|effects|symbol`. Its type variables are `S`
(receiver), `T` (element), `K` (key) and `V` (value); `*X` means an eight-byte container slot,
`#` a static type descriptor, and `%X` a physical LLVM type. An empty symbol means
`pys_<key>` with dots replaced by underscores. Calls are checked against the entries;
`tools/check_runtime.py` checks them against the C and subset runtime implementations.

<a id="7-what-it-enables-next"></a>
<a id="71-language-level-optimizations"></a>

## Optimizations

`OPTS` lists the available switches. Only `listget` and `dictfuse` are whole-function IR
passes; the others select frontend or lowering choices.

| Option | Implemented behavior |
|---|---|
| `listget` | Replace a sequence loop's list read with an unchecked load when the loop test proves the index valid and no intervening effect can shorten the list |
| `dictfuse` | Reuse a known dictionary entry across membership tests, reads and updates of the same dictionary/key, until a mutation or user-code effect invalidates it |
| `tupleiter` | Traverse tuple slots directly instead of materializing a list |
| `listfast` | Inline a checked fast path for arbitrary `list[int]` reads, retaining the runtime fallback for negative or out-of-range indices |
| `moduleints` | Use stable module-level integer literals directly while preserving required initialization checks |

Disable one with `PYSTACHY_OPT=-dictfuse`, several with a comma-separated list, or all with
`PYSTACHY_OPT=-all`. Differential runs check that the choices preserve behavior.
Dictionary fusion is deliberately bounded; it does not promise to combine every equivalent
lookup. Calls that may mutate containers, joins and exception handlers limit reuse.

<a id="72-exceptions-m5-10"></a>

## Exception lowering

Before lowering, `Blk.handler` identifies the enclosing landing block. This implicit
exception edge is included when optimization passes compute predecessors; handler paths
cannot reuse facts that are valid only at the end of a successful try body.

After optimization, `Gen.eh_ir` turns covered may-raise calls into LLVM `invoke` operations.
A local `raise` or `throw` can branch directly to its handler. Unused landing pads are removed;
a function that needs no remaining landing pad gets no personality function. The post-pass
verifier checks unwind edges and rejects leftover unprotected may-raise calls in covered blocks.

The runtime uses table-driven native unwinding, rather than the error-flag scheme considered
in the original design. `finally` and `with` cleanup are part of the shipped implementation;
see [architecture](internals.md#errors-and-cleanup) for the runtime overview.

<a id="13-defects-found-on-the-way"></a>
<a id="6-migration-plan"></a>
<a id="61-the-oracle"></a>
<a id="62-steps"></a>
<a id="63-the-first-steps-in-detail"></a>
<a id="64-behaviour-fixes-and-the-resolver-track"></a>
<a id="65-cost-and-budget"></a>

## Validation

- `make check-ir` verifies generated IR and checks IR probes, including calls and effect summaries.
- `make check-runtime` checks runtime signature/effect declarations.
- `make irsame` and `make irsame-py` compare a refactor's IR, diagnostics and exit status with a
  reference compiler. Behavior changes need their own explicit tests, not a byte-identical promise.
- Bootstrap validation compares the CPython-hosted and native compilers; differential tests
  run supported programs against CPython through JIT and AOT.

See the [testing guide](testing.md) for the full workflow. Historical corpus sizes and
self-compile timings in the design log are not current test totals or performance claims.

<a id="73-a-webassembly-gc-backend"></a>
<a id="74-the-cpython-extension-mode-4-4"></a>
<a id="77-other-gains"></a>
<a id="78-what-stays-out-of-scope"></a>
<a id="8-risks"></a>
<a id="9-open-questions"></a>

## Remaining work

Typed instruction coverage is complete for the LLVM backend. Further backend neutrality
needs shared compiler/runtime layout definitions and a clearer separation of frontend
elaboration from machine contracts. WebAssembly GC, more general check elimination and a
Python-object representation backend are design possibilities, not supported modes.

CPython extension modules **are supported** through `pystachy ext` and boundary wrappers.
They do not implement the historical proposal to represent all compiled containers as
CPython objects. See the [FFI guide](ffi.md) for the actual boundary contract and limitations.
Explicit [closed scalar unions](language/typing.md#closed-scalar-unions) are supported.
[Bounded native reference unions](language/typing.md#native-reference-unions) also
support explicitly declared class/file alternatives. General dynamic values remain
outside the current language.

Mixed scalar/list/dict unions permit finite, explicitly written nesting. Recursive
JSON aliases remain a separate representation milestone: the parser currently
discards PEP 695 alias bodies, and type operations compare expanded canonical
strings. A recursive alias must retain its declaration and use a finite reference
to its type graph, with cycle-safe equivalence and descriptor traversal. Repeated
string expansion or a chosen maximum JSON depth would not provide recursive
types. Mutable list/dict element types must remain invariant through that change.

<a id="appendix-a-how-this-design-was-chosen"></a>
<a id="appendix-b-prior-art-and-the-measurements-behind-the-exception-and-none-designs"></a>
<a id="b1-prior-art"></a>
<a id="b2-exceptions-three-lowering-strategies"></a>
<a id="b3-none-and-optional-pointers"></a>
<a id="b4-generators-later"></a>
<a id="appendix-c-where-the-implementation-departs-from-the-design"></a>

## Design history

The [archived design](archive/typed-ir-design.md) preserves the original goals, migration
sequence, prototype measurements, prior-art links and implementation-departure log.
Its [exception and optional-value analysis](archive/typed-ir-design.md#appendix-b-prior-art-and-the-measurements-behind-the-exception-and-none-designs)
explains rejected alternatives. The [prototype diff](typed-ir-prototype.diff) applies to
`bd4cd6a`, not current source. Proposed operations and unsupported feature sketches there
must not be read as executable examples for today's compiler.
