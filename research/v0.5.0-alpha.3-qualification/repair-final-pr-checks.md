# Storage repair PR #1501 check qualification

Head: `0a2fe77a580106c197face4d2904be80e3f85dbc`. Observed: 2026-11-15 08:06:44 UTC. State: **all_observed_runs_completed**.

| Workflow | Status | Conclusion | Attempt |
| --- | --- | --- | ---: |
| [Submission format](https://github.com/den-run-ai/pystachy/actions/runs/43692829139) | completed | success | 1 |
| [Lint](https://github.com/den-run-ai/pystachy/actions/runs/43691494240) | completed | success | 1 |
| [Submission format](https://github.com/den-run-ai/pystachy/actions/runs/43691494255) | completed | success | 1 |
| [DCO (legacy)](https://github.com/den-run-ai/pystachy/actions/runs/43691494233) | completed | skipped | 1 |
| [CI](https://github.com/den-run-ai/pystachy/actions/runs/43691494236) | completed | success | 1 |

CodeQL: **not observed on this exact SHA**. This is not counted as passed.

Reviews: 0; review threads: 0; issue comments: 3; inline comments: 0.

## Every observed job

| Job | Status | Conclusion | Seconds |
| --- | --- | --- | ---: |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43692829139/job/132746874968) | completed | success | 6.0 |
| [make lint (ruff, shellcheck, clang -Wall -Wextra)](https://github.com/den-run-ai/pystachy/actions/runs/43691494240/job/132742907317) | completed | success | 837.0 |
| [Check title and description](https://github.com/den-run-ai/pystachy/actions/runs/43691494255/job/132742909393) | completed | success | 11.0 |
| [DCO certified (fork pull requests)](https://github.com/den-run-ai/pystachy/actions/runs/43691494233/job/132742910648) | completed | skipped | 0.0 |
| [verify (bootstrap, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132742907282) | completed | success | 327.0 |
| [native JIT and variants (worker 0)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137259) | completed | success | 406.0 |
| [native JIT and variants (worker 1)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137300) | completed | success | 275.0 |
| [verify (native-aot-3, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137305) | completed | success | 279.0 |
| [verify (native-aot-1, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137306) | completed | success | 242.0 |
| [verify (safety-0, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137312) | completed | success | 297.0 |
| [verify (native-aot-0, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137338) | completed | success | 164.0 |
| [verify (native-aot-2, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137353) | completed | success | 154.0 |
| [verify (cache-gc, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137364) | completed | success | 571.0 |
| [verify (safety-1, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137375) | completed | success | 411.0 |
| [verify (contracts, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137409) | completed | success | 648.0 |
| [verify (opt-in, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137412) | completed | success | 232.0 |
| [verify (hosted, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137425) | completed | success | 429.0 |
| [verify (benchmarks, x86_64)](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744137490) | completed | success | 423.0 |
| [Bootstrap tier and native archive qualification](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132744138449) | completed | skipped | 0.0 |
| [Verification](https://github.com/den-run-ai/pystachy/actions/runs/43691494236/job/132746557501) | completed | success | 20.0 |

## Conditional skips

- DCO certified (fork pull requests): Legacy placeholder intentionally false for its only pull_request_target event. Condition: `github.event_name != 'pull_request_target'`.
- Bootstrap tier and native archive qualification: Native archive/tier qualification belongs to non-PR workflows; this exact job condition excludes pull_request. Condition: `github.event_name != 'pull_request'`.

Every step status, timestamp, duration and source condition is retained in `qualification.json`. Skipped GitHub jobs can report inverted timestamps; those retain the raw dates and no invented duration.

The PR profile selects x86_64 bootstrap, eleven verification groups, two JIT/variant workers and the Verification aggregate. Archive qualification is expressly excluded from pull_request runs. Other committed workflows are push/schedule/manual/release-tag workflows rather than PR triggers.

## Limits

- Read-only snapshot; no workflows rerun/cancelled, metadata changed, reviews posted or PR merged.
- Parent owns the final live check before merge. CI PR profile is not the full release qualification suite.
- Gate names are requested release gates; parent owns branch protection and release qualification.
- Exact committed workflow sources were read at the integrated head. Managed CodeQL has a GitHub-generated dynamic path rather than committed YAML; its run, jobs and aggregate check remain distinct evidence.
- No managed CodeQL success is inferred from its absence; any observed managed jobs and check output are reported separately.
