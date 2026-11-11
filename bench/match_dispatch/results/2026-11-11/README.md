# Bounded match qualification — November 11, 2026

This research branch preserves evidence for [PR #1272](https://github.com/den-run-ai/pystachy/pull/1272). The final implementation is `dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6`, tree `0e4c2682f25b0555cac052fa36830ed567c3fa1e`, based on main `b40ee875bf72b86804c4f5a300066f4f7c3eb20b`.

**Checkpoint: final corpus IR comparison, final timings and aggregate CI are still pending.** This is evidence preservation, not a merge-ready claim.

The final source passed compiler/runtime three-stage fixed points (910,731 and 21,214 IR lines), 45 focused checks through each native and hosted compiler, 45 program-GC checks, 6 combined compiler/program-GC checks, 28 optimizer-off checks, 28 promoting-int checks, 28 dynamic-Any checks, 112 cross-mode checks, and 22 example pytest checks. Collecting during every compiler allocation performed 22,395 collections and produced byte-identical IR for the guard/capture regression.

The `baseline-620c35f` directory contains the initial standalone implementation's measurements and qualification. It is not final-head evidence. The initial pyperf tuple/if mixed series was noisy (26.8% CV); retain its means and medians, and do not infer a precise speedup from its mean. The accepted conjunction change reduced capture-heavy JIT time by roughly half in the short diagnostic pilot; final measurements remain to be recorded.

`experiments` retains both the accepted conjunction pilot and the rejected extra code-generation experiment. The global constant-folding proposal was rejected after an independent review demonstrated stale narrowing in a capture guard. Neither rejected proposal is in the implementation.

`reproduce` contains the local diagnostic scripts as executed. The maintained benchmark controller and workloads live in `bench/match_dispatch` in the implementation commit. Raw reports preserve commands, hashes and configuration; local paths identify the original run and need adapting for another checkout.
