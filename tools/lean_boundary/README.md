# Lean payload-guard prototype

This optional developer tool checks the guards of `dyn.payload` operations in
one selected function from a completed Pystachy typed-IR snapshot. It does not
change compilation, dynamic-`Any` opt-ins, library behavior or runtime checks.

## Provenance and license

The Pystachy-specific model, proofs, examples and checker source are covered by
the repository's [MIT license](../../LICENSE). They implement a certificate
checker for Pystachy's normalized tag-state control flow, with a Python adapter
for its inspection schema. They do not import or vendor CPython models, proofs,
registries or test data from
[Broyojo/python-formalization](https://github.com/Broyojo/python-formalization).
That project's [Apache-2.0-licensed work](https://github.com/Broyojo/python-formalization/blob/17bf78a9856c06fea409349246be4a06482518d1/LICENSE)
was a reference for the discussion motivating this separate prototype.

The provenance review compared the three Lean source files with that project's pinned
`17bf78a9856c06fea409349246be4a06482518d1` tree, including its axiom audit;
it found no copied implementation. The shared logical axiom names and
`Lean.collectAxioms` calls are standard Lean interfaces. This records a source
and dependency review, not a formal proof of authorship.

Lean imports are limited to `Std`, `Lean` and the local `PystachyBoundary`
module; `lake-manifest.json` contains no external packages. The pinned Lean
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
  point of a block that a `try` statement covers to its landing block.

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

Generator functions, stores into boxes or descriptors, landing blocks missing
from the snapshot and unknown operations are explicitly refused. No selected
function is silently skipped. The Python bridge allows at most 4,096
instructions, 1,024 blocks, 16,384 normalized nodes, 65,536 certificate facts
holding 262,144 tags, 4 MiB input/candidate JSON and 200,000 inference
iterations; the native checker has a ten-second subprocess deadline.

## Coverage of compiled code

On 2026-11-11, every function that reads a dynamic payload in the compiled
`typed-after` IR of 420 dynamic-`Any` test programs, inspected from this
checkout with the hosted compiler, was checked once per distinct function body:
1,039 functions holding 2,308 payload reads. Lean accepted 1,004 functions
outright. Two functions whose landing blocks the snapshot lacks (23 reads) were
refused. In the other 33, the uncovered reads were removed and Lean accepted the
rest: 2,137 reads (92.6%) are proved. That is every float, str, bool, dict, list,
tuple, function and generator read, 98.3% of class reads (the rest are in the two
refused functions) and half of the int reads. The slowest check took 0.07 seconds.

The other 148 int reads depend on invariants the model cannot express:

- Slice bounds of an `Any` value (`index_bound`, `src/pystachy_compiler/dynamic.py`)
  read the int payload of a box that may be None, then discard it. That is
  memory-safe only because runtime.c's None box has a zero payload word; its
  payload contract does not hold (106 reads).
- `sum()` of `Any` values reads its accumulator's int payload where its phase
  word says the accumulator holds an int, without testing its tag (42 reads).

## Trust and coverage limits

The formal theorem concerns the normalized tag-state program. The following are
not proved by this version:

- Fidelity of the inspection snapshot and Python normalization to actual IR
  execution, including the operation roles, edges, join threading and slot
  pairing described above.
- The descriptor table: that it lists every DynType the program emits, and that
  runtime.c's builtins have the kinds the bridge assumes. (runtime.c's iterator
  descriptors have no base, class number or kind that an interpreted test admits.)
  The class numbers that dispatchers switch on must identify the program's classes.
- Payload layout: that a subclass's, a secondary role's, a bool's and a native
  int list's payloads have the layouts their accepted reads assume.
- Object initialization, null/unbound behavior (a null dynamic value has no tag,
  so it must never pass a guard), GC, aliases in mutable containers, or the
  implementation of runtime tag operations.
- Source-language or LLVM equivalence, generic specialization, identity-slot
  elision, absence of dynamic operations, or necessity/removal of `Any`.
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
actual selector against temporary Git histories. It downloads the pinned,
SHA-256-checked Linux Lean release and adds no
PR job. Lean is not a compiler, runtime or installation dependency.

This is a verification building block for
[#1210](https://github.com/den-run-ai/pystachy/issues/1210). The compiler already
has a separate [closed-union proof](../../docs/typed-ir.md) from
[#840](https://github.com/den-run-ai/pystachy/pull/840). With
`PYSTACHY_IRCHECK=1`, the stock verifier also checks `float`, `str`, `bool` and
`int` dynamic payload tags over its actual control-flow graph. That compiler
analysis is not proved here, and does not yet check the class, container and
function reads this optional checker covers. Runtime layout, lifetime,
identity, GC and LLVM obligations remain outside both checks. Neither satisfies
#1210's acceptance requirement of reducing a consumer's dynamic footprint; the
typed TOML namespace state in
[#1211](https://github.com/den-run-ai/pystachy/pull/1211) is separate containment work.
