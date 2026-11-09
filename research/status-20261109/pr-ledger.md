# PR ledger, 2026-11-09 (20:45 UTC)

All ten PRs below landed on main at 19:56 UTC as `c1796654` ("Merge verified PRs #1188 through
#1197", through #1198), with the maintainer's approval. Its second parent is `b1b21a75`, the tree
PR CI passed 18/18 and Codex reviewed without findings; GitHub marks each PR merged. Main's gate on
`c1796654` passed: CI 68/70 with the 2 PR-only jobs skipped as expected (longest job 12.4 min),
and Packages, Installation, Lint, Variants, Coverage and Performance smoke. #1167 is closed: its
last leftover went with MCJIT (#1189), and `jitfdprobe` passed on main on x86-64 and ARM64. The v0.4.0-alpha.2 tag and publication are still left to the
maintainer.

## Landed

All have green CI at their heads and a Codex review there with no findings.

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
| #1197 | #1178: move the PR program-cache probe out of the near-limit `contracts` job | `574ef783` | 18/18; `contracts` 6.7 min, worker 0 8.9 min | clean |

Merge order: #1188 → #1189 → #1192, and #1191 → #1195. Merge #1197 before #1192: the
afternoon's `contracts` jobs took 13.7 (#1195) and 14.0 (#1192) of their 15 minutes on slower
runners, about 4 minutes of it the probe that #1197 moves. The others are independent.

## Landing

The maintainer approved merging all ten. They land through #1198, which merges each reviewed head
in the order above (one conflict: `driver.py`'s JIT late passes take #1196's `LATE_PASSES` before
#1188's `-O0` critical-edge split), so that main's CI runs once on a tree PR CI tested. #1189,
#1192 and #1195 now target main, so GitHub marks every PR merged when #1198 lands, as `56678df4`
did for #1172 through #1177.

An earlier version of this ledger said a missing `DCO certified` check blocked six PRs. The
maintainer confirmed DCO is not required; that inference from GitHub's `blocked` state, made
without access to the branch protection settings, was wrong.

The 16:00-18:00 UTC `pull_request_target` outage left #1190, #1191, #1193 and #1194 without the
Submission format status; updating their bodies with their CI results restored it. GitHub also
marked #1192's first CI attempt's bootstrap `abandoned` although both jobs passed; re-running
failed jobs rebuilt it, and the run passed.

## Drafts for the maintainer to file upstream

- LLVM: the `-O0` landing-pad PHI miscompile, in [llvm-upstream/](llvm-upstream/).
- json_repair: a stray `/` before a value drops data, in [upstream-json-repair/](upstream-json-repair/).
