# Final bounded-match source review

Reviewed on 2026-11-11. This is a source-review and evidence-attribution note, not a completed merge qualification.

## Assessment and identity

**No additional source-level blocker found in the final bounded implementation.** Final bootstrap/fixed-point verification, required CI, and the planned full-corpus IR comparison were still pending when this note was written. The change should not yet be described as merge-ready or as having proved unchanged output for all existing programs.

The reviewed comparison is base `b40ee875bf72b86804c4f5a300066f4f7c3eb20b` to published candidate `dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6`. The local worktree was clean at `e4c1219516b572dd0ee8a960d34db3bdbb2b3cbf`; both commits have the identical tree `0e4c2682f25b0555cac052fa36830ed567c3fa1e`. Both tree identities were read directly from Git. `git diff --check b40ee875 HEAD` passed. The final diff contains 71 files, with 2,049 insertions and 24 deletions.

The original standalone implementation at `620c35f42d8c35d7a27341bbe4ba259b043b959d` was reviewed previously. The complete change from that revision to the final tree is the conjunction helper in `src/pystachy_compiler/patterns.py` plus `match_condition_order.py` and its recorded output. `expressions.py` is unchanged by this follow-up.

Permanent source references: [complete final comparison](https://github.com/den-run-ai/pystachy/compare/b40ee875bf72b86804c4f5a300066f4f7c3eb20b...dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6), [lowering and pattern operations](https://github.com/den-run-ai/pystachy/blob/dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6/src/pystachy_compiler/patterns.py), [new callback/guard regression](https://github.com/den-run-ai/pystachy/blob/dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6/tests/programs/language/match_condition_order.py).

## Correctness and final integration

The lowering evaluates the subject once, stages captures before exposing them to user code, commits them only after the complete pattern succeeds, and evaluates the guard after those commits. A false guard retains successful captures. The reviewed tests cover failed partial patterns, OR alternatives, `as`, closure/nonlocal visibility, private names, alias retention, exceptions, and generator use. Dataclass fields are loaded before subpattern comparisons, including the case where an equality callback mutates a later field. This ordering has a specific regression in `match_dataclasses.py`.

The two independently reproduced original faults are fixed and have permanent regressions: a promoting `int+` scalar falls through a fixed-sequence pattern, and a huge canonical hexadecimal literal containing `e` digits remains an integer. Positive and negative huge values are exercised, with a no-match control. Dynamic-Any and union dataclass subjects are explicitly rejected before a storage-type mismatch could be folded to false.

The final `pattern_then` helper is scoped to generated conjunctions. It appends along their AND right spine, preserves operand order, leaves OR subtrees intact, and keeps the final user guard opaque. All call sites satisfy that boundary: the source guard is appended only after pattern tests and capture commits have been constructed, and no later concatenation traverses it. This changes how existing flow analysis sees guaranteed staged assignments without changing capture timing or callback short circuiting. The new regression records equality callbacks, custom guard `__bool__` calls, false-guard bindings, OR evaluation, and a capture that changes a union-typed variable before its `isinstance` guard.

The proposed global `static(matchbind) = true` optimization is absent. It was independently shown to miscompile that union-rebinding case by analyzing the guard against stale narrowing before the assignment executes. The subsequent local `gen_boolop` experiment is also absent; it did not produce a consistent performance benefit. The final patch changes neither global static-folding rules nor `gen_boolop` beyond the previously reviewed match dispatch hooks.

Compiler source registration includes `patterns.py`. The end-to-end dispatch example and paired benchmark have corpus consumers, and the example is registered in the native pytest suite. CI runs the benchmark correctness target in its existing benchmark group and saves its JSON artifact. The controller validates CPython agreement, complete outputs, checksums and iteration counts before reporting timings; smoke mode makes no speedup claim. The statistics KDE rejection fixture advances to its next existing type restriction rather than incorrectly retaining the old unsupported-match diagnostic.

## Evidence and its limits

| Evidence | Result | Attribution |
|---|---|---|
| Independent scratch audit, eleven probes in JIT/AOT with normal and program-GC-stress execution | 44/44 exact stdout, stderr and exit-status comparisons against pinned CPython 3.13.16; all eleven AOT builds succeeded | Original standalone `620c35f` pattern implementation, before right association. Durable raw results: `match_audit_native_results.json`; controller: `run_match_audit_native.py`. |
| Right-association focused run | Benchmark worker reported 29 selected cases and 42 passing native checks | Final compiler-helper implementation; run preceded the union-rebinding lines added to the regression. |
| Complete final callback/guard regression rerun | JIT and AOT passed: one selected case, two passing checks | Worker reran after restoring `expressions.py`, before committing the accepted helper. This rerun is recorded in the tool transcript; it has no separate saved log. |
| Final review | Clean worktree, matching published/local tree IDs, no whitespace errors, no remaining source-level blocker identified | Final tree `0e4c2682`; source review only. No heavy work was launched during bootstrap. |
| Full bootstrap/fixed point, required CI and full-corpus IR comparison | Pending at review time | Must be evaluated on the final candidate, not inferred from the earlier focused runs. |

The earlier audit's `patterns.py` SHA-256 is `bab41351e8ae5f2cdcbba2a1e85d2354c84990ba0fca6aa6a29fcb24c585d932`, which exactly matches `620c35f`. The final file's SHA-256 is `43d4b10314b87f6015edde218202c83863d7989d3056a2e9a57d1c707c4dd411`. Thus the 44 comparisons are attributable evidence, not mislabeled final-head coverage. Pilot IR and timing artifacts are `match-v1-raw.ll`, `match-v1-jit-clean.ll`, and `match-right-association-pilot.json`; final performance conclusions require the completed candidate's benchmark records and their stability diagnostics.

The prepared `run_match_irsame.py` accepts the final candidate SHA and regenerates its input inventory from that Git tree. It verifies base/candidate/worktree input identity, the reference source snapshot and compiler hashes, then runs the repository's existing comparison with only its displayed-difference cap raised. Both compilers use the same verified runtime/library home, without IR text normalization. Earlier proof covered 105 identical executable inputs. The final follow-up changes none of them. Its extra regression increases the expected inventory from 4,437 to 4,438 inputs; the actual run must establish the counts. The currently prepared report is still for `620c35f` and is not evidence of an executed comparison.

## Supported contract and remaining qualification

This remains bounded matching: scalar literals, captures/wildcards/`as`, OR alternatives, guards, fixed tuples, and plain fields of statically known dataclasses. Mappings, starred/general sequence matching, arbitrary classes, class hierarchies, attribute hooks, custom `__match_args__`, and complex literals are outside the contract. Dynamic Any supports literal/capture patterns; class matching requires concrete subjects, and sequence matching requires a fixed tuple or a known scalar mismatch. Existing value-equality and type-join restrictions still apply.

No runtime implementation files changed. That fact and the lowering's use of ordinary assignments/branches support the intended architecture, but do not substitute for final IR or performance evidence. Every IR difference needs review, including expected newly supported programs and changed rejection boundaries. The known `syntax_match_duplicate_key_over_limit` mismatch predates this work: unchanged parser/lexer/fixture code intentionally reports a huge duplicate key in hexadecimal while pinned CPython raises its decimal-conversion-limit `ValueError`. The saved `match-syntax-baseline.json` contains its source/history proof; it must be disclosed as a baseline discrepancy, not counted as newly achieved full syntax parity.

Within the stated contract, the review found no further actionable semantic blocker. The outstanding decisions are the results of the final-tree qualification gates and any unexplained failures or IR differences they reveal.
