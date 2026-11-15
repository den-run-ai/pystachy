# Final PR ready status and automated-review limit

[PR #1495](https://github.com/den-run-ai/pystachy/pull/1495) is **open, ready for review, unmerged and mergeable** at the recorded observation, 2026-11-15T00:13:58.805Z.

Head `1f9309a0b6db9598ea16ff2b5195bd3e1aa30504` and base `adac7f4c88fd86ddaecbb889042b778c701b29ed` are unchanged. The final PR body is byte-identical before and after the ready event and still links to the pinned [complete core qualification](https://github.com/den-run-ai/pystachy/tree/e613a0b2607aa4007cb3d37592ceb4d2b022cd66/research/any-boundary-continuation-2026-11-14).

| Event or gate | Run | Result |
|---|---|---|
| Final body edit: Submission format | [43657035332](https://github.com/den-run-ai/pystachy/actions/runs/43657035332) | Success |
| Mark ready: Submission format | [43657104879](https://github.com/den-run-ai/pystachy/actions/runs/43657104879) | Success |
| CI at the final head | [43654295644](https://github.com/den-run-ai/pystachy/actions/runs/43654295644) | Success |
| Lint at the final head, attempt 2 | [43654295641](https://github.com/den-run-ai/pystachy/actions/runs/43654295641) | Success |

All 23 current check runs are accounted for: 21 successes and the two expected qualification/DCO skips. The earlier cancelled Lint check remains in the full history, bringing the captured total to 24. The latest Submission format status agrees with the complete per-context status history. The unchanged strict capture auditor accepts the final metadata; no current check is pending or failed.

## Automated Codex review did not complete

The ready event triggered the automated review service. Its [summary comment](https://github.com/den-run-ai/pystachy/pull/1495#issuecomment-6886418592) reports failure for this exact head. Its [explicit quota comment](https://github.com/den-run-ai/pystachy/pull/1495#issuecomment-6886418892) states that the account's code-review usage limit was reached.

**This is not a clean completed automated review.** The original tool response, including the service's reported state fields, is preserved verbatim. This service failure was observed as comments; no separate failed check was present in the final captured check collection. CI, Lint and format success do not substitute for the unavailable automated review. No review retry, source edit, timeout relaxation or PR edit was performed during this final readback.

The independent compiler/proof reviews and complete tests remain in the pinned core evidence. This small supplement records the later metadata events and the automated-review limitation without changing that evidence or the PR's pinned link.

## Verification and raw records

`summary.json` contains the exact identifiers, timestamps, body hash, status accounting and review limitation. `captures.tar.gz` preserves all raw API pages for the body-edit and ready-event snapshots, the exact Codex response, the frozen read-only auditor and this packaging script. `manifest.json` records every archived file's byte count, mode and SHA-256. `SHA256SUMS` covers the other published files.

```sh
sha256sum -c SHA256SUMS
mkdir captured
tar -xzf captures.tar.gz -C captured
python3 captured/summarize_snapshot.py captured/ready-001 --final --output re-audit.json
```
