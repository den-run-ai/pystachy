# Integrated release PR #1494 check qualification

Head: `bbc8c8c38858ea2d90859751e34b885fdea1ca1d`. Observed: 2026-11-15 06:53:21 UTC. State: **all_observed_runs_completed**.

| Workflow | Status | Conclusion | Attempt |
| --- | --- | --- | ---: |
| [Submission format](https://github.com/den-run-ai/pystachy/actions/runs/43685740059) | completed | success | 1 |
| [Lint](https://github.com/den-run-ai/pystachy/actions/runs/43685669503) | completed | success | 1 |
| [CI](https://github.com/den-run-ai/pystachy/actions/runs/43685669509) | completed | success | 1 |
| [Submission format](https://github.com/den-run-ai/pystachy/actions/runs/43685667657) | completed | success | 1 |
| [DCO (legacy)](https://github.com/den-run-ai/pystachy/actions/runs/43685667693) | completed | skipped | 1 |
| [PR #1494](https://github.com/den-run-ai/pystachy/actions/runs/43685666640) | completed | success | 1 |

CodeQL: observed; see JSON for exact results.

Reviews: 0; review threads: 0; issue comments: 0; inline comments: 0.

## Every observed job

| Job | Status | Conclusion | Seconds |
| --- | --- | --- | ---: |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43685740059/job/132725726261) | completed | success | 8.0 |
| [make lint (ruff, shellcheck, clang -Wall -Wextra)](https://github.com/den-run-ai/pystachy/actions/runs/43685669503/job/132725531205) | completed | success | 563.0 |
| [verify (bootstrap, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132725531304) | completed | success | 348.0 |
| [native JIT and variants (worker 1)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874684) | completed | success | 556.0 |
| [native JIT and variants (worker 0)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874733) | completed | success | 781.0 |
| [verify (hosted, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874784) | completed | success | 430.0 |
| [verify (cache-gc, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874801) | completed | success | 584.0 |
| [verify (native-aot-3, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874802) | completed | success | 201.0 |
| [verify (benchmarks, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874803) | completed | success | 431.0 |
| [verify (native-aot-1, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874808) | completed | success | 171.0 |
| [verify (native-aot-2, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874811) | completed | success | 241.0 |
| [verify (contracts, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874812) | completed | success | 649.0 |
| [verify (native-aot-0, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874826) | completed | success | 185.0 |
| [verify (safety-0, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874828) | completed | success | 389.0 |
| [verify (opt-in, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874835) | completed | success | 305.0 |
| [verify (safety-1, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726874844) | completed | success | 410.0 |
| [Bootstrap tier and native archive qualification](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132726875905) | completed | skipped | — |
| [Verification](https://github.com/den-run-ai/pystachy/actions/runs/43685669509/job/132729766685) | completed | success | 21.0 |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43685667657/job/132725528241) | completed | success | 13.0 |
| [DCO certified (fork pull requests)](https://github.com/den-run-ai/pystachy/actions/runs/43685667693/job/132725529273) | completed | skipped | 0.0 |
| [Analyze (c-cpp)](https://github.com/den-run-ai/pystachy/actions/runs/43685666640/job/132725525017) | completed | success | 74.0 |
| [Analyze (python)](https://github.com/den-run-ai/pystachy/actions/runs/43685666640/job/132725525279) | completed | success | 1381.0 |
| [Analyze (actions)](https://github.com/den-run-ai/pystachy/actions/runs/43685666640/job/132725525296) | completed | success | 34.0 |

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
- The connector rejects check-run annotations endpoints; annotation-endpoint-errors.json preserves that limitation. Completed CodeQL job logs and the aggregate check output are retained for warning review.
