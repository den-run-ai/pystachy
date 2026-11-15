# Independent review of the sparse-tag Lean adapter repair

Base: `b0bda81ec2b9954c3c5e0f658c051439126a5c22`. Reviewed frozen proposed tree: `51f6c150748b2d17945e4d1c6779d8080b6edd6a`.

Exact patch SHA256: `cdf17f7de0c8b03e41c3f632483f41e05b29c54139ef581d13f14519dce5c238`.

**No blocking soundness or regression issue found.** All four working files and their frozen evidence copies were independently hash-checked, and the full difference from the base contains exactly those four files.

## Sparse union tag inventory

The compiler assigns a numeric tag only when gen_utag is called. split_layout still takes its semantic domain from every declared scalar union member; only the completeness precondition on the literal decoder is removed. No domain member or obligation is deleted.

Source: `tools/check_lean_guards.py:654-690`, `src/pystachy_compiler/unions.py:168-173`.

## Branch refinement and defaults

A missing literal cannot produce a member fact. Unknown comparisons remain opaque choices, and unknown switch tags are unsupported. A final default arm can be proved as one member only after guards exclude all other members from the full domain, including any member that lacks an emitted literal.

Source: `tools/check_lean_guards.py:1209-1248`, `tools/check_lean_guards.py:1251-1299`, `tools/check_lean_guards.py:1800-1811`.

## Stored and reconstructed payloads

pair_source still accepts only a known literal, matched tag/payload provenance, verified optional lookup, or matched phi edges. Unknown literal pair stores refuse. ubox with an unknown literal refuses unless the tag and payload are reconstructed from the same tracked box. Existing payload interpretation and construction obligations are unchanged.

Source: `tools/check_lean_guards.py:1332-1363`, `tools/check_lean_guards.py:1744-1766`, `tools/check_lean_guards.py:1844-1858`.

## Error propagation

failures includes the existing top-level/worker failures and now nested unproved records with status error. Both rendered summary.failed and canonical completion.failed use it. Rejected and explicitly unsupported models remain completed results with visible limitations; they are not reclassified as proved.

Source: `tools/lean_report.py:355-369`, `tools/lean_report.py:538-549`, `tools/lean_report.py:588-591`, `tools/lean_report.py:734-750`.

## Regression evidence

Positive regression checks the full bool/float/int domain despite only bool/float emitted tags. Negative controls cover missing used tags, unknown tests, unguarded default paths, unknown split literals and unknown/missing ubox tags. Reporting tests distinguish adapter errors from completed rejections and unsupported results. Before-fix evidence reproduces one adapter error and two assertion failures; retained after-fix suite passes 49/49.

Source: `tools/test_lean_union_split.py:45-52`, `tools/test_lean_union_split.py:101-154`, `tools/test_lean_report.py:80-86`, `tools/test_lean_report.py:811-812`.

## Limits

- Independent read-only source/integration review; no tests or compiler/Lean executions rerun by this reviewer.
- The retained complex-decline replay records 21/21 union reads, 21/21 payload obligations and 4/4 null-check removals; this is inspected prior-run evidence.
- No compiler, runtime or Lean theorem/checker source changes are present in this four-file patch.
- The separate complex_union_none residual obligations are neither proved nor relabeled by this repair. A full-corpus fresh report and its final status remain separate release gates.
