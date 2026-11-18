# Compiler-stage checks

`PystachyPipeline.lean` proves ordering properties of the compiler's six-stage
state machine. `check_lean_pipeline.py` checks actual inspection reports against
that model and binds the selected finalized snapshot to the report by its
SHA-256 digest and attempt index. It accepts a completed compilation to LLVM,
or an explicitly requested `--stop-after finalize` run that retains typed IR.

From the repository root, with the pinned Lean toolchain on `PATH`:

```sh
make check-lean-boundary PY=python3.13
python3.13 tools/inspect_compiler.py tests/programs/containers/lists.py \
  --output /tmp/pystachy-pipeline-example --stop-after finalize
python3.13 tools/check_lean_pipeline.py \
  --report /tmp/pystachy-pipeline-example/report.json
```

The output directory must be new. The checker defaults to `typed-after.json`
beside the report; `--snapshot` selects another file whose digest must still
match the report. `--checker` selects the built Lean executable. Exit 0 means
Lean accepted the candidate, 1 means it rejected the recorded stage facts,
and 3 means malformed input, missing evidence/checker or an operational error.
Reports produced before the artifact-digest field was introduced require a new
inspection; the tool does not infer missing provenance.

## Proven properties

The state model records the last completed stage, any active stage and the
completion history. The stage numbers correspond to `prepare`, `discover`,
`analyze`, `optimize`, `finalize` and `lower`. Its `step` function follows the
actual `PipelineState.begin` and `PipelineState.complete` guards, including
rejection of empty/unknown stages and completion without the matching predecessor.

`step_preserves` and `reachable_wellFormed` prove that transitions starting from
a fresh state keep an ordered completion prefix and at most one active next
stage. `active_cannot_begin` proves that an unfinished stage prevents any new
stage from starting. `consumed_cannot_step` proves that completed lowering is
terminal, and `consumed_has_finalization` proves that finalization precedes it.

The report checker requires sequential attempt indices, valid stage histories,
matching active stages, and a complete inventory of completed/partial/unavailable
stage evidence. Every preceding attempt must be a retry with an unfinished active
stage that does not cross the requested target. The terminal attempt must complete
exactly the requested target with no active stage. Successful
finalization is accepted only when requested explicitly in the report settings;
a failed lowering run with retained typed IR is rejected. Report and snapshot
statuses and source-change records must agree with successful completion.
The Python bridge also requires the nonempty consumed-source inventory to contain
the input's recorded byte hashes and the requested IR verification to be complete.

`accepted_report_complete`, `accepted_report_attempts`, `accepted_attempt_ordered`,
`accepted_terminal_target`, `accepted_report_target` and `accepted_terminal_consumed`
establish these acceptance properties in the
model. The existing `Audit.lean` checks their transitive axioms, allowing only
Lean's standard `propext`, `Classical.choice` and `Quot.sound`.

## Correspondence and limits

The tests compare all 208 combinations of the actual Python state machine's
13 reachable states, both operations, six stage names and empty/unknown names
with the Lean executable. Mutation controls corrupt real ordinary, retried and
finalization-only inspection reports: swapped/duplicated/omitted completions,
stale active stages, forged stage evidence, foreign snapshot attempts, repeated
attempt indices, partial snapshots, changed sources and failed terminal outcomes
must fail closed. Content mutations also must fail the report's snapshot digest.

These checks establish report sequencing and association. They do not prove
that a stage body implements its stated postcondition, that the exporter faithfully
records execution, that a prepared Python object belongs to an attempt, or that
typing, specialization, representations, IR operations, GC or LLVM are correct.
The Python normalization, reported provenance, JSON parser, Lean compiler/runtime
and native checker execution remain trusted. A digest binds bytes to a report;
it does not authenticate that report. Ordinary compiler ownership, differential,
bootstrap, native execution and other Lean IR checks remain necessary.

`check-fast` runs the Python tests and executable controls when the checker is
available. `check-lean-boundary` builds the model/checker, audits proofs and
requires every executable control. They run within the existing Lint job.
