# Null-check redundancy and closed-union guards

`tools/check_lean_guards.py` checks two independently inventoried obligations with
Lean's existing finite-tag certificate checker:

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
  When identical check keys occur more than once and only some disappear, the
  removed locations are ambiguous: their validated count remains inventoried,
  but the pass record is explicitly unsupported and receives no proof credit.

The adapter does not call the compiler's `UnionProof`, `Values`, dominator
solver or nullcheck proof. It reuses the boundary adapter's structural validation,
certificate inference and executable checker, and builds a separate normalized
graph. Certificates are untrusted; Lean checks each edge and obligation.
`PystachyGuards.lean` specializes the existing safety theorem to nonnullness and
exact member agreement. `GuardAudit.lean` audits all three public corollaries.

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

The bounded CI selection exercises 30 inventoried union reads and 16 removed
null checks: `examples/null_guards.py` and five existing inference programs,
`dynany_cmp_union_fields.py`, `mixed_union_repr_cycle.py`,
`reference_union_calls.py`, `scalar_union_chained_optional.py` and
`scalar_union_operand_pair.py`. This small gate does not claim complete-corpus
acceptance. `union_identity_none.py` remains a useful investigation target; its
call and container-result domains are currently unproved.

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

Nullness has only two states, null and nonnull; no parameter is assumed nonnull.
Private storage is copied and overwritten explicitly. Must-pairing follows a
loaded immutable SSA value and its private slot only until a write, redefinition,
escape or incompatible join. Entry-only slot aliases additionally require a
single entry store, no early load, no entry backedge and no live entry exception
handler. An exception before initialization cannot borrow the parameter's facts.
Calls cannot mutate nonescaping local slots; escaped or external storage has no
retained facts. A union loaded from such storage additionally permits null: its
load annotation is not accepted as initialization proof. Closure-cell correlation
and hidden interprocedural storage aliases are outside this abstraction.

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
aliasing, machine slot writes, downstream phi uses, ambiguous duplicate check
removals, missing pass records and count mismatches. No malformed IR is executed.
