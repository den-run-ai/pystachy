# Independent review of enum comparison repair

Reviewed PR: https://github.com/den-run-ai/pystachy/pull/1496

Reviewed head: `7baadaf1cb1c34901ce31c70a5ba0c43c05391c2`

Reviewed tree: `e027b37c888326e3d8a3e8b89522a6b397dcb86d`

Base: `f4336d21f5d2c73bc7f146a15386bd6c4586ec26`

## Result

No blocking defect found in the final repair. This review covered the complete PR diff and the affected alpha.3 comparison, enum construction, class layout, reflection, and dynamic admission paths. It was an independent source review by a separate review agent. No repository code, GitHub metadata, or workflows were changed during review.

## Contracts checked

- IntEnum/IntFlag versus int or promoting int, and StrEnum versus str, give the enum subtype comparison priority. Bool and float on the left retain their builtin comparison priority.
- The `@scalar` comparison candidate is terminal: it uses the original operator and operand ordering after earlier custom methods decline, without continuing to later stages after accepting.
- Inherited scalar `__ne__` uses the scalar payload instead of negating an overridden `__eq__`, consistent with the scalar slot contract.
- Optional primitive operands split before class dispatch. Concrete class alternatives exclude None before hidden payload reads; custom comparison methods can still receive None.
- Tuple searches explicitly pass leniency through recursive optional splits. Strict ordinary comparison behavior remains separate. The formerly observed narrow-annotation rejection is repaired on this reviewed head.
- StrEnum's immutable scalar payload is an ordinary hidden string field, initialized during enum-member construction and included in the scanned allocation. Public field lookup and reflection hide it. Reassigning `_value_` does not change the payload used by repaired comparisons.
- The Lean-layout test asserts both the original fixed-width parameter and the separately widened held tuple. The update corrects the held definition's representation without discarding the original parameter contract.
- Dynamic Any admission still rejects direct boxing of scalar enum members; this change does not claim a new dynamic enum representation.

## Evidence inspected

The local checkout `/workspace/scratch/9d370b13f051/enum-fix` was clean and at the reviewed SHA. The final bootstrap receipt records that same clean head and tree before and after execution, three identical compiler IR stages, three identical runtime IR stages, and return code zero.

The retained PR validation reports 128 focused native JIT/AOT executions, 14 GC-stress executions, 80 comparison/state unit checks, ten Lean-layout tests, and a 4,771-case IR comparison with no changed acceptance status. These are inspected prior-run results, not tests rerun by this review.

Detailed validation: https://github.com/den-run-ai/pystachy/pull/1496#issuecomment-6889405782

Existing local evidence:

- `/workspace/scratch/9d370b13f051/final-bootstrap.json`
- `/workspace/scratch/9d370b13f051/final-native-enum-tests.log`
- `/workspace/scratch/9d370b13f051/enum-lean-evidence/final-comparison-summary.json`

## Limits

This review did not rerun bootstrap, native execution, CI, or a full-corpus Lean census. The focused proof report leaves three pre-existing `_pystachy_copy._memo_get` obligations unchanged. Final merged-tree and release qualification remain separate gates.

Hashing and other enum methods after private `_value_` mutation remain documented limitations outside this comparison repair. The review did not establish whole-compiler or collector correctness.
