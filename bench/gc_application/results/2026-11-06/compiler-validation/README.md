# Scalar-union compiler experiment: validation evidence

This archive records correctness checks for `PYSTACHY_OPT=+atomicunion`, the
experimental lowering that allocates a closed-union box as pointer-free only
when its program-wide tag proves a native `int`, `float` or `bool` payload.
The experiment is off by default. Runtime tags, optional-to-union conversions
and reference payloads retain scanned boxes; a wide integer's `Mpz` remains a
traced reference. These checks concern Pystachy's built-in collector and do not
validate an external-collector adapter or establish a performance improvement.

## Records and integrity

[validation-summary.json](validation-summary.json) is the compact combined
record. It and the raw files were copied byte for byte from the original run.
[manifest.json](manifest.json) maps each archived file to its original absolute
path, byte count and SHA-256. Absolute paths in the historical JSON and command
snapshots identify the original environment; resolve archived evidence using
the manifest instead of assuming those paths exist on another machine.

The archive includes the original `native-optin.log` as well as its explicitly
named failure copy because the first-attempt JSON references the original name.
Both files have the same hash. It also retains the first-attempt unit log and
the final unit log. No generated LLVM IR, binaries, runtime caches or mutated
runtime copies are included.

## Results and scope

The toolchain was LLVM 18.1.3 with CPython 3.13.16. Exact compiler identities,
commands, settings and the 23 application paths are in the JSON records.

| Check | Result | Evidence |
|---|---|---|
| Native bootstrap | Compiler stages agree on 832,558 IR lines; runtime stages agree on 18,805 lines | [bootstrap.log](bootstrap.log) |
| Hosted scalar-union, union-proof and optimization-variant units | 54 passed | [unit-final.log](unit-final.log) |
| Runtime signatures and effects | 645 runtime entries, 70 exception classes and 172 runtime.py functions agree | [runtime-contract.log](runtime-contract.log) |
| Default IR against the pre-experiment compiler | All 23 distinct final cases match; 24 comparisons include the corrected fixture rerun | [initial comparison](default-ir-parity.log), [corrected fixture](default-ir-parity-corrected-fixture.log) |
| Opt-in native versus hosted compiler IR | Corrected fixture matches | [native-optin-ir-parity.log](native-optin-ir-parity.log) |
| Opt-in ordinary JIT/AOT behavior | 46 passing checks across 23 cases, composed as explained below | [first attempt](native-optin-literal-expression-failure.log), [corrected fixture](native-optin-corrected-fixture.log) |
| Opt-in JIT/AOT with collection at every program allocation | 46 passed across the same 23 cases | [native-optin-stress.log](native-optin-stress.log) |
| Corrected fixture with default options | 2 passed, JIT and AOT | [native-default-corrected-fixture.log](native-default-corrected-fixture.log) |
| Box layout and exact reachability | Passed with object and block marking, including a block-marker box stress run | [gc-probes.log](gc-probes.log), [boxprobe-block-stress.log](boxprobe-block-stress.log) |
| Deliberately wrong allocation kinds | All six runs rejected the mutation | [negative-controls.log](negative-controls.log), [recipes and results](negative-kinds/results.json) |

The positive native application total is **94**: 46 ordinary opt-in checks,
46 opt-in GC-stress checks and two default-option checks of the corrected
fixture. This total excludes the two initial failures and the negative controls.

The summary separately records 64 compiler ownership-inventory tests observed
passing through the interactive tool. No standalone raw log was captured for
that invocation, so they are **not part of the 54 tests with archived raw
evidence**. The same limitation applies to its preceding package-mode import
failure, which was corrected by invoking unittest discovery. The summary keeps
both facts explicit; this archive cannot independently substantiate that
additional count from a process log.

## Initial fixture failure and correction

The first native application run had 44 passes and two failures, both from the
new `union_gc_boxes` fixture. Its boundary expressions `-(2**63)` and
`2**63 - 1` first computed `2**63`, which overflows native-integer mode. The
trusted pre-experiment compiler reproduced the same failure; see
[baseline-literal-expression-failure.json](baseline-literal-expression-failure.json).

The correction used the directly representable signed integer literals
`-9223372036854775808` and `9223372036854775807`. The fixture was re-recorded
with CPython 3.13.16 and its expected output did not change. Both corrected
opt-in executions passed. The other 22 application source files were unchanged,
so their original 44 passing checks plus these two passing checks establish the
ordinary 23-case result. All 23 corrected cases then ran again under GC stress.
The first attempt remains in
[validation-first-attempt.json](validation-first-attempt.json); the continuation
is in [validation.json](validation.json).

## Independent ownership controls

[gcmarkprobe.c](../../../../../tools/gcmarkprobe.c) builds an explicit-root graph
whose expected edges are independent of the collector's tracing decisions.
It distinguishes a reference payload from scalar bits that happen to equal a
heap address, checks transitive ownership, roots boxes through their payload-word
addresses, and checks optional-reference and wide-integer boxes.

The six negative runs change exactly one allocator kind at a time: scalar union
storage becomes scanned, reference-union storage becomes atomic, or wide-integer
storage becomes atomic. Each mutation must fail under both object and block
marking. The results JSON preserves the exact replacement, build commands,
mutated-source hash, executable hash, exit code and expected diagnostic.

The compiler-side boundary tests are
[test_typed_atomicunion.py](../../../../../tools/test_typed_atomicunion.py), and
the runtime fixture is
[union_gc_boxes.py](../../../../../tests/programs/inference/union_gc_boxes.py).
Historical orchestration scripts are preserved as text in `commands/`. They
contain the original absolute path constants; adapt those constants before
reproducing the run. They were not executed while packaging this archive.

## Source identity and integration

The native compiler was built at `c6e1402c24c0b5dc8ede1eab47e85043c1a85eed`.
The fixture correction is `e0e8ac4979a397253ab4020c4747b2649ea8607e`; the subsequent
`a055b652c0146503737cd2eadc4a2ea9d2f2c31a` changes documentation wording only.
Compiler, runtime and library sources remain identical to the compiler-build
revision. The native compiler SHA-256 is:

```text
b2806609c66900ed20f36aeb42833ae65a14b1036f4871f0386048920d11b8fe
```

The manifest also records the parent's **local integration** cherry-picks.
These map the changes, not complete repository trees, and are not claims about
eventual published commit IDs:

| Original worktree commit | Local integration commit |
|---|---|
| `c6e1402c24c0b5dc8ede1eab47e85043c1a85eed` | `a2615f3227b52ebeee14a084c568df49ae2b0401` |
| `e0e8ac4979a397253ab4020c4747b2649ea8607e` | `651194c91d26a26cef7a1e1938513ff7777e159f` |
| `a055b652c0146503737cd2eadc4a2ea9d2f2c31a` | `84b27481a3d0761e6ef869272255f7f643913e0a` |

Full verification, UBSan and hosted CI are not claimed by this compiler-focused
archive. They belong to the integrated change's validation. Durations in the
orchestration records measure validation work, not application benchmark results.
