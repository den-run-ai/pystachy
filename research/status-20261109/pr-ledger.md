# PR ledger, 2026-11-09 (evening)

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
| #1193 | Halve the objects gc-self's collections mark (470 s → 292 s; Refs #1181) | `41452c39` | 18/18 | clean |
| #1194 | Accept `encoding`/`errors` by name in `bytes.decode`/`str.encode` | `97448add` | 18/18 | clean |
| #1195 (on #1191) | json_repair port 0.64.1 → 0.64.8; corpus 837 → 943; upstream 0.64.8's behaviour failures 20 → 0 | `691df1f7` | 18/18 | requested 18:27 UTC |
| #1196 | LLVM 18–23: `coro.end` form, `fmod` NaN, decimal floats, LLVM 23 `forceattrs`; defaults unchanged | `725383d2` | 18/18 | requested 18:27 UTC |

## Waiting for CI

| PR | Change | Status |
|---|---|---|
| #1192 (on #1189) | In-process LLJIT runner replacing `lli` on Linux | `fed5f2ed` fixes Codex's self-check overflow. Its first run created only the two bootstrap jobs (both passed) and reported failure; rerun at 18:24 UTC. A fresh Codex review follows green CI. |
| #1197 (draft) | #1178: move the PR program-cache probe out of the near-limit `contracts` job | CI running at `574ef783`; ready once green |

Suggested merge order: #1188 → #1189 → #1192; #1191 → #1195. The others are independent.

## Repository issue (resolved)

From about 16:00 to 18:00 UTC both `pull_request_target` workflows, **Submission format** (a
required status) and **DCO**, failed at startup on every PR event, for example
[run 42656162019](https://github.com/den-run-ai/pystachy/actions/runs/42656162019). They ran again
from 18:03. A startup failure cannot be rerun, so the PRs it left without the status (#1190, #1191,
#1193, #1194) got it when their bodies were updated with their CI results.

## Drafts for the maintainer to file upstream

- LLVM: the `-O0` landing-pad PHI miscompile, in [llvm-upstream/](llvm-upstream/).
- json_repair: a stray `/` before a value drops data, in [upstream-json-repair/](upstream-json-repair/).
