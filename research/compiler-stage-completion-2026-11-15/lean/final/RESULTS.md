# Final Lean qualification results

The fresh qualification passed at published commit
`eabfe7b3d8f1be3e4615442423c7d3fbab10285b`, tree
`4deb05cd2f645d516dd37480d5510d0920747b6f`. The strict compiler, checker and corpus
input inventories were clean, and all source identities and four checker hashes
were identical before and after execution.

| Check | Result |
|---|---|
| Full `test_lean*.py` discovery, `LEAN_BOUNDARY_REQUIRED=1` | 409 discovered and executed; zero skips, failures, errors, expected failures or unexpected successes. Unit runner: 142.676 s; complete command: 143.433 s. |
| Fresh original ten-program report | Ten complete records; 535/535 obligations or uses proved; zero rejected, unsupported or incomplete records. Jobs: 2; process start method: `spawn`. Complete command: 25.723 s. |

The actual report counts are:

| Property | Proved / obligations or uses |
|---|---:|
| Dynamic payload reads | 12 / 12 |
| Unchecked accesses | 38 / 38 |
| Removed null checks | 17 / 17 |
| Closed-union reads | 31 / 31 |
| Union payload bits | 46 / 46 |
| Field initialization | 168 / 168 |
| Collector scanning | 75 / 75 |
| Promoting-integer fit claims | 0 / 0 |
| Promoting-integer inline arithmetic | 32 / 32 |
| Promoting-integer storage | 116 / 116 |
| Total | 535 / 535 |

These obligations overlap across bounded models. The total is not a
whole-compiler proof or a verified-code percentage. The separate stage model's
11 audited guarantees and its 208 transition comparisons are documented in the
stage review; the 21 stage-checker tests are included in the 409-test suite.

## Clean-source control

The first attempt used the active verification worktree and stopped before any
validation phase. Its ignored `build/verify/home/lib/*.py` copies made corpus
provenance unclean even though tracked compiler/checker files were unchanged.
[The failed preflight](run/summary.json) is preserved; it was not treated as a
successful or partially completed proof run.

A new detached checkout at the exact published commit was created at
`/workspace/scratch/9f30aa4fd4fd/pystachy-lean-qualification`. The four existing
Lean executables were copied into their ordinary `.lake/build/bin` locations.
SHA-256 equality was checked against each source executable before and after
copying, and recorded in [checker-transfer.json](checker-transfer.json).
No executable was rebuilt, no compiler source was edited, and the concurrent
native execution worktree was left intact.

## Evidence

- [summary.json](run-clean/summary.json): pinned tools, exact commands and selected environment, source/checker identities, structured test results, proof totals and artifact hashes.
- [unit-results.json](run-clean/unit-results.json) and [unit-tests.log](run-clean/unit-tests.log): full discovery/execution counts and individual results.
- [report.md](run-clean/report.md), [records.jsonl](run-clean/records.jsonl) and [report.log](run-clean/report.log): fresh per-program checks, complete clean provenance and actual obligation counts.
- [run.py](run.py) and [cases.json](cases.json): the runner and byte-identical original case manifest. The runner and manifest hashes were unchanged through validation.

The commands were sequential and used the existing four native Lean checkers.
No validation jobs remain running. These results do not replace the parent's
native execution, bootstrap, ABI, IR-comparison, CI or performance evidence.
