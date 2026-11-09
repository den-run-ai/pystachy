# Pystachy release plan: open PRs, milestones and the gap to v0.4.0

Prepared 2026-11-09 (UTC) against main `56678df4c667afb4c9b35d854e97cdc9f5c0c3f7`
(tag `v0.4.0-alpha.1` = `ce8c887f`; main is 22 commits past it). Analysis only:
nothing was changed on GitHub and nothing was pushed.

## TL;DR

- **v0.4.0-alpha.2** = the fixes already on main since alpha.1 (#1171–#1177, including a
  segfault fix in #1172 and the JIT descriptor/signal handoff in #1176) + **#1170** + small,
  scoped crash/driver fixes (**#1183**, **#1184**, the MCJIT remainder of **#1167**) + the CI
  capacity work that keeps release gates green (**#1181** has a projected hard-failure date of
  about Nov 17–19; **#1178**). Close **#1154** (fixed by #1162/#1176). Do not hold alpha.2 for
  the optional I/O stacks.
- **v0.4.0-alpha.3 (conditional)** = the two optional I/O stacks and the restricted numerical
  workers, each only after the combined gates in §2.2/§2.3. Neither I/O stack has CI evidence
  on current main; the libuv stack's native code never runs in CI (no workflow installs
  libuv); Lint already timed out on #1156 (15.3 min) after the stack added netio checks to it.
- **v0.4.0 (RC → stable)** needs: ≥20% CI headroom, a fix-or-document decision for open
  silent divergences (#69, #1182, #512, #51, #52), a written support matrix qualified on the
  exact RC commit (macOS has no corpus differential, #708; the PyPI hosted compiler is tested
  only on CPython 3.13.16 although it declares `>=3.11`), an LLVM-version/MCJIT decision,
  and a defined RC freeze (v0.3.0 went rc.1 → final in about 65 minutes).
- **Close 8 PRs outright** (#672, #743, #784, #796, #816, #1063, #1110, #1126) and, as
  recommended, **7 research drafts** whose shippable parts already landed or whose evidence
  must be remeasured anyway (#1089, #1090, #1091, #1111, #1133, #1095, #1105). Keep all
  branches (issues link commit-pinned evidence on them). That leaves 11 open PRs.
- The maintainer's audit is accurate in substance; §6 lists the nuances and omissions.
- Spot-checked afterwards on the same day: milestone and label counts, #1154's acceptance
  against #1162/#1176, #1063 → #1122, #1110 → #1147, #1181's projection, the release-notes,
  `docs/testing.md` and `requires-python` claims, and #1170's clean merge onto `56678df4`.

## 0. Method and limits

- Live GitHub data via the GitHub MCP tools (PRs, check runs, reviews, review threads,
  comments, issues, releases, tags, workflow runs/jobs), read 2026-11-09. Searches via
  `gh api -X GET search/issues`.
- Mergeability: a private bare clone in the scratchpad, all PR heads fetched from
  `refs/pull/*/head` (every fetched head equals the API head SHA), then
  `git merge-tree --write-tree` against main and against each stacked PR's base tip.
  No builds, tests or benchmarks were run.
- Limits:
  1. Milestones were enumerated through search (`milestone:` qualifiers return the full
     milestone object). A milestone with no items would not appear; confirm on the
     Milestones page.
  2. Branch-protection settings are not readable with these tools; inferred from
     `mergeable_state` (`blocked` on heads lacking the required `Verification` check).

## 1. Inventory of open pull requests (26)

24 drafts, 2 ready (#1170, #743). None has a milestone, assignee or approval. Only #672 has
CHANGES_REQUESTED. The only unresolved review thread is #816's Codex P1. Codex reviews exist
only on #1170 (no findings), #743 (2 findings, resolved) and #816 (4 findings, 1 unresolved);
apart from the maintainer's CHANGES_REQUESTED on #672, the other 23 PRs have no GitHub review
(the agent reviews cited in PR bodies were local).
No PR opened since Nov 8 is still open except #1170
(#1171–#1177 opened and merged). 18 of 26 conflict with main; 11 are stacked on non-main
bases, so their CI ran against those bases. PRs whose base descends from Nov 4–5 main
(#1063, #1088, #1136, #1089–#1091, #1111, #1133) ran the **old CI layout** (aggregate check `make verify (Linux x86-64, LLVM 18, Python 3.13)` instead of the
now-required `Verification`). None of those results is evidence for current main.

"Ahead/behind" is head vs main. "Base" merge is head vs its base branch tip (stacked PRs only).
Times are head-commit times; CI is the latest run on the current head.

| PR | Title (short) | Branch → base | Head (date) | Ahead/behind; merge vs main | Latest CI on head | Review | Links | Already on main |
|---|---|---|---|---|---|---|---|---|
| #1170 ready | Fix relative links in the PyPI description | `codex/pypi-description-links` → main | `ee1004bf` (Nov 9 00:52Z) | 1/22; **clean** (README unchanged on main since base) | Verification ✓ (docs-only path), Lint ✓ 9.9 m, Submission ✓ | Codex: no findings; no human review | – | No (main README still has 27 relative links) |
| #1145 | Native socket and readiness I/O | `prototype/native-network-io` → main | `9c2d9e5c` (Nov 8 01:14Z) | 2/58; clean | Verification ✓ (16 jobs incl. macOS distribution), Lint ✓ 9.8 m, smoke ✓ | none | Refs #1135 | No |
| #1156 | Dogfood compiler pipes, benchmark readiness I/O | `prototype/network-io-dogfood` → #1145 | `b9ab8d9d` (Nov 8 03:50Z) | 3/58; clean (base: clean) | Verification ✓; **Lint cancelled at 15.3 m (job timeout)**; smoke ✓ | none | Refs #1145, #1154 | No |
| #1161 | Bound drain accumulation, reject late completions | `perf/native-netio-receive` → #1156 | `c7f282b2` (Nov 8 04:36Z) | 4/58; clean (base: clean) | Verification ✓, Lint ✓ 12.2 m, smoke ✓ | none | stacked on #1156 | No |
| #1146 | Owned libuv TCP exchanges | `prototype/libuv-owned-io` → main | `5b50ebd3` (Nov 7 21:59Z) | 1/79; **conflict** (Makefile lint list) | Verification ✓, Lint ✓ 12.9 m, smoke ✓ | none | – | No |
| #1155 | Dogfood libuv with compiler source transfers | `prototype/libuv-io-dogfood` → #1146 | `b68c4262` (Nov 8 03:46Z) | 2/79; conflict via #1146 (base: clean) | Verification ✓, Lint ✓ 10.6 m, smoke ✓ | none | Refs #1146 | No |
| #1158 | Preserve libuv completions across copy failures | `fix/libuv-io-completion` → #1155 | `a9389c5e` (Nov 8 04:11Z) | 3/79; conflict via #1146 (base: clean) | Verification ✓, Lint ✓ 12.3 m, smoke ✓ | none | Refs #1146 | No |
| #1088 | Verified native float-map parallelism | `research/minimal-native-parallel` → main | `163fe22c` (Nov 5 06:50Z) | 3/195; **conflict ×5** (Makefile, docs/concurrency.md, driver.py, ircheck.py, program.py) | old layout ✓, Lint ✓ | none | Refs #714, #754, #702, #767 | No (no `lib/parallel.py`) |
| #1136 | Ordered row scoring on native workers | `prototype/numeric-row-workers` → #1088 | `86fe869b` (Nov 7 08:17Z) | 4/195; conflict ×5 via #1088 (base: clean) | old layout ✓, Lint ✓ | none | stacked on #1088; does not compose #1122/#1125 | No |
| #1135 | Owned native subprocesses, compiler supervision | `prototype/native-process-supervision` → main | `6ac75c62` (Nov 7 08:23Z) | 2/184; **conflict ×3** (docs/concurrency.md, docs/stdlib.md, runtime.c) | Verification ✓, Lint ✓, smoke ✓ | none | Refs #754, #767 | No (no `lib/process.py`) |
| #1089 | Compiler build parallelism, stage timings | `research/compiler-parallelism` → main | `3f4318a5` (Nov 5 18:49Z) | 3/193; conflict ×7 | old layout ✓, Lint ✓ | none | Refs #1011, #105, #767, #104 | Stage timings → **#1148** (`PYSTACHY_TIMING`) |
| #1090 | Faster bootstrap, runtime caching | `research/self-build-pipeline` → #1089 | `626c3bf1` (Nov 5 19:58Z) | 17/193; conflict ×8 (base: clean) | old layout ✓, Lint ✓ | none | Refs #1011, #105, #767 | Retained IR → **#1144**; C-runtime cache → **#1149** (both "Extract … from #1090"); its cheaper temporary compiler shipped separately as the O1 tier in **#1160** |
| #1091 | Bootstrap optimization, host comparisons (ThinLTO) | `research/compiler-host-scaling` → #1090 | `f8127dc2` (Nov 6 07:06Z) | 56/193; conflict ×11 (base: clean) | old layout ✓, Lint ✓, smoke ✓ | none | Refs #1011, #46, #767 | No ThinLTO on main |
| #1111 | Runtime overlap for ordinary bootstraps | `prototype/ordinary-runtime-overlap` → #1091 | `cf6fa8dc` (Nov 7 01:00Z) | 58/193; conflict ×11 (base: clean) | old layout ✓, Lint ✓ | none | stacked on #1091 | No |
| #1133 | Bounded process workers, detached backend jobs | `prototype/bounded-process-workers` → #1111 | `a8b8eb20` (Nov 8 03:28Z) | 60/193; conflict ×16 (base: clean); stack carries 189k added lines | old layout ✓, Lint ✓, smoke ✓ | 1 owner comment (ownership findings fixed) | stacked on #1111 | Local workers → **#1153** (`tools/process_workers.py`, `application_workers.py`) |
| #1095 | GC on application workloads, optional BDWGC | `research/gc-locality-atomic-20261106` → main | `08963a31` (Nov 6 06:05Z) | 23/185; conflict ×7; 68k added lines | Verification ✓, Lint ✓, smoke ✓ | none | Refs #715, #650 | No (no BDWGC) |
| #1105 | StringZilla scans, bounded float parsing | `research/text-kernels` → main | `d47528a7` (Nov 6 21:46Z) | 1/184; conflict ×4 (Makefile, docs/internals.md, runtime.c, float_span.py) | Verification ✓, Lint ✓, smoke ✓ | none | Refs #30, #655 | Float parser → **#1143**; StringZilla: no |
| #1134 | Preserve list bounds across element/identity writes | `research/list-shape-effects` → `research/typed-list-contracts` | `7b4946fe` (Nov 7 07:49Z) | 1/181; conflict ×1 (optimizations.py); base already in main (#1128/#1125) | Verification ✓, Lint ✓, smoke ✓ | none | stacked on #1128/#1125 | Base yes; own change no |
| #1126 | Byte-BPE vs Cython, mypyc, PyPy | `research/byte-bpe-runtime-comparison` → `prototype/byte-bpe-showcase` | `ae2c0afe` (Nov 7 05:54Z) | 1/178; clean; base already in main (#1107) | **Verification ✗** (native-0 cancelled at 15 m), Lint ✓, smoke ✓ | none | Refs #1012, #361 | Base yes; comparison runner no |
| #1110 | Validate/measure installed JSON-repair companion | `fix/json-repair-installed-validation` → main | `45501309` (Nov 6 23:05Z) | 1/183; conflict ×3 | Verification ✓, Lint ✓, smoke ✓ | none | stacked on #1109 (merged) | Safety/smoke part → **#1147**; API bench + Nov 6 results: no |
| #1063 | Guarded callbacks for bisect | `prototype/v020-callback-skew-probe` → main | `169c8459` (Nov 4 08:18Z) | 1/280; clean but `blocked` (no `Verification` on head) | old layout ✓, Lint ✓ | none | Refs #1054, #392, #389 | **Superseded by #1122** (compiler guards, `bench/guarded_callbacks`) |
| #816 | Do not merge: batched comparison declines | `claude/festive-einstein-8ucfv8-declines` → main | `63e3db29` (Oct 21) | 4/1168; conflict ×7 | old: 32 ✓, 1 skip | **1 unresolved Codex P1** (silent wrong result) | Refs #801 | No (unsound) |
| #796 | Research: dynamic Any roadmap | `claude/festive-einstein-8ucfv8` → main | `93e2fd10` (Oct 21) | 10/1195; textually clean, `blocked`; adds root `research/` (rejected by `make check-repository`) | old: 32 ✓, 1 skip | 8 comments | filed #797–#805 | Follow-ups #806/#808/#809/#811/#812/#813 merged |
| #784 | Research: where dynamic Any pays off | `claude/admiring-albattani-pj7tyr` → main | `4d61e4ce` (Oct 20) | 6/1271; textually clean, `blocked`; adds root `research/` | old: 32 ✓, 1 skip | none | filed #777–#783 | n/a |
| #743 ready | Compatibility audit through #842 | `codex/compatibility-audit-exceptions-20261019` → main | `8873520f` (Oct 22) | 51/1034; conflict (its `docs/reports/` was deleted on main by #1001); 108k added lines; body ≈11k words | Lint ✓ only; no Verification, no Submission status | Codex threads resolved | Refs #769 | n/a |
| #672 (fork) | Decode named Unicode literals | `Lazarus000s:bureau/named-unicode-literals` → main | `ad465695` (Oct 18) | 2/1681; conflict ×9 | Lint ✗, source wheels ✗, old verify ✓ | **CHANGES_REQUESTED** (Oct 18), unaddressed | Refs #122 | No |

## 2. Recommendations by workstream

### 2.1 Ready now

| PR | Recommendation | Next action | Gates | Risks |
|---|---|---|---|---|
| #1170 | **v0.4.0-alpha.2 — merge** | Maintainer review, then merge (no refresh needed: README is unchanged on main since the PR's base and the merge is clean) | Packages/Lint on the merge commit; `twine check --strict` and the rendered description in the alpha.2 sdist/wheel | All 27 links target `blob/main/`, so a release's PyPI page links to newer docs than the installed version. Optional follow-up: rewrite links to the release tag at packaging time (release notes already pin tags). |

### 2.2 Optional native I/O: two stacks (target v0.4.0-alpha.3; alpha.2 only if every gate passes before the cut)

Merge order: **#1145 → #1156 → #1161** and **#1146 → #1155 → #1158**. Merge main into the bottom
PR (no rebase), push, run CI, merge; then retarget the next PR to main and repeat. Only
examples, tools, tests, docs, Makefile and Lint registration change; no compiler/runtime code.

| Finding | Evidence |
|---|---|
| #1146 conflicts with main | Makefile lint-python list: main added `test_retained_ir.py`, `test_jitfdprobe.py`; #1146 adds `test_check_uvio.py`. Keep both. |
| The two stack tips also conflict with each other | Same Makefile list (#1161 vs #1158). Trivial keep-both; `examples/README.md` auto-merges. #1146's "merge cleanly in a local trial" no longer holds for the tips. |
| Netio Lint cost is already marginal | #1145 adds a Lint step running `examples/netio/check.py` and `check_drain.py` with the hosted compiler plus an ASan/LSan harness. #1156's Lint timed out (15.3 m); #1161's passed in 12.2 m (19% headroom). |
| Libuv has no CI execution | No workflow or `tools/setup.sh` installs libuv; only harness unit tests run in `make lint`. `uvio-check` (JIT/AOT/GC) is local-only. |
| Obsolete workaround | #1156's launcher duplicates pipes to FD64+ to avoid #1154, which #1162/#1176 have since fixed. |
| Platform | Both Linux x86-64 only in practice; netio's kqueue path and all ARM64 runs are unexecuted. |

**Combined gates (both stacks):**
1. Refresh on current main; each PR's CI must run against main with today's checks
   (`Verification`, Lint, `Submission format`, Performance smoke).
2. Lint ≤ 12 minutes (20% headroom on znver3): move the hosted-compiler netio checks out of
   Lint into an opt-in job/target, or land #1178 first.
3. Native evidence in CI, not only local: netio check/drain in JIT/AOT and program GC stress
   on x86-64 and ARM64; `uvio-check` against a pinned libuv build with ASan/UBSan/LSan
   (LSan was blocked locally).
4. Ownership, cancellation, deadlines and cleanup: keep the existing regressions; add uvio's
   unvalidated items (queued incomplete-write cancellation, allocation-failure injection);
   check descriptor and child cleanup after SIGINT/SIGTERM; rerun after the #1162/#1176
   descriptor/signal handoff; drop the FD64+ workaround or justify it with a low-descriptor
   control.
5. Scope stated: Linux-only, optional, no default dependency; macOS kqueue either executed once
   on `macos-15` or excluded in docs and Makefile.
6. Claims bounded: uvio 0.82–1.15x CPython (overlapping ranges); netio bulk transfers ~20%
   slower than CPython. No performance claim beyond recorded results.
7. Mark ready to trigger Codex; resolve findings; maintainer review of each PR and of the
   combined diff if both stacks ship together.

Risks: CI budget (#1178), new external dependency provisioning (libuv), FD/signal interactions
with the JIT handoff, ~14k (netio) and ~4.4k (libuv) added lines, mostly results — committed
results beside workloads have precedent on main (195 files, 9.2 MB in `*/results/` directories,
including callgrind dumps).

### 2.3 Restricted numerical workers: #1088 → #1136 (target v0.4.0-alpha.3; Research if not met by RC freeze)

These change the compiler core (`driver.py`, `gen.py`, `ircheck.py`, `lower_module.py`,
`program.py`, `specs.py`, a new `parallel.py`) and `runtime.c`, and add a public API (`parallel.map_float`, `parallel.sum_rows_float`).

Gates:
1. Refresh #1088 onto main (5 conflicts, 3 in compiler core), then #1136.
2. `make irsame REF=56678df4`: explain every new acceptance/rejection (PRs claim one new API
   acceptance and no new rejection).
3. `make check-ir check-runtime` (ABI/effects of the pthread entry points); GC stress JIT/AOT;
   TSan on #1136's generated kernels (only #1088 ran TSan).
4. Composition with #1122's guarded callbacks and #1125's bounds proofs (#1136: "does not
   compose").
5. Regression policy: workers default to 1 (serial); document that cheap kernels regress
   (affine scoring 1.58x slower at 4 workers; 8 workers slower than 4), or add a work threshold.
6. macOS pthread backend executed, or Linux-only stated.
7. API labelled experimental in `lib/README.md`, `docs/stdlib.md`, `docs/concurrency.md`
   (which currently says native parallel loops are unsupported).

Risk: a stable v0.4.0 would freeze this API. Ship it as explicitly experimental or defer it.

### 2.4 Compiler build/bootstrap research stack: #1089 → #1090 → #1091 → #1111 → #1133

Shipped extractions, verified by code on main: `PYSTACHY_TIMING` (#1148 ← #1089),
`build --emit-ir` (#1144 ← #1090), `PYSTACHY_RUNTIME_C_CACHE` (#1149 ← #1090),
`BOOTSTRAP_AOT_OPT` (#1160, the same idea as #1090's cheaper temporary compiler; its body does not cite #1090), `tools/process_workers.py`/`application_workers.py` (#1153 ←
#1133). Not on main: ThinLTO, full-LTO partitions, witness scheduling, runtime overlap,
detached jobs/leases/object caching.

**Recommendation: post-0.4 research; close the five PRs and track residual experiments in
#1011 (and #105, #767; #754 for #1133's detached jobs), keeping the branches.** Reasons: the
shippable parts landed; every PR conflicts with main in 7–16 files; the stack carries 189k
added lines that must never merge; the CI on these heads is the old layout; the remaining
claims (ThinLTO 29.7% less bootstrap time at 16.4% more CPU; overlap 6.6% at 7.8% more CPU)
need fresh evidence on current main anyway. Alternative: park all five as drafts in a
"Research" milestone.

### 2.5 Native subprocess supervision: #1135 (Research, keep draft)

Adds `lib/process.py` and runtime support (Linux, executable/JIT owners). Before any 0.4
alpha it would need: a refresh over #1162/#1176's descriptor/signal handoff (SIGCHLD
disposition, inherited descriptors), ABI/effects, sanitizers, macOS or Linux-only scope, and
a named consumer beyond the example. It also overlaps the CPython-hosted local workers that
already shipped (#1153).

### 2.6 GC, text kernels, list bounds

| PR | Recommendation | Reason / next action |
|---|---|---|
| #1095 | Close (track in #715/#650) | Collector research; 68k lines, 7 conflicts; its own conclusion keeps BDWGC and the chunk marker experimental. Extract "compiler-proven atomic union boxes" as a focused PR later if wanted. |
| #1105 | Close (track StringZilla in #30) | Float parser shipped as #1143. The remainder adds a pinned third-party dependency (StringZilla 5.3.2), which needs a dependency decision first. |
| #1134 | Research, keep draft | Retarget its base to main (#1128/#1125 are already in main; one conflict in `optimizations.py`). Parked until the 10.6% whole-process JIT slowdown is explained; then irsame and current CI. |

### 2.7 Evidence and benchmark drafts

| PR | Recommendation | Reason |
|---|---|---|
| #1063 | Close as superseded | #1122 ("Generate guarded callback specializations in the compiler", Refs #1063) merged; `bench/guarded_callbacks` is on main. The v0.2.0 tracker already kept #1063 as research. |
| #1110 | Close; refile residual if wanted | Safety portion shipped as #1147. The rest is `tools/json_repair_api_bench.py` and Nov 6 measurements, which need remeasurement on current main (a small new PR, tracked under #861/#1012). |
| #1126 | Close (cite from #1012) | Body says "keep this research draft unmerged"; its Verification failed (native-0 hit the 15-minute cap); base #1107 is already in main. |

### 2.8 Older backlog

| PR | Recommendation | Reason |
|---|---|---|
| #743 | Close as obsolete | Its rolling `docs/reports/` log was removed from main by #1001 (policy: dated audits live in history/branches). Evidence stays at `8873520f`. Body ≈11k words vs the 200-word format. Codex threads are resolved. |
| #784, #796 | Close; keep branches | Research records adding root `research/`, which `make check-repository` rejects, so they cannot merge as-is. Findings are filed (#777–#783, #797–#805) and many follow-ups merged. Issues link files at commits of these branches: do not delete them. |
| #816 | Close | Explicitly unsound; one unresolved Codex P1 (a valid cross-type `__eq__` silently declined). The record is on #801. |
| #672 | Close as stale, with thanks (optionally one final ping with a deadline) | Changes requested 22 days ago (lazy table loading instead of +21% binary, drop reports, sync `ports/THIRD_PARTY_NOTICES`, remove the ETH address from the body) are unaddressed; Lint and source wheels fail; 9 conflicts; DCO now needs a `dco-signers.txt` line. #122 stays open. |

## 3. Milestones and roadmap

### 3.1 Existing milestones (found via search)

| # | Title | State | Open/closed items | Shipped |
|---|---|---|---|---|
| 1 | v0.2.0 | open | 0 / 16 (8 issues, 8 PRs) | v0.2.0 on Nov 6 |
| 2 | v0.3.0 | open | 0 / 2 | v0.3.0 on Nov 7 |

All 235 open issues and 26 open PRs have no milestone and no assignee. Issue triage snapshot:
38 open `bug`, 11 `priority: P2`, 7 `priority: P3`, **0 P0/P1** (7 P1 closed), 11
`design proposal`, 8 `status: backlog`, 1 `status: blocked` (#122), 23 unlabeled. Only 18 of
235 carry a priority label, so "no P0/P1" does not yet mean "no release blocker".

### 3.2 Proposed structure

| Milestone | Purpose | Exit criteria |
|---|---|---|
| **v0.4.0-alpha.2** | Correctness since alpha.1, PyPI description, crash/driver fixes, CI capacity that keeps gates green | #1170 merged; #1183/#1184 fixed; #1167 remainder fixed or documented; gc-self below its cap (#1181); release-prep PR (VERSION + `docs/releases/v0.4.0-alpha.2.md`); the four workflows green on the exact commit; archives, Docker and PyPI verified |
| **v0.4.0-alpha.3** | Conditional optional features: both I/O stacks, restricted numerical workers | Each passes §2.2/§2.3 gates; otherwise moves to Research at RC freeze |
| **v0.4.0** | RC → stable: freeze scope at rc.1, qualify, document | §5 checklist complete on the RC commit; only RC-found regressions after rc.1 |
| **Research (post-0.4)** (optional) | Prototypes and measurements not targeted at 0.4 | – |

Everything else stays unassigned (backlog).

### 3.3 Assignments

- **v0.4.0-alpha.2** — PR #1170. Issues: #1183 (compiler crash/hang on a directory or FIFO
  named `NAME.py`), #1184 (inherited `PYSTACHY_ARGV0` breaks the compiler; temp dirs leak),
  #1167 (remaining MCJIT descriptor; in-flight `llc -O0` + ORC work), #1181 (gc-self, about
  9–11 days to its 600 s cap as of Nov 8), #1178 (PR CI headroom). Optional, for release-notes
  traceability: merged #1171–#1177. Close #1154 (see §7).
- **v0.4.0-alpha.3** — PRs #1145, #1156, #1161, #1146, #1155, #1158, #1088, #1136.
- **v0.4.0** — #1179 (full CI/Variants headroom), #708 (macOS/LLVM verification), #430 (JIT
  codegen policy, MCJIT decision), #69 (P2: tuple identity lost on optional widening),
  #1182 (closed standard streams), #512 (annotation evaluation errors silently accepted),
  #51 (locale coercion), #52 (partial-write buffers), #854 (stalled apt setup in CI);
  stretch: #1180 (per-case AOT cost), #1185 (36 ms program-cache hit); the new release
  tracker (§7).
- **Research (post-0.4)** — PRs #1134, #1135 (plus any research PR the maintainer prefers to
  keep). Issues (optional): #707, #714, #715, #754, #767, #801, #1011, #1012.
- **#998** stays post-0.4 as the native-wheel/portability tracker; its v0.4 part (a stated,
  qualified support matrix) goes in the release tracker.

### 3.4 README and release documentation

- **README roadmap**: keep as is (AGENTS asks for a stable roadmap with no active issues).
  After v0.4.0, add at most one sentence if optional I/O or workers ship.
- **docs/releasing.md** needs: (a) an RC/freeze section: what may change after rc.1, the
  minimum qualification evidence per platform, a minimum soak; (b) PyPI publication and
  post-upload verification as numbered steps of "Publish a version" (today a separate
  manual run with `pypi=publish`); (c) a release tracker and milestone close/rollover step;
  (d) "patch releases are fixes only" (v0.3.1 also shipped opt-in features); (e) a required
  "Known issues" section: `docs/install.md` tells users to check each version's notes for
  known issues, but no release since v0.1.0-alpha.4 has one.
- **docs/testing.md** says "Issue #766 tracks requiring both checks…"; #766 is closed. Restate
  the current branch-protection requirement.
- **docs/releases/v0.2.1.md** describes a version that was never tagged or published
  (folded into v0.3.0-alpha.1). Remove it or mark it unreleased.

## 4. Gaps between main and a v0.4 stable release (ranked)

| Rank | Gap | Evidence | Owner issue(s) | Milestone |
|---|---|---|---|---|
| 1 | **CI capacity will break the release gate.** Jobs sit near 15-minute caps with 1–5%/day growth; the release needs CI, Installation, Lint and Packages green on the exact commit. | gc-self 357 → 454 s (Nov 2 → 8) on znver3, quadratic in compiler size, 600 s cap ≈ Nov 17–19; main `ubsan-0` 13.7 m (56678df4); PR native-aot 13.1–13.8 m, contracts up to 14.3 m; Lint 10.0–13.7 m with one timeout (#1156); Variants shards 14.1 m; #1126's native-0 timed out | #1181, #1178, #1179, #1180, #1083, #854 | alpha.2 / v0.4.0 |
| 2 | **Open correctness defects need fix-or-document decisions; triage is incomplete.** | Crash/hang: #1183. Compiler broken by env: #1184. Program-visible JIT descriptor (MCJIT): #1167. Silent divergences: #69 (P2, `is` result), #1182 (prints to a reused fd; documented), #512 (CPython TypeError not raised), #51 (LC_CTYPE differs, inherited by children), #52 (partial-write buffers; not in compatibility docs), #858 (opt-in identity). Only 18/235 issues prioritized; 23 unlabeled; 38 open bugs. | listed | alpha.2 / v0.4.0 |
| 3 | **Platform and distribution qualification.** Full differential verification runs only on Linux (LLVM 18) x86-64/ARM64. | macOS (LLVM 20) gets installation, distribution and archive smoke only (#708); the PyPI package is the hosted compiler, not native wheels (#998); `requires-python >=3.11` with no upper bound, but every workflow uses 3.13.16 (3.11 is checked only statically by mypy; CPython 3.14/3.15 untested); glibc ≥ 2.39 only; ARM64 page-size variants untested; macOS JIT relinks its runtime per launch (#704). | #708, #998, #704 | v0.4.0 (matrix), post-0.4 (wheels) |
| 4 | **Toolchain policy and MCJIT.** | Two LLVM majors in production (18 Linux, 20 macOS); no written supported-version or upgrade policy; the LLVM 20/22/23 evaluation is not a PR yet; `PYSTACHY_JIT_CODEGEN=0` uses legacy MCJIT, the source of #1165/#1167 (perf jitdump); the ORC replacement is in flight. Results can change across LLVM versions (#656). | #430, #1167, #708, #707 | v0.4.0 decision |
| 5 | **Release process has steps without owner or evidence.** | No v0.4 tracker; milestones unused since v0.3.0; no RC freeze or soak (v0.3.0 rc.1 → final in about 65 minutes; v0.3.1 fixed a live-pipe read hang seven hours later); PyPI post-upload verification and macOS qualification unowned; patch release carried features; stale docs (#766, v0.2.1 notes, missing known-issues sections); 25 of 26 open PRs are maintainer-authored and Codex is the only reviewer: define independent review for release-affecting changes. | new tracker | v0.4.0 |
| 6 | **Scope and API stability of opt-in features.** | alpha.1 added local workers, a buffer/completion API ("experimental"), the O1 tier ("not qualified"), FFI bridge changes; candidates add netio/uvio/parallel/process. A stable label must not freeze these unintentionally. | tracker | v0.4.0 |
| 7 | **Coverage regressions.** | Hosted 96.0/92.5% → 95.7/92.2% after #1175; native branches 87.5% → 84.9% (error paths from about ten PRs). Review changed-code gaps with `COVERAGE_BASE=v0.3.1` before rc.1. | #45 | v0.4.0 |
| 8 | **Performance-claim hygiene.** | A program-cache hit costs 37.8 ms vs 1.46 ms for the executable (≈ CPython startup); I/O prototypes are neutral to slower in places. Release notes must not imply startup or I/O wins. | #1185 | v0.4.0 stretch |
| 9 | **PR backlog hygiene.** | 26 open, 18 conflicting, 11 stacked on stale bases, 0 milestones. §7 reduces this to 11 actionable PRs. | – | now |

## 5. Proposed v0.4.0 qualification checklist (for the release tracker)

1. Scope freeze at `v0.4.0-rc.1`; afterwards only fixes for RC-found regressions.
2. CI headroom ≥ 20% on znver3 for PR, main and Variants jobs (#1178, #1179, #1181).
3. Every open `bug` triaged as blocker / known issue / later; each known divergence fixed or
   listed in `docs/language/compatibility.md` and in a "Known issues" section of the notes.
4. Written support matrix in `docs/install.md`, each row with evidence on the RC commit:
   Linux x86-64 and ARM64 (Ubuntu 24.04, glibc 2.39+, LLVM 18): existing main gates;
   macOS arm64 (primary) and x86-64 (secondary), LLVM 20.1.8: one native JIT/AOT corpus
   differential including exact-float cases (#708, #656); PyPI hosted compiler on CPython
   3.11–3.14 (and 3.15, or cap `requires-python`) on Linux x86-64/ARM64 and macOS arm64:
   install plus JIT/AOT smoke; Docker amd64/arm64.
5. LLVM decision: keep LLVM 18 (Linux) / 20 (macOS) for 0.4 and state it; schedule any
   upgrade for 0.5 with corpus, float-exactness and cache-identity evidence. MCJIT: replace
   with the ORC path before rc.1 or deprecate `PYSTACHY_JIT_CODEGEN=0` in the notes.
6. Experimental labels on every opt-in API/tool added in 0.4.
7. Coverage review of changed code since v0.3.1.
8. Soak: at least one full main CI + Variants + Coverage run on the RC commit, the macOS
   differential and the PyPI matrix, and no new P0/P1 for a fixed period (suggest 3–7 days).
9. Publish: Release workflow, archive/Docker verification, then PyPI verify → publish →
   install-from-index check of version and commit; close the milestone.

## 6. Audit claims checked

| Claim | Finding |
|---|---|
| Releases v0.3.1 (Nov 7), v0.4.0-alpha.1 (Nov 8) | Correct in Pacific time (published 2026-11-08 03:54Z and 17:12Z). Note: `docs/releases/v0.2.1.md` exists but v0.2.1 was never tagged. |
| Main 56678df4 includes #1171–#1177; all seven main workflows passed | Correct: CI (70 jobs: 68 ✓, 2 skipped), Installation, Lint, Packages, Performance smoke, Variants, Coverage all succeeded. #1171 merged separately (`e81bdb0c`); `56678df4` merged #1172–#1177, all marked merged. |
| No release-preparation PR or newer version | Correct (VERSION is `v0.4.0-alpha.1`). |
| ~26 open PRs (24 drafts, 2 non-drafts), no milestones; ~235 open issues, no milestones | Correct: exactly 26/24/2 and 235. Also: no assignees on any of them. No new PR is open since Nov 8 besides #1170. |
| v0.2.0/v0.3.0 milestones still open | Correct; both have 0 open items. |
| #1170 non-draft, green, clean | Correct; "green" is the docs-only CI path (appropriate), Codex found nothing, no human review yet; links target `blob/main`. |
| I/O stacks: #1146 conflicts; #1156 lacks a passing Lint run | Correct, but incomplete: #1155 and #1158 also conflict with main (via #1146); the two stack tips conflict with each other (Makefile); #1156's Lint was cancelled by the 15-minute timeout; no CI executes libuv. |
| Shipped: timings, retained IR, C-runtime cache, O1 bootstrap, local workers | Correct, verified in code: #1148, #1144, #1149, #1160, #1153. |
| #1088 → #1136 base conflicts | Correct (5 files, 3 in compiler core). |
| #1134 parked for a 10.6% JIT regression; #1105's float parser shipped | Correct (#1143). Omitted: #1134's base is already in main, so it can be retargeted. |
| #1063, #1110, #1126 are historical | More precisely: #1063 is superseded by merged #1122; #1110's safety part shipped as #1147; #1126 has a failing Verification. |
| #672, #743, #784, #796, #816 statuses | Correct. Additions: #743's target directory no longer exists on main (#1001); #784/#796 cannot pass `check-repository`; #816 has an unresolved P1. |
| Priorities #1183 and #1178 | Agree; add **#1181**, which has the nearest hard deadline (gc-self cap ≈ Nov 17–19). |
| Follow-ups filed Nov 9 (#1178–#1185) | Filed 2026-11-09 03:51Z = Nov 8 19:51 PT; the audit mixes UTC and Pacific dates. |
| JSON-repair rerun evidence saved at `research/status-20261109/` on `claude/happy-franklin-mc6j4c` (eed2912f) | Correct: `eed2912f` is on the remote branch and holds `json-repair/`; the branch head is now `9aa6c53f` (three later record commits). |
| (Not in audit) #1154 | Still open although #1162 and #1176 fixed it (both "Refs #1154"; `make jitprobe` covers inherited descriptors, shared/object runtimes, MCJIT, embedding and cached launches). Close it. |

## 7. Exact list of proposed GitHub changes (for maintainer approval)

Nothing below has been applied.

**Milestones**
1. Close milestone **v0.2.0** (#1): shipped Nov 6; 0 open / 16 closed.
2. Close milestone **v0.3.0** (#2): shipped Nov 7; 0 open / 2 closed.
3. Create **v0.4.0-alpha.2**: "Correctness fixes since alpha.1, PyPI description links,
   import/driver crash fixes and the CI capacity needed to keep release gates green."
4. Create **v0.4.0-alpha.3**: "Conditional optional features (native readiness I/O,
   libuv, restricted numerical workers) after refresh on main, CI within budget and stated
   platform scope."
5. Create **v0.4.0**: "Scope freeze at rc.1; qualify the exact release commit on the
   supported matrix; fix or document known divergences; ≥20% CI headroom."
6. (Optional) Create **Research (post-0.4)**.

**Assignments**
- v0.4.0-alpha.2: PR #1170; issues #1183, #1184, #1167, #1181, #1178. Optional: merged PRs
  #1171–#1177.
- v0.4.0-alpha.3: PRs #1145, #1156, #1161, #1146, #1155, #1158, #1088, #1136.
- v0.4.0: issues #1179, #708, #430, #69, #1182, #512, #51, #52, #854; stretch #1180, #1185;
  the new tracker below.
- Research (if created): PRs #1134, #1135; optionally issues #707, #714, #715, #754, #767,
  #801, #1011, #1012.
- Assign the v0.4.0 tracker (and optionally the alpha.2 issues) to the maintainer.

**Issues**
- Close **#1154** as completed: fixed by #1162 and #1176; `make jitprobe` covers its acceptance.
- Create **"Prepare and qualify v0.4.0"** (release tracker, milestone v0.4.0): the §5 checklist,
  support matrix, LLVM/MCJIT decision, known-issues list, RC freeze.
- (Optional) Create "Pin PyPI description links to the release tag" (follow-up to #1170).

**PRs to close — high confidence** (keep every branch; do not delete)
1. #743 — obsolete: its `docs/reports/` log was removed from main by #1001; evidence stays at `8873520f`.
2. #816 — explicitly unsound (unresolved Codex P1); the approach is recorded on #801.
3. #1063 — superseded by merged #1122 (compiler-generated guarded callbacks).
4. #784 — research record with a root `research/` tree `check-repository` rejects; findings filed as #777–#783.
5. #796 — research record with a root `research/` tree; findings filed as #797–#805, follow-ups merged.
6. #672 — stale fork draft: changes requested Oct 18 unaddressed, failing Lint/source wheels, 9 conflicts; #122 stays open.
7. #1110 — safety portion shipped as #1147; the remaining API benchmark needs fresh measurements in a new PR.
8. #1126 — research comparison marked "keep unmerged"; Verification failed; base #1107 already in main.

**PRs to close — recommended research cleanup** (alternative: keep as drafts in "Research";
on closing, comment the residual work on the named issue)
9. #1089 — stage timings shipped as #1148; residual LTO partitions → #1011.
10. #1090 — retained IR and C-runtime cache extracted (#1144, #1149), cheaper temporary compiler shipped as #1160's O1 tier; residual witness scheduling → #1011.
11. #1091 — ThinLTO/inlining research needing fresh evidence on current main → #1011.
12. #1111 — runtime-overlap research (6.6% bootstrap time at 7.8% more CPU) → #1011.
13. #1133 — local workers shipped as #1153; detached jobs/leases are distributed-execution research → #754.
14. #1095 — collector research (BDWGC adapter, union boxes; 68k lines, 7 conflicts) → #715/#650.
15. #1105 — float parser shipped as #1143; StringZilla needs a dependency decision → #30.

**PRs kept open after this cleanup (11)**: #1170 (merge for alpha.2); #1145, #1156, #1161,
#1146, #1155, #1158, #1088, #1136 (alpha.3, conditional); #1134, #1135 (research drafts;
retarget #1134's base to main).

**Documentation PRs to open later (not GitHub settings)**: release-prep for alpha.2
(VERSION + notes with a "Known issues" section); `docs/releasing.md` RC/freeze, PyPI and
milestone steps; `docs/testing.md` #766 wording; remove or mark `docs/releases/v0.2.1.md`.
