---
name: land-changes
description: Integrate and merge Pystachy pull requests and stacks, and judge their CI and review state. Use before merging or integrating any pull request, when refreshing a branch from main or resolving conflicts, and when deciding whether CI runs, skips or reviews count as evidence.
---

# Integrate and merge pull requests

These rules extend [AGENTS.md](../../../AGENTS.md#coordinate-publish-and-hand-off). Merge only
where the maintainer has authorized it.

- Integrate stacks in dependency order; refresh dependent bases and review the combined
  diff. Preserve both sides' runtime hooks, tables, test registrations and checks.
  A clean textual merge is not semantic validation. Never rebuild from an older tree
  (`git commit-tree` once dropped 41 files); merge/cherry-pick and diff against main.
- Script conflict resolution with the kept side explicit: `ours`/`theirs` depend on
  merge direction. Hotspots include notices, docs tables, Makefile `.PHONY`,
  `tests/verify.sh`, `check_runtime.py`'s `ALLOC` and `analysis.py`'s FFI names.
  State shared-file resolutions in both affected PRs.
- Before an authorized merge, recheck the live head/base, review threads and **all
  applicable workflows**. Validate against current main, use an expected-head SHA and
  recheck main afterwards. Old-head CI, mergeability and admin bypass are not evidence.
  Follow every checks/jobs page (`per_page=100`); distinguish expected conditional skips
  from missing/cancelled required checks. Green CI does not resolve design risks:
  experimental PRs can remain draft, and author self-review is not independent review
  ([#647](https://github.com/den-run-ai/pystachy/pull/647),
  [#658](https://github.com/den-run-ai/pystachy/pull/658)).
- Merge main into branches rather than rebasing; land CI-tested trees with merge
  commits. If GitHub rejects a locally clean merge, refresh from main and compare the
  remote tree to the tested one ([#170](https://github.com/den-run-ai/pystachy/pull/170)).
  Check for stray files (`*.rej`, `-`) and stale status text. When authorized, land
  independent green PRs instead of growing stacks; distinguish local trial merges from
  actual GitHub merges.
- CI runs on PRs except Markdown/docs-only ones, main pushes and manual dispatch;
  branches without PRs and conflicted PRs get no PR CI. Batch pushes: a new push can
  cancel earlier checks. Do not rerun merely to restart the queue. Measure worker time,
  critical-path execution, setup/transfer and queue delay separately. Inspect live
  concurrency rather than hard-coding limits; preserve per-commit main release-gate runs.
- Distinguish queued, running, failed, cancelled/skipped and `action_required` runs.
  No jobs can mean pending fork-workflow approval. Do not bypass approvals or cancel
  other sessions' useful runs. Integration branches must preserve fork provenance and
  do not waive review before execution
  ([#659](https://github.com/den-run-ai/pystachy/pull/659),
  [#665](https://github.com/den-run-ai/pystachy/pull/665)).
- Codex review triggers on opening/readying a PR or `@codex review`, not later pushes.
  Open drafts; mark them ready once validated and check the reviewed SHA.
  Failed/quota-limited reviews are not completed reviews or code findings. Reproduce
  each finding; fix real, proportionate ones with a regression and name the commit,
  or decline with reasons, then resolve the thread. Arrange fresh review through
  authorized means.
