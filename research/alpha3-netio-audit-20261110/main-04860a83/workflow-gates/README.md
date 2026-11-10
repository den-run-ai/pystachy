# Exact-main Packages and Performance evidence

Main commit: `04860a83618e744c6f461761b6ee7fdbbe21f985`  
Tree: `bc34d9b1a3f648fbae6368e1c78485baf8d60c99`

This bundle records two completed workflows and the scoped Variants decision. It does not claim publication or completion of the other release workflows.

## Completed workflows

- Packages: https://github.com/den-run-ai/pystachy/actions/runs/42864866834 — passed on exact main. Its sole job passed the native build and both package smoke invocations. The log records matching offline hashed dependency sync through CPython library/module/CLI, JIT and standalone AOT for both compiler routes.
- Performance smoke: https://github.com/den-run-ai/pystachy/actions/runs/42864866829 — passed on exact main. The retained report compares exact ad3d0c0e against 04860a83 and is complete: 11 workloads, 49 comparisons, all classified ok, with no warning or unconfirmed candidate.

All job pages are accounted for: each workflow has one job, returned on the first 100-item page. The workflow/job JSON and full logs preserve the evidence. Performance smoke is an advisory bounded comparison, not a general performance guarantee.

The original performance ZIP is preserved. Its SHA256 matches GitHub artifact 13787222610:
`05d523ffb5ca42e3d78d64365d2f00a5add316d20b9e00f8fefa05b301cf08cb`.
The raw JSON is unmodified. Its exact revisions, runner hash and all reported workload source hashes were checked against the candidate.

## Variants

**Not triggered and not executed on 04860.** The actual merge changes 39 paths; none matches the workflow's six push-filter paths. No compiler/runtime/library, corpus, variant script, toolchain setup or optimizer-spec source changes. Makefile only adds optional netio targets and PHONY entries.

The workflow header labels Variants advisory. docs/testing describes daily, manual and relevant-push execution. docs/releasing and tools/release_gate.py require CI, Installation, Lint and Packages. No additional Variants matrix was dispatched.

Historical run https://github.com/den-run-ai/pystachy/actions/runs/42847908900 passed all 24 jobs on exact ad3d0c0e. This is historical evidence for unchanged variant-tested source, not an exact-04860 workflow pass. The policy JSON records actual changed paths, watched paths, empty intersection, required workflows and source hashes.

## Roadmap snapshot

Milestone 4 remains open with 10 completed items and five conditional drafts: libuv #1146/#1155/#1158 and numerical workers #1088/#1136. Those stacks are unqualified and excluded from the prepared candidate. The repository has 22 open PRs; the older non-draft audit #743 remains conflicted. Publication remains pending.

## Integrity

`SHA256SUMS` covers every other file in this directory. Original artifact bytes and full logs are retained; structured verification summaries describe checks performed without rerunning the workflows.
