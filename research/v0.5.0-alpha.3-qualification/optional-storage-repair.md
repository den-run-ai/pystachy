# Nested optional tuple storage adapter repair

The release blocker is an incomplete storage-adapter model, supported by the exported typed IR and retained LLVM. No compiler, runtime, differential fixture, or Lean theorem source changed. The historical census remains a strict-storage failure: eight counted obligations passed, but three functions had unsupported results with unknown counts. The repaired adapter checks all 142 target obligations and accepts every selected storage function.

## Source and evidence identity

- Base commit: `94f472d6de5350fc9481ecf3b9ec019d2ecdb4f2`, tree `51f6c150748b2d17945e4d1c6779d8080b6edd6a`.
- Frozen repair tree: `107460d5f89bdcf37f2741b233eac0568d82604a`.
- Worktree: `/workspace/scratch/980402bc01c4/alpha3-storage-fix`; four staged files, no local commit or push.
- Exact patch and file hashes: `frozen-repair.json`, `repair.patch`, and `frozen-source/` beside this note.
- Historical complete-census row: `historical-census-target-record.json`, preserving census snapshot SHA `9638ff0347f8a12f23fdd7a7be72bd35343080ec966bcfe432f74c3819c7d76b`.
- Focused snapshot: `baseline-inspection/typed-after.json`, SHA `da903fa37e5e7685dad7eae60c9b8812c2bd8c79e41aad0ffc0b171f44abc62e`. This is a fresh hosted `--typed-after-only` inspection without `--guard-evidence`, not an exact replay of the census snapshot.
- Retained LLVM: `/workspace/scratch/980402bc01c4/ir-audit/cases/1969/new.ll`, SHA `f9011ef418d21a5c87f28aedff531b400f35a6dae82aff2747b9d1ec9de2c207`.

## Exact unsupported boundaries

`baseline-boundary-failures.json` preserves the original adapter failures with defining operations and consuming phi/return instructions.

| Function and value | Original representation | Requested view | Operation |
|---|---|---|---|
| `@main.init`, `%t411` | `tuple[opt[tuple[int,int]],str]` | `tuple[opt[tuple[int+,int+]],str]` | Incoming edge of `%t528` phi |
| `@f.exercise`, `%t903` | `tuple[opt[tuple[int,int]],str]` | `tuple[opt[tuple[int+,int+]],str]` | Incoming edge of `%t1027` phi |
| `@f.fixed_optional_tuple_keys$read_nested`, `%t7` | `opt[tuple[opt[tuple[int+,int+]],str]]` | `opt[tuple[opt[tuple[int,int]],str]]` | Return |

Once those child shapes were recognized, the next previously masked boundary was `@main.init` `%t459`: `tuple[tuple[int+,int],str]` to `tuple[opt[tuple[int+,int+]],str]`, at the incoming edge of `%t588`. This adds optionality to an existing nonnull child and still requires the fixed integer's marker check. `first-repair-boundary-results.json` retains that intermediate finding.

The compiler's `gen_big_tuple_narrow` explicitly guards optional tuples before descending into their children. In `read_nested`, LLVM tests the outer `%t7` and inner `%t13` for null. The present path decodes both integer cells under their marker tests and checks each digit pointer before returning the original pointer. Both failed narrowing checks raise `OverflowError` and terminate. The complete typed function is retained as `read_nested-typed.json`. This source/IR review identifies the adapter mismatch; it is not a new native-runtime execution or a proof of general null safety.

## Narrow repair and soundness boundaries

`Normalize.tuple_path` now preserves an optional tuple child's identity through its tuple load and pack/unpack operations. Source-layout lookup descends through an optional parent and preserves the child's original representation rather than adopting the consuming view.

Recursive boundary comparison checks every changed integer cell inside optional tuple children. It permits the same optionality and adding optionality to a nonnull tuple child. Removing a child's optionality, changing a scalar representation, or changing tuple arity remains refused. Adding optionality never supplies a fit or marker fact.

An actual null branch may establish the existing absent-or-fit property recursively. For a fixed integer cell it may similarly establish absent-or-non-marker. These facts describe an actual integer encoding only on paths that decode a present tuple; null-dereference safety is a separate model obligation.

An intermediate complete normalization exposed 142 obligations but left six promoting-view sites unproved. The exact result is retained in `target-after-first-complete.json`. All six concern a nested child explicitly stored as null in `%t411`, `%t903`, or stack tuple `%stk.1034`; the optional copy test's boolean phi was opaque to the adapter. `nested-null-construction-sites.json` preserves the actual stores and surrounding operations.

The repair does not add general boolean-phi reasoning. It emits absence facts at the actual literal-null tuple store in the normalized CFG. Every nested child store first invalidates all descendant marker, digits, and fit facts; only that store's explicit null value can install new absence facts. The existing second reset pass also clears cells introduced later by phi-edge boundary extraction. Branch joins therefore retain only facts justified on all incoming paths, and replacing a child cannot preserve its earlier absence. Aliased or raw tuple writes remain outside the supported model and are refused.

## Validation on the frozen files

`final-all-storage-tests.json` and `.log` record all **69 tests passing**, with no skips, errors, or failures, across every `test_lean_storage*.py` suite. The unittest runner reports 21.375 seconds; the outer process receipt records 21.531 seconds. The receipt verifies that all four source file hashes were unchanged throughout execution.

The real target's result in `final-target-result.json` is:

| Selected storage function | Proved obligations |
|---|---:|
| `@main.init` | 50 |
| `@f.show` | 0 |
| `@f.exercise` | 76 |
| `@f.fixed_optional_tuple_keys$add_fixed` | 2 |
| `@f.fixed_optional_tuple_keys$contains_fixed` | 2 |
| `@f.fixed_optional_tuple_keys$read_fixed` | 4 |
| `@f.fixed_optional_tuple_keys$read_nested` | 8 |
| **Total** | **142 / 142** |

The program has eight exported functions; seven are selected for storage checking, including the zero-obligation `show`. The target has zero unclassified, unsupported, rejected, or error results. Its accompanying integer/inline result also accepts. No obligation denominator was waived or replaced by zero.

New controls verify:

- Each of the two real nested narrowing guards remains necessary.
- Skipping either actual outer/inner null test cannot manufacture absence facts.
- Bypassing the `%t459` nonnull child's sentinel copy guard is rejected.
- Adding optionality does not excuse either narrowing or promoting-view guards.
- Literal-null construction accepts, while unknown children and later unknown replacements reject.
- A branch with a present/unknown child cannot inherit the other branch's null facts.
- Replacing a null child with a present `INT64_MIN` tuple rejects without a promoting-view guard.
- Fresh and stack tuple overwrites invalidate cells introduced only by later phi-edge boundaries.
- Aliased and raw overwrites remain unsupported.
- Original source layout and identity survive optional parent/child loads, while incompatible scalar, optionality-removal, and arity changes remain refused.

`baseline-final-regressions.json` and `.log` run the final new regression methods against the exact pre-repair adapter loaded from Git. Twelve test methods produce six failed assertions and fifteen errored subtests, with no skips; the expected pre-repair failure is preserved. These counts include unsupported normalization and diagnostic assertions, not fifteen independent runtime defects. The runner and baseline adapter bytes are retained beside the logs. Earlier intermediate attempts are preserved separately.

The unchanged boundary and integer checker executables and their SHA256 values are recorded in `reused-checkers.json`. Ruff on the three changed Python files and the staged diff whitespace check pass.

## Remaining release work and limits

The parent must integrate the reviewed four-file repair and run a fresh full census on its immutable source. The complete earlier census must remain labeled as strict-storage-failed. This focused result is not a replacement header for that run and does not certify unrelated model residuals.

The Python adapter, snapshot fidelity, runtime integer encoding, and immutable tuple contracts remain trusted. This repair changes proof inventory and normalization only; it does not claim a new bootstrap, native runtime run, or whole-compiler equivalence proof.
