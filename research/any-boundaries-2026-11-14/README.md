# Typed/Any boundary qualification — 2026-11-14

This research record qualifies [PR #1493](https://github.com/den-run-ai/pystachy/pull/1493), **Tighten constructor, numeric identity, and Lean boundaries**, at published commit [`adac7f4c88fd86ddaecbb889042b778c701b29ed`](https://github.com/den-run-ai/pystachy/commit/adac7f4c88fd86ddaecbb889042b778c701b29ed). Its tree is `ddb2991da45e803167a0cf46a11020389a01f485`, stacked on alpha.2 commit `950c0440ad793dc6c34664f591383a5e6bba14dd`. The implementation PR retains the original histories of #1482–#1486 and #1489–#1491.

All local gates below passed. The exact-head GitHub workflows are [CI run 43616433423](https://github.com/den-run-ai/pystachy/actions/runs/43616433423) and [Lint run 43616433420](https://github.com/den-run-ai/pystachy/actions/runs/43616433420). Their final status and the independent review record are reported in the PR qualification comment. The [automatic Codex review](https://github.com/den-run-ai/pystachy/pull/1493#issuecomment-6880882082) could not complete because the account's code-review quota was exhausted; this is not a completed clean bot review.

## Changes and scope

The implementation discovers imported constructor dependencies on demand so fixed-layout classes can retain inheritance and constructor specialization. It preserves source identities through optional numeric lists and runtime-length tuples, and records the existing-source companion writes performed by tuple widening. Unused hierarchy members remain lazy. The native numeric payload representations remain specialized.

The Lean work checks real C layouts, allocation kinds, and bounded allocation/setter/getter shapes for initialized list companions. Its theorems cover direct identity readback and the list-header → companion → numeric-box tracing chain, including composition through an Any box. The storage adapter also recognizes exact canonical integer generator-yield pairs with a third independently checked identity operand. It retains the separate two-word generator-return contract.

These are bounded contracts. They do not prove general aliasing, resizing/copying, arbitrary generator identity, root discovery, or collector correctness. Static `Annotated` constructor dependencies, some prior standalone template instantiations, fixed-shape tuple identities, numeric union containers, and whole native numeric tuple boxing remain outside this work. The inherited runtime-tuple representation adds an eight-byte companion pointer to the header; ordinary typed programs allocate no identity companion. Additional conservative null guards in TOML are retained and classified as real generated-code changes.

## Validation

| Gate | Result |
|---|---|
| Native three-stage bootstrap | Compiler IR: **940,800 lines**; runtime IR: **21,214 lines**; all three stages identical for each |
| Complete native IR comparison against alpha.2 | **4,634 cases**, **21 new acceptances**, **zero new rejections**; every difference classified |
| Focused native qualification | **172 checks passed**: 84 normal, 84 GC-mode, four combined-consumer executions |
| Storage/effect/runtime-tuple units | **38 passed**, including the old-effect-declaration negative control |
| Native Lean unit target | **383 tests**, 17 groups, **zero skips/errors** |
| Lean kernels and axiom audits | **44 targets**, all public theorem audits passed |
| Selected Lean report | **14 programs**, **570/570 obligations proved** |
| Strict promoting-integer storage inventory | **178/178 programs accepted**, **18,610/18,610 obligations proved** |

Each 84-check native pass includes eight compile-only rejection checks; the other selected cases execute in JIT and AOT. The combined consumer executes in normal and GC-stressed JIT/AOT and matches pinned CPython output with empty stderr. It crosses imported constructors, a generic Box, a non-opt-in type-check helper, a numeric generator, optional numeric list/tuple storage, and an imported Any observer.

The selected Lean report contains 369 collector-scanning, 152 field-initialization, 31 storage, 11 removed-null-check, and seven unchecked-access obligations. Other categories have zero obligations in that selected set; their checker behavior is exercised by native unit controls. This selected report does not replace the exhaustive all-program Lean report. The strict storage inventory retains all **22,597 raw low-word uses**.

The IR audit classifies 4,220 oracle-identical cases, 238 generated-home-only IR differences, 14 diagnostic-home-only differences, 138 substantive IR changes, 21 new acceptances, and three more-specific rejection diagnostics. The latter acceptance/diagnostic changes are added fixtures. Raw output and each normalization decision remain available; the audit does not claim that all cases were separately executed or semantically proved.

## Review findings and negative controls

The broader qualification exposed three issues that were corrected before this final record:

1. A resolved optional-list observation still expected the old failure in a deviation fixture. It was removed from the deviation, with separate positive coverage and direct normal/GC JIT/AOT replay retained.
2. Tuple widening could materialize an existing source companion while declaring only raising/allocation effects. Adding object-read/write effects prevents reuse of a stale heap fact; a stack-slot fact still survives. The regression reproduces the omission under the old declaration. No user-visible wrong-output counterexample is claimed for that metadata omission.
3. The strict storage adapter recognized only two-operand generator yields. It now accepts the exact paired yield plus an independently checked identity operand, preserving same-integer pairing and rejecting malformed or tainted transport. The same two functions failed on standalone #1486 and the earlier integration. Their real obligations now prove **22/22**, while all 34 raw low-word uses remain inventoried.

Independent reviews reproduced the positive cases and rejected broken pairs, wrong operand types, extra operands, tainted identity operands, unsupported return shapes, and invalid C tracing/layout mutations. Earlier setup failures and the rejected storage run are preserved separately rather than relabeled as passing runs.

## Source correspondence

The final native binary was built and qualified from local `d68c9837ccad11e46b29a8955cc125c1a33cb77b`, whose tree equals published `5731ec352284a87a6df6eabc1a5396f90f194dd0`. Its SHA256 is `5dc9973d3a0ff8b79b8ae9ba2ca7d81347b460c8de0a015d6b2acd898c2ebf6e`. The final published head adds only the storage adapter, its tests, and its scope documentation. Every native compiler/runtime/library/corpus input remains byte- and mode-identical. The Lean gates run on the exact final tree. Detailed mappings and toolchain identities are recorded in [provenance.json](provenance.json), [native/publication-correspondence.json](native/publication-correspondence.json), and [ir/final-tree.json](ir/final-tree.json).

The pinned toolchain is CPython **3.13.16**, LLVM **18.1.3**, and Lean **4.35.0** on Linux x86-64. The dependency-equipped Python environment was used for final recording and Lean unit checks. Earlier logs from the interpreter lacking development dependencies remain labeled as setup failures.

## Evidence layout

- [native/](native/) contains the final consumer, commands, expected/actual output, suite selection, results, effect regression, and input correspondence.
- [ir/README.md](ir/README.md) explains the complete IR audit. [ir/classification.md](ir/classification.md) accounts for every difference. Compressed archives retain the complete ledgers, source hashes, diagnostics, and changed IR.
- [lean/README.md](lean/README.md) explains the exact-tree Lean qualification. Its archive includes 53 files covering final reports, inputs/checker hashes, preceding failures, and independent controls.
- [fixture-correction/](fixture-correction/) retains the removed observation's separate positive replay and the remaining documented deviations.
- [local-gates/](local-gates/) and [preceding-native/](preceding-native/) preserve explicitly earlier runs and their corrections. Their old-source results are not substituted for the final qualification.

The two large IR archives are transported as numbered parts. Run `python ir/reassemble.py` to restore their original filenames. The script verifies every part and each complete archive before exposing the result. The original audit manifest then verifies the restored archives and associated files. The raw archive expands to **723,685,359 bytes across 71,411 members**; metadata has 52 members. No native binary blobs are included in this publication.
