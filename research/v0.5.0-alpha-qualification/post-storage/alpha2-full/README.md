# Alpha.2 complete qualification

The complete alpha.2 Lean census and independent evidence audit passed. PR #1488
is merged at `80490143498d149d407343ba1cb7aedb1db2d2c5`; its entire source tree is
identical to the qualified candidate `950c0440ad793dc6c34664f591383a5e6bba14dd`.
Both trees are `717a8c9386ae9f5f6545cc3686a9e22282fc560c`. Exact-main workflow and
distribution results are retained separately as the subsequent release gates.

## Full census and comparison

The fresh one-worker run under pinned CPython 3.13.16 reused no records and completed
all 2,550 unique programs. Every required check is present, all recorded report,
status, acceptance and comparison exits are zero, and there are no inspection or
checker failures. All 175 selected promoting-storage programs pass strict acceptance,
with 18,582/18,582 storage obligations proved and no unsupported storage functions.

The complete comparison with the independently accepted alpha.1 census preserves all
2,529 previous programs. Twenty-one added programs fully prove 1,195 obligations:
44 access, 605 field, 444 GC and 102 null obligations. Eight existing Enum/IntFlag
null-check dictionaries each gain one function, obligation and proof. Every other
shared check dictionary is identical, including every existing unproved list.
There are no obligation/proof-count decreases or newly unproved results. The total
gain is 1,203 proved obligations.

The independent audit verifies the exact current corpus, clean source provenance,
all three prepared checker hashes, report completion metadata and byte-for-byte
Markdown reconstruction. It explicitly confirms the formerly slow logging case and
the repaired context-manager storage result of 19/19. Existing bounded-model gaps
in other proof categories remain disclosed in the full report.

| Frozen file | SHA-256 |
|---|---|
| Complete records | `98d2cd703064e39dbb14e41f3d13bb1b5df7bbcf4d30903966db4b427ecd09a6` |
| Rendered report | `18eb6dc0772dfbd4b2d95036c724ff9c438a08d7766027cc502587fa403e76cd` |
| Independent audit JSON | `2fc8ec22aaaa6d1380b937209ecb952d42e263a30ce930512e93cd65f36439bc` |

## Other candidate qualification

Current-head PR CI, Lint and the final Submission format run passed before merge.
The sole historical review thread was resolved with actual test-discovery and CI
execution evidence. Two independent current-head source reviews found no actionable
issues. Four GitHub Codex refresh attempts failed before completion; those failures
are retained and are not counted as completed reviews.

Previously verified compiler/runtime source and binary identities bind the three-stage
fixed points (932,028/21,214 IR lines), 46 focused native GC executions and
95 native/97 hosted cache checks to this candidate's consumed sources. The complete
4,579-case IR comparison has zero new rejections; 17 new acceptances, ten substantive
IR changes and six improved diagnostics are explained. Earlier interrupted or partial
proof evidence remains historical and is superseded by this complete census.

The archive contains both full census datasets, current acceptance/comparison/source
records, independent reviews and audit helpers, raw logs, the pre-merge status snapshot,
the final merge record and exact source-tree equivalence. Each archived file has a
SHA-256 entry in the manifest. The frozen proof checkout remains at the candidate;
the release checkout and GitHub main were separately verified at the merge commit.

References: [merged PR](https://github.com/den-run-ai/pystachy/pull/1488),
[review disposition](https://github.com/den-run-ai/pystachy/pull/1488#issuecomment-6880303611),
[published alpha.1 baseline](https://github.com/den-run-ai/pystachy/releases/tag/v0.5.0-alpha.1).

This is qualification evidence on a research branch and must not be merged into main.
