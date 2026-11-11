# Match PR #1272 — immutable CI snapshot

As of **2026-11-11 20:41:49 UTC**.

## Current integration head: not qualified by CI yet

PR [#1272](https://github.com/den-run-ai/pystachy/pull/1272) is open, draft, and mergeable. Its head is `601807e3686fa83a362cceb0d962d8e6332fbc34`; its base and live main are both `a339ab3748a59d6e4da899f0f3f2d5965b95e5ba`.

The synthetic merge ref `d7572fad12cde21f0ff34d98e417e1a7d88826dd` has the same tree as the reviewed integration head: `b28d80a94d0ac11e18cd6da7c6586e704a757bfd`.

| Workflow | Run | Status | Jobs created |
|---|---:|---|---:|
| CI | [43096685652](https://github.com/den-run-ai/pystachy/actions/runs/43096685652) | Queued | 0 |
| Lint | [43096685712](https://github.com/den-run-ai/pystachy/actions/runs/43096685712) | Queued | 0 |
| Performance smoke | [43096685661](https://github.com/den-run-ai/pystachy/actions/runs/43096685661) | Queued | 0 |

**No current-head workflow or job has passed. Verification aggregate has not been created or run.** No completed current-head CI matrix, full contracts/IR evidence, current-head benchmark job, or current-head native pytest job is available. The current head must remain unqualified pending those gates.

There are **0 submitted reviews, 0 review threads and 0 discussion entries** at this snapshot.

## Previous head `dec4d9f1`: incomplete, with upload failures

The [previous CI run](https://github.com/den-run-ai/pystachy/actions/runs/43092514310) is nonterminal: **2 successful bootstrap jobs, 4 jobs still marked in progress after upload failures, and 9 queued verification groups**.

The x86-64 and ARM64 compiler/runtime fixed-point jobs passed. Both ordinary native JIT corpus halves passed, but subsequent variant/cache coverage did not execute. The separate previous-head Lint and Performance workflows passed; those successes are tied to `dec4d9f1`, not the new integration head.

| Affected job | Failed upload step | Recorded interval (UTC) | Missing later coverage |
|---|---|---|---|
| [Linux distribution 130778605709](https://github.com/den-run-ai/pystachy/actions/runs/43092514310/job/130778605709) | Retain Linux netio reports | 20:20:06–20:22:06 | pip/uv installation; source packages/native archive smoke |
| [macOS distribution 130778605821](https://github.com/den-run-ai/pystachy/actions/runs/43092514310/job/130778605821) | Retain native kqueue reports | 20:21:12–20:23:12 | pip/uv installation |
| [Native JIT worker1 130778605765](https://github.com/den-run-ai/pystachy/actions/runs/43092514310/job/130778605765) | Upload native JIT report; final upload | 20:18:18–20:29:34 | Sampled configurations |
| [Native JIT worker0 130778605808](https://github.com/den-run-ai/pystachy/actions/runs/43092514310/job/130778605808) | Upload native JIT report; final upload | 20:19:55–20:31:22 | Sampled configurations; native program-cache checks |

The queued groups are hosted, safety0, safety1, opt-in, cache/GC, native AOT0, native AOT1, contracts and benchmarks. Their tests have **not run** in this attempt. The failed retention steps cannot be treated as a completely successful test matrix with only missing artifacts.

Two attempts to retrieve Linux distribution logs returned connector `ReadTimeout`; the failure intervals and skipped stages above come from the job/step API. No compiler/test failure is shown in the observed steps, but absent coverage is not a pass. This snapshot does not establish an official GitHub outage.

## Evidence and handling

Raw workflow/job JSON, PR metadata, review state and live main ref are included beside this summary. Every jobs query used `per_page=100`, and every returned count equals its `total_count`. The workflow's top-level `head_sha` identifies its source; nested `pull_requests` metadata can change with the PR and is not used as historical source identity.

No manual reruns, cancellations, source edits, timeout changes or workflow changes were performed by this monitor. The previous head is superseded and should not be rerun. This folder is an immutable snapshot; later status belongs in a separate snapshot.

