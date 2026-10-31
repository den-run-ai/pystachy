# Current-main kernel evidence for PR #996

This completed series contains all **252 timing processes** and **24 instruction-count observations**. Current main is `07b26e02425d023288ed95a9d2a5077be5aeb45e`; final is `ea68529b8a590eb8f3df7200b857e1d16becd7a3`. The archived `da84d382ff83f09e46d4ef104e62e6f64e9c37c1` source is a historical comparison, separately identified throughout. Both current-main and final native compilers have fresh certified fixed points. The closed db14/06e3 checkpoint was not pooled or relabeled.

`measurement.json` contains every original command, stdout/stderr, checksum, sample, round/order, source/tool/build binding and count-collection detail. `analysis.json` adds absolute loop durations, within-round paired ratios/ranges and per-mode provenance. `curated.json` is the frozen measurement harness's own summary. No observations were removed.

## Instruction counts

Each observation covers eight complete kernel calls, including warmup and runtime/GC. Compilation, timers and printing are outside collection. Count input sizes differ from timing sizes and are explicit below. JIT uses client markers. AOT uses the unmodified `f.kernel` symbol where retained; ordinary-call AOT uses the documented marker fallback in all three variants. All original non-entry raw function bodies were verified identical under instrumentation; this does not assert identical downstream JIT machine code.

| Case | Mode | Count n | Main instructions | da84 instructions | Final instructions | Final/main | Final/da84 |
|---|---|---:|---:|---:|---:|---:|---:|
| ordinary_calls | JIT | 1,000,000 | 80,000,160 | 80,000,233 | 80,000,233 | +0.0001% | +0.0000% |
| ordinary_calls | AOT | 1,000,000 | 50,000,217 | 50,000,296 | 50,000,296 | +0.0002% | +0.0000% |
| object_calls | JIT | 1,000 | 18,036,184 | 18,036,392 | 18,036,392 | +0.0012% | +0.0000% |
| object_calls | AOT | 1,000 | 13,432,624 | 13,432,776 | 13,432,776 | +0.0011% | +0.0000% |
| json_calls | JIT | 2,000 | 572,272,054 | 598,872,532 | 591,301,608 | +3.3253% | -1.2642% |
| json_calls | AOT | 2,000 | 526,398,962 | 536,695,570 | 535,597,286 | +1.7474% | -0.2046% |
| json_file_calls | JIT | 2,000 | 570,990,154 | 597,948,531 | 590,351,032 | +3.3908% | -1.2706% |
| json_file_calls | AOT | 2,000 | 526,452,858 | 536,749,438 | 535,725,438 | +1.7613% | -0.1908% |

Ordinary/object final counts exactly match da84 in both modes; current-main count differences are small at the explicit input sizes above. JSON retains measurable overhead versus current main, reduced relative to da84. These are complete kernel observations, not compiler-startup counts.

## Elapsed kernel observations

Each process warms the kernel, then records seven calls; its contribution is their median. Six balanced variant orders provide six within-round final/main ratios. The displayed absolute time is the median of the six process medians. Ranges are observed min/max ratios, **not confidence intervals**. Warmed JSON has four additional untimed kernel calls. All timing phases ran in an explicitly coordinated quiet window with other task agents paused.

| Case | Mode | n | Main loop ms | da84 loop ms | Final loop ms | Paired final/main | Observed paired range | Slower pairs |
|---|---|---:|---:|---:|---:|---:|---|---:|
| ordinary_calls | JIT | 10,000,000 | 17.4555 | 17.8999 | 17.1333 | -0.14% | -11.06% to +12.67% | 3/6 |
| ordinary_calls | AOT | 10,000,000 | 13.3669 | 14.4086 | 13.9386 | +1.39% | -0.42% to +19.27% | 4/6 |
| object_calls | JIT | 100,000 | 20.8926 | 20.6778 | 19.4156 | -4.00% | -13.32% to +13.46% | 2/6 |
| object_calls | AOT | 100,000 | 14.4480 | 14.8805 | 14.5958 | -5.35% | -9.64% to +10.61% | 2/6 |
| object_long | JIT | 1,000,000 | 207.7939 | 209.0487 | 199.8151 | -0.45% | -16.20% to +67.73% | 3/6 |
| object_long | AOT | 1,000,000 | 162.4282 | 157.3226 | 164.2255 | -0.51% | -25.07% to +21.53% | 2/6 |
| json_calls | JIT | 2,000 | 8.8662 | 9.0086 | 8.4459 | +2.98% | -19.14% to +17.03% | 4/6 |
| json_calls | AOT | 2,000 | 7.9499 | 7.5237 | 7.4817 | -3.80% | -22.23% to +9.63% | 3/6 |
| json_warmed_short | JIT | 2,000 | 8.4081 | 8.2392 | 8.2068 | -2.10% | -16.56% to +15.57% | 3/6 |
| json_warmed_short | AOT | 2,000 | 7.0057 | 7.5713 | 7.3722 | +4.90% | -6.64% to +15.96% | 4/6 |
| json_warmed_long | JIT | 20,000 | 70.1898 | 76.4445 | 71.9924 | +3.13% | -17.27% to +19.88% | 5/6 |
| json_warmed_long | AOT | 20,000 | 68.0854 | 70.2276 | 69.5044 | +0.93% | -9.90% to +26.32% | 4/6 |
| json_file_calls | JIT | 20,000 | 73.7708 | 79.8317 | 76.0981 | +3.46% | -0.44% to +4.69% | 5/6 |
| json_file_calls | AOT | 20,000 | 64.7777 | 66.5903 | 68.9943 | +6.54% | -2.50% to +23.10% | 5/6 |

Short loops last roughly 7–21 ms, and many paired ranges cross zero widely. Longer object and AOT cases also vary substantially. In particular, the original short JSON JIT ratio of process medians is negative while its within-round median ratio is positive. Neither isolated statistic establishes a precise general speedup. The longer JSON JIT observations are consistent with a few-percent cost; AOT timing estimates remain less stable than the instruction counts. Retain the full distribution when reviewing acceptance; no outlier filtering, workload pooling, or significance claim is applied.

## Reproduction and artifact scope

See [reproduction-ea685-audit.txt](reproduction-ea685-audit.txt) for the exact restore map, external archive dependencies, fresh-output commands, and startup instruction errata. The note supplements this review selection without changing any report or measurement controller.

Keep `measure_current.py`, `count_support.py` and `replay_support.py` together. Their exact hashes are in the raw phase records. The scripts use the recorded recovery workspace/toolchain paths and expect the original `final-perf/` placement; restore that layout from the archive before rerunning. This publication directory is a review selection, not a relocated execution environment. Run the three phases sequentially in a new output directory with the final commit argument and certified fresh bootstrap record. The original command records, environment allowlist, private cache locations, CPU pin and tool hashes are in `measurement.json`.

The source probes are included under `probes/`. All generated LLVM, binaries, Callgrind files, caches and count-attempt JSON remain in the complete `final-perf/results-ea685` archive; their hashes and original paths remain in the report. This selection retains the complete raw observation report and companion scripts while leaving those larger artifacts in the archive. `curate_current.py` is the separate read-only derivation/publication controller; it does not run a compiler or benchmark.
