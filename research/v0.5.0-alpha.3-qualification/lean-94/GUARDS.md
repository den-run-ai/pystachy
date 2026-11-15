# Null-check redundancy and closed-union guards

`tools/check_lean_guards.py` checks two independently inventoried obligations with
Lean's existing certificate checkers:

- **Closed unions:** every `union.tag`, `union.payload` and recognized machine
  read through a union-derived address. Tag reads require nonnullness; a payload
  read requires the declared member tag. Unrecognized derived addresses remain
  inventoried and fail explicitly as unsupported.
- **Union payload bits:** every read of a union's payload bits as a member's, every
  box made of a tag and bits, and every tag/payload pair stored into a split union
  local requires the member those bits hold (see
  [Payload bits and split locals](#payload-bits-and-split-locals)).
- **Removed null checks:** every check removed during each invocation of the
  `nullcheck` optimization, identified by comparing captured pass inputs and
  outputs. The removed count must match the pass's rewrite count and the export
  manifest. Lean proves that the check's pointer is nonnull at that point in the
  **before-pass** control-flow graph. This proves redundancy in that graph; it
  does not prove that other changes to the after-pass graph preserve semantics.
  The proof uses the [access model](ACCESS.md), else the finite-tag model; see
  [Removed checks through memory](#removed-checks-through-memory).
  When identical check keys occur more than once and only some disappear, the
  removed locations are ambiguous: their validated count remains inventoried,
  but the pass record is explicitly unsupported and receives no proof credit.
- **Field initialization** (`tools/check_lean_fields.py`): every field that a class's
  code reads without testing its "is assigned" flag is assigned before that code can
  see an object under construction (see [Field initialization](#field-initialization)).

The adapter does not call the compiler's `UnionProof`, `Values`, dominator
solver or nullcheck proof. It reuses the boundary adapter's structural validation,
certificate inference and executable checker, and builds a separate normalized
graph. Certificates are untrusted; Lean checks each edge and obligation.
`PystachyGuards.lean` specializes the existing safety theorem to nonnullness,
exact member agreement and assigned fields. `GuardAudit.lean` audits all four
public corollaries.

## Removed checks through memory

The pass treats two values as one where `Gen.canon` follows a load to the value an
earlier load or store of the same address left there: a parameter's slot, a module
global, an object's field or a closure cell, unless an operation between may write
that memory. A removal can therefore depend on memory that the finite-tag model does
not represent. Each nullcheck invocation's removals are first normalized to the
access model's `deref` obligations (`check_lean_access.normalize_program` with the
removal inventory and the pass's input function). There a field read is a cell of
its object, class and index, a tracked global and a private slot hold what was last
stored, and every write, call, callback, generator suspension and exception edge
invalidates what it may change. `PystachyAccess.accepted_access_safe` then proves
each pointer nonzero where its removed check ran. If that model does not accept the
record, the finite-tag model of this module is tried; either acceptance is a Lean
proof of every obligation of the record, and the report names the model.

Effects come from runtime contracts and from the compiler's summaries joined with an
independent scan of every function body (`check_lean_effects.py`), never from
`Gen.canon`. The scan does not count stores to a function's own stack slots, to memory
it allocated itself (an `alloc.fixed` object's fields, a fixed tuple's words and a
literal-sized runtime allocation's words within the n + 1 bytes it holds) or through
`%idret` where every direct call passes a slot of its caller there: none changes state
that existed when the function was called. Inside the function, such a store may
change only that new memory's cells; a box payload read and a closure cell, the
function's own or one its environment names, are cells as well. A write of one class's field keeps the fields of
classes that the snapshot's `classes` table relates to it in no way, by base, secondary
base or overlap through a common subclass (`Gen.disjoint`'s rule; `writeField`'s
`unrelated` list). Lean refuses a write that lists its own class,
and `accepted_write_progress` shows every accepted write can happen.

[`examples/null_reloads.py`](examples/null_reloads.py) has removals justified through
a field reloaded from the same object, a field reloaded across a write of another
field, a global reloaded across a list write, a closure cell reloaded in a lambda and
a parameter reloaded from the cell it shares with a nested function.
[`test_lean_null_access.py`](../test_lean_null_access.py) corrupts the pass input of
each: a null store to the tested field, to the same field of another object or
through a related or unknown class view, object-writing and unknown calls, raw and
unknown stores, global writes, cell writes (directly or through an environment) and
callbacks, a reversed test, an exception edge around it and an escaped parameter slot. Lean must reject every one,
while writes of another field, global or unrelated class and a store to an escaped
slot of the function keep the proof.

## Coverage of compiled code

A sweep on 2026-11-11 at `e25327d` inspected every differential test program and
deviation (2,416) with `--guard-evidence`; 861 have removed null checks. Lean proved
135,958 of their 135,977 removals, counting each program's copy of shared library code
(17,372 of 17,391 distinct obligations), all in the access model; the finite-tag
model alone proves 78,855. The 19 unproved removals, in four records, rest on facts
neither model states: a dynamic box's payload reread after a call that may write
objects (`dynany_graph.py`'s `render` and `checksum`, `lib_tomllib.py`'s `typed`),
which needs box immutability across calls, and a `repr` of exceptions that runs no
user code because the program defines no exception class and exception arguments are
formatted at construction (`exc_values.py`). Each was traced to the compiler's
justification and found sound; no removal was found to be wrong.

A union sweep on 2026-11-12 over the 288 programs with union records (snapshots of the
compiler at `e7ec9bb8`) found no possible box write and proved 5,712 of the 6,043 inventoried
union reads, 12,777 of the 13,026 payload obligations and 1,922 of the 1,951 typed union
memory domains: 836 of 847 parameters, 312 of 316 returns, 240 of 253 packed words, 181 of
182 globals, all 65 fields and every program's indirect-call arguments. The inventory counts
reads of union values and of what typed union memory holds; the
[whole-object inventory before it](https://github.com/den-run-ai/pystachy/blob/8257a3cd079329b322fbd6b07a8e7e32520582de/tools/lean_boundary/GUARDS.md#coverage-of-compiled-code)
counted 8,916 reads, of which Lean proved 2,428. Of the 331 reads left, 247 are rejected:
`string.Formatter`'s methods in `logging` read a union default another method passes (70),
a tuple is indexed by a variable (35), closure cells and nonlocal snapshots hold union values
(21), `logging.getLogger` narrows a union of classes (20), and 17 functions of other shapes
hold the other 101 (reflection over union fields, recursive aliases, `min` and `max` with
defaults, a JSON value's dict, "is assigned" flags). 84 are unsupported: template results
whose union read has no declared domain (65) and generators (19). Each kind was traced to IR
that guards the read; no union read was found to be wrong.

Field initialization was swept over all 2,416 programs on 2026-11-12 (snapshots of the
compiler at b27908f4): Lean proved 157,697 of 157,934 obligations (all 4,662 unchecked
reads, 116,412 of 116,641 escapes, 8,118 of 8,126 call pre-conditions, all 28,273
post-conditions and all 232 flag stores) in 16,187 of 16,696 functions. Before closure
cells were modeled, 82 more functions were rejected: `weakref.ref`'s callback closure, which
`logging` uses, its callers, and the tests of closures in `__init__`. The four rejected
functions, `logging`'s `getLogger`, join in a `with` handler a path where `__init__` of the
new `Logger` raised (no value holds it) with one that returns it complete; facts are not
relational, and the IR assigns `rv` only once `__init__` returns, as CPython does.
505 functions (53 distinct) are unsupported: beyond the boundary validator's bounds
or the certificate's size, or a list store, generator or long type name it refuses.
Designing these checks found the bug b27908f4 fixes (no corpus program had its shape),
and they reject that program as compiled before the fix. The check now validates a function
as the collector check does: a `list.store`, which the validator's guard model refuses, as the
runtime write it stores as (the field model takes a write's operands as escapes), and a type
name past 256 characters by its digest (the model reads the IR's own types).

## Payload bits and split locals

The `unionslots` pass keeps a local of a union of numbers (or an optional scalar) out of
the heap: it replaces the local's slot by an int tag slot and an int payload slot
(`optimizations.gen_unionslots`), storing and loading the two as a pair and making a box
again where the value leaves. `inspect_compiler.py --guard-evidence` records each pair
and the type of the slot it replaced (`split_unions`); a pair it did not record, or any
other access of the slots, is unsupported. Each pair is a virtual box. A pair store writes
the member a literal tag stands for (union tags; for an optional scalar 0 for None and 1
for its value; for a None-first local, `opt[None]`, the member of the bits stored with 1),
and its payload must be that member's bits; or the box both parts were read of
(`union.tag` and `union.raw`, or one pair load); or each edge's pair, for a phi of tags and
a phi of payloads; or, for a dictionary lookup's optional, None or the dictionary's scalar
value member, its presence `found >= 0` and its payload `dict.val_or_zero` of one
`dict.find`. A pair load gives its tag value a copy of the virtual box, which its tag
tests narrow, with the virtual box while it is unchanged.

Payload bits are what `union.payload` and `union.raw` read of a box, a pair load's payload,
and what `slot.pack` and phis make of them; their member is the box's (whose tag never
changes), the pair load's or, for a phi, each edge's. Every other use reads them as a
member and is an obligation: `slot.unpack` and a typed select as their type, an operand as
its annotated type (an encoded `*element` as its element), a scalar box as the type all its
uses give it; on a phi's edge a word literal is the bits of the phi's own type. A use with no member
type is unsupported. A `ubox` with a literal tag requires bits of that member: a word
literal holds an int's or a bool's, a value of its type (a `slot.pack` operand's, a fixed
tuple's item or a proved dynamic payload, as their text names it, a list's encoded item or
a generic one of the receiver's item type), a phi its operands'; `ubox_opt` with `deref`
boxes the word its pointer points at (`pys_ubox_opt`), a promoting int's low word as int
bits after the compiler's overflow check. A box made again of the tag and bits of one box
or pair load is that box, which also proves the return domains of functions that return
one. IR operand types, container item types, the inspection record and these runtime
semantics are trusted; payload checks prove member agreement, not numeric ranges.

## Field initialization

`flow.gen_fl_fields` decides which fields of a class get an "is assigned" flag: a read of a
field without one (or whose flag only `hasattr` tests) loads it unchecked, so the field must
hold a value wherever such a read can run. `inspect_compiler.py --guard-evidence` records each
class's struct (`class_layouts`): its fields, then its flags and identity boxes, a class's
struct being a prefix of each subclass's. A class's view is what its code and its bases' code
reads unchecked (unflagged fields, a tagged class's class word, an exception's hidden fields);
an object is complete once every field of its class's view is assigned.

`check_lean_fields.py` follows each object under construction (an allocation of a class, or a
parameter a contract covers) by a tag on each value and private slot that may hold it, and
each of its fields by a location that a store sets. In the finite-tag model, Lean requires
the field `set` at each unchecked read of such an object, at each escape (any use but a field
access, a private slot, a comparison, a join or a call a contract covers) for its whole
view, at each call for the callee's pre-condition (and, where the callee lets the argument
escape, the fields the parameter's class cannot see), and at each return for the function's
post-condition. Contracts cover every `__init__`'s self and each parameter that a call passes
a possibly incomplete object in, such as `super().m(...)` before `super().__init__()`; they
are inferred as a greatest fixed point and each function is then checked separately, and a
function Lean rejects gives its callers none, so its calls are escapes, as for return domains.
A value's possible objects at each site come from the previous pass's facts, which a payload
asserts (Lean's guards narrow only the tested value), and an allocation that runs again needs
its previous object complete, else the values still holding it may not be used. Where a
loaded flag (as `hasattr` loads one) is true, its field was stored: a flag is set only after
its field (`setfield`), which each flag store of an object under construction must show.
Objects that compiled code did not make here (parameters, loads from memory, call results)
are complete: the function that allocated each let it escape only once complete.

A variable that a def or lambda takes lives in a cell, a word the function allocates as it
begins, and each closure's environment holds the cells it takes. A cell is a private slot of
its function until an environment holding it escapes (into a `Callable`, memory or a call):
it is then published, so the objects it holds escape there, each object stored into it later
escapes, and each load from it may also be another, complete object (a `nonlocal`
assignment elsewhere). A direct call of a def, given an environment none of whose cells is
published, is covered instead by a contract for each cell holding an object under
construction, as is a call of a `Callable` the function made of a lambda, through its
adapter (its code word), where the adapter only passes the environment on: the closure
function, which loads the cell from its environment, is checked as if given that object;
a contract that lets the object or its cell escape, or assigns the cell, publishes the cell
in the caller and lets its content change.

A call of a generator function runs only its entry block: it returns at `gen.start`, which
suspends the generator before its body. The field check therefore takes a generator's
post-condition at `gen.start` (its body's stores come later). Each read of its body is
required at the call, conservatively, since fields only become assigned while it is
suspended. The union check treats `gen.start` and each `gen.yield` as edges to where the
generator resumes: its caller runs meanwhile and may write the tracked globals, which are
reset there, but not the generator's private slots, and boxes stay immutable. `gen.ret` ends
the function. [`examples/generators.py`](examples/generators.py) has a union local tested
before a suspension and read after it, a union global that a generator stores, then tests
again after suspending, and a generator method that assigns a declared field.
[`test_lean_generators.py`](../test_lean_generators.py) requires a rejection when the local's
test is removed, when the global's test after the suspension is removed, and when a layout
corrupted to read that field unflagged reads it right after the call. With the suspension
made a branch, the same global read is accepted.

[`examples/field_init.py`](examples/field_init.py) has class attribute defaults, a field
assigned on one path, a list built in a loop, an object join, a tagged hierarchy whose
calls dispatch on the class word, `super().fmt(...)` before `super().__init__()`, a field
that only `hasattr` tests, a dataclass factory, an exception subclass's class variable
shadowing its base's field, a def and a `Callable` lambda called during `__init__`, a lambda
that escapes once its object is complete, a `nonlocal` counter and a weak reference with a
callback.
[`test_lean_fields.py`](../test_lean_fields.py) corrupts its IR: an `__init__` that forgets
a field, an object no `__init__` was given, a class default not stored, a class word not
stored, a loop's object escaping into the next before its `__init__`, a read before the
field's store, a flag set before its field, a base whose code reads the shadowed field
unflagged, a def called before a field it reads is stored, a lambda escaping before one is
stored, a def that assigns its cell (later stores may miss self), a def that passes self on
early, an incomplete object stored into a published cell, a `Callable` lambda called before
a field it reads is stored and an adapter that also uses its environment must each be
rejected; so must a call that does not meet a tampered (stronger) contract.
The class layouts, the classes table, the IR's operand views and typed memory are trusted, as
are that only compiled allocations make objects of the program's classes, that complete
objects' flags are set only after their fields and the closure layout (`functions.py`'s cells,
`closure()`'s environments and `Callable`s); a raw access other than its class word counts as
an escape (conservatively), and functions beyond the boundary adapter's bounds are
unsupported.

## Run

Build `tools/lean_boundary` with the pinned Lean toolchain, then:

```sh
python3.13 tools/inspect_compiler.py tests/programs/optional/union_identity_none.py \
  --output /tmp/union-guards --typed-after-only --guard-evidence
python3.13 tools/check_lean_guards.py --snapshot /tmp/union-guards/typed-after.json
python3.13 -m unittest discover -s tools -p test_lean_guards.py
python3.13 tools/check_lean_guard_corpus.py --jobs 2 --progress --report /tmp/guard-corpus.json
```

Output paths must be new. Evidence capture is opt-in; ordinary inspection and
compilation do not pay for pass snapshots. The corpus command uses **every**
differential test program and deviation, including imported code, without an
annotation or source-text selector. Explicit program arguments restrict the run.
Every program, function result, unsupported obligation and failure remains in the
report. An inspection failure has explicitly unknown counts and makes inventory
completeness false; a zero-obligation program is labeled vacuous. Empty default
inventories fail, and accepted records must prove their complete counted inventory. Counts distinguish inventoried reads/removals from proved ones. A
rejection is an investigation target; it does not establish a compiler bug.

## Supported abstraction and boundaries

The bounded CI selection exercises 61 inventoried union reads, 101 payload obligations, three
proved union return domains, twenty-seven removed null checks, 151 field obligations and 136
collector-scanning obligations ([GC.md](GC.md)) in `examples/union_guards.py`,
`examples/union_effects.py`, `examples/union_split.py`, `examples/union_memory.py`,
`examples/union_defaults.py`, `examples/gc_arrays.py`, `examples/null_guards.py`,
`examples/null_reloads.py` and `examples/field_init.py`.
This small gate does not claim complete-corpus acceptance. Programs whose union values
come from closure cells or from library initializers' defaults remain investigation targets
(Typed union memory, below, covers fields, globals, containers and callees).
[`test_lean_union_effects.py`](../test_lean_union_effects.py) corrupts
`union_effects.py`: each kind of possible box write, placed in the callee `bump`,
restores the conservative rules; a return outside its declared
domain (another member's tag, or a reachable null) is not assumed by its caller; a join
whose test is removed, and phis that swap their boxes in a loop, are rejected.
[`test_lean_union_split.py`](../test_lean_union_split.py) corrupts `union_split.py`:
float bits stored with an int tag, swapped tag phi edges, a test of the other member, a
missing test, an optional's payload read where it is None, an int word stored as a float,
a box of float bits made with an int tag, `next()`'s None appended to a `list[int]` and an
int payload formatted as a float are rejected; a split pair the inspection did not record, a
tag store without its payload store, a box made of a tag and bits of different sources and a
lookup's presence set where it missed are refused.

Union domain facts come only from modeled private-slot copies (a store of `null` makes the
slot null), literal-tag `ubox`/`ubox_opt` construction, split locals' virtual boxes and boxes
made again of one box's parts (above), joins of such values and typed union memory (below).
Optional domains include null, as do reference union domains. Runtime
constructors' tag and null behavior remain ABI assumptions. A phi is its incoming value
on each edge (edge copies; parallel, so where one phi feeds another of its block they
havoc instead) and a select is either operand as its condition decides, whatever their
annotations. Other producers, such as casts, have unknown tags: their destination
annotations cannot discard null or an incoming union member. An unknown result may cause
rejection even when the actual operation is safe; a rejection names the first read the
inferred facts do not cover.

A boolean join (a block of a phi and a branch on it, as `and` and `or` make) is threaded
whatever else uses its phi: on each edge in, the branch follows the incoming condition, and a
following join that the phi flows into is threaded with it, the phi taking its value on that
path, a constant where the branch that chose the edge decided it. A boolean has no location
here, so another use of such a phi tests it as an opaque condition.

## Typed union memory

`proved_domains` types union memory by its declaration and proves it. Its keys are a field
word (by `class_layouts`, whose structs are prefixes of their subclasses', so every view of
one object's word shares it), a module global or class variable that compiled code loads and
stores only whole, the words `slot.pack` makes of a union (every container item, tuple item
and generic word: `slot.unpack` is how each comes back), each parameter and result of a
union, and the union arguments of indirect calls. Each write of a key is a Lean obligation in
its writer: a store, a pack, a call's argument (an indirect call's against its operand
types; a parameter of type `None` takes no operand, so a direct call's operands are the other
parameters' in order) and a return must be a member of the declared union, null only where the union has it.
Each read assumes the key's domain: a load of the memory, an unpacked word, a parameter (of a
function whose address code takes, only while indirect calls are proved) and a call's
result. The keys start all assumed; a key a write of which Lean does not prove, or that a
function this check does not support may write, is dropped and every function is checked
again, a greatest fixed point. A word read under another view of its field, written through
a raw access to its object, or whose address escapes is no key.

Memory may be unassigned: a field or global read assumes null too, but where it is assigned.
A field its class's view reads unflagged is assigned wherever read in a class
`check_lean_fields.py` proves complete (`initialized_classes`: no function it does not
accept makes, initializes or is given under construction an object of a related class). A
module global or class word is assigned where a passed check of an "is defined" flag
(`@g.NAME.def`, which the compiler tests to raise `NameError`) follows every store of true
in it after the word's store (`def_flags`: dominance in the setting function, an exception
handler's reach excluded): the check's edge sets a witness location, and Lean checks the
word's loads where it is set. A word `@main.init` stores is assigned in each function that
only runs after the store (`late_functions`: none that an operation not after the store may
call, directly, through an `init` or as user code a runtime function or indirect call runs).
Within a function, a global loaded and stored only directly is a location, which an
operation that may write globals (`check_lean_effects`) may change to a value of its domain.

This rests, by induction over the writes of a run, on immutable boxes (`box_writes`), on the
runtime passing compiled callbacks values of their parameters' types and copying container
words whole, on `list.load` reading below its list's length (`check_lean_access.py`), on the
field checker's own trust and on the adapter's dominance and call-graph analyses.
[`examples/union_memory.py`](examples/union_memory.py) and
[`examples/union_defaults.py`](examples/union_defaults.py) (a dynamic program, which stores
union defaults once) read fields, globals, list and tuple items, parameters, defaults and
chained conditions; [`test_lean_union_memory.py`](../test_lean_union_memory.py) corrupts them:
a field store, pack or argument outside its union (also one after a `None` parameter), an
uninitialized field, a default read before its class statement, and swapped branches of a
chained join must each be rejected.

Inventory follows union-derived operands through every result-producing
operation, including opaque operations, and conservatively tracks raw memory,
tuple storage and address transports. Unrecognized derived machine reads stay
in the denominator and fail unsupported; they cannot disappear when their
address loses its union annotation. What reads a box's words is no transport of
its address: a tag, payload bits (each a member's value, which payload checks
oblige) and a word a machine read loads through a union-typed value. Memory that
the IR types as a union is read as one, not tracked as raw memory: a field word
some view of it types as a union (by `class_layouts`, whose structs are prefixes
of their subclasses', so every view shares the word), a tuple item whose type is
one, a private slot or module global (whose address no other operation uses) and
a compiled callee's result (but of a callee that may return a union value's
address as another type, which makes its results transports). Each other way of
reading such a word remains a transport: another view of the field word, a raw
access to an object of its class hierarchy or a tuple that holds one, a tuple
read under another type or through a value of another type, and a slot loaded as
another type ([`test_lean_guards.py`](../test_lean_guards.py)). The trust is the
IR's, as for container items: what a typed load returns is its type's.

Union member proofs require stable box contents. `box_writes` scans every compiled
function of the snapshot for an operation that may write a union box: a store (or raw
`memmove`) whose address is not shown to lie outside boxes, an unknown runtime function,
a box passed to a runtime function other than as a value word (`*T`, `*V`), a list write
into a box, a call or initialization of code the snapshot does not define, and a
generator operation on a value that is no generator.
Addresses outside boxes are stack slots, module globals, the caller's identity-return
slot, fields of classes of the classes table, closure cells an environment holds, a
generator's promise, memory the function allocated itself (unless it is made into a
union value) and words at offsets of these. Where it finds none, no execution changes a
box's tag: pys_ubox and pys_ubox_opt alone make boxes (a fresh allocation with a fixed
tag, running no user code: a trusted ABI contract), the compiler treats them as immutable
values, and the runtime functions it passes them to read them or store them whole. Writes and calls then leave the finite-tag state alone but for escaped slots,
which the graph does not track. This rests on typed memory (a field, list or tuple
address lies in its object, and indexing stays in bounds), the runtime ABI, complete
inspection evidence (every compiled function, generator body and callback is in the
snapshot) and FFI code respecting its declared C types.

Where `box_writes` finds an operation, the conservative rules apply to every function of
the program: any write through a derived box address, or through an address that is not
a declared local storage slot, fails unsupported, as do opaque calls and generator
operations that can precede a later union read, including paths through handlers,
unwind edges and loop backedges. Merely clearing a box's tag facts would be
insufficient: a comparison computed before a mutation could otherwise reintroduce a
stale fact at a later branch. Write-only functions are inspected too and cannot make a
program pass vacuously. The `union_box_writes` diagnostic counts writes through
nonprivate addresses; `possible_box_writes` counts what `box_writes` found.

A function returning a union proves its returns: each returned value must be in its
declared return domain, null included only where that domain has it (a dead block's
return is unchecked). A direct call of such a function assumes that domain for its
result. Return domains are typed union memory keys (above); `proved_returns`, the earlier
fixed point over returns alone that assumes every parameter's declared domain, remains for
its tests. Call sites and indirect calls are checked against parameter domains; runtime
callbacks are trusted to pass their parameters' types.

In the finite-tag model, nullness has only two states, null and nonnull; no
parameter is assumed nonnull.
Private storage is copied and overwritten explicitly. Must-pairing follows a
loaded immutable SSA value and its private slot only until a write, redefinition,
escape or incompatible join. Entry-only slot aliases additionally require a
single entry store, no early load, no entry backedge and no live entry exception
handler. An exception before initialization cannot borrow the parameter's facts.
Calls cannot mutate nonescaping local slots; escaped or external storage has no
retained facts. A union loaded from such storage additionally permits null: its
load annotation is not accepted as initialization proof. Closure-cell correlation
and hidden interprocedural storage aliases are outside this abstraction; the access
model covers removals that need closure cells, fields or globals.

The graph includes branch, switch, check-failure, invoke/unwind and handler edges.
A handler conservatively receives an edge before every covered operation. Pure
boolean-phi and pointer-phi/null-test joins can be threaded only when their results
are used exclusively by the join's own branch/comparison. Other phis retain
unknown results; a loop cannot keep facts from a previous SSA definition.

The checker does **not** prove reconstruction from other tag sources, payload
bits through memory other than split slots, generator suspension, general memory aliases,
GC roots/lifetime, source semantics, LLVM lowering or whole-pass equivalence.
The Python adapter, complete inspection evidence, runtime representation and
operation semantics remain trusted. Export manifest consistency detects accidental
omissions; an exporter that forges both evidence and manifest remains trusted.

Mutation tests cover wrong members/tags, branch reversal, missing guards,
nullable-source and transport-result annotation spoofing, direct machine tags,
indirect address/cast/slot/big-word/tuple transport inventory, exception-before-store
aliasing, machine slot writes, direct and transported box writes, unknown aliases,
calls between tag comparisons and branches, mutation/exception paths, downstream
phi uses, ambiguous duplicate check removals, missing pass records and count
mismatches. No malformed IR is executed.
