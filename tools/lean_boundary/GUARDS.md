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

The bounded CI examples exercise all 69 inventoried union reads in
`tests/programs/optional/union_identity_none.py` and all six null removals in
`examples/null_guards.py` (branches, loops, rebinding and exception paths). This
small gate does not claim complete-corpus acceptance.

Union domains come from parameter declarations, producer representations and
literal-tag `ubox`/`ubox_opt` construction, never narrowed use-site annotations.
Optional domains include null. Reference union domains conservatively include
null. Runtime constructors' tag and null behavior remain ABI assumptions.

Nullness has only two states, null and nonnull; no parameter is assumed nonnull.
Private storage is copied and overwritten explicitly. Must-pairing follows a
loaded immutable SSA value and its private slot only until a write, redefinition,
escape or incompatible join. Entry-only slot aliases additionally require a
single entry store, no early load, no entry backedge and no live entry exception
handler. An exception before initialization cannot borrow the parameter's facts.
Calls cannot mutate nonescaping local slots; escaped or external storage has no
retained facts. A union loaded from such storage additionally permits null: its
load annotation is not accepted as initialization proof. Closure-cell correlation is currently outside this abstraction.

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
nullable-source annotation spoofing, direct machine tags, indirect address/cast/slot-transport
inventory, exception-before-store aliasing, machine slot writes, downstream phi
uses, missing pass records and count mismatches. No malformed IR is executed.
