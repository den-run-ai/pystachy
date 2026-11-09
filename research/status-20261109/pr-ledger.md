# PR ledger, 2026-11-09 (19:05 UTC)

Main is `f60df76d`: v0.4.0-alpha.2 merged at 14:19 UTC and its release gate is green. The tag and
publication are left to the maintainer. Every PR below needs the maintainer's explicit go-ahead to
merge.

## Ready to merge

All have green CI at their heads and a Codex review there with no findings, except where noted.

| PR | Change | Head | CI | Codex |
|---|---|---|---|---|
| #1188 | `-O0` JIT: split critical edges so `except` clauses read correct values | `a4c324aa` | 19/20, DCO skipped | clean at `4189a6a2`; the head's merge of main leaves the diff unchanged |
| #1189 (on #1188) | Replace MCJIT `-O0` with `llc` objects that ORC links | `581d2397` | 19/20, DCO skipped | clean |
| #1192 (on #1189) | In-process LLJIT runner replacing `lli` on Linux | `fed5f2ed` | 18/18 | clean; Codex's earlier finding (self-check argv overflow) is fixed |
| #1190 | Correct stale BPE and JSON repair notes (docs) | `2e852444` | docs plan green | clean |
| #1191 | Replay the JSON repair corpus natively; report a skipped replay | `56e5c7be` | 18/18; the replay ran 837/837 JIT and AOT under 3.13.16 | clean |
| #1195 (on #1191) | json_repair port 0.64.1 → 0.64.8; corpus 837 → 943; upstream 0.64.8's behaviour failures 20 → 0 | `691df1f7` | 18/18 | clean |
| #1193 | Halve the objects gc-self's collections mark (470 s → 292 s; Refs #1181) | `41452c39` | 18/18 | clean |
| #1194 | Accept `encoding`/`errors` by name in `bytes.decode`/`str.encode` | `97448add` | 18/18 | clean |
| #1196 | LLVM 18–23: `coro.end` form, `fmod` NaN, decimal floats, LLVM 23 `forceattrs`; defaults unchanged | `725383d2` | 18/18 | clean |
| #1197 | #1178: move the PR program-cache probe out of the near-limit `contracts` job | `574ef783` | 18/18; `contracts` 6.7 min, worker 0 8.9 min | requested 19:03 UTC |

Merge order: #1188 → #1189 → #1192, and #1191 → #1195. Merge #1197 before #1192: the
afternoon's `contracts` jobs took 13.7 (#1195) and 14.0 (#1192) of their 15 minutes on slower
runners, about 4 minutes of it the probe that #1197 moves. The others are independent.

## Before merging: the missing DCO check

From about 16:00 to 18:00 UTC both `pull_request_target` workflows, **Submission format** (a
required status) and **DCO**, failed at startup on every PR event, for example
[run 42656162019](https://github.com/den-run-ai/pystachy/actions/runs/42656162019). A startup
failure cannot be rerun.

- Submission format: #1190, #1191, #1193 and #1194 got the status when their bodies were updated
  with their CI results.
- DCO (`DCO certified (fork pull requests)`, required; skipped, which passes, for this
  repository's own branches) runs only on a push or a reopen, so #1190, #1191, #1193, #1194, #1195
  and #1196 still lack it. Merging main into each before it merges, which validates it against the
  new main anyway, runs it. #1188, #1189 and #1192 have it.
- #1197, opened at 18:27, lacks it too: its DCO run concluded `skipped` without creating the job,
  unlike #1188's and #1192's, and a rerun at 19:05 did the same
  ([run 42674246285](https://github.com/den-run-ai/pystachy/actions/runs/42674246285)). If a fresh
  push's run also creates no job, running the job for every PR and skipping only its step would
  keep the check present.

GitHub also marked #1192's first CI attempt's bootstrap jobs `abandoned` although both passed, so
no test jobs were created. Re-running all jobs kept that state; re-running failed jobs rebuilt the
bootstrap, and the run passed.

## Drafts for the maintainer to file upstream

- LLVM: the `-O0` landing-pad PHI miscompile, in [llvm-upstream/](llvm-upstream/).
- json_repair: a stray `/` before a value drops data, in [upstream-json-repair/](upstream-json-repair/).
