# RC.2 stabilization qualification

RC.2 prepares corrected integer-enum exit statuses from #1392 and redistribution of existing CI checks. RC.1 is published and publicly verified from merged main `30822255ee7ee704e0e780e01cd8c23357ba13ab`. Source integration and independent review used ChatGPT.

The final candidate is [PR #1403](https://github.com/den-run-ai/pystachy/pull/1403), remote head `1a53d86c5fb81514d8cd9bd3f2e264f51849fdcb`, tree `2b06c58a6fe0b41b6240190e750add7bb3c85237`, identical to local `e1ce4280aa94d918b059b5024ba9e9b94c1efa9c`. [The frozen-source receipt](frozen-source-receipt.json) preserves every integration mapping and all 12 unchanged qualified source/corpus objects.

## Corrected behavior and provenance

Supported `IntEnum`, `IntFlag` and integer-mixin enum members now supply the integer recorded when the member was created to `sys.exit` and `SystemExit`. This covers zero values, aliases, computed flags, base-typed views and `SystemExit` subclasses. User-overridden `__index__`/`__int__` and later `_value_` mutation cannot change the process status. The compiler-only payload is hidden from ordinary attribute lookup and reflection.

The original PR head is `78b7c5422b00d006013e3de4d1f3b77623b07122`. Local commit `440b7a09` is its genuine cherry-pick, followed by the immutable payload correction `5cba0c6f` and reflection correction `395227b75bb777401627c0296a18fe71388070e7`. A merge-tree comparison independently produced the first cherry-pick's exact tree, `7437c4e991bcd501ecf8a099e74be241b3232459`. The remote integration preserves the original PR head as a real second parent. The [source handoff](enum/handoff-report.md) and manifest distinguish original, corrected and integration sources.

The measured enum object layouts grow by eight bytes, a scalar slot with no new referenced object or identity box. Existing construction-time exception formatting remains documented: a side-effecting `__str__` can still execute earlier than in CPython. This correction does not expand general dynamic-Any enum support or enum integer range.

## Local qualification

The frozen compiler correction is local commit `395227b75bb777401627c0296a18fe71388070e7`, tree `066f5a791216fc721d734bb1e23bdd6194bce42f`. Its baseline is local RC.1 `7c75948747090c7d6a0a0bf76f9aecee8de90a15`, whose complete tree is identical to merged RC.1 main. Pinned CPython 3.13.16 and LLVM 19.1.7 produced three identical compiler stages of 915,570 IR lines and three identical runtime stages of 21,214 lines. The final native compiler SHA-256 is `cec4a5470dce6ad3cb6358b9b47552609b799e401fad1385e23a31a9af0571fc`.

All 96 exact stdout/stderr/status checks passed across normal and GC-stressed JIT/AOT, along with 70 related normal checks and 40 related GC checks. The baseline and original proposal have retained negative controls; the faulty intermediate private-slot reflection behavior is reproduced separately. Full typed-IR and LLVM assembly checks accepted 2,569 cases. Pinned CPython verification checked 2,336 recordings, 130 documented deviations, 11 stdlib copies and six pinned agent-source files.

LLVM19's runtime-effect checker is **not a passing gate**: its 57 findings and diagnostic bytes are identical to the retained RC.1 baseline. Hosted LLVM18 and the final integration tree require their own complete CI. The local baseline native receipt was recorded after bootstrap, not as a contemporaneous sealed CI bundle.

## Complete compiler comparison

Both native compilers completed all 4,481 inputs: 2,569 accepted and 1,912 rejected, with no new acceptances, new rejections, compilation-status changes or invalid records. All 339 raw difference cases are accounted for in [the adjudication](enum/ir-adjudication.json).

Of the 269 IR differences, 237 contain only exact checkout-path string substitutions; four add reviewed unused enum base declarations plus those paths; 14 change enum library layout/initialization; and 14 contain exit-specific semantic paths. The library audit accounts for 1,249 functions and verifies 42 payload initialization stores against original numeric member values. An independent reviewer checked all 28 old/new IR hashes for the exit cases and found no additional issue.

All 70 raw diagnostic differences are exact checkout-home substitutions. The repository's existing normalizer handles 56 and leaves 14 for explicit review. No raw IR or diagnostics were discarded. The complete 28,300-file comparison is retained in `pystachy-rc2-raw-compiler-comparison.tar.gz`, 221,507,656 bytes, SHA-256 `f287ffff4cfbea24a113f2659f18c34c207f8501c67d5f6358569a9a30b55b65`. The compact public [handoff bundle](enum/handoff-evidence.tar.gz) includes its selected execution and adjudication evidence.

## CI scheduling and remaining qualification

The PR profile moves `scaling-1` from benchmarks to the fourth AOT shard, preserving exactly 19 job rows and every existing check. Seventy-two independently executed harness tests passed, including negative controls for missing or duplicated halves, overlapping shapes and a failing scaling stage after a passing AOT shard. The two CI documentation rows were corrected after independent review.

The full profile separately moves annotation widening from the slowest promoting-integer worker to the runtime-cache worker, retaining its pinned dependencies and all existing cache probes. Scheduling estimates are based on retained job and step timings; they do not establish measured improvement or satisfy the repeated znver3 headroom criteria. Final source identities, harness review, full GC/platform CI, fresh Codex review and merged-main publication evidence will be appended as each gate completes.

The first Lint run on `0554eb05`, [43324381350](https://github.com/den-run-ai/pystachy/actions/runs/43324381350), failed because an older Lean workflow test still excluded the newly assigned runtime-cache dependency owner. The test-only correction preserves pinning, installation ordering and failure assertions. Nine Lean workflow and 27 workflow-limit tests passed, and independent review found no issue. The production workflow, compiler/runtime and corpus are unchanged by that follow-up. The failed log and the actual cancelled outcomes of superseded initial PR/full runs remain retained; none counts as passing qualification.

Fresh [PR CI](https://github.com/den-run-ai/pystachy/actions/runs/43325124749), [Lint](https://github.com/den-run-ai/pystachy/actions/runs/43325124750) and [full candidate CI](https://github.com/den-run-ai/pystachy/actions/runs/43325282489) qualify the corrected source. Full GC/platform completion remains pending at this checkpoint.

## Frozen scope

The new PR review defers #1399/#1400's annotation and circular-import dependency stack, and #1402's inferred collection-storage changes. #1401 also has an unresolved P1 new-rejection finding involving global loss of Any-to-dict refinement. The [scope review](new-wip-scope-review.json) records exact heads, dependencies and evidence boundaries. Those changes do not enter this candidate.

Stable-release issues #1178, #1179 and #1181 remain open. A successful RC run cannot establish three representative CPU-identified headroom cohorts or at-most-linear GC self-compilation growth.

