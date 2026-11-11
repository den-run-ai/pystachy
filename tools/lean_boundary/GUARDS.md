# Null-check redundancy and closed-union guards

`tools/check_lean_guards.py` checks two independently inventoried obligations with
Lean's existing certificate checkers:

- **Closed unions:** every `union.tag`, `union.payload` and recognized machine
  read through a union-derived address. Tag reads require nonnullness; a payload
  read requires the declared member tag. `union.raw` and unrecognized derived
  addresses remain inventoried and fail explicitly as unsupported.
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

The adapter does not call the compiler's `UnionProof`, `Values`, dominator
solver or nullcheck proof. It reuses the boundary adapter's structural validation,
certificate inference and executable checker, and builds a separate normalized
graph. Certificates are untrusted; Lean checks each edge and obligation.
`PystachyGuards.lean` specializes the existing safety theorem to nonnullness and
exact member agreement. `GuardAudit.lean` audits all three public corollaries.

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

The bounded CI selection exercises seven inventoried union reads and twenty-two
removed null checks in `examples/union_guards.py`, `examples/null_guards.py` and
`examples/null_reloads.py`. This small gate does not claim complete-corpus
acceptance. Existing programs with calls,
storage writes and container-result domains remain investigation targets rather
than qualifying examples until those effects and representations are proved.

Union domain facts come only from parameter declarations, modeled private-slot
copies and literal-tag `ubox`/`ubox_opt` construction. Optional domains include
null, as do reference union domains. Runtime constructors' tag and null behavior
remain ABI assumptions. Other producers, including calls, phis, selects, casts
and slot unpacking, have unknown tags: their destination annotations cannot
discard null or an incoming union member. An unknown result may cause rejection
even when the actual operation is safe.

Inventory follows union-derived operands through every result-producing
operation, including opaque operations, and conservatively tracks raw memory,
tuple storage and address transports. Unrecognized derived machine reads stay
in the denominator and fail unsupported; they cannot disappear when their
address loses its union annotation. This overapproximation can also inventory
reads that would need additional analysis to distinguish from union reads.

Union member proofs require stable box contents. Any write through a derived
box address, or through an address that is not a declared local storage slot,
fails unsupported: an unrelated raw pointer may alias a box. This conservative
rule also rejects writes to globals and fresh heap objects whose disjointness
has not been established. Write-only functions are inspected too, receive an
explicit unsupported record, and cannot make a program pass vacuously. The
`union_box_writes` diagnostic counts these potential mutations; it does not
assert that each destination really aliases a box.

Opaque calls and generator operations that can precede a later union read also
fail unsupported, including paths through handlers, unwind edges and loop
backedges. Merely clearing a box's tag facts would be insufficient: a comparison
computed before a mutation could otherwise reintroduce a stale fact at a later
branch. Calls strictly after all covered reads remain admitted. Exact `ubox`
and `ubox_opt` construction retains its trusted fresh-allocation, fixed-tag and
no-user-callback ABI contract. Runtime effect summaries are not used to exempt
byte copies or other calls from this rule.

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

The checker does **not** prove raw union transport, matching payload unpacking,
reconstruction from a dynamic tag, generator suspension, general memory aliases,
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
