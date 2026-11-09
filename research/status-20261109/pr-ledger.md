# PR ledger, 2026-11-09 (afternoon)

Main is `f60df76d`: v0.4.0-alpha.2 merged at 14:19 UTC and its release gate is green. The tag and
publication are left to the maintainer. Every PR below needs the maintainer's explicit go-ahead to
merge.

## Ready to merge

| PR | Change | Head | CI | Codex |
|---|---|---|---|---|
| #1188 | `-O0` JIT: split critical edges so `except` clauses read correct values | `a4c324aa` | 19/20, DCO skipped | clean at `4189a6a2`; this head adds only a merge of main |
| #1189 (on #1188) | Replace MCJIT `-O0` with `llc` objects that ORC links | `581d2397` | 19/20, DCO skipped | clean at `69b3c95e`; re-review the #1187 merge before merging |
| #1190 | Correct stale BPE and JSON repair notes (docs) | `2e852444` | docs plan green | clean |
| #1191 | Replay the JSON repair corpus natively; report a skipped replay | `56e5c7be` | 18/18; the replay ran 837/837 JIT and AOT under 3.13.16 | clean |
| #1194 | Accept `encoding`/`errors` by name in `bytes.decode`/`str.encode` | `97448add` | 18/18 | clean |

## Waiting for CI or review

| PR | Change | Status |
|---|---|---|
| #1192 (on #1189) | In-process LLJIT runner replacing `lli` on Linux | CI rerunning at `79fac626`, after three harness fixes |
| #1193 | Halve the objects gc-self's collections mark (470 s → 292 s; Refs #1181) | CI rerunning at `41452c39`, after classifying its memo tables |

## Branches pushed, PR not yet opened (waiting for CI capacity)

| Branch | Change |
|---|---|
| `claude/happy-franklin-mc6j4c-json-repair-0648` (on #1191) | json_repair port 0.64.1 → 0.64.8; corpus 837 → 943; upstream's 0.64.8 behaviour failures 20 → 0 |
| `claude/happy-franklin-mc6j4c-llvm23-compat` | LLVM 18–23: `coro.end` form, `fmod` NaN, decimal floats, LLVM 23 `forceattrs`; defaults unchanged |
| `claude/happy-franklin-mc6j4c-pr-ci-headroom` | #1178: move the PR program-cache probe out of the near-limit contracts job |

## Repository issue

From about 16:00 UTC, both `pull_request_target` workflows fail at startup on every PR and edit:
**Submission format** (a required status) and **DCO**. Ordinary `pull_request` workflows run
normally, main and the workflow files are unchanged, and githubstatus.com reports no incident. Until
this is fixed, new PRs cannot get the required Submission format status. See, for example,
[run 42656162019](https://github.com/den-run-ai/pystachy/actions/runs/42656162019).

## Drafts for the maintainer to file upstream

- LLVM: the `-O0` landing-pad PHI miscompile, in [llvm-upstream/](llvm-upstream/).
- json_repair: a stray `/` before a value drops data, in [upstream-json-repair/](upstream-json-repair/).
