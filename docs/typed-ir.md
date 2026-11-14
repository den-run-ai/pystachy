<a id="a-typed-ir-for-pystachy"></a>

# Typed intermediate representation

Pystachy's typed IR sits between the type checker and LLVM lowering. It gives control flow,
runtime calls, effects and exception handling explicit representations shared by JIT and AOT.
The implementation lives in the [compiler components](../src/README.md):
[IR records](../src/pystachy_compiler/ir.py),
[verification and effects](../src/pystachy_compiler/ircheck.py),
[optimizations](../src/pystachy_compiler/optimizations.py) and
[LLVM lowering](../src/pystachy_compiler/lowering.py).
The original proposal and measurements are retained in the [historical design](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/archive/typed-ir-design.md).

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
the current backend; WebAssembly remains future work, and dynamic `Any` values are a
[prototype](dynamic-any.md) that a module opts in to.

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
7. `Gen.lower` rewrites layout reads into machine operations (`Gen.machine_ir`, see
   [machine lowering](#machine-lowering)) and prints LLVM text; `Gen.program` then releases
   the function's temporary IR data.

`PYSTACHY_IRCHECK=1` verifies IR before the passes and after transformations. Function effect
summaries remain available after the rest of the function's IR is released.

The hosted [inspection prototype](compiler-inspection.md) captures those live
stages, function signatures/effects and per-pass diffs in one compilation. Its
JSON report also retains terminal diagnostic locations and specialization notes.

Module declarations follow the same boundary. Globals retain native types in `Val`
records; `Data` records retain string bytes, constant tuples' slots, callable
code/environment references, exception descriptor references and classes' reflection
records with their name and field
tables (see [reflection](internals.md#reflection)). `lower_module.py` alone selects their LLVM layouts,
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
`union[int,str]`; `exc` is an exception, `exctype` its class (the exception itself, as a
context manager's `__exit__` takes it), and `opt[exc]` and `opt[exctype]` use null for `None`. A closed union is an immutable pointer to a program-wide
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
In a module that opts in to [dynamic `Any`](dynamic-any.md), `dyn` is a pointer to an immutable
box of a `DynType` pointer and an eight-byte payload, which is a number's bits or a reference's
own pointer. `dyn.type` reads the `DynType` (type `dyntype`), and `dyn.payload` reads the payload
as the static type its `s` names. With `PYSTACHY_IRCHECK=1`, the stock verifier
additionally requires every reachable payload read to find only tags whose boxes
have that type's payload layout: for an `int` read, an `int` or `bool` tag (a
bool's payload is its int value, while a wide int's box and None's hold none); for
a class read, the tag of the class, of a subclass or of a class that takes it as
its role; for any other, the `DynType` of the type's boxes. It reads the tags from
the program's `DynType` constants and rejects a read of a type no `DynType` holds.
Neither instruction has a memory effect, since a box never changes. A box in a container slot
is descriptor `A`, which runtime walks follow
through the box's own `DynType`, and a boxed function is `Z`; runtime calls whose descriptor
holds an `A` have every effect, as an `O` does.

Identity comparisons use a separate pure `dyn.raw` operation: its empty `s` claims no
Python type, and its `%slot` result is only opaque payload bits. With
`PYSTACHY_IRCHECK=1`, those bits may appear only as a direct integer `==` or `!=`
operand; no arithmetic, pointer conversion, store, call, phi or select may consume
them, and the operation's internal address cannot escape. This distinguishes a
float's or reference's identity bits from a typed integer extraction while keeping
the same LLVM loads. A live, non-null box remains a frontend obligation. The result
does not establish that its source has any particular dynamic type.

The builtin guard proof uses the actual typed-IR control-flow graph. A function's
tags are the `DynType`s its tests and reads name, with an open unknown-tag case for
every other one, a wide int's or a runtime iterator's among them. Its tests compare
a box's `DynType` with a `DynType`, compare with zero the result of `pys_dyn_isa` or
`pys_dyn_role_isa`, which follow bases and admit None for a class, or switch on the
class number a `DynType` holds, as class dispatchers do. It follows copies, private scalar slots, boolean
conditions, simultaneous phis, selects, joins and loop backedges to a fixed point.
It checks exception and cold-check edges as well as normal flow. Rebinding loses
the old slot's facts while preserving earlier SSA copies. A slot whose address
escapes receives no memory facts; calls retain facts only for immutable box
values and nonescaping private storage. Globals, fields and container reloads
cannot borrow an earlier load's guard. Unrelated functions bypass this analysis.

This compiler check is not a Lean proof. It does not prove null/lifetime safety,
runtime tag/layout correctness, the `DynType` constants it reads, SSA
well-formedness, identity preservation, GC or LLVM lowering. Its negative tests
include forged guards, overwritten bindings, unguarded joins, saved loop
conditions that refer to a previous phi value, a class test that admits None, a
base's test before a subclass's read and a switch on another box's class number.
A bounded model compares its verdicts on class tests and dispatch with a concrete
interpreter. [A test](../tools/test_typed_dynamic_tables.py) checks the runtime facts
it copies (DynType kinds and flags, builtin DynTypes, the class number word and
constant boxes) against runtime.c, as it does the Lean bridge's.

In a module that opts in to [promoting ints](python-int.md), an `int` value is `int+`, an LLVM
`{i64, ptr}`: the 64-bit value and a null pointer where it fits, else 0 and the value's immutable
digits. `big.make` builds one from an `int` and a `%ptr`, and `big.lo` and `big.hi` read its two
words; none has a memory effect. Container slots and unions hold `int`. A fixed tuple holds an
`int+` item in the item's own slot, the value where it fits, but -2\*\*63 (`TSLOT_BIG`) for one
past 64 bits and for -2\*\*63 itself, whose pointer (null for -2\*\*63) is then in slot `n + i`
past the `n` items: a `tuple.load` or `tuple.store` whose `k` is that slot and whose `s` is
`int+` reaches it (`tslots`, `hislot`), and a read of it is guarded by its item's slot
(`big_item`). Descriptors give such an item as `i`: such a tuple reaches the runtime narrowed
(`to_slot`), and its `repr()`, comparisons and `hash()` are compiled item by item.
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
| Known-arity runtime-length tuple construction | `vtuple.make` |
| Fixed tuple slots | `tuple.load`, `tuple.store` |
| Object layout addresses | `field.addr` |
| Container payload conversions | `slot.pack`, `slot.unpack` |
| Fresh empty result layout | `empty.kind` (typed dict/set key kind, or a deferred result hole) |
| Closed union reads | `union.tag`, `union.payload`, `union.raw` |
| Dynamic box reads | `dyn.type`, `dyn.payload`, `dyn.raw` |
| Promoting ints | `big.make`, `big.lo`, `big.hi` |
| Numeric promotion and comparison | `num.cast`, `num.cmp`, `int.ucmp` |
| Native reference identity and null tests | `ptr.cmp` |
| Calls | `rt`, `call`, `icall`, `init` |
| Ordinary control flow | `br`, `cbr`, `switch`, `ret`, `ret.none`, `unreachable` |
| Value joins and checked arithmetic | `phi`, `select`, `ovf` |
| Guards and errors | `check`, `raise` |
| Optimized list reads and stores | `list.len`, `list.load`, `list.store` |
| Exception handling | `landing`, `throw`, `exc.match` |
| Generators (LLVM coroutines) | `gen.start`, `gen.yield`, `gen.ret`, `gen.promise`, `gen.resume`, `gen.drop` |

The operation registry is closed: unknown operations, including `raw`, are rejected.
Operations carry typed operands and finite operators, predicates, flags and metadata;
they never carry an LLVM instruction string. Entry slots lower to `alloca`; LLVM's
`mem2reg` later builds SSA form. A local's "is assigned" flag (`k` 1) and numeric
identity companions share its slot number, so analyses name each slot by its text
and kind as lowering does (`slot_register`), never by number alone. A stack tuple
(`k` 2) is a tuple value.

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

`vtuple.make` constructs the final runtime-length tuple from already evaluated,
coerced homogeneous elements. Its result is `vtuple[T]` and every operand has native
type `T`; it owns one semantic result and an allocation effect. A fresh tuple display
can use it directly, while conversion from an existing fixed tuple first reads that
tuple without changing its storage. Literal constant displays keep their existing
constant path. Lowering allocates the existing scanned layout (length followed by
eight-byte elements), retaining native references across that allocation; address
and bool-widening temporaries are local to the emitter. This removes intermediate
fixed tuples and the copy through `vtuple.from` without a new runtime API, allocator
attributes, or specialization on runtime lengths. The verifier checks the supported
element representations, operand agreement, result count and allocation declaration.

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
result and metadata contracts. Closed-union payloads additionally carry the tag proofs
described below; ordinary container element typing remains a frontend contract.

The optional [Lean payload-guard checker](../tools/lean_boundary/README.md)
checks a selected function or every payload-reading function in a completed
inspection snapshot; the corpus gate checks test programs that opt in to dynamic
`Any` or import a module that does. Its theorem establishes tag safety for
accepted normalized programs, including copies, rebinding, joins and loops.
Supported descriptor sets cover scalar, integer/bool, class/subclass and container
payloads. The adapter gives other operations' dynamic results unknown tags,
follows exception and check edges, and refuses generators, unlisted payload types
and stores into boxes. Tests use actual emitted guards plus corrupted snapshots
and certificates. This is separate from the built-in dynamic guard and
closed-union verifiers: it neither runs during ordinary compilation nor proves
snapshot fidelity, the Python adapter, descriptor correspondence, payload layout,
identity, GC or LLVM lowering.

`union.tag` reads a nonoptional closed union's integer tag. `union.payload` records the
declared member type and reads its opaque `%slot`; `slot.unpack` then recovers the native
value. With `PYSTACHY_IRCHECK=1`, a control-flow proof requires that the box is non-null
and holds that member on every incoming path. `union.raw` copies the opaque payload bits
without declaring a member; `unionslots`
uses it to carry a box's tag and bits together through split storage or reconstruct the box.
A raw copy does not establish a type for interpreting the bits. The verifier follows its
provenance through slots, phis and selects; interpreting it requires the matching member,
and rebuilding a box requires its tag and payload to agree. A raw copy alone is valid.
Domains come from definitions, parameter and storage declarations, not narrowed use-site
annotations. A box read through an indexed machine slot of a tuple whose items are all of one
union type (a loop over a `tuple[U, U]` or `tuple[U, ...]`, also one that may be `None`, where
it is not) has that union's members, as a list item read has its list's declared element type:
container typing is its own contract. Tests cover missing/wrong guards, different boxes, joins, loop backedges,
nullable values, aliasing stores, calls and exception edges. Writes discard mutable storage
facts; previously loaded immutable boxes retain their facts. Non-escaping local slots and
provably disjoint fresh storage retain facts across unrelated writes.

Standalone tag reads and box construction also require these proofs. An integer
machine load whose defined source is a union is checked as a tag read, including its
nonnull requirement; one from a `tuple[T, ...] | None` reads its length word, no tag. Simple guards of immutable, nonnullable union parameters can
be proved by a bounded predecessor walk without allocating dataflow states. Mutable
slots, nullable sources, raw payload transport and unsupported control-flow shapes
fall back to the general solver.

The finite worklist joins possible tags and common equalities until stable, without a path
product or an iteration cutoff. Conditional facts survive boolean phis and short-circuit
expressions and are dropped after their last possible use. Type-name domains have no
machine-word tag limit. The proof modules are `union_proof.py` and `union_state.py`;
`tools/test_typed_union_proofs.py` checks malformed IR without lowering or executing it.
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

The generator operations mark an LLVM switched-resume coroutine's structure (see
[generators](internals.md#generators)). `gen.start` ends the entry block of a generator function
(`IFn.coro`, printed `presplitcoroutine`) and holds its name; `gen.yield` (a `%slot` value and a
flag: whether closing the generator there runs its code) and `gen.ret` (an optional `%slot`)
end blocks where it suspends (lowering alone sizes the promise, five words or seven with `send()`
and `throw()` in the program, and gives a generator that has not started its state); `gen.promise` without an operand is its own promise's address,
and with a generator operand that generator's. `gen.resume` runs a generator to its next
suspend and has every effect (user code); the exception passes make it an `invoke` like a
call. `gen.drop` closes and destroys a generator a loop owns and never raises. The verifier
checks their places, operands and metadata; lowering alone emits the `llvm.coro.*` calls.

Each block ends with one terminator. Branch labels stay within the function, and phi
predecessors must branch to their join. `switch` branches on an `int` to the label of the
case it equals, else to its default: its cases are distinct `int` literals, and it reaches a
block that starts with a phi by one edge at most, since a phi has one entry per block that
branches there. Comparisons dispatch on class tags with it, which LLVM may lower to a jump
table. Checked operations share cold error blocks per function, message and handler. The
verifier checks these invariants and number bounds.

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
fixed-point oracle; `tests/programs/language/summary_worklist.py` also executes the solver natively.

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
`U?` applies only when a static descriptor can contain user classes or custom exceptions;
a dict or set operation carries its keys' descriptor in `Ins.x` for this, where an object
hashed by its class (`H<id>`) runs `__hash__` and `__eq__`, and one hashed by identity
(`P<id>`) runs only the `__repr__` of a `KeyError`. `R?` is `R` only when the descriptor
holds a recursive alias's edge (`R<n>:`): the runtime's descriptor walks count those edges
and raise `RecursionError` past 512 of them, and no other descriptor nests without bound.
Allocation-triggered collection can close unreachable files; that unspecified cleanup timing
is represented by `A`, rather than adding file or I/O effects to every allocation.

Each `RUNTIME` entry has the form `result:params|effects|symbol`. Its type variables are `S`
(receiver), `T` (element), `K` (key) and `V` (value); `*X` means an eight-byte container slot,
`#` a static type descriptor, and `%X` a physical LLVM type. An empty symbol means
`pys_<key>` with dots replaced by underscores. Calls are checked against the entries;
`tools/check_runtime.py` checks them against the C and subset runtime implementations.

### Shared native-list storage contracts

`LIST_WRITES` selects the append, indexed-assignment and insert adapters. Their
signatures and effects remain in `RUNTIME`; `list_write_error` supplies the same
operand, result and metadata checks to `Gen.list_write` and the IR verifier.
These `rt` instructions retain the receiver's list type and the packed item's type
(`*int`, `*dyn`, etc.). Equal LLVM pointer or slot widths do not establish compatible
storage. Existing inference holes, including the None-only `list[opt[?]]`, still
belong to frontend refinement; this validator checks retained type agreement,
not canonical type resolution. Other runtime families use their existing builders.

`LIST_READS` selects the indexed-read adapters. `Gen.list_get` and the verifier
share `list_read_error`: `list.get` and inline `list.load` retain a concrete list
receiver, native integer index and encoded result `*element`. The identity adapter
returns `dyn` and requires the receiver's numeric identity kind. Decoding the
packed slot and reading a promoting integer's companion remain separate operations;
the encoded result is not an address or an unpacked Python value. Union payload
provenance continues to use the receiver definition's element type. `list.store`, which only
`listguard` emits, writes an encoded `*element` item of a concrete list receiver at a native
integer index proved within the length; the verifier rejects it in a program whose lists may
hold numeric identities, which an inline store would not update.

`Gen.list_len` preserves the measured list as the operand of `list.len` for source
`len`, sequence-loop bounds and unpacking. The value index records this operation
so `listget` can connect a captured range stop to its owner without reconstructing
list header pointer arithmetic. No length is cached across a mutation: each semantic
operation still lowers to the same single LLVM load, and the bounds pass retains
its conservative invalidation rules. Runtime signatures and lowering are unchanged.

`ListLayout` records the outer list's semantic element and packed slot, scalar
promoting-integer capability, numeric identity capability, payload-array GC policy
and supported dynamic-layout descriptor. It takes the program's promoting-integer policy explicitly: `list[int]`
alone cannot establish whether its bigint companion is available. `atomic`
describes only the payload array; bigint and identity companions remain scanned.
Nested held-value layouts and the types returned by reads remain with the existing
conversion helpers.

| Store adapter | Required representation |
|---|---|
| Ordinary | Receiver element and packed slot type agree; index is a native `int` |
| Bigint | `list[int]` with promoting storage; payload is a bigint pointer |
| Numeric identity | Native integer/float slots plus the original `dyn` box and matching identity kind |

The caller evaluates and coerces operands before construction. Identity stores keep
the original value's box; they never reconstruct identity from packed bits.
`Val.identity()` remains the representation-only identity transfer API.
Native write symbols, mutation order, exceptions and LLVM lowering are unchanged.
Dynamic boxing, unboxing and layout tests also consume `ListLayout.dynamic_type`:
boxed `list[Any]`, checked `list[int]` and promoting `list[int]` have different
descriptors. A Python `list` tag does not establish any of these storage layouts.
The shared IR constraints cover the nine registered native writers; runtime checks
and focused alias, mutation and GC tests cover the exposed dynamic mutation paths.

<a id="7-what-it-enables-next"></a>
<a id="71-language-level-optimizations"></a>

## Optimizations

`OPTS` lists the available switches. `charslots`, `listget`, `listguard`, `dictfuse`, `unionslots` and
`nullcheck` are whole-function IR passes. `callbacks` versions eligible functions after
ordinary compilation and before effect summaries and recursion accounting;
the remaining options select frontend or lowering choices.

`callbacks` finds a loop that calls an erased `Callable` parameter through a
private, write-once slot. It emits at most two precompiled copies, guarded by the
exact immutable callable objects already materialized in the program. A matching
copy calls the existing signature adapter directly; the ordinary body handles
every miss. This exposes the callback to LLVM inlining without user-written
guards, decorators, profiling or runtime compilation. Arguments are evaluated
once before dispatch, and a selected body never restarts on an exception.

The prototype considers module functions with the same callable signature in
deterministic materialization order; it does not learn target frequencies or
prove call-site reachability. Bodies are limited to 256 IR instructions, with
4096 additional instructions per compilation. Reassigned/captured callback slots,
multiple callback parameters, methods, generators, local exception handlers and
dynamic identity ABIs retain ordinary compilation. Closures and bound methods
remain valid fallback callbacks. The original entry owns the source recursion
frame and its generated helpers add none. Disable this pass alone with
`PYSTACHY_OPT=-callbacks` for identical-source comparisons.

`PASS_CONTRACTS` declares their order, prerequisites, preserved facts and invalidation.
They require typed IR before exception lowering and conservative bounds on
raising, allocation, callbacks, runtime state and every write category.
Each invocation owns its analyses; no range, alias or value proof is cached between
passes. These preserved effect bounds support mutation proofs and exception lowering.
`unionslots` may introduce tag and payload reads when splitting a union box, so the
old summary need not bound all reads. A consumer needing read-effect bounds must
rerun `Gen.effects`; exact effect reporting already does so after a rewrite.

| Pass | Analyses built locally | Additional invalidation after a rewrite |
|---|---|---|
| `charslots` | Use counts, private slot accesses and predecessor reachability | Slot layout and instruction-derived proofs |
| `listget` | Predecessors, loop bounds, values and invariant slots | Instruction-derived value, range and alias proofs |
| `listguard` | Predecessors, loop bounds, values and invariant slots | CFG, loop shape and instruction-derived value, range and alias proofs |
| `dictfuse` | Predecessors, values and lookup proofs | Instruction-derived value, range and alias proofs |
| `unionslots` | Values, uses, aliases and reaching stores | Read-effect bounds, slot layout and instruction-derived proofs |
| `nullcheck` | Predecessors, dominators, values and reaching stores | CFG, dominance and instruction-derived proofs |

With `PYSTACHY_IRCHECK=1`, scheduling checks reject lowered exception edges or
insufficient bounds on those preserved effects, and every changed pass reruns typed-IR verification
before the next pass. Normal compilation does not add these verification scans.

| Option | Implemented behavior |
|---|---|
| `charslots` | For a private local assigned once in the IR from a string index, keep the indexed code point if the store dominates every read and each read only compares it to a one-byte ASCII string literal. Indexing and its exceptions stay at the assignment. |
| `listget` | Replace a list read in a sequence loop or an invariant forward range loop with an unchecked load when the loop test proves the index valid and effects preserve the list's length; a loop over a `bytes`, which never changes in place, reads each byte inline as it is lowered |
| `listguard` | Give an innermost forward range loop whose ops change no list's length a copy whose item reads and assignments, at the index plus a constant, of lists the loop does not rebind are unchecked (`list.load`, `list.store`), and run the copy where tests before the loop find every such list long enough; give inline list reads and stores TBAA tags |
| `dictfuse` | Reuse a known dictionary entry across membership tests, reads and updates of the same dictionary/key, until a mutation or user-code effect invalidates it |
| `tupleiter` | Traverse tuple slots directly instead of materializing a list |
| `listfast` | Inline a checked fast path for arbitrary `list[int]` and `bytes` reads, retaining the runtime fallback for negative or out-of-range indices |
| `moduleints` | Use stable module-level integer literals directly while preserving required initialization checks |
| `fieldtbaa` | Give every load and store of an object field a struct-path TBAA tag, so that LLVM knows that two fields at different offsets of one class, or fields of classes neither of which lays out the other, are never the same memory; it keeps such fields in registers across each other's stores ([#701](https://github.com/den-run-ai/pystachy/issues/701)) |
| `tupleret` | Return a function's new fixed tuple as an LLVM aggregate of its slots to the calls that only read the slots (`a, b = f()`, `f()[0]`, a loop over `f()`), so that neither makes the tuple ([#703](https://github.com/den-run-ai/pystachy/issues/703)) |
| `unionslots` | Keep a local of a union of numbers (`int`, `float`, `bool`) in a tag slot and a payload slot instead of a box per value, where its slot's address goes only to its loads and stores and, on every path, each load whose value leaves the local (to a call, a return, a phi) follows a store of a box made for that store alone, with no other such load between them: stores keep a `pys_ubox`'s operands or a union phi's parts, `union.tag` and `union.payload`/`union.raw` (and tag loads) of a loaded value read the slots, a leaving value is boxed where it is loaded (each box for one that a store no longer makes), and boxes nothing uses any more are dropped |
| `nullcheck` | Drop a check that a value is not None (before a read through it) where a passed test of the same value dominates it: the block after a check, or the branch of a null test where the value is not None, reached from nowhere else. The same value is the value, an equal one, or a load of a slot that only the entry block stores and only loads and stores use (a parameter the function never assigns). The check becomes a branch, its test goes once nothing reads it, the block after it joins its block where nothing else goes there, and a cold block no check goes to any more goes too; a walk down the dominator tree keeps the work linear ([#787](https://github.com/den-run-ai/pystachy/issues/787)) |
| `allocelide` | Allocate an object or fixed tuple that holds no reference (every field or item an `int`, a `float` or a `bool`) with `pys_new`, a call that LLVM may delete when nothing keeps its object (`allockind`); the others keep `pys_alloc`, as without it, so that one the program still reads keeps what it holds. AOT builds inline the allocator's fast path into the calls left ([#1017](https://github.com/den-run-ai/pystachy/issues/1017), [internals](internals.md#whole-program-optimization)) |

`unionslots` also splits private `int | None`, `float | None` and `bool | None`
locals into a presence slot (zero or one) and a payload slot. Inferred None-first
locals whose slot still has the provisional `opt[None]` type use the same checks.
Stores must come from `None`, scalar `box` operations, phis of those values,
or the eligible dictionary lookup described below. Loads may only test against
`None` or read the packed scalar payload; no nullable pointer is dereferenced to
extract its parts. The payload stays as bits, so zero, `False`, negative zero and
NaN remain distinct from absence. A plain scalar dictionary `get` result can also
split when its default is `None` and it has exactly one private local consumer.
The original `dict.getbox` is replaced by one `dict.find`, a presence test on the
entry index, and an immediate `dict.val_or_zero` payload snapshot. A negative
index produces zero without reading dictionary storage; absence is carried by
the separate presence slot. Lookup callbacks, exceptions and evaluation order
remain on the original call, before the payload snapshot. Dynamic-`Any` and
promoting-int programs retain the existing representation.

An optional parameter or other call result, an optional copy, a phi-produced
lookup, a non-`None` default, an escaping or identity-sensitive pointer use, and a
generator frame retain their boxes. Numeric identity companions remain unchanged.
This uses the existing typed slot/phi operations. The dictionary path adds the
internal runtime entry `pys_dict_val_or_zero(Dict *, I)` and changes no object
layout or public ABI.
`PYSTACHY_OPT=-unionslots` disables both scalar-union and optional-local splitting.

Disable one with `PYSTACHY_OPT=-dictfuse`, several with a comma-separated list, or all with
`PYSTACHY_OPT=-all`. Differential runs check that the choices preserve behavior.
The optional [Lean access checker](../tools/lean_boundary/ACCESS.md) independently proves the
unchecked reads these choices leave: each `list.load` index within its list's current length and
each dict or set entry read or written by index live, on every path of a function's typed-after IR.

For `range(k, len(xs), step)`, `listget` reads the owner from the captured `list.len`
and requires a nonnegative constant start and a positive constant step. It proves the first matching read uses the same list and the
unchanged induction value on a forward path without joins; entry-only local stores
can establish invariant list bindings. The whole function must exclude list writes
(`wL`) and unknown user code (`U`), so a captured length remains valid across iterations.
Coroutines are excluded because their callers can mutate a list while they are suspended.
`listguard` handles the range loops `listget` leaves checked.

`listguard` copies an innermost loop over `range(start, stop)` or `range(start, stop, step)`,
with constants `start >= 0` and `step > 0`, such as `t += a[i] * b[i]`,
`b[i] = (a[i - 1] + a[i] + a[i + 1]) / 3` or `zi[j] += xik * yk[j]`. No op of the loop may change
a list's length (`wL`, except an item assignment) or run user code (`U`); a coroutine, a loop
that a `try` statement covers, one holding another loop and one of more than 400 ops keep
their checks. In the copy, each read or assignment of an item of a list that the loop does not
rebind (a value it does not define, or a local slot it never stores), at the index plus a
constant `c` with `start + c >= 0`, is unchecked: a `list.load`, or a `list.store`, which stores
the item inline as `list.set` does where no module opts in to promoting ints or dynamic `Any`
(elsewhere assignments keep their checks); and listfast's inline test always passes. Tests
before the loop run the copy where every such list has `stop <= len(xs) - c` for its largest
`c`, which keeps `0 <= i + c < len(xs)` for every `i` the loop takes; a list that a local not yet
assigned would hold, and any shorter list, run the loop as compiled, which raises `IndexError`
(or `UnboundLocalError`) after the same iterations as CPython. The copy doubles the loop's code.
A call in the loop of a function that the program calls nowhere else is `alwaysinline` in the
copy, and the callee's ops count toward the 400. LLVM inlines an internal function's only call
almost whatever its size, but each of two calls only if it is cheap: the copy's second call once
left `float`'s `Point.__init__` out of line, 37% slower
([#1300](https://github.com/den-run-ai/pystachy/issues/1300)). The loop's call then is the
callee's last, which LLVM inlines too.
With `listguard`, inline list reads and stores carry TBAA tags under `fieldtbaa`'s root, of a
list's items pointer and of an item, so that LLVM keeps a loop's items pointers in registers
across its item stores and can vectorize the copy.

For a statically known string variable `s`, the frontend can lower `ord(s[i])` and
comparisons such as `s[i] == ":"` directly to `text.ord_at`. The comparison accepts
`==` or `!=` with a single ASCII literal on either side. The indexed read evaluates
at its original position and raises the usual indexing errors. The separate `charslots`
pass above handles the case where a local holds the character between the read and comparison.

The native recursion depth policy is not an option: `Gen.recursionscope` decides which
source functions count toward `sys.setrecursionlimit()` once the whole program is built
and summarized, before these passes, and gives exactly those functions a checked
`recursion.enter`, restorations before their returns and the effects (`R I`) of both in
their summaries. A source function counts if it lies on a cycle of direct calls and
generator resumes, or reaches `U` other than its resumes and yields; every other function
keeps at most its entry-depth snapshot (`recursion.depth`), for its handlers. Resumes of
generators that cannot recur lose their accounting (`recursion.resume` and its restoration). A cycle that reaches nothing else that
uses the depth (closed recursion) keeps its entries without restorations: lowering passes
its depth as an argument. See
[native recursion depth](internals.md#native-recursion-depth).

`tupleret` applies to a function whose every `return` returns a tuple display that the return's
own block makes (`alloc.fixed`) and that nothing but that block's `tuple.store`s reaches: a new
tuple, which CPython makes too and no code could hold. Where another `return` makes one, a
`return` of a constant tuple (below) qualifies too. A call of it whose result only
`tuple.load`s read takes the slots from the function's by-value body, `@v.<symbol>`, which
returns `{i64, ...}`; the function's own symbol becomes a wrapper that makes the tuple from them,
for every other call and use. A function that may return a constant returns `{i64, ..., ptr}`:
the last member is the constant's address, or null for a new tuple, and the wrapper returns that
constant where it is set. A function that returns another tuple on some path (`return t`),
a generator, and a function no such call reaches are lowered as before, which keeps the identity
of a tuple a function returns again. `tests/programs/containers/tuple_return_values.py` checks behavior, and
`tests/ir/tuple_return.calls` pins which calls allocate.

A tuple display of literals makes no `alloc.fixed`. `Gen.tuple_const` makes it module data,
`@tc.N`, an `[N x i64]` constant of its slots, as CPython's compiler makes such a display a
constant ([#1016](https://github.com/den-run-ai/pystachy/issues/1016)). There is one constant
for each module and items, and `()` is one for the whole program, because CPython merges a
module's equal constants. Its items are literals and the addresses of static strings, bytes
and other such tuples, so the collector need not scan it. A promoting int item (a module that
opts in to [promoting ints](python-int.md)) is held as its 64-bit literal: a tuple of 64-bit ints
is a tuple of promoting ints as it is (`big_tuple_view`), so one constant serves both types,
and a by-value return gives its Mpz words as 0; a display with `-2**63` is not one. Only displays that the parser made
(`Node.src`) qualify: one that the compiler builds, such as a call's `*args`, is a new tuple
at each run, as CPython's is. `tests/programs/containers/tuple_constant_identity.py` and
`tests/programs/imports/tuple_constant_modules.py` check identity, and
`tests/ir/tuple_const.calls` pins that such displays allocate nothing.

Scalar list displays with at least 32 literal `int`, `float` or `bool` items use
immutable `Data("listdata")` slots and one `list.from_const` operation. The normal
item typing and coercion runs first. The runtime helper always allocates a fresh
scanned header and pointer-free item array, then copies the exact eight-byte
slots; float signed zeros and other bit patterns are not converted. The frontend
emits one copy operation regardless of the item count. The helper remains
eligible for LLVM inlining, preserving small-constant simplifications; LLVM
controls the eventual copy expansion and optimized code size.
Small, mixed, pointer-bearing, tuple and computed displays retain ordinary
construction, as do all dynamic-Any and promoting-int program graphs. The data
pool is module state like string constants: function save/restore and dry typing
may retain immutable entries; a whole-program retry constructs a new `Gen`.
`test_typed_list_constants.py` guards instruction growth and these boundaries;
the differential literal fixtures and `listprobe` check fresh storage, mutations,
exact slot bits, allocation kind and collection.

A field's TBAA tag names the class whose struct lays the field out. A derived class's struct
begins with its base's, flags included, so an inherited field has its base's tag whichever class
a reference names, and two references to one object agree (the rule of `Gen.disjoint`). The
tags hang from a root of their own, so LLVM never sets them apart from the accesses of
`runtime.c` (clang's root) or of `runtime.py` (its own): only the program's field accesses are
told apart from each other. Tuple slots, union payloads, container slots and runtime calls carry
no tag. `tests/programs/classes/field_alias.py` checks the orders that a wrong tag would change, and
`tests/ir/field_tbaa.tbaa` pins the tags (`tools/check_ir.sh`).
Dictionary fusion is deliberately bounded; it does not promise to combine every equivalent
lookup. Calls that may mutate containers, joins and exception handlers limit reuse.
Unpacking a list (`a, b = xs`, `a, *b, c = xs`) reads its items with `list.load` whatever
the switches: its length check has passed, and no code that could shorten it runs before
the reads. Reads interleave with stores only when every target is a plain name; any other
target (a setter, a subscript, a nested tuple whose item has `__iter__`) is stored only once
every item is read, as CPython does.

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

## Machine lowering

`Gen.lower` begins with `Gen.machine_ir`, the last typed-IR stage. Until then a read of a
runtime layout keeps its meaning: `list.len`, `union.tag`, `union.payload`, `union.raw`,
`dyn.type`, `dyn.payload` and `dyn.raw` carry their receiver's type, effects and guard proofs
through the passes, the verifier and the inspection snapshots. The stage rewrites each into the
`mach.addr` and `mach.load` operations that other header reads already use, from one table of
word offsets (`WORD_READS` in `machine_ir.py`). The LLVM printer has no case for a layout read
and rejects one that reaches it.

The rewrite keeps every value number, label and source line, so the emitted LLVM is unchanged.
With `PYSTACHY_IRCHECK=1`, `Gen.verify_machine` then checks that no layout read is left and
that machine memory operations keep their shape; only there may a `mach.load` give a payload's
opaque `%slot`. Other layout-dependent operations are still printed directly. Inline list
items need a struct address and TBAA tags that `mach.addr` cannot express, and `tupleret`
decides a fixed tuple's slots while its function is printed.

<a id="13-defects-found-on-the-way"></a>
<a id="6-migration-plan"></a>
<a id="61-the-oracle"></a>
<a id="62-steps"></a>
<a id="63-the-first-steps-in-detail"></a>
<a id="64-behaviour-fixes-and-the-resolver-track"></a>
<a id="65-cost-and-budget"></a>

## Validation

- `make check-ir` verifies generated IR and checks IR probes, including calls, function attributes
  and effect summaries.
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
support explicitly declared class/file alternatives. Experimental [dynamic `Any`](dynamic-any.md)
supports boxed values whose types are determined at runtime in modules that opt in with
`# pystachy: dynamic-any`. Modules without the comment retain inference-only `Any`.
This is bounded compiled support, without runtime compilation or unrestricted Python dynamism.

Mixed scalar/list/dict unions permit finite, explicitly written nesting. The
[recursive value-alias prototype](language/typing.md#recursive-value-aliases-prototype)
also supports nongeneric module-level PEP 695 closed recursive unions such as
`type Tree = int | list[Tree]` and the native JSON codec's recursive value type.
Named edges retain a finite type graph rather than repeatedly expanding canonical strings.
Recursive aliases are nominal, and existing mutable list/dict storage remains invariant.
Mutual recursion, generic recursive aliases and recursive shapes outside that documented
form remain unsupported. Runtime traversals have recursion guards; the
[JSON codec's depth and integer limits](json.md) are separate from the type graph.

<a id="appendix-a-how-this-design-was-chosen"></a>
<a id="appendix-b-prior-art-and-the-measurements-behind-the-exception-and-none-designs"></a>
<a id="b1-prior-art"></a>
<a id="b2-exceptions-three-lowering-strategies"></a>
<a id="b3-none-and-optional-pointers"></a>
<a id="b4-generators-later"></a>
<a id="appendix-c-where-the-implementation-departs-from-the-design"></a>

## Design history

The [archived design](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/archive/typed-ir-design.md) preserves the original goals, migration
sequence, prototype measurements, prior-art links and implementation-departure log.
Its [exception and optional-value analysis](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/archive/typed-ir-design.md#appendix-b-prior-art-and-the-measurements-behind-the-exception-and-none-designs)
explains rejected alternatives. The historical [prototype diff](https://github.com/den-run-ai/pystachy/blob/30b51d9169d802563380216b6352df561b7d8fc8/docs/typed-ir-prototype.diff) applies to
`bd4cd6a`, not current source. Proposed operations and unsupported feature sketches there
must not be read as executable examples for today's compiler.
