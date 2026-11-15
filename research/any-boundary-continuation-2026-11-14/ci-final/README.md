# Final CI qualification for PR #1495

**CI, Lint and Submission format passed for exact head `1f9309a0b6db9598ea16ff2b5195bd3e1aa30504`.**
This immutable capture was completed at 2026-11-15T00:08:41.609Z, before the PR was marked ready for review. Later body/ready metadata is recorded separately.

Base: `adac7f4c88fd86ddaecbb889042b778c701b29ed`. Head tree: `3960ae03b0cacfeaa71b8b2c32ced798562fc68b`. GitHub's synthetic merge commit `81a8c451f5fd6db69f143cdf5b27531dc80f8e8f` has that same tree and exactly the base/head parents, so the pull-request CI checkout has the final source tree.

The final commit changes only `tools/lean_boundary/REPORT.md` relative to the published source parent. The retrieved workflow files also match both the base commit and the locally qualified source byte for byte. Raw compare, commit and workflow records are included.

## Workflow outcomes

| Workflow | Run | Attempt | Event | Result | Created (UTC) | Last updated (UTC) |
|---|---|---:|---|---|---|---|
| CI | [43654295644](https://github.com/den-run-ai/pystachy/actions/runs/43654295644) | 1 | pull_request | success | 2026-11-14T23:39:05Z | 2026-11-14T23:53:59Z |
| DCO (legacy) | [43654293819](https://github.com/den-run-ai/pystachy/actions/runs/43654293819) | 1 | pull_request_target | skipped | 2026-11-14T23:39:04Z | 2026-11-14T23:39:10Z |
| Lint | [43654295641](https://github.com/den-run-ai/pystachy/actions/runs/43654295641) | 2 | pull_request | success | 2026-11-14T23:39:05Z | 2026-11-15T00:08:34Z |
| Submission format | [43654293773](https://github.com/den-run-ai/pystachy/actions/runs/43654293773) | 1 | pull_request_target | success | 2026-11-14T23:39:03Z | 2026-11-14T23:39:15Z |
| Submission format | [43654339567](https://github.com/den-run-ai/pystachy/actions/runs/43654339567) | 1 | pull_request_target | success | 2026-11-14T23:39:39Z | 2026-11-14T23:39:55Z |
| Submission format | [43655856876](https://github.com/den-run-ai/pystachy/actions/runs/43655856876) | 1 | pull_request_target | success | 2026-11-14T23:58:30Z | 2026-11-14T23:58:44Z |

The capture includes 22 check runs in all: 1 cancelled, 2 skipped, 19 success. Of these, 21 belong to current required attempts: 2 skipped, 19 success. The combined commit status is success, including the explicitly required Submission format context, reconciled against its latest historical status.

The two expected skipped current jobs are the CI qualification job, whose condition excludes pull requests, and the legacy DCO job, whose condition excludes `pull_request_target`. Every applicable current CI/Lint job and declared step passed; conditional steps outside this PR's selected matrix were checked as skipped. Earlier attempts remain visible below and in full raw metadata.

## Jobs, durations and limits

Durations below are GitHub job timestamps, not benchmark measurements. No benchmark timing was repeated for this qualification.

| Job | Run | Result | Seconds | Configured timeout (minutes) |
|---|---|---|---:|---:|
| [Bootstrap tier and native archive qualification](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630558113) | 43654295644 | skipped | 0 | 15 |
| [Verification](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132632893095) | 43654295644 | success | 22 | 10 |
| [native JIT and variants (worker 0)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630556861) | 43654295644 | success | 506 | 15 |
| [native JIT and variants (worker 1)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630556859) | 43654295644 | success | 366 | 15 |
| [verify (benchmarks, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630557046) | 43654295644 | success | 435 | 15 |
| [verify (bootstrap, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132629324378) | 43654295644 | success | 295 | 15 |
| [verify (cache-gc, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630557087) | 43654295644 | success | 569 | 15 |
| [verify (contracts, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630557042) | 43654295644 | success | 527 | 15 |
| [verify (hosted, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630556986) | 43654295644 | success | 362 | 15 |
| [verify (native-aot-0, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630556989) | 43654295644 | success | 181 | 15 |
| [verify (native-aot-1, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630556953) | 43654295644 | success | 181 | 15 |
| [verify (native-aot-2, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630557049) | 43654295644 | success | 168 | 15 |
| [verify (native-aot-3, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630556984) | 43654295644 | success | 213 | 15 |
| [verify (opt-in, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630556965) | 43654295644 | success | 286 | 15 |
| [verify (safety-0, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630557044) | 43654295644 | success | 204 | 15 |
| [verify (safety-1, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43654295644/job/132630556948) | 43654295644 | success | 445 | 15 |
| [DCO certified (fork pull requests)](https://github.com/den-run-ai/pystachy/actions/runs/43654293819/job/132629322424) | 43654293819 | skipped | -1 | 2 |
| [make lint (ruff, shellcheck, clang -Wall -Wextra)](https://github.com/den-run-ai/pystachy/actions/runs/43654295641/job/132633664559) | 43654295641 | success | 707 | 15 |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43654293773/job/132629321753) | 43654293773 | success | 7 | 2 |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43654339567/job/132629466395) | 43654339567 | success | 11 | 2 |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43655856876/job/132634091479) | 43655856876 | success | 10 | 2 |

### Historical attempts retained

| Job | Attempt | Result | Seconds | Current replacement |
|---|---:|---|---:|---|
| [make lint (ruff, shellcheck, clang -Wall -Wextra)](https://github.com/den-run-ai/pystachy/actions/runs/43654295641/job/132629324385) | 1 | cancelled | 916 | 132633664559 (attempt 2) |

The first Lint attempt was cancelled during its final `make check-recordings` step after 916 seconds against the unchanged 15-minute job limit. The log reports cancellation without an assertion failure; its timing is consistent with that job cap. Its cancelled check is retained as historical only because a separately captured later attempt of the same pinned workflow/job independently passes all required steps. The retry does not change source, limits, or gates. No still-active or unknown check is treated as superseded.

The comparison with the preliminary head's successful Lint is scheduling evidence only. It shows broad elapsed-time increases across separate successful steps, and it cannot substitute for completion at the final head. The original cancellation log, annotation-endpoint access limitation, exact step-duration comparison and all attempt metadata are archived.

The pinned workflows configure 19 PR job rows against a budget of 19. CI has 16 rows: bootstrap, 11 verification groups, two native JIT/configuration workers, the expected skipped qualification row, and the aggregate Verification gate. Lint, Submission format and legacy DCO add one row each. The 22 observed jobs include 3 Submission format runs (2 metadata retriggers) and 1 historical retry predecessor(s); these are separate events/attempts rather than additional matrix expansion.

The native AOT group permits four shards; other matrix groups permit at most two workers. The workflow sets `PYSTACHY_JOBS=4`. No matrix `max-parallel` is configured. Observed peak overlap was 13 CI jobs and 14 jobs across the captured workflows. Workflow concurrency groups cancel superseded runs for the same PR; they do not impose a global running-job cap.

The saved audit checks 163 required successful steps and 173 expected conditional skips against the exact pinned definitions. It covers compiler/runtime fixed points, all native AOT and JIT partitions, configuration samples, Lean build/audit and CI guard proofs, FFI, sanitizer controls, cache/GC/runtime contracts, workload checks, recordings and final report aggregation. Complete names, conditions, timestamps and status records are in `summary.json` and the raw captures.

## Evidence and reproduction

`captures.tar.gz` preserves every selected raw API response, all observed progress snapshots, the pinned workflow sources, correspondence checks, and the read-only audit script. `manifest.json` lists each archived file's exact byte length, mode and SHA-256; it also records the published artifacts' hashes. `SHA256SUMS` covers all other package files. Progress snapshots are historical observations; only the named final snapshot establishes completion.

All pages were followed until collection counts matched (or the historical-status collection returned its terminal short page). The final audit rejects changed head/base, an unexpected merge tree, missing jobs, unobserved required steps, unexpected skips/failures, incomplete pagination or non-success final statuses.

```sh
sha256sum -c SHA256SUMS
mkdir captured
tar -xzf captures.tar.gz -C captured
python3 captured/summarize_snapshot.py captured/snapshot-015 --final --output re-audit.json
```

Monitoring and auditing used read-only observations. A separately authorized root action retried the one cancelled Lint job; its exact receipt is archived. Workflow source, timeout limits and required checks were unchanged.
