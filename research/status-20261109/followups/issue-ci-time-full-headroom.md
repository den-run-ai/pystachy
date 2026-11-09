# Restore 20% headroom in full CI and Variants jobs

## Problem

Between Nov 4 and #1163, `gc-jit` hit its 15-minute limit in 5 of 15 sampled main runs; #1163 then split it. In those runs and on `ce8c887`, the slowest other x86-64 groups on EPYC 7763 runners took:

| Group | Minutes |
|---|---:|
| `ubsan-*` | 12.0–12.7 |
| `python-int-optin-2`, including 54 s of annotation-widening | 12.4 |
| `python-free-*` | 12.2 |
| `gc-ir-1` | 12.1 |

The same ARM64 groups take at most 7.3 minutes. Variants' `opt-1 cflags-O0` shards reach 13.1–14.1 minutes. Each of the 24 Variants jobs rebuilds the compiler, which costs 2.3–4.5 minutes per job. At 1–5% growth per day, the full-profile groups would reach 15 minutes in 3–20 days.

## Scope

Main and manual coverage stays exhaustive. Candidates:

- Add a fifth `ubsan` shard on main, and fourth shards for `python-free` and `python-int-optin`.
- Move annotation-widening to the lightest shard.
- Share one verified compiler across Variants jobs.
- Refresh case weights after large corpus merges.

## Done when

Over three main runs, each full-profile and Variants job keeps at least 20% headroom on `znver3`. Refs #41, #1083.
