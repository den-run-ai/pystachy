# PR #1493 — final combined Lean qualification

All final gates passed on tree `ddb2991da45e803167a0cf46a11020389a01f485`.
The verified commit is `e4faeab2b2241b9fe77ef6daec7df94535046279`; the integrated
local commit is `5acdbfddea96ce43e0a389dcec6c0392114fa6e5`; the published PR head is
`adac7f4c88fd86ddaecbb889042b778c701b29ed`. Their complete Git trees are identical.

## Results

| Gate | Result |
|---|---|
| `make check-lean-boundary` | 383 tests across 17 groups; no skips or errors; 114.7 s. |
| Lean build and audits | All 44 targets and public axiom audits passed. Unchanged kernel artifacts were reused for the final run. |
| Selected `make lean-report` | All 14 requested programs completed; 570/570 obligations proved; no rejected, unsupported, or incomplete checks. |
| Strict promoting-int storage corpus | All 178 selected programs accepted; 18,610/18,610 obligations proved in 1,718 inventoried function records; no unclassified functions, errors, rejections, or unsupported results. The checker report records 338.4 s. |
| Generator adapter controls | Seven new native Lean tests and an independent actual-IR review passed, including wrong-pair, missing-high, wrong-type, extra-operand, tainted-companion, and unsupported return-shape negative controls. |

The selected report proves 369 collector-scanning, 152 field-initialization,
31 promoting-storage, 11 removed-null-check, and seven unchecked-access
obligations. Its dynamic-payload, closed-union, union-bits, integer-fit, and
inline-arithmetic rows have zero obligations. Native unit tests separately
exercise those checkers. The selected report does not replace the exhaustive
all-program report. Its external combined consumer and two helper modules are
SHA256-pinned; the report correctly marks that corpus input as external.

## Storage rejection found and fixed

The preceding full storage run on `6cb04cef038e059f8cba5f491b075f5553c58f1a`
rejected `@f.fresh.1` and `@f.wide$repeat.1` in
`tests/programs/numbers/python_int_generator_identity.py`: 18,606/18,614
obligations received proof credit. The same normalized candidates failed on
standalone #1486 head `7e96403e34512fae29f885b87445eb716f797d57` and on
`d68c9837ccad11e46b29a8955cc125c1a33cb77b`.

This was an adapter coverage omission. #1486 adds a third `dyn` identity operand
to a generator yield that transports a canonical low-word/digit-pointer pair.
The adapter previously recognized only two operands, so it incorrectly demanded
numeric-fit evidence at four pair-transport sites. Two rejected batches withheld
credit for eight obligations.

Commit `e4faeab2b2241b9fe77ef6daec7df94535046279` recognizes only the exact
`[%slot, %ptr]` or `[%slot, %ptr, dyn]` yield shapes and still requires both
numeric words to come from the same promoting integer. The third identity
operand is checked independently. `gen.ret` retains its two-word contract.
No compiler, runtime, or Lean-kernel code changed.

The generator fixture now proves 22/22 real obligations and retains all 34 raw
low-word uses. Across the full corpus, all 22,597 raw low-word uses remain
inventoried. Only that fixture's obligation totals changed: four spurious fit
obligations were removed, and the remaining obligations in both functions pass.

## New companion proof scope

The earlier companion commit proves bounded contracts for an initialized,
stable numeric-list companion: direct identity write/readback, the live item's
scanned companion word, and the list-header → companion → numeric-box root
chain, including composition with a boxed-list root. The trusted adapter checks
actual C field offsets, allocation kinds, and bounded setter/getter/allocation
AST shapes. Negative controls reject changed allocation scanning, pointer
stores, slot offsets, and extents. The four new public theorems passed the
standard-axiom audit.

This does not prove general alias preservation, resizing or copying, arbitrary
tuple or generator identity, root discovery, or collector correctness. The C
normalizer, allocator/collector contracts, and compiler/lowering correspondence
remain explicit trusted boundaries.

## Evidence and provenance

`run-summary.json` contains exact commands, exit codes, counts, timings, source
identities, and the before/after storage comparison. `source-manifest.json` pins
6,304 source/input files and five native checker binaries. Source, external
consumer inputs, and checker binaries remained unchanged after the final run.
`units.log`, `theorem-audit.log`, `selected-records.jsonl`, and
`storage-report.json` retain the underlying results and candidate/snapshot hashes.

The initial standalone-Python unit attempt failed because PyYAML was missing;
the pinned development venv fixed that setup issue. The initial strict storage
failure and its eventual correction remain separate evidence. An earlier
inventory note incorrectly said the resolved deviation fixture was outside both
corpora: it is outside the selected 14, but inside the strict 178. The final full
run recompiles and accepts that changed fixture directly.

Toolchain: CPython 3.13.16, LLVM 18.1.3, Lean 4.35.0 on Linux x86_64. All final
checks used one worker and the pinned development environment. No jobs remain
running, and the verified checkout is clean.
