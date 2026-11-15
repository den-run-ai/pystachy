# Final Lean validation

Final qualification passed on the published source: **409 tests, zero skips,
and 535/535 obligations or uses across the original ten programs**. See
[RESULTS.md](RESULTS.md), [the linked report](linked-report.md) and
[the machine-readable summary](summary.json).
The initial attempt correctly stopped on verification-generated ignored source;
the successful run used a clean equal-tree checkout and the same checker binaries.
Full local 58-stage compiler verification remains pending at this evidence checkpoint.

## Published evidence layout

The successful run's files were copied from the historical `run-clean/` directory
into this directory. Its initial `run/summary.json` is published as
[generated-input-preflight.json](generated-input-preflight.json).
The raw records retain their original paths, commands and recorded hashes.
[report.md](report.md) is the unmodified generated report whose hash appears in
[summary.json](summary.json); [linked-report.md](linked-report.md) is a labeled
navigation copy with model-document links pinned to the published compiler commit.
The command below records the actual successful invocation and original paths.

The successful invocation was:

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python \
  /workspace/scratch/9f30aa4fd4fd/evidence/lean-final/run.py \
  --root /workspace/scratch/9f30aa4fd4fd/pystachy-lean-qualification \
  --output /workspace/scratch/9f30aa4fd4fd/evidence/lean-final/run-clean
```

The default source is `/workspace/scratch/9f30aa4fd4fd/pystachy`; `--root` selects
another clean equivalent checkout with all four built Lean checkers. The default
output is `evidence/lean-final/run`, outside the repository. It must not already
exist. Use `--output NEW_PATH` for another fresh attempt; existing reports are never
resumed or overwritten.

The runner first requires clean compiler/checker/corpus inputs using
`lean_report.inputs`, including ignored source files and import-path checks, and
pins tree `4deb05cd2f645d516dd37480d5510d0920747b6f`. It accepts published commit
`eabfe7b3d8f1be3e4615442423c7d3fbab10285b` or its identical local tree at
`527dc89a02e8e8866fc4d83997847663a6e7c0aa`; both identities are recorded explicitly.
It does not rewrite native report provenance to another commit.

It then performs exactly two validation phases:

1. One full `test_lean*.py` unittest discovery with `LEAN_BOUNDARY_REQUIRED=1`,
   retaining structured test counts. Failures, errors, loader errors, skips,
   expected failures, unexpected successes or missing executions fail the run.
2. Fresh `tools/lean_report.py --jobs 2 --start-method spawn --timeout 300`
   execution over the ten original programs in `cases.json`, with new Markdown,
   JSONL records and logs. Missing/duplicate programs, incomplete checks, dirty
   provenance, unproved obligations or unsupported/error records fail the run.

The runner records exact commands, selected environment, pinned CPython/Lean
identities, hashes of all four native checkers and source inventories before,
between and after phases. Any source/checker change fails closed. Counts are
aggregated from the actual records, with no hard-coded expectation of 535.
Obligations overlap across checks and are not a whole-compiler proof percentage.

`summary.json` distinguishes running, failed, interrupted and passed states.
`unit-results.json`, `unit-tests.log`, `records.jsonl`, `report.md` and `report.log`
retain detailed evidence. Default overall phase deadlines are 900 seconds for
unit tests and 600 seconds for the ten-program report; the exact limits are
recorded. Compiler sources and the committed historical `REPORT.md` are not edited.

The manifest is copied from the prior stage evidence's `lean/cases.json`:
`/workspace/scratch/78a63a74ecb5/pystachy-stage-evidence/research/compiler-stages-2026-11-15/lean/cases.json`.
