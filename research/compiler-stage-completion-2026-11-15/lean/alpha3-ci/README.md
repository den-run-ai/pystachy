# Lean CI evidence after alpha.3 integration

**Derived audit of the completed Lint and Contracts jobs on the integrated compiler tree.** Both jobs passed. The original GitHub decoded job logs are retained unchanged as [lint.log](lint.log) and [contracts.log](contracts.log), including their initial BOM and timestamps. These are the decoded texts returned by GitHub, not copies of the workflow log ZIP archives.

The exact suite commands, counts, audited declaration names, source identities and guard summary printed by CI are in [audit.json](audit.json). This Markdown file and the JSON audit are derived summaries; the two logs are the original source records.

## Source identity

| Identity | SHA |
|---|---|
| Published compiler head | `d266e919eb0c11dbbb41918b8d212bce7872910a` |
| Alpha.3 main integrated | `6bf3f73af7edb02c5b2bdb6b2ac23fc3f5fffe93` |
| Synthetic merge checked out by both jobs | `106dfa1cfa5d8ebdb457ebb1d3011e10fd7f972f` |
| Tree shared by published head and synthetic merge | `c242877c659b89a9131d5a17b2c4b170de095f76` |

Both logs print the synthetic checkout commit. GitHub commit metadata independently confirms that its tree equals the published head tree.

## Observed checks

[Lint job 132774658594](https://github.com/den-run-ai/pystachy/actions/runs/43701897755/job/132774658594) ran **463 Lean-related tests in 19 invocations**, all reporting `OK`, with no skips and `LEAN_BOUNDARY_REQUIRED=1`. This includes 21 pipeline tests and 44 report tests. The selected patterns cover 32 of the 33 current `test_lean*.py` files; `tools/test_lean_corpus.py` is omitted by this PR target.

[Contracts job 132776356046](https://github.com/den-run-ai/pystachy/actions/runs/43701897758/job/132776356046) ran **119 required guard-related tests**, all reporting `OK` without skips. These repeat selections already included in Lint's 463. They must not be presented as 119 additional distinct tests.

Each job completed a fresh Lake build reporting 50 successful build jobs. Each also recorded **60 axiom-audit passes**: 56 declarations in `Audit.lean` and four in `GuardAudit.lean`. These include all 11 pipeline guarantees and alpha.3's Layout, Alias and Companion guarantees. The same declarations were audited in both jobs; this is not 120 distinct guarantees.

## Bounded guard corpus

Contracts also checked nine named example programs with two workers. Its logged aggregate reports accepted status, complete inventory, and zero rejected, unsupported, erroneous, uninventoried or vacuous programs.

| Category | Inventoried | Proved |
|---|---:|---:|
| Union reads | 61 | 61 |
| Removed null checks | 27 | 27 |
| Payload obligations | 101 | 101 |
| Field obligations | 151 | 151 |
| GC obligations | 136 | 136 |
| **Counted uses across the models** | **476** | **476** |

The models may overlap. The total is a sum of reported obligation uses, not a count of independent source-level correctness properties.

## Coverage and proof limits

The full local `test_lean*.py` discovery command and the original ten-program `lean_report.py` qualification were **not rerun on this integrated head**. The historical 535 results across ten programs qualify `5ccd1841` only; these nine guard examples cover a different selection and set of checks. No whole-corpus Lean report was generated during this qualification.

The [pipeline model](https://github.com/den-run-ai/pystachy/blob/d266e919eb0c11dbbb41918b8d212bce7872910a/tools/lean_boundary/PIPELINE.md) proves bounded stage/report properties while trusting its Python correspondence and exporter. The [other models](https://github.com/den-run-ai/pystachy/blob/d266e919eb0c11dbbb41918b8d212bce7872910a/tools/lean_boundary/README.md) retain their stated adapter, layout, typed-memory and runtime assumptions. These results do not prove stage-body semantics, whole-compiler correctness, source-to-LLVM equivalence, general lifetime safety or collector correctness.

No local tests, builds or reruns were performed while preparing this audit. It reports the observed GitHub CI executions.
