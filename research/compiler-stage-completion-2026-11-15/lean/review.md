# Lean compiler-stage verification evidence

The final stage model, axiom audit and focused bridge tests pass for local commit
`527dc89a02e8e8866fc4d83997847663a6e7c0aa`, tree
`4deb05cd2f645d516dd37480d5510d0920747b6f`. The parent published the same tree as
[`eabfe7b3d8f1be3e4615442423c7d3fbab10285b`](https://github.com/den-run-ai/pystachy/commit/eabfe7b3d8f1be3e4615442423c7d3fbab10285b).
This note records completed checks; the parent owns subsequent full Lean-suite and
corpus-report qualification. No tests or builds were rerun while preparing this note.

## Model and correspondence

`tools/lean_boundary/PystachyPipeline.lean` models the actual six-stage
`PipelineState.begin`/`complete` guards. Eleven public guarantees passed
`Audit.lean`, allowing only the standard `propext`, `Classical.choice` and
`Quot.sound` axioms. They establish preserved ordered prefixes, one active next
stage, refusal to start while work is unfinished, finalization before consuming
lowering, terminal lowering, consistent report attempts and explicit terminal
targets of `finalize` or `lower`.

The implementation-correspondence test constructs all 13 reachable Python states
(seven idle and six active states). For each state it tries both methods with six
valid stage names, an empty name and an unknown name: **13 × 2 × 8 = 208
transitions**. It compares acceptance and resulting state against one batched
invocation of the compiled Lean model. Rejected Python transitions must also leave
state unchanged. This is exhaustive over those states/actions, not over compiler
programs or stage bodies.

The complete focused suite has **21 passing tests**. Real ordinary, retried and
finalization-only inspections supply its positive reports. Mutation controls cover
missing/reordered/duplicated stages, stale active state, forged stage evidence,
foreign or repeated attempt indices, changed sources, partial snapshots, absent
verification/provenance, mismatched snapshot contents and inconsistent checker
responses. Retry records must retain an active stage and must not cross the
requested terminal boundary. An explicitly requested finalization stop is accepted;
failed lowering with retained typed IR is not successful finalization evidence.

## Trust boundary

`tools/check_lean_pipeline.py` validates the inspection schema and consumed-source
inventory, checks requested IR verification is complete, binds snapshot bytes to
the report's SHA-256 digest and projects stage records into the Lean model. Lean
checks the normalized sequence and snapshot-attempt association.

The Python bridge/exporter, reported provenance, JSON/IO implementation and native
Lean compiler/runtime remain trusted. A digest binds contents to a report; it does
not authenticate the report. These results do not prove stage-body postconditions,
Python object ownership, typing/specialization, representation correctness,
optimization equivalence, exception semantics, GC or LLVM correctness. They are
**not a whole-compiler correctness proof**. Ordinary ownership, differential,
bootstrap and native execution checks remain separate requirements.

## Commands and retained results

The worktree was `/workspace/scratch/9f30aa4fd4fd/pystachy`. The pinned Lean binary
directory was `/workspace/scratch/c2b093657c17/toolchains/lean-4.35.0-linux/bin`;
the Python development environment was
`/workspace/scratch/c2b093657c17/dev-venv/bin` (CPython 3.13.16).

From `tools/lean_boundary`, the final targets ran sequentially with the pinned
Lean directory prepended to `PATH`:

```sh
lake build PystachyPipeline
lake build Audit
lake build pystachy-pipeline
lake build pystachy-boundary
lake build pystachy-access
lake build pystachy-int
```

From the worktree root, the final focused commands were:

```sh
LEAN_BOUNDARY_REQUIRED=1 /workspace/scratch/c2b093657c17/dev-venv/bin/python \
  -m unittest discover -s tools -p test_lean_pipeline.py -v
/workspace/scratch/c2b093657c17/dev-venv/bin/ruff check \
  tools/check_lean_pipeline.py tools/test_lean_pipeline.py
git diff --check
```

All succeeded. Logs are under `/workspace/scratch/9f30aa4fd4fd/`:

| Log | Recorded result |
|---|---|
| `lean-pipeline-build-final.log` | Final model, all 11 audited guarantees and pipeline executable pass. Audit: 136.949 s wall / 42.855 s child CPU; executable target: 154.000 s wall / 56.826 s child CPU. These shared-host build times are not performance claims. |
| `lean-pipeline-tests-final.log` | 21 tests pass in 3.496 s, including the 208 transition comparisons. |
| `lean-boundary-build.log` | Existing payload checker builds successfully. |
| `lean-access-build.log` | Existing unchecked-access checker builds successfully. |
| `lean-int-build.log` | Existing integer checker builds successfully. |

Ruff reported `All checks passed!`; `git diff --check` was silent. Their output is
in the tool transcript, not a separate retained log. All four native checker
executables are available for the parent's broader suite.

## Review fixes and preliminary failures

Independent compiler/validation agent review found that malformed
`artifact_sha256` or `artifacts` values could raise an uncaught `AttributeError`.
The bridge now validates both mappings and has negative controls. The validation
review also prompted checks for a nonempty consumed-source inventory, matching
input hashes and complete requested IR verification. Parent review tightened
retry records to require an unfinished active stage. A further target-boundary
control prevents a finalization-only report from hiding a prior retry in lowering.
The final model and tests include all these fixes.

A preliminary combined `lake build pystachy-pipeline Audit` was interrupted with
exit 130 after `PipelineMain` and `Audit` reported success at about 185 s each;
executable completion was not established by that run. A later diagnostic wrapper
failed because `/proc` did not expose its own subprocess PID. That wrapper had
successfully rebuilt the final model before failing during Audit supervision.
The final log retains its setup/retry marker. Subsequent sequential builds
completed successfully and supersede both incomplete runs; neither preliminary
failure was a Lean rejection. No owned verification jobs remained running at handoff.
