# Promoting-int compatibility baseline review

The experimental `# pystachy: python-int` mode is checked across the differential program
corpus by `make python-int-gate`. Every entry module receives the pragma, while its imports
retain their own policy. Fresh CPython recordings account for the inserted source line.
The gate executes JIT and AOT and checks the original program on every opt-in failure.

## Baseline and classification

The initial review used main `daeb6e0dff0e164df26cbd1239c0c5002bb891b5`, a freshly
bootstrapped native compiler, LLVM 18.1.3 and CPython 3.13.16. Its 1,819-program JIT sweep
reported 266 failing checks. These are not 266 independent language defects:

- 222 entry modules explicitly enable dynamic Any. Combining both pragmas is rejected by
  the documented representation contract.
- Ten entry programs exposed integration bugs addressed by this change: dataclass copying,
  repeated-field inference, inherited class attributes, in-place power, optional sorting
  keys, never-returning calls, Unicode exception positions and byte-hex separator grouping.
- 33 other programs reach known inference, union, callable, identity or dynamic-storage
  limitations. They are retained as individual exact compiler-rejection entries, not
  counted as successful promotion coverage.
- One failure was local oracle setup: a Python virtual environment pointed through an
  interpreter alias that made `sys.base_prefix` differ from `sys.base_exec_prefix`.
  Correcting the interpreter path restores the intended oracle. No exception permits it.

An initial cold-cache warmup also failed after the local LLVM installation left a temporary
file behind; a subsequent warmup succeeded. That setup failure is separate from corpus
results and is not exempted by the gate.

The prior PR's 267 failures used CPython 3.13.17, rather than the pinned 3.13.16; raw totals
from different oracle environments are not interchangeable. The checked-in manifest is
reviewed expected behavior; a successful gate run must still observe every entry in each
execution mode. Reports retain exact counts and identities rather than relying on this
dated narrative.

## Remaining rejected surface

The manifest is [tools/python_int_optin_exceptions.json](../../tools/python_int_optin_exceptions.json).
Every row names a case, execution mode, category, exact diagnostic, concrete reason and
tracking issue. Related cases have one underlying limitation:

| Family | Remaining behavior |
| --- | --- |
| Conflicting dynamic representation | Explicit dual pragmas, plus the typed TOML consumer crossing into dynamic Any, remain unsupported. |
| Mixed unions and storage | Promoting ints do not fit all closed-union fields, results, displays, reflection dictionaries or generic widening destinations. |
| Recursive inference | Recursive `Chain` and nine forward-cycle template cases specialize int64 and promoting-int arguments separately, then fail to reconcile their return or container contexts. A captured local with a string/int join also remains rejected. |
| Compound callable arguments | A variadic generic callable binds stored tuple and callable argument layouts differently. |
| Integer identity | `operator.indexOf` uses `is` on its integer arguments; promoting integer identity remains unsupported. |

These are known compiler limitations in otherwise valid Python. Recording their safe
rejections does not declare them intentional Python semantics or close the integer
promotion tracker. Existing documented runtime boundaries, including nested optionals
and `dataclasses.astuple()`'s optional tuple result, remain in
[the feature contract](../python-int.md#64-bit-boundaries).

## Enforcement and regression coverage

- A manifest entry can permit only one compiler exit 1 with its exact stderr diagnostic
  and no stdout. A crash, timeout, invalid LLVM, runtime exception or output mismatch
  cannot be added as an exception.
- A fixed case must have its obsolete entry removed. New or changed failures and failed
  original-program oracles remain failures. Compiler filenames may lose only the verified
  checkout prefix; arbitrary diagnostic text is never normalized away.
- Eight required CI shards cover every corpus case in both modes exactly once. Reports
  bind the pinned Python version, source/support inputs, manifest, corpus and executed
  native compiler. Missing, duplicated, partial or inconsistent reports fail aggregation.
- Eight explicit-pragma regression programs exercise the repaired operations in the
  normal, GC-stressed, sanitizer and other existing verification configurations. Tooling
  tests independently inject crashes, altered diagnostics, stale exceptions, incomplete
  evidence and source mutations; they also preserve `/dev/full` fixture behavior.

This is a release gate for an experimental supported subset. It is not a default-on
promotion decision, a full CPython test-suite claim or a performance-budget certification.
