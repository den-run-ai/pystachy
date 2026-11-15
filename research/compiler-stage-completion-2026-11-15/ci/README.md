# Current-head CI qualification

Observed complete on **2026-11-15 at 07:46:51 UTC** for
[PR #1499](https://github.com/den-run-ai/pystachy/pull/1499).
The PR remained **open, draft and unmerged**. Monitoring changed no compiler
source, PR metadata, reviews, comments or workflow state, and ran no local builds,
tests or measurements.

## Source identity

| Identity | SHA |
| --- | --- |
| Published PR head | `eabfe7b3d8f1be3e4615442423c7d3fbab10285b` |
| PR base | `80490143498d149d407343ba1cb7aedb1db2d2c5` |
| Initially tested local commit | `527dc89a02e8e8866fc4d83997847663a6e7c0aa` |
| CI checkout merge commit | `a59d373a5355fff42909121be09d96fd7b41975b` |
| Identical full tree for head, local commit and CI merge | `4deb05cd2f645d516dd37480d5510d0920747b6f` |

The published branch and PR refs were checked independently through both Git and
GitHub. GitHub's Git-data API confirmed the published and CI merge trees. All 61
file digests in the contracts report's source manifest matched the frozen local
checkout. The final checkout was clean.

The initial local commit had not been published when monitoring began; the
observation is retained in `unpublished-527dc89.json`. Qualification below applies
to the subsequently published head with the identical tested tree.

## Complete inventories

| Workflow | Run | Jobs | Successful | Skipped | Conclusion |
| --- | --- | ---: | ---: | ---: | --- |
| CI | [43689994102](https://github.com/den-run-ai/pystachy/actions/runs/43689994102) | 16 | 15 | 1 | success |
| Lint | [43689994113](https://github.com/den-run-ai/pystachy/actions/runs/43689994113) | 1 | 1 | 0 | success |
| CodeQL default setup, named PR #1499 | [43689989556](https://github.com/den-run-ai/pystachy/actions/runs/43689989556) | 3 | 3 | 0 | success |
| Submission format | [43689990842](https://github.com/den-run-ai/pystachy/actions/runs/43689990842) | 1 | 1 | 0 | success |
| DCO (legacy) | [43689990814](https://github.com/den-run-ai/pystachy/actions/runs/43689990814) | 1 | 0 | 1 | skipped |
| Total | 5 workflows | 22 | 20 | 2 | no failures |

There are **23 check runs: 21 successful and 2 skipped**, because the CodeQL
aggregate contributes a check beyond its three workflow jobs. The separate
Submission format commit status is also successful. No workflow, job or check
remained queued, running, failed or cancelled. All workflow attempts were the
first attempts.

The two whole-job skips are intentional:

- `Bootstrap tier and native archive qualification` runs only when the event is
  not `pull_request`, according to `.github/workflows/ci.yml`.
- `DCO certified (fork pull requests)` retains a legacy check name and is always
  skipped for its workflow's `pull_request_target` event.

Matrix-specific skipped steps are preserved separately in the complete job
inventories. The CodeQL aggregate was briefly neutral while Python analysis was
unfinished; its final aggregate and Python, C/C++ and Actions analyses all passed.

`final-eabfe7b3.json` contains the reviewed PR metadata, source association, all
workflow/job/step/check inventories, commit statuses, artifact metadata, source
API URLs and saved-file hashes. First-page completeness was checked against each
API's total count with a page size of 100.

## Verification evidence

The CI aggregate reports **43/43 checks passed across 14 groups** under the
**PR profile**. This is distinct from the full local 58-stage verification, which
was still running when this review finished. The aggregate report is retained as
`aggregate-verification.json` and its original 87,327-byte ZIP as
`verification-14152477307.zip`. The ZIP's SHA-256 matches GitHub's recorded digest:
`044c7b3fd9e1be416147ea0b610cd3081efa5f11a52e2945c79598ec2571c3eb`.

Lint's 47 steps all succeeded. Its logs explicitly record:

- 33 inspection, 12 pipeline, 8 admission and 6 ABI stage tests: **59 passed**.
- **21 Lean pipeline tests passed**.
- **11 pipeline guarantees passed the Lean axiom audit**.

The original source log line numbers are preserved in
`lint-stage-proof-excerpt.log`. `lint-132738436117.json` retains its full step
inventory; `verification-summary-excerpt.log` records the aggregate command,
head/base variables, PR profile and successful gating.

## Full FFI coverage

The contracts job invoked `tests/ffi/run.sh` without a corpus selector. The
downloaded original `verify/ffi.log` contains:

```text
Checking /tmp/pystachy-ffi.25526/repair/pystachy_json_repair/_native.abi3.so
943/943 match; 0 problems
196 passed, 0 failed
```

There are **no reported skipped cases or modes**. The dedicated CI step
`Require C, embedding and extension FFI coverage` passed; it checks that the FFI
log exists and rejects any `; skipped:` suffix. The contracts JSON independently
records FFI as pass, 196 passed, 0 failed, 65.886 seconds. The group reports
22/22 verification steps passed.

Preserved evidence includes `contracts-ffi.log`, `contracts-verification.json`,
`ffi-qualification.json` and the source-numbered `contracts-job-excerpt.log`.
The original 42,899-byte contracts archive is `contracts-14152039125.zip`; its
SHA-256 matches the GitHub artifact digest:
`45517b4bf606f5046feac86028f46c06ab87f2c7ebfe9fe212bae336e5203601`.

No code issue or failed CI job was observed on this published head. These results
do not change the scope of the compiler or Lean correctness claims, and this
review did not mark the PR ready or merge it.
