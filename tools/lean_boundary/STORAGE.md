# Promoting-integer storage guards

This developer check extends the Lean guard model to the boundary between
Pystachy's promoting integers, container slots and signed 64-bit values.
It does not change generated code or add a runtime dependency.

## Representation and obligations

A promoting integer has two words: its signed value and a null digit pointer
when it fits, or zero and a pointer to its digits when it does not. A promoting
tuple item instead stores `INT64_MIN` as a marker for both large values and
`INT64_MIN` itself. Its trailing pointer distinguishes those cases.

The checks address three different obligations:

| Operation | Required evidence |
|---|---|
| Use a promoting integer's low word as a number | Its digit pointer is null, or the use belongs to a precisely recognized representation-preserving operation. |
| Read a tuple item's trailing digit slot | The corresponding item is the marker, and its source representation permits that read. |
| Cross between plain and promoting tuple views | Plain-to-promoting excludes the marker; promoting-to-plain excludes a non-null digit pointer. Nested mixed tuples retain each item's own representation. |

A `**kwargs` record, `kw[a:A,b:B]`, is the tuple of its values at run time, and the
function that receives one reads it as that tuple: the checks compare its layout,
`tuple[A,B]`, with the view's as they compare a tuple's. A type's text may hold
4,096 characters: a nested tuple's grows with its nesting, as a name's cannot.

For optional tuples, a fit fact means either the tuple is absent or its item
fits. A null branch may establish the absent case, while every present branch
must justify the item checks. This does not prove null-dereference safety.

The distinction between a storage representation and a declared type matters.
A promoting view can refer to a shorter plain tuple when its words exclude the
marker. A marker guard alone cannot establish that the trailing slot exists.

`tools/inspect_compiler.py` exports `representation_metadata` on each function:
the original definitions and parameter contracts, constant tuple contents, and
container-read origins observed at the compiler's representation conversions.
Each operand still carries its separate view type. These are read contracts,
not an assertion that every value has the largest physical allocation.
Observations are tied to live instruction objects and their defining shape, so
temporary-name reuse and later rewrites cannot inherit an unrelated origin.

## Proof and trust boundary

For `search_hold`, a newly emitted optional phi records a proposed read contract
that the adapter checks on every incoming conversion. An unchanged input alias
is never relabeled with that contract.

`PystachyStorage.lean` models the low word, marker and optional digit pointer
over Lean's `Int`. It proves decoding, marker exclusion and null-pointer
narrowing, and connects them to `PystachyBoundary.accepted_payload_safe`.
The graph checker validates every proposed fact, join, loop edge and reachable
obligation; inferred certificates are not trusted. Kernel examples include
wrong-value tests, missing guards, an unguarded join, a circular certificate
and an exception bypass. `Audit.lean` audits the public theorems for admitted
proofs, extra axioms and native-computation assumptions.

Large functions use bounded proof batches. Each keeps the same control flow and
replaces only the other batches' non-mutating payload checks with jumps to their
unchanged successors. Every inventoried obligation belongs to one batch, and
every batch must pass. The Lean erasure theorem preserves reachability for a
retained obligation; batching does not relax the checker resource limits.

The Python adapter and exporter remain trusted: these proofs do not establish
their correspondence to the compiler or LLVM. Runtime integer canonicalization,
container read contracts, pointer lifetime and the implementation of integer
operations also remain trusted. Tuple construction must finish on fresh storage
before the tuple escapes; the adapter does not prove allocation freshness or
general heap aliasing. Arithmetic fit claims use the separate
[integer proofs](INT.md); they are not inferred from the mere presence of a
`select` that discards digits. These are bounded compiler checks, not a proof
of Python equivalence or memory safety for the entire compiler.
Index bounds for tuple iteration are also a separate obligation; the storage
check concerns the marker and layout of its trailing digit read.
Stack tuple escape copies are a separate transport case. The adapter accepts
only a contiguous, complete copy of every word at the same index into a fresh
allocation, with identical source-slot and destination representations and no
other use of the copied words or addresses. Each copied trailing word requires
the `on_stack` test of that exact source pointer. This relies on an additional
call ABI contract: an on-stack tuple has the full physical extent of its
specialization layout. A promoting read view alone does not establish that
extent. The stack-copy theorem proves bounds and unchanged copied words under
this explicit premise; it does not authorize ordinary digit decoding without
a marker guard. Reports count these transport reads and obligations separately.
Speculative operations are restricted to total machine operations and the
recognized read-only `range.has` and boolean-list search forms; their runtime
contracts are trusted. Calls that can raise or run user code are not treated
as speculative arithmetic.

## Run and coverage

Use the pinned Lean toolchain in `lean-toolchain` and the repository's pinned
Python interpreter:

```sh
make check-lean-boundary
make check-lean-storage LEAN_STORAGE_FLAGS='--jobs 2 --report /tmp/lean-storage.json'
python3.13 tools/check_lean_storage_corpus.py --list
```

The report path must be new. Selection follows imports and `.path` files with
the compiler's `python-int` pragma recognizer. It includes programs that only
import an opted-in module, including a typed caller of such a module.
Each selected program is compiled afresh by the hosted compiler. Reports retain
snapshot and candidate hashes, per-function outcomes, proof batches and obligation counts. Unsupported
forms and failed inspections fail the gate, and an empty corpus or vanished
obligation inventory cannot pass. Corpus coverage is limited to the existing
differential programs and deviations, not examples, benchmarks or arbitrary
user programs.
Raw low-word uses and trailing reads are reported separately from deduplicated
normalized proof obligations. An incomplete normalization increments
`unclassified_functions`; a successful run must report zero.

CI reuses the pinned Lean archive and existing verification jobs, with two
workers and a separate `lean-storage.json` artifact: PR `opt-in` and full-run
x86 `scaling`. This keeps the full dynamic-`Any` job within its existing time
budget. No extra CI job is added.
