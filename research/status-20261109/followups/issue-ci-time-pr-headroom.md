# Rebalance PR CI jobs near 15 minutes on EPYC 7763 runners

## Problem

About 46% of x86-64 jobs run on EPYC 7763 (`znver3`) runners, which are 1.34× slower than `znver4` runners. Reports' per-group `platform.cpu` shows this. On those runners, Nov 8 PR runs [42493253529](https://github.com/den-run-ai/pystachy/actions/runs/42493253529) and [42496378373](https://github.com/den-run-ai/pystachy/actions/runs/42496378373) took:

| Job | Minutes |
|---|---:|
| `native-aot-0/1` | 13.1–13.8 |
| `contracts`, with the 209 s program-cache probe | 13.5 |
| `cache-gc`: runtime-cache 274 s, then gc-self 443 s | 12.5 |
| Lint on main, any runner (PR #1156: timed out at 15.3) | 10.0–12.9 |

Both native JIT and variants workers finished in 3.0–3.8 minutes. Since Nov 2, corpus work has grown in bursts that averaged 5% a day.

## Scope

Keep 20 jobs, every case and mode, and the bootstrap and aggregate checks. Options:

- Move the program-cache probe, or runtime-cache, into the JIT workers.
- Overlap Lint's LLVM cache controls (179–236 s) with its other steps.
- Give each JIT worker a weighted slice of the AOT corpus. This needs agreement on the two-worker rule.

## Done when

Across three PR runs, every PR job keeps at least 20% headroom on `znver3`, and docs/testing.md describes where the work runs. Refs #41. Prepared with Claude Code assistance.
