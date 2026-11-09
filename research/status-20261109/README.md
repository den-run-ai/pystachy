# Fixes and investigations, 2026-11-09

Evidence for the work that followed the [2026-11-08 status check](../status-20261108/README.md).
This branch is not for merging; main ignores `research/`. Claude Code prepared the fixes,
measurements and drafts under the maintainer's direction.

## Issues and pull requests

The six issues drafted on 8 November were filed as #1164–#1169. Agents fixed them in separate
worktrees, and #1171 merged as `e81bdb0c`. The maintainer then stacked #1172–#1177 in that order
on `e81bdb0c`, each merging its predecessors. Each stacked head's tree equals a clean merge of
its own and its predecessors' branch tips onto `e81bdb0c`, checked locally. Every stacked head
passed all 20 PR checks and a Codex review with no findings:
`51bde21a`, `bcd0771a`, `c0d639d2`, `fb91d1aa`, `338fde17` and `6ae42170`.

| PR | Fixes | Notes |
|---|---|---|
| #1171 | #1168 program-cache key | Merged as `e81bdb0c`. Also keys `PYSTACHY_RUNTIME_C_CACHE`, found in a full audit of compile settings. |
| #1172 | #1164 `zip()` order with dynamic `Any` | A `__next__` that cleared a dict or set given before it also segfaulted. |
| #1173 | #1166 extensionless imports | Program-cache probes now record the path's kind, so file/directory flips invalidate. |
| #1174 | #1169 `input()` with a closed stdin | Records closed descriptors after start-up, so #1176's handoff composes with it. |
| #1175 | Hosted/native coverage drop | Measures existing unit tests of native-only code; three tests for unrun dynamic-`Any` paths. |
| #1176 | #1165, #50; part of #1167 | One start-up handoff; MCJIT keeps `lli`'s own close-on-exec dump descriptor. |
| #1177 | GC identity weights | Now also the maintainer's integration branch for #1172–#1176. |

The maintainer merged #1177 as `56678df4`, whose tree equals `6ae42170`'s; GitHub marked
#1172-#1176 merged. All seven main workflows passed (CI: 68 jobs, plus 2 PR-only skips). Hosted
coverage reached 95.7%/92.2% (projection 95.7%/92.3%), native runtime 94.7% lines and 84.9%
branches. `gc-ir` took 493/637 s on x86-64 (replay: 630/634 s) and 6.4/6.4 minutes on ARM64;
`ubsan-0` took 13.7 minutes on a `znver3` runner, the closest job to the cap (#1179).

Cross-PR checks: #1174 and #1176 were built and tested merged (closed stdin, stdout and stderr
match CPython under ORC, MCJIT and hosted JIT); #1176 documents `JITDUMPDIR` so #1171's settings
test passes after merging main. Agents' pushes kept PR CI to two runs at a time; the stacked
verification ran six at once.

## Coverage regression

Hosted coverage fell from 96.0%/92.5% (statements/branches, `72cc962e`) to 93.9%/90.6%
(`39fc6de3`). Most of the drop is measurement: the native program cache (#1103) never runs in the
CPython-hosted compiler, and its unit tests (and those of `--emit-ir`, the C runtime cache,
`ctypes_schema.py`, `source_lines.py`) ran in Lint but not under coverage. Counting them projects
95.7%/92.3%. Real gaps: #1102 left no case for `type()` of `Any` values in modules that do not
opt in; #1057 and #1112 left two runtime paths unrun. Native branches fell from 87.5% to 84.6%,
mostly error paths spread over ten PRs. Scripts: [coverage/](coverage/).

## Main CI time

Several jobs run close to the 15-minute cap on EPYC 7763 (`znver3`) runners, which take about 46%
of x86-64 jobs and run 1.34× slower than `znver4`: ubsan 12.7, python-int-optin-2 12.4,
python-free 12.2, gc-ir-1 12.1, PR native-aot 13.8, PR contracts 13.5, Variants' slowest shard
14.1 minutes. Growth since 2 November: 401 new corpus cases at 2.4× an existing case's cost
(72%), existing cases 10.7% slower, AOT builds 19% slower, and `gc-self` growing with the square
of compiler size. #1177 rebalances `gc-ir`; #1178–#1181 cover the rest.
The six stacked PR runs peaked at 14.3 minutes (#1172's `contracts`); Lint took 8.0–13.7.
Data and scripts: [ci-time/](ci-time/).

## JSON-repair throughput on `ce8c887`

Re-measured with the 2 November method (`tools/json_repair_bench.py`, 180 processes, one pinned
CPU, outputs checked). This host is faster (upstream took 26–36% less time), so read ratios:

| Workload | AOT vs upstream, 2 Nov | Today |
|---|---:|---:|
| `bench.py 200` | 5.3× | 5.9× |
| facade malformed | 5.8× | 6.8× |
| scaling escaped 2000 | 187× | 1541× |
| scaling unicode 2000 | 1.7× | 4.3× |
| scaling logs 1000 | 3.4× | 22.6× |
| scaling valid 4000 | 1.41× | 0.94× (host: CPython's C scanner 2.1× faster here) |

A same-host A/B against a rebuilt `ec442a20` puts today's AOT 9–86% ahead, from port changes;
compiler instruction counts moved by −1.1% to +1.9%. A `pystachy run` cache hit costs 37.8 ms
against 1.46 ms for its executable alone, mostly re-statting about 6,800 toolchain paths, eight
helper processes and a 717 KB manifest ([draft](followups/cache-hit-overhead.md)). Results and
configs: [json-repair/](json-repair/).

## Follow-up issues

Filed on 9 November (UTC) from the drafts in [followups/](followups/), all passing `tools/check_submission.py`:

- CI time, under tracker #41: #1178 PR job headroom, #1179 full-profile and Variants headroom,
  #1180 per-case AOT/import cost (with #706 for runtime re-optimization), #1181 `gc-self` scaling.
- #1182 closed standard streams as `None` (deviations #1174 documents).
- #1183 non-regular `NAME.py`/`__init__.py` crash or hang the compiler.
- #1184 rejected settings leak temporary directories; an inherited `PYSTACHY_ARGV0` breaks the compiler.
- #1185 program-cache hit overhead.

The `irsame` draft was not filed: #527 already tracks library paths in IR strings. They now make
about 264 of 4,345 programs differ when nothing changed, against 194 at `9c8bc746`.

## Retiring MCJIT

Agents worked from `56678df4` on replacing MCJIT with `llc -O0` and ORC, on newer LLVM
releases and on an in-process LLJIT launcher. The [launcher evaluation](lljit-launcher/report.md)
recommends the `llc -O0` route now and the launcher later under #707. It also found that
`-O0` code generation, main's `PYSTACHY_JIT_CODEGEN=0` included, gives an `except` clause
stale or unset values from its loop: an LLVM PHI-elimination bug in LLVM 18, 20 and 23.

## Release planning

An agent mapped the 26 open PRs, 235 open issues and the milestones onto v0.4.0 releases, from
live GitHub data and `git merge-tree` against `56678df4`, without changing GitHub:
[release-plan.md](release-plan.md). Its proposed milestones, assignments and closures (#1154 and
15 PRs) await the maintainer's decision.

## Not run

`make verify`, sanitizer suites (no clang runtime here), macOS and ARM64 locally, and the native
runtime coverage workflow. Local timings are single-host; CI timings come from GitHub's job logs.
