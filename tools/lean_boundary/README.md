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

python3.13 tools/check_lean_boundary.py \
  --snapshot /tmp/pystachy-lean-example/typed-after.json \
  --function nested_float

python3.13 tools/inspect_compiler.py \
  tools/lean_boundary/examples/guarded_state.py \
  --output /tmp/pystachy-lean-state --function boundary_

python3.13 tools/check_lean_boundary.py \
  --snapshot /tmp/pystachy-lean-state/typed-after.json \
  --function boundary_loop
```

The inspection output directories must be new. `narrowed_float` and `nested_float`
contain one and two payload reads respectively. `guarded_state.py` adds boolean
and string guards, a saved dynamic copy surviving rebinding, and a loop that
rechecks the tag after each reassignment. Its four functions contain one, one,
two and one payload reads respectively. The checker reports the selected symbol,
payload and node counts, exact snapshot/candidate SHA-256 hashes, its scope, and
its remaining trust assumptions. Selection is by exact function name or symbol;
ambiguous selections fail. A function with zero payload reads is reported as such
and provides no evidence about a dynamic crossing.

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
a location whose abstract tag equals the operation's expected tag. The theorem
quantifies over arbitrary initial tags and every finite execution, including
loops and nondeterministic branches. It does not assume that payload execution
was already safe.

The model has copies, assignment of an unknown tag (`havoc`), exact-tag guards,
unconstrained branches, jumps, payload reads and stops. A location represents an
SSA value or a mutable private slot. Copying a location copies its current tag;
subsequent reassignment does not change the earlier copy.

Python suggests positive tag facts at each program point. Those facts are
untrusted: the Lean checker independently checks empty entry facts, certificate
length, every target, every edge transfer and every payload obligation. Joins
must justify their facts from every predecessor. A cyclic certificate cannot
invent a reachable fact without an establishing guard.

The build also checks ten examples with kernel reduction, including successful
slot reloads and a guarded loop, and rejections for wrong values, forged facts,
rebinding, unknown writes, unguarded joins, circular facts and missing targets.
`Audit.lean` checks the transitive axiom dependencies of the public theorems,
rejecting admitted proofs, extra axioms and native-computation assumptions. The
allowed axioms are Lean's standard `propext`, `Classical.choice` and `Quot.sound`.

## How actual IR reaches the model

`tools/check_lean_boundary.py` reads the existing inspection schema, validates
the selected function and emits a normalized node for each instruction. It
supports exact builtin `float`, `str` and `bool` tag comparisons, private scalar
slots, copies, simple scalar operations, jumps and returns. Unknown conditions
become nondeterministic branches. Supported scalar operations that cannot change
a dynamic tag or control flow become jumps; private dynamic loads and stores
remain explicit copies or unknown assignments.

Pystachy commonly loads a private slot for its guard, then reloads that slot for
the payload. The normalizer may put the guard fact on the slot only when the
load, tag read, comparison and branch occur in the same block and no intervening
store changed the slot. Otherwise it retains the original SSA operand, and a
later slot reload cannot borrow its fact. Tests corrupt both stores after the
branch and stores between comparison and branch. They also exercise swapped
comparison operands, equivalent negated guards, unrelated stores, and a
cross-block comparison for which the adapter conservatively derives no fact.

The real-IR loop test accepts a fresh guard on every iteration, then redirects
the backedge past that guard and requires rejection. The copy test removes a
redundant guard after rebinding: a saved copy still passes, while reloading the
changed original slot fails. These are checks of the trusted Python bridge in
addition to the kernel-checked model examples; they do not prove its fidelity.

Calls, exception handlers, dynamic phi nodes, escaping addresses, unsupported
instructions and unreachable blocks are explicitly refused. No selected function
is silently skipped. The Python bridge allows at most 1,024 instructions, 16,384
certificate facts, 4 MiB input/candidate JSON and 20,000 inference iterations;
the native checker has a ten-second subprocess deadline.

## Trust and coverage limits

The formal theorem concerns the normalized tag-state program. The following are
not proved by this version:

- Fidelity of the inspection snapshot and Python normalization to actual IR
  execution, including the same-block slot remapping described above.
- Object initialization, null/unbound behavior, payload layout, GC, aliases in
  mutable containers, or the implementation of runtime tag operations.
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

This is a first verification building block for
[#1210](https://github.com/den-run-ai/pystachy/issues/1210). The compiler already
has a separate [closed-union proof](../../docs/typed-ir.md) from
[#840](https://github.com/den-run-ai/pystachy/pull/840); the stock `dyn.payload`
checks cover instruction shape, with dynamic guard safety still a frontend
obligation. This optional checker addresses that obligation in its normalized
subset. It does not satisfy #1210's acceptance requirement of reducing a
consumer's dynamic footprint; the typed TOML namespace state in
[#1211](https://github.com/den-run-ai/pystachy/pull/1211) is separate containment work.
