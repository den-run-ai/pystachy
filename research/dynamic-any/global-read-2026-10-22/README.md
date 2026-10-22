# Mutable-global identity allocation fix — 2026-10-22

Measured fix: PR #866, published commit `a6e1dafba8aae2801f341bbf666be89da6d490c5`.
Its tree `8ba3d61637a3228e16462ee5248d51b5c7f0b889` equals local measured commit `6eb693d18e87bf32af99390b95e6dccf512ae632` exactly.
Parent PR #864: `db4b8517b730eb0c365995e315520434dde8a5cc`.
Current main baseline: `7514bef719ca8cfe5ad816060574c54f25fd5e2d`.

The fix skips mutable-global numeric identity snapshots only in proven scalar arithmetic operand trees. Stores, copies, calls, dynamic operands, walrus expressions and unsupported syntax remain conservative. No runtime/layout changes and no benchmark/threshold changes.

## Findings

Ten CPU-pinned interleaved AOT pairs across all three variants recover the exact prior global-loop probes:

| Probe | Main | PR #864 | Fix | Extra peak RSS after fix |
|---|---:|---:|---:|---:|
| Integer 2M | 10.797 ms | 21.476 ms | 10.563 ms | none measured (previously 31 MiB) |
| Float 1M | 5.148 ms | 10.524 ms | 5.097 ms | none measured (previously 15.5 MiB) |
| Integer 6M | 33.784 ms | 53.207 ms | 34.635 ms | none measured (previously 32.6 MiB) |
| Float 6M | 31.456 ms | 53.399 ms | 34.191 ms | none measured (previously 32.6 MiB) |

GC diagnostic runs return from 16–33 MiB to a 1 MiB heap peak on these bounded probes. This is a peak/allocation result, not a long-lived application retention guarantee.

The maintained paired smoke's cases, metrics, three-pair batches, 20%/5 ms thresholds and confirmation rules are unchanged. Against main: 43 of 44 comparisons okay, one unconfirmed local-float JIT process result (initial +26.1%, confirmation +2.7%, overlapping ranges), zero confirmed warnings. Against #864: all 44 comparisons okay. Mutable-global AOT: integer 33.518→34.329 ms (+2.4%) and float 32.803→31.532 ms (-3.9%) versus main; versus #864 -33.6% and -36.0%. Compilation is measured once per source, separately from JIT/AOT process and in-process timing. All outputs are checked against CPython.

These are fresh local shared-host measurements, not a claim to reproduce the earlier CI numbers exactly. Raw samples and binary/input hashes are in measurement.json. Native compilers use identical runtime/library inputs to isolate compiler changes; those files are byte-identical in the three source revisions. Recorded baseline binaries were reused; candidate compiler and runtime fixed points were rebuilt in this session.

## Reproduction

Check out the main, parent and fix commits in separate worktrees. Use CPython 3.13.16 and LLVM 18.1.3. In each worktree run `make` with the same toolchain. Compile rss_meter.c with a C compiler. From this directory set these paths and run:

```sh
export MAIN_COMPILER=/absolute/main-worktree/pystachy
export PARENT_COMPILER=/absolute/parent-worktree/pystachy
export CANDIDATE_ROOT=/absolute/fix-worktree
export RSS_METER=/absolute/path/to/rss_meter
export MEASURE_OUTPUT=/absolute/empty/output-directory
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin
python3.13 reproduce.py
```

Do not overlap with heavy builds or other benchmarks. The runner pins one available CPU and locks its output directory. It first runs the exact historical AOT recurrence at 2M/1M and 6M iterations, collecting ten interleaved samples and diagnostic GC runs. It then calls the unchanged maintained performance smoke for all 10 workloads against both baselines. It separates process/loop/build timing and verifies all checksums. Runtime/library inputs are intentionally shared; this isolates compiler differences.

See the validation logs and review.md for performed checks. Full CI status belongs to PR #866 and must be checked at the current head before any merge. Neither #866 nor #864 is authorized for automatic merge by this investigation.

## Local validation completed

- Full compiler and runtime bootstrap fixed points: 668,946 and 18,709 IR lines.
- Ruff, mypy (47 source modules), check-fast, pinned CPython recordings: pass.
- Proof unit tests: 12 pass, including diagnostic/Rejoin restoration and unsafe-proof detection.
- Identity fixtures: 18 native JIT/AOT + 18 allocation-interval-1 program GC checks pass; 18 optimizer-off checks pass.
- Broader dynamic corpus: 112 fixtures, 224 JIT/AOT checks pass.
- Fuzz: 3 seeded programs, 540 total cases including 90 typed/Any parity cases, in JIT/AOT/JIT-GC/AOT-GC, zero mismatches.
- IR guards: both pass; new global-read guard fails on the old compiler's unwanted boxing calls.
- Full current-main oracle: 3,518 inputs, 3,476 identical, 42 intended IR-only differences; no status or diagnostic differences. The prior #864 oracle has the exact same 40 file set, plus the two added fixtures. The strict byte-identity command returns 1 for these expected feature differences. Its preview pipelines print broken-pipe messages when truncating displayed diffs; all 3,518 results completed.
- An unsafe scalar proof makes both global and local walrus publication lose identity in the new fixture; negative-control.log retains the two actual output differences.
- Two independent agent reviews found no blocker; final-review.txt records the final review.

Full hosted CI remains a separate merge gate. Check PR #866's current head; this local evidence does not claim the full CI matrix has passed.

## Test-only CI follow-up

Final PR head `bd219ace454d84724f3c01c01542725f3ace3964` differs from measured production commit `a6e1dafb` only in the comment and expected call list of the existing `dynany_global_constants` IR fixture. The expected calls fall from two to one: `value = MUTABLE` still snapshots identity, while `MUTABLE += 1` consumes only the payload. Independent emitted-IR review confirmed the saved value survives rebinding. Full local `make check-ir` now passes for all 1,758 programs; see check-ir-full.log.

The initial GitHub contracts job caught this stale expectation; its other 20 contract steps passed. Lint, installation, packages and unchanged performance smoke passed on the measured production commit. Final-head CI is a fresh run and remains a merge gate. Performance run: https://github.com/den-run-ai/pystachy/actions/runs/39860174637 — merge `7886d0f1` against `db4b8517`, integer global AOT loop 66.1→37.5 ms (-43.3%), float 70.4→35.4 ms (-49.7%). These shared-runner results are separate from the local raw measurements above.
