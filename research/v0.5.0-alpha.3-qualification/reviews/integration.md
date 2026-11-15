# Independent alpha.3 integration source review

Reviewed on 2026-11-15 UTC. This is a read-only source review, not a new execution or release-gate result.

- Repository: `den-run-ai/pystachy`.
- Baseline: alpha.2, `80490143498d149d407343ba1cb7aedb1db2d2c5`.
- Reviewed target: PR #1496 head, `7baadaf1cb1c34901ce31c70a5ba0c43c05391c2`.
- Source: git objects in `/workspace/scratch/f0e0f1c84d2f/pystachy`; all reviewed source/diffs were selected by the target commit, independently of the checkout's current HEAD.
- Prior evidence consulted: `/workspace/scratch/f0e0f1c84d2f/alpha3-independent-review`, whose recorded older review target was `ae71fb03f3f5c44da0bd7fbaf48e63f7b0488fe3`. Those execution results have not been relabeled as evidence for the new target.

## Conclusion

No actionable release-blocking defect found in the reviewed integration paths. The alpha.3 release notes accurately bound the advertised implementation and Lean proof scope. This conclusion is a source-review result; exact merged-commit CI, bootstrap, full IR, Lean/GC and artifact qualification remain separate required evidence.

## Integration paths checked

1. **Runtime-length tuple ABI and identity.** Traced the new `VTuple.ids` header field through runtime layout assertions, allocation extents, compiler item offsets, fast iteration, copying/slicing/list conversion and runtime operations. The structure is 16 bytes before its items, with generated item offsets moved consistently from one to two words. The identity companion remains distinct from optional scalar representation boxes. Equality/order recognize shared identities before scalar comparisons, including NaN behavior.

2. **Optional numeric lists and tuples.** Reviewed new optional identity kinds 9/10, preservation of the optional bit in kind masks, nullable identity materialization, list get/set representation handling and the runtime effect specifications. Existing representations are reused where necessary without conflating representation boxes and identity boxes.

3. **Keys and promoting integers.** Traced None/optional/union key hashing and equality guards, identity-only class-union eligibility, runtime-length versus fixed tuple hashes, set re-kind operations, missing None lookups and optional fixed-tuple wide-integer narrowing/widening. Union/optional absent payloads are checked before dereference; unions with overloaded class equality/hash remain rejected by the intended boundary.

4. **Generator identity storage.** Reviewed promise slot extents, wide-integer and identity side channels, `yield from`, snapshotting before resume, destructuring and `next(g, default)`. The new numeric identity channel uses an independent nullable pointer and private snapshots where the promise can be overwritten. The release notes advertise optional numeric lists/tuples, not general optional generator support.

5. **Complex and numeric dispatch.** Reviewed the two-float complex representation, synthetic module loading, class emission, primitive/reflected dispatch, read-only fields, constructor identity behavior and the C numerical routines' bounded CPython 3.13 correspondence. Release notes preserve the restrictions on ordering, floor division, modulo, assignment, sum and cmath.

6. **Decimal surface and cross-type operations.** Reviewed context and rounding structure, integer-coefficient arithmetic, comparison/hash paths, complex equality, supported conversion/rounding protocols and documented exclusions. The limited API, absence of configurable signal/trap behavior, global context/thread limits and unsupported constructors/subclasses are documented. No new execution equivalence is claimed by this review.

7. **Constructor specialization.** Checked fixed-layout eligibility, hierarchy retries, field initialization/layout restrictions, temporary class/template state restoration and lazy unused imports/classes. Documentation limits the claim to supported hierarchies rather than arbitrary constructors.

8. **Lean correspondence and release wording.** Reviewed the expanded layout inventory, payload-consumer validation, bounded reference transfer adapter, initialized numeric-list companion adapter and storage handling for generator identity operands. Unknown executable AST shapes fail closed in the adapters. The documentation explicitly retains the exporter/lowering, helper, allocation and concrete collector assumptions and excludes general collector/alias correctness and tuple/generator companion proofs from the numeric-list theorem.

This complements the separate focused #1496 comparison review; it is not an exhaustive line-by-line audit of every changed test and documentation file.

## Non-blocking documentation discrepancy

`tools/lean_boundary/README.md` near its Lean import inventory says the current local imports are limited to a list that omits the new `PystachyLayout` and `PystachyCompanion` modules. Both are actually imported by `Audit.lean` and the relevant front ends and are documented in the new sections below. The exhaustive inventory sentence should eventually include those two local modules. This is a documentation-list omission, not an untracked external dependency or proof/runtime defect, and does not warrant holding the prerelease.

## Checks performed and boundaries

- Read `AGENTS.md`, release instructions, workflows, release gate/PyPI logic, release notes, changed runtime/compiler paths and bounded-proof adapters.
- `git diff --check 80490143498d149d407343ba1cb7aedb1db2d2c5 7baadaf1cb1c34901ce31c70a5ba0c43c05391c2` completed without output/errors.
- No compiler build, runtime execution, test suite, Lean build or heavy qualification was started by this review.
- No source checkout mutation, workflow dispatch or GitHub write was performed.
- Publication preparation is recorded separately in `publication-plan.md` in the same analysis directory.

