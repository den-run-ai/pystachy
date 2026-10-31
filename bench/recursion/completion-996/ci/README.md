# PR #996 exact-head CI evidence

`8ca9/summary.json` is the verified historical checkpoint for source commit
`8ca9b82c60651f746d538ad5da41ba02775bbd3c`. It must not be used as final evidence
for the later `860b6c503a4261a6c4dd86b803f4cf270ce95c74` candidate.

The checkpoint contains every check and job, all seven workflow runs (including
the skipped `pull_request_target` DCO workflow), original verification group ZIPs,
the verified-bootstrap bundle, both combined coverage reports and their original
part reports/logs, port preservation, performance smoke, and selected job logs.
GitHub artifact IDs, stable API URLs, digest/size/CRC results and retained membership
are recorded in the machine-readable files. `manifest.json` hashes every retained
file except itself. Ephemeral signed download URLs are excluded.

## Reuse for the next head

`collect_ci.py fetch --head HEAD --merge MERGE --out DIRECTORY` collects public
GitHub metadata with complete pagination and all workflow events. It can instead
consume equivalent raw JSON collected through the GitHub connector; preserve the
same filenames and record retrieval provenance. The current `fetch` operation is
read-only and may require network permission in a sandbox.

Download the artifact ZIPs named `verification`, every `verification-GROUP`,
`verified-bootstrap`, `port-check`, `coverage`, `runtime-coverage`, and
`perf-smoke` into `DIRECTORY/artifacts/NAME.zip`. Use the artifact IDs in the raw
inventory. Connector downloads provide authenticated artifact access when needed.
Capture the lint job's decoded log as `logs/lint-JOB_ID.txt`; retaining port,
upstream-large and coverage report logs gives additional audit context.

Create an isolated clean checkout at the exact source head, then run:

```sh
python3 ci-evidence/collect_ci.py verify \
  --head HEAD --base BASE --merge MERGE \
  --out DIRECTORY --source CLEAN_EXACT_HEAD_CHECKOUT
```

Verification enumerates `tests/verify.sh --list` and invokes the repository's
report validators. It does not run tests or compilers. It independently remerges
all original group reports, validates full shard/corpus membership and opt-in
deferrals, binds source and bootstrap identities, verifies the head/merge tree and
merge parents, checks every job and step conclusion, and checks coverage part
membership. Only assembly time and local report/log path prefixes are normalized
when comparing the rebuilt aggregate with GitHub's aggregate.

The expected workflow/check set and conditional matrix steps are deliberately
fail-closed. A changed workflow, extra attempt, new check, changed skip condition,
or report schema needs explicit review before updating the collector. Numeric
corpus and verification-stage expectations come from the exact-head contract.

## Interpretation

The 8ca9 checkpoint has 59 successful checks and two expected job skips: DCO for a
same-repository PR and badge publication restricted to main. The 54 logical stages
span 31 groups and 84 group-stage records: one bootstrap producer plus 30 consumer
bootstrap validations account for the repeated stage. Conditional matrix-step
skips are recorded individually and are required to run in their designated jobs.

Opt-in completed checks include exact expected compiler rejections and AOT checks
deferred only when the native IR matches; those categories are preserved rather
than counted as fresh successful executions. Coverage percentages are report-only.
Successful performance-smoke execution does not establish performance acceptance.
All local measurements and eventual merge decisions must bind to the final head.
