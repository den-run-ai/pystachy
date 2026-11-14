# Lean compiler safety checks

The checkers prove selected properties of normalized generated IR. There is no
compiler-wide verified-code percentage: obligations overlap, and a theorem about
the model does not establish that the exporter or runtime implements that model.

| Area | Enforced property | Current boundary |
|---|---|---|
| Dynamic `Any` | Payload reads have matching type guards | Runtime tag/layout contracts |
| Lists, dictionaries and sets | Unchecked accesses have bounds/live-entry facts | Runtime effects and container contracts |
| Closure cells and calls | Captured-container facts survive only valid reads; visible callee writes invalidate facts | Independent Python body-effect scan and cell ABI |
| Promoting integers | Selected result-fit claims and actual checked `+`, `-`, `*` reconstruction paths | Other inline arithmetic, LLVM and integer runtime |
| Integer storage | Low-word, tuple-tail, narrowing and complete stack-copy obligations | Exported representations, fresh allocation and stack ABI |
| Null-check removal | Removed checks are redundant in the captured before-pass graph | Whole-pass equivalence and broader heap correlations |
| Closed unions | Inventoried tag/payload reads have nonnull/member guards | Raw transport, dynamic reconstruction and unsupported forms |

All accepted certificates are checked by Lean. Mutation controls exercise the
Python adapters, including lost inventories, exceptional edges and forged facts.
Parsing, inference, specialization, GC/lifetime, general optimization equivalence,
exception semantics and LLVM lowering remain unproved.

[GUARDS.md](GUARDS.md) describes the bounded null/union CI examples and the strict
full-corpus inventory command; full-corpus acceptance is not claimed.
Broader null/union correlations and unsupported forms are tracked in
[#1270](https://github.com/den-run-ai/pystachy/issues/1270).

The same Lean project also builds the [unchecked-access checker](ACCESS.md), which proves list
reads within bounds and reused dict entries live.
The [promoting-integer storage checker](STORAGE.md) extends the same checked
control-flow model to low-word uses, tuple digit slots and representation
crossings. Its storage model and trust boundary are separate from the dynamic
payload-tag obligations described here.

This optional developer tool checks the guards of `dyn.payload` operations in
one selected function, or in every function, of a completed Pystachy typed-IR
snapshot; `make check-lean-corpus` checks every such read of the dynamic-`Any`
test programs. It does not change compilation, dynamic-`Any` opt-ins, library
behavior or runtime checks.

[INT.md](INT.md) describes the proofs of promoting ints' fit claims and
`make check-lean-int`, which checks each such claim of the programs that opt in.

## Provenance and license

The Pystachy-specific model, proofs, examples and checker source are covered by
the repository's [MIT license](../../LICENSE). They implement a certificate
checker for Pystachy's normalized tag-state control flow, with a Python adapter
for its inspection schema. They do not import or vendor CPython models, proofs,
registries or test data from
[Broyojo/python-formalization](https://github.com/Broyojo/python-formalization).
That project's [Apache-2.0-licensed work](https://github.com/Broyojo/python-formalization/blob/17bf78a9856c06fea409349246be4a06482518d1/LICENSE)
was a reference for the discussion motivating this separate prototype.

The original payload-checker provenance review compared its three Lean source files with
that project's pinned `17bf78a9856c06fea409349246be4a06482518d1` tree, including its axiom
audit; that historical comparison found no copied implementation. The shared logical axiom names and
`Lean.collectAxioms` calls are standard Lean interfaces. This records a source
and dependency review, not a formal proof of authorship.

Current Lean imports are limited to `Std`, `Lean` and the local `PystachyBoundary`,
`PystachyAccess`, `PystachyInt`, `PystachyInline`, `PystachyStorage` and
`PystachyGuards` modules; `lake-manifest.json`
contains no external packages. The pinned Lean
toolchain is an external development dependency with its own
[Apache-2.0 license](https://github.com/leanprover/lean4/blob/v4.35.0/LICENSE).
It is downloaded for CI and is not vendored in this repository. Its license is
separate from the MIT identifiers on this project's Lean sources. Future copied
or adapted third-party code must retain its actual license and provenance.

## Build and run

Install the Lean toolchain named by `lean-toolchain` (Lean 4.35.0), with `lake`
available on `PATH`. This project has no external Lean package dependencies.
From the repository root:

```sh
make check-lean-boundary PY=python3.13

python3.13 tools/inspect_compiler.py \
  tools/lean_boundary/examples/narrowed_float.py \
  --output /tmp/pystachy-lean-example --function float

python3.13 tools/check_lean_boundary.py \
  --snapshot /tmp/pystachy-lean-example/typed-after.json \
  --function narrowed_float

python3.13 tools/inspect_compiler.py \
  tools/lean_boundary/examples/classes_and_ints.py \
  --output /tmp/pystachy-lean-classes

python3.13 tools/check_lean_boundary.py \
  --snapshot /tmp/pystachy-lean-classes/typed-after.json \
  --function dyn.call.label.0

python3.13 tools/check_lean_boundary.py \
  --snapshot /tmp/pystachy-lean-classes/typed-after.json --all

make check-lean-corpus PY=python3.13
```

The inspection output directories must be new. `narrowed_float.py` and
`guarded_state.py` exercise float, string and bool guards, a saved copy that
survives rebinding, and a loop that rechecks its tag after each reassignment.
`classes_and_ints.py` reads a class's payload after `isinstance` (its subclass
passes the test too), an int's after `isinstance(x, int)` (a bool passes too), and
each class's in the dispatcher that a method call on an `Any` value compiles to.
The checker reports the selected symbol, payload and node counts, exact
snapshot/candidate SHA-256 hashes, its scope, and its remaining trust
assumptions. Selection is by exact function name or symbol; ambiguous
selections fail. A function with zero payload reads is reported as such and
provides no evidence about a dynamic crossing.

`--all` checks every function of the snapshot that reads a dynamic payload and
reports each one's result, read count and candidate hash. Its status and exit
code are the worst function's: an error, then a rejection, then an unsupported
form. A read in a block that nothing reaches cannot run; it counts as proved
with its function. The snapshot must be a completed typed-after inspection even
when no function reads a payload.

`tools/check_lean_corpus.py`, which `make check-lean-corpus` runs after building
the checker, does that for the dynamic-`Any` corpus: each differential test
program and deviation that opts in to dynamic `Any` (the compiler's own pragma
test), or whose imports reach a module that does. Imports are followed through
the program's search path as the compiler gives it (its directory, its
`NAME.path` directories, then `lib/`), each regular package's `__init__.py` on
the way, namespace packages (directories without one) included, and every import
of a file, wherever it is, so the selection over-approximates.
Each program is compiled by the hosted compiler under
`tools/inspect_compiler.py --typed-after-only`, which records only the final
snapshot, and the run fails unless Lean accepts every function that reads a
payload and, by the [unchecked-access checker](ACCESS.md), every function with an
unchecked list read or dict entry. `--list` prints the selection; named programs
are checked instead of it.

`--checker PATH` selects another built checker. `--emit NEW_FILE` writes only the
candidate program and certificate: its report says `prepared`, `checked: false`.
The output file must not already exist. A candidate can be checked directly with
`tools/lean_boundary/.lake/build/bin/pystachy-boundary < candidate.json`.

| Python command exit | Meaning |
|---|---|
| 0 | Accepted by Lean, or candidate prepared when `--emit` was requested; inspect `status` and `checked`. |
| 1 | Lean rejected the candidate proof obligations. This alone does not establish a compiler bug. |
| 2 | Selected IR uses a form outside the supported abstraction. |
| 3 | Malformed snapshot, missing checker, timeout, inconsistent checker response or another operational error. |

## What is proved

`PystachyBoundary.accepted_payload_safe` states that, if `check` accepts a
normalized program and its certificate, every reachable payload operation reads
a location whose abstract tag is one of the tags that operation accepts. The
theorem quantifies over arbitrary initial tags and every finite execution,
including loops and nondeterministic branches. It does not assume that payload
execution was already safe.

The model has copies, assignment of an unknown tag (`havoc`), guards that test
whether a location's tag is one of a finite set, unconstrained branches, jumps,
payload reads that accept a finite set of tags, and stops. A location represents
an SSA value, a mutable private slot or an immutable constant box. Copying a
location copies its current tag; subsequent reassignment does not change the
earlier copy.

Python suggests facts at each program point, each confining one location's tag
to a set. Those facts are untrusted: the Lean checker independently checks empty
entry facts, certificate length, every target, every edge transfer and every
payload obligation. A guard's success narrows a fact to the tested set and its
failure removes those tags; joins must justify their facts from every
predecessor. A cyclic certificate cannot invent a reachable fact without an
establishing guard.

The build also checks eighteen examples with kernel reduction: successful slot
reloads and a guarded loop; an int read that accepts a bool; a class test whose
None case a second guard excludes; and a switch's default case. Rejections cover
wrong values, forged facts, rebinding, unknown writes, unguarded joins, circular
facts, missing targets, a join of two tags only one of which a read accepts, and
a class read without the None exclusion. `Audit.lean` checks the transitive axiom
dependencies of the public theorems, rejecting admitted proofs, extra axioms and
native-computation assumptions. The allowed axioms are Lean's standard
`propext`, `Classical.choice` and `Quot.sound`.

## How actual IR reaches the model

`tools/check_lean_boundary.py` reads the existing inspection schema, validates
the selected function and emits normalized nodes for its instructions. A box's
tag is its DynType descriptor's symbol: a runtime.c builtin's, or one of the
program's own, which `typed-after.json` lists in `dynamic_types` (its kind,
class number, base, role, flags and payload type). Each typed-IR operation has an
explicit role:

- A payload read accepts the descriptors whose boxes hold its static type's
  layout: the builtin type's own, and also a bool's for an int (its payload is its
  int value) and both native int list descriptors for `list[int]`. A class's read
  accepts its own descriptor, those whose bases lead to it (subclasses share its
  layout) and those naming it as their secondary role. A function's or
  generator's read accepts its one descriptor. Other payload types are refused.
  Before constructing the proof, the adapter also checks how the projection's
  bits are consumed: `slot.unpack` must use the declared payload type, and only
  an `int` payload may be used directly as an integer or copied unchanged into
  the runtime's `box`/`ubox` slot argument. The internal address may
  not escape, and other raw-slot transports are unsupported. Producer identity
  comes from result numbers, not a consumer's operand annotation. This is a
  structural check in the trusted Python bridge, not a Lean proof of runtime
  layout or of `slot.unpack` lowering.
- Guards come from tests of a box's tag: comparisons of its DynType with a
  descriptor; runtime.c's `pys_dyn_isa` and `pys_dyn_role_isa`, whose accepted
  descriptors the table determines (a class's subclasses and None, or both int
  descriptors); class dispatchers' switches on the class number a DynType holds
  (word 3, which only program classes set); and `and`, `or` and negation of these.
  A branch or a `check` on such a condition becomes a decision over its tests;
  an unknown operand becomes an unconstrained branch. A test is used where its
  result is used: operands are SSA values whose definitions dominate their uses,
  so the tested boxes are unchanged there.
- Private slots are named as lowering names them, by text and kind. A local's
  "is assigned" flag (`%x.def.N`) and numeric identity companions (`%x.box.N`,
  `%x.boxgen.N`) share the local's number `N`; each remains a separate location.
  Loads and stores become copies or unknown assignments; a null store (an
  unbound local, or an identity box not made yet) is an unknown assignment. A
  stack tuple's register is a tuple value, not storage.
- A numeric parameter's identity companion (`%aidN`) also starts with an unknown
  tag, since the caller's box may be null. The compiler's numeric-identity
  predicate identifies the eligible parameters, including optional and joined
  numeric types; a nonexistent companion or a non-box annotation is malformed.
- A slot paired with a box, because the box was loaded from or stored into it and
  no path since writes the slot, is guarded together with the box: a later reload
  of the slot keeps the fact. Paths on which the two tests would disagree stop.
  The pairing is a must analysis over every edge, including exception edges.
- A slot whose address reaches any other operation, such as an identity-return
  buffer passed to a callee, is not private: its loads get unknown tags, and no
  guard is moved onto it.
- Every other operation, including calls, generator resumption, field and
  machine loads, `select` and `phi`, can write neither a private slot nor a box,
  which the runtime keeps immutable. It only defines its results: one the
  function uses as `dyn` gets an unknown tag. A store through an address computed
  from a box or a descriptor is refused; immutability beyond that is part of the
  trusted runtime contract.
- Terminators give the edges: branch and `switch` targets, an invoke's unwind
  edge, each `check`'s error block (the snapshot's `check_targets`), a `raise` or
  `throw` that branches to its handler and, conservatively, an edge from every
  point of a block that a `try` statement covers to its landing block. Exception
  lowering has run: it turned each call there that may raise into an invoke and
  dropped a landing block that no invoke reaches. A block whose landing block was
  dropped keeps its name but has no exception edge; a call there that raises
  anyway leaves the function (runtime.c's personality routine continues unwinding
  past a call site without a landing pad).

A short-circuit condition such as `flag and isinstance(x, str)` joins in a block
that holds only a boolean `phi` and a branch on it. An edge into that join whose
incoming value is known there (a constant, the branch condition that chose the
edge, or a tag test) goes directly to the matching successor, through that
test's guards. Other edges reach the join's branch, which is unconstrained.
Blocks and nodes that nothing reaches cannot run and are omitted. Facts about a
location that no later node reads are not kept in the certificate. The report
counts omitted blocks, threaded edges, paired guards and escaped slots.

Tests corrupt the real IR of each supported form and require rejection: a
redirected loop backedge, a rebinding or a store between a test and its branch,
the None exclusion of a class test, a subclass read after a base-class test, an
int read whose test admits a float, swapped or misread class-dispatch cases, a
renumbered class, and each edge form leading to an unguarded payload. `json`'s
shipped dynamic key writer is accepted only with both of its guards. These are
checks of the trusted Python bridge in addition to the kernel-checked model
examples; they do not prove its fidelity.

Generator functions, stores into boxes or descriptors and unknown operations
are explicitly refused. No selected function is silently skipped. The Python
bridge allows at most 4,096 instructions, 1,024 blocks, 16,384 normalized nodes,
65,536 certificate facts holding 262,144 tags, 4 MiB candidate JSON, a 4 MiB
snapshot (512 MiB with `--all`) and 200,000 inference iterations; the native
checker has a ten-second subprocess deadline.

## Coverage of compiled code

On 2026-11-11, `make check-lean-corpus` checked the 480 programs it selects
from this checkout: 1,153 functions read a dynamic payload, 2,579 times. Lean
accepted every function, so every one of those reads is proved to be guarded.
The same run proved all 7,500 of their [unchecked accesses](ACCESS.md), in about
250 seconds with two workers. An earlier sweep found the two forms
this needed: slice bounds of an `Any` value and `sum()` of `Any` values read int
payloads that no tag test guarded (their compiler guards are
[#1227](https://github.com/den-run-ai/pystachy/pull/1227)), and two length-hint
and iterator helpers kept the names of landing blocks that lowering dropped.
CI runs the same check on every code change, so a compiler change that leaves a
payload read unproved fails.

## Trust and coverage limits

The formal theorem concerns the normalized tag-state program. The following are
not proved by this version:

- Fidelity of the inspection snapshot and Python normalization to actual IR
  execution, including the operation roles, edges, join threading and slot
  pairing described above.
- The descriptor table: that it lists every DynType the program emits. (runtime.c's
  iterator descriptors have no base, class number or kind that an interpreted test
  admits.) The class numbers that dispatchers switch on must identify the program's
  classes. The bridge's copies of runtime.c's builtin kinds, role flag, class number
  word and builtin payload tags are tested against runtime.c
  ([test_typed_dynamic_tables.py](../test_typed_dynamic_tables.py)), not proved.
- Payload layout: that a subclass's, a secondary role's, a bool's and a native
  int list's payloads have the layouts their accepted reads assume.
- Object initialization, null/unbound behavior (a null dynamic value has no tag,
  so it must never pass a guard), GC, aliases in mutable containers, or the
  implementation of runtime tag operations.
- Source-language or LLVM equivalence, generic specialization, identity-slot
  elision, absence of dynamic operations, or necessity/removal of `Any`.
- That the corpus covers every program shape: it is the test programs and
  deviations whose imports reach an opted-in module. Examples, benchmarks and
  ports are not checked.
- Termination or a performance improvement.

The CLI runs compiled Lean code, so its result also trusts the Lean compiler,
runtime and JSON/IO front end. The theorem's proof and axiom audit use the kernel;
the model-to-implementation relationship remains a separate obligation. Hashes
identify the checked artifacts and do not prove that relationship. Continue the
ordinary CPython differential, JIT/AOT and GC validation when changing behavior.

`make check-fast` runs the Python bridge tests and runs executable checks when a
built checker is present. `make check-lean-boundary` builds and audits the proofs
and requires every executable check. The existing Lint job runs that target for
PR changes to the prototype, its tests, the compiler, the inspection exporter,
build/workflow files or development tool pins; it also runs on every main push
and manual dispatch. PR selection uses the cumulative merge diff and runs
conservatively if its history is missing. Five workflow tests exercise the
actual selector against temporary Git histories. `make check-lean-corpus` runs in
the x86_64 verification group `opt-in` of every PR that changes code, and in
`runtime-cache` on main and manual runs; a sixth test keeps both jobs on one
Lean archive; that target first runs the corpus tool's own tests
(`tools/test_lean_corpus.py`). Both jobs download the pinned, SHA-256-checked
Linux Lean release; no PR job is added. Lean is not a compiler, runtime or
installation dependency.

This is a verification building block for
[#1210](https://github.com/den-run-ai/pystachy/issues/1210). The compiler already
has a separate [closed-union proof](../../docs/typed-ir.md) from
[#840](https://github.com/den-run-ai/pystachy/pull/840). With
`PYSTACHY_IRCHECK=1`, the stock verifier also checks the tags of every dynamic
payload read, including class, container and function reads, over its actual
control-flow graph. That compiler analysis is not proved here; this optional
checker is an independent check of the same obligation. Runtime layout, lifetime,
identity, GC and LLVM obligations remain outside both checks. Neither satisfies
#1210's acceptance requirement of reducing a consumer's dynamic footprint; the
typed TOML namespace state in
[#1211](https://github.com/den-run-ai/pystachy/pull/1211) is separate containment work.
