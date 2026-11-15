# Integrated release PR #1494 after storage repair

Head: `328b945f02788b296d9981d1b44706a2a0092255`. Observed: 2026-11-15 08:28:25 UTC. State: **all_observed_runs_completed**.

| Workflow | Status | Conclusion | Attempt |
| --- | --- | --- | ---: |
| [Lint](https://github.com/den-run-ai/pystachy/actions/runs/43692995147) | completed | success | 1 |
| [CI](https://github.com/den-run-ai/pystachy/actions/runs/43692995189) | completed | success | 1 |
| [Submission format](https://github.com/den-run-ai/pystachy/actions/runs/43692956681) | completed | success | 1 |
| [Submission format](https://github.com/den-run-ai/pystachy/actions/runs/43692898557) | completed | success | 1 |
| [DCO (legacy)](https://github.com/den-run-ai/pystachy/actions/runs/43692898607) | completed | skipped | 1 |
| [PR #1494](https://github.com/den-run-ai/pystachy/actions/runs/43692897923) | completed | success | 1 |

CodeQL: observed; see JSON for exact results.

Reviews: 0; review threads: 0; issue comments: 0; inline comments: 0.

## Every observed job

| Job | Status | Conclusion | Seconds |
| --- | --- | --- | ---: |
| [make lint (ruff, shellcheck, clang -Wall -Wextra)](https://github.com/den-run-ai/pystachy/actions/runs/43692995147/job/132747355706) | completed | success | 543.0 |
| [verify (bootstrap, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132747356180) | completed | success | 337.0 |
| [native JIT and variants (worker 1)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691257) | completed | success | 554.0 |
| [native JIT and variants (worker 0)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691312) | completed | success | 512.0 |
| [verify (native-aot-3, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691389) | completed | success | 294.0 |
| [verify (hosted, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691412) | completed | success | 548.0 |
| [verify (safety-0, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691415) | completed | success | 327.0 |
| [verify (native-aot-2, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691421) | completed | success | 170.0 |
| [verify (native-aot-1, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691437) | completed | success | 253.0 |
| [verify (native-aot-0, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691444) | completed | success | 243.0 |
| [verify (cache-gc, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691486) | completed | success | 683.0 |
| [verify (contracts, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691492) | completed | success | 644.0 |
| [verify (benchmarks, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691505) | completed | success | 423.0 |
| [verify (opt-in, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691509) | completed | success | 452.0 |
| [verify (safety-1, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748691608) | completed | success | 504.0 |
| [Bootstrap tier and native archive qualification](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132748692563) | completed | skipped | — |
| [Verification](https://github.com/den-run-ai/pystachy/actions/runs/43692995189/job/132751423526) | completed | success | 24.0 |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43692956681/job/132747240376) | completed | success | 6.0 |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43692898557/job/132747067300) | completed | success | 7.0 |
| [DCO certified (fork pull requests)](https://github.com/den-run-ai/pystachy/actions/runs/43692898607/job/132747067838) | completed | skipped | 0.0 |
| [Analyze (c-cpp)](https://github.com/den-run-ai/pystachy/actions/runs/43692897923/job/132747065881) | completed | success | 86.0 |
| [Analyze (actions)](https://github.com/den-run-ai/pystachy/actions/runs/43692897923/job/132747066006) | completed | success | 47.0 |
| [Analyze (python)](https://github.com/den-run-ai/pystachy/actions/runs/43692897923/job/132747066072) | completed | success | 1233.0 |

## Conditional skips

- Bootstrap tier and native archive qualification: Native archive/tier qualification belongs to non-PR workflows; this exact job condition excludes pull_request. Condition: `github.event_name != 'pull_request'`.
- DCO certified (fork pull requests): Legacy placeholder intentionally false for its only pull_request_target event. Condition: `github.event_name != 'pull_request_target'`.

Every step status, timestamp, duration and source condition is retained in `qualification.json`. Skipped GitHub jobs can report inverted timestamps; those retain the raw dates and no invented duration.

The PR profile selects x86_64 bootstrap, eleven verification groups, two JIT/variant workers and the Verification aggregate. Archive qualification is expressly excluded from pull_request runs. Other committed workflows are push/schedule/manual/release-tag workflows rather than PR triggers.

## Limits

- Read-only snapshot; no workflows rerun/cancelled, metadata changed, reviews posted or PR merged.
- Parent owns the final live check before merge. CI PR profile is not the full release qualification suite.
- Gate names are requested release gates; parent owns branch protection and release qualification.
- Exact committed workflow sources were read at the integrated head. Managed CodeQL has a GitHub-generated dynamic path rather than committed YAML; its run, jobs and aggregate check remain distinct evidence.
- No managed CodeQL success is inferred from its absence; any observed managed jobs and check output are reported separately.
