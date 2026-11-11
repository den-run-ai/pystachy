# Bounded match: implementation and qualification

**The implementation and focused local qualification are complete. PR [#1272](https://github.com/den-run-ai/pystachy/pull/1272) remains draft because required integration CI has not run.** At the immutable **2026-11-11 20:41:49 UTC** snapshot, all three workflows for the integrated head were queued with zero jobs. The preceding attempt encountered report-upload failures and skipped later tests. These are incomplete gates, not successful verification with missing attachments. See the [CI snapshot](ci/final-snapshot/summary.md).

The measurements also disprove a blanket performance-parity claim: capture-heavy JIT patterns still take about **1.58–2.11 times** as long as equivalent handwritten conditions in these workloads. AOT results depend on the workload. This report preserves those limitations alongside the passing checks.

## Source and measurement identity

| Role | Commit or tree |
| --- | --- |
| Published implementation, including current main | `601807e3686fa83a362cceb0d962d8e6332fbc34` |
| Integration tree | `b28d80a94d0ac11e18cd6da7c6586e704a757bfd` |
| Main merged into the implementation | `a339ab3748a59d6e4da899f0f3f2d5965b95e5ba` |
| Final compiler source used for local builds and measurements | `dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6` |
| Reference compiler source for IR comparison | `b40ee875bf72b86804c4f5a300066f4f7c3eb20b` |
| Earlier standalone implementation, retained as historical evidence | `620c35f42d8c35d7a27341bbe4ba259b043b959d` |

The integration is a true merge, with ordered parents `dec4d9f1` and `a339ab37`. Main added the Lean verification harness and LLVM download recovery changes while the measurements ran. The [main-update proof](irsame/match-main-update-equivalence.md) and [integration proof](irsame/match-integration-equivalence.md) establish identical consumed sources: 161 recorded measurement hashes, 146 additional inputs, eight complete directory trees, and all 4,438 IR input paths/modes/blobs. The bootstrap recipe and match targets are unchanged. The earlier main update proof also checks 303 individual inputs.

The original reports retain their original commit labels. Long pyperf measurements used the retained `dec4d9f1` AOT executable while the checkout was the equivalent local merge `62b93c37`; that local merge and published `601807e3` have the same tree. The [measurement sidecar](final-dec4d9f/match-final-measurement-checkout.json) records the distinction. The identity proof carries the local compiler/runtime evidence forward; it does not replace the new integration CI gates.

| Retained executable | SHA-256 |
| --- | --- |
| Native compiler | `39177cf908ec1b681ea133db3d830e5c9c12dff6ddbb7de46189166a913e74dc` |
| AOT dispatch benchmark | `da6dcda2fa6ed927bed503f5e7ca6e079d15bd474fcf5db57bae65806246bc46` |

Local environment: pinned CPython **3.13.16**, LLVM **18.1.3**, pyperf **2.11.0**, Linux x86-64/glibc 2.41, Intel Xeon Platinum 8573C. Timings were pinned to allowed CPU 0. Native program caching was disabled; the controller used a private warmed runtime cache. Full flags, tool hashes, source hashes, load observations and raw timings remain in the JSON reports. No other owned heavy build or test ran during the final timing sessions; the host was shared and was not a controlled bare-metal performance machine.

## What was implemented

The original #1252 draft depended on seven unrelated syntax PRs. This standalone implementation brings its bounded match work onto current main and integrates it with the compiler build, tests, examples, documentation and existing benchmark CI group.

Supported forms are literals/value patterns, captures, wildcards, `as`, OR alternatives, guards, fixed tuples and plain fields of statically known dataclasses. Dynamic `Any` supports literal/capture matching within the documented type contract. List/general-sequence subjects, starred patterns, mappings, complex literal patterns, arbitrary classes, class hierarchies, attribute hooks and custom `__match_args__` remain outside this scope. Both bracketed sequence-pattern spellings can match a fixed tuple. Dynamic/union tuple or class subjects require appropriate narrowing. Existing value-equality and type-join restrictions still apply.

The lowering evaluates the subject once and uses ordinary typed branches and assignments. It stages captures until the complete pattern succeeds, exposes captures before the guard, retains those captures after a false guard, and short-circuits alternatives in order. Dataclass fields are loaded before subpattern comparison callbacks, including callbacks that mutate a later field. Regression cases exercise these rules with exceptions, closures/nonlocals, aliasing, private names, generator suspension and close/finally cleanup.

Two concrete defects were reproduced and fixed:

- A promoting `int+` scalar now fails a sequence pattern normally instead of being rejected by compilation.
- Huge canonical hexadecimal integer literals containing `e` remain integers instead of being mistaken for floating-point literals and crashing compilation.

Generated conjunctions are right-associated while preserving operand order, OR subtrees and the user guard. This lets existing flow analysis eliminate unnecessary capture bookkeeping. In the inspected tuple matcher, raw IR fell from 224 to 180 lines and definedness slots from six to two. For the dataclass matcher, raw IR fell from 370 to 250 lines and slots from twelve to two. The tuple matcher then fully inlined in the existing JIT cleanup pipeline; the dataclass matcher shrank from 281 to 116 optimized lines with one remaining call site.

The [source review](match_final_review.md) and [historical performance investigation](match-performance-interpretation.md) explain the implementation and rejected approaches. They predate final qualification; this README and the completed reports below supersede their pending-status text. A proposed global constant fold for capture assignment was rejected because it miscompiled a guard after rebinding a union-typed variable. A further local code-generation experiment was omitted because it produced no consistent speed gain. Their probes and patches are preserved under [experiments](experiments); neither is part of the implementation.

The [command-dispatch example](../../../../examples/match_dispatch/README.md) provides an end-to-end consumer, with valid and invalid commands, tuple parsing and dataclass dispatch. Its eleven shared pytest cases run in both JIT and AOT. The maintained [benchmark](../../README.md) supplies independent checksum/count validation and mixed/skewed dispatch distributions. The newly accepted scalar kernel match in `statistics.kde` exposes its next existing function-storage restriction; this change does not claim KDE support.

## Completed local qualification

These final compiler tests are recorded at `dec4d9f1`, with the source-equivalence proof above linking them to the integrated implementation.

| Check | Result | Evidence |
| --- | --- | --- |
| Compiler bootstrap fixed point | Stages 1, 2 and 3 identical: 910,731 IR lines | [Bootstrap](final-dec4d9f/match-final-bootstrap.json), [log](final-dec4d9f/bootstrap.log) |
| Runtime bootstrap fixed point | Stages 1, 2 and 3 identical: 21,214 IR lines | Same bootstrap report |
| Focused native compiler, JIT/AOT | 45/45 checks | [Qualification](final-dec4d9f/qualification.json) |
| Focused hosted compiler, JIT/AOT | 45/45 checks | Same qualification report |
| Focused native execution, program GC interval 1 | 45/45 checks | Same qualification report |
| Compiler GC interval 1,000 plus program GC interval 1 | 6/6 checks on three selected programs | Same qualification report |
| Optimizer disabled | 28/28 positive-program executions | Same qualification report |
| Promoting-int mode | 28/28 positive-program executions | [Mode report](final-dec4d9f/python_int.json) |
| Dynamic-Any mode | 28/28 executions; zero expected failures or AOT deferrals | [Mode report](final-dec4d9f/dynany.json) |
| Combined mode/GC matrix | 112/112 executions | [Matrix](final-dec4d9f/match-mode-matrix.json) |
| Command-dispatch shared pytest suite | 11 JIT plus 11 AOT cases passed | [Example report](final-dec4d9f/pytest-example.json) |
| Separate compiler GC interval 1 probe | 22,395 collections; IR identical to unstressed compilation | [GC report](final-dec4d9f/match-final-compiler-gc.json) |
| Integrated-tree `make check-fast` | Passed with 806 of 915 discovered unit tests executed and 109 skipped, largely optional Lean-dependent checks | [Integration log](integration/check-fast.log) |

The focused set has **14 positive programs and 17 rejection fixtures**. Positives execute in JIT and AOT; rejections are compile checks, giving 45 checks per focused pass. The combined matrix is four configurations × fourteen programs × two execution modes: promoting-int plus GC stress, dynamic-Any plus GC stress, both modes without stress, and both modes with stress. Across the final qualification runner this is 337 checks plus the 22 example cases, with deliberate repetition across configurations, not 359 distinct source programs.

Earlier evidence is preserved under [baseline-620c35f](baseline-620c35f) and is explicitly historical: 25 adapted pyperformance workloads checked against CPython in JIT/AOT, 78 shared pyperformance pytest checks, seven extended workload smokes, six benchmark-controller negative-control unit tests, and 2,299 recording checks. A separate source audit ran eleven additional probes in JIT/AOT with normal and stressed program GC, giving 44 exact output/status comparisons. These earlier runs are not relabeled final-head executions. Final CI Lint at `dec4d9f1` checked the expanded 2,300 recordings before the current main integration.

## Full IR and diagnostic comparison

The completed comparison covered **4,438 unique inputs: 4,407 identical and 31 differing**. Every difference was manually classified, and the inventory exactly matches the completed per-case timing rows. See the [classification](irsame/match-irsame-classification.md), [machine report](irsame/match-irsame-report.json) and [full difference log](irsame/match-irsame-full.log).

| Difference | Count |
| --- | ---: |
| Newly accepted match programs: fourteen regressions, benchmark and example | 16 |
| More specific bounded-match rejection diagnostics | 13 |
| Imported decorated special method reaching an existing rejection | 1 |
| KDE reaching its next existing function-storage restriction | 1 |
| Previously accepted inputs newly rejected | **0** |
| Differing IR for an input accepted by both compilers | **0** |

The repository's normal IR/diagnostic/status oracle was used, with only its displayed-difference limit raised to retain all differences. IR and exit status are compared exactly. Existing narrow diagnostic source-location normalization is unchanged. A shared home was permitted only after proving all 105 consumed library/runtime inputs identical. The reference retains its actual `b40ee875` provenance. Comparison exit status 1 is expected for the 31 reviewed feature differences; the comparison itself completed.

The separate syntax sweep agreed with CPython on 52 of 53 fixtures. The one discrepancy, `syntax_match_duplicate_key_over_limit.py`, predates this feature: CPython reaches its decimal-conversion limit while Pystachy prints the duplicate key in hexadecimal. Its unchanged source/history and identical base/candidate result are retained in the [baseline-discrepancy proof](irsame/match-syntax-baseline.json). This is not reported as full syntax parity.

## Performance results

The final controller covers six workload cells in JIT and AOT, with **seven alternating match/if pairs per cell and mode**: 84 pairs, 168 timed commands. Each command performs 10,000 × 4,096 = **40,960,000 dispatches**. The kernel timer excludes construction, validation, warm-up, compilation and process startup. Every controller output is validated against the CPython oracle.

Real pyperf then measures the retained AOT executable with **three workers and five measured values per worker per variant/cell**: 36 worker runs and 180 measured values, excluding warm-ups. Each invocation performs 100,000 × 4,096 = **409,600,000 dispatches**. Worker blocks alternate variant order. Twelve long-run preflights validate checksums/counts; `pyperf command` itself discards child output and checks exit status. These whole-command measurements include setup, validation, warm-up and startup, so they are distinct from kernel timings.

All ratios below are **handwritten-if time / match time**. Values above 1 favor match. Controller values are medians of paired ratios; pyperf values are ratios of separate means or medians.

| Workload | JIT kernel ratio | AOT kernel ratio | AOT pyperf mean ratio | AOT pyperf median ratio |
| --- | ---: | ---: | ---: | ---: |
| Literal, mixed | 1.119 | 1.340 | 1.333 | 1.349 |
| Literal, 99:1 skew | 1.109 | 1.899 | 1.830 | 1.870 |
| Tuple, mixed | 0.474 | 1.077 | 1.061 | 1.064 |
| Tuple, 99:1 skew | 0.632 | 1.060 | 1.169 | 1.173 |
| Dataclass, mixed | 0.536 | 0.886 | 0.908 | 0.900 |
| Dataclass, 99:1 skew | 0.496 | 1.106 | 0.982 | 1.107 |

The capture-heavy JIT penalty remains substantial: about **1.58–2.11×** versus handwritten conditions. Right association reduced match-kernel time by roughly **1.8–2.1×** in the short before/after pilot, but did not establish parity. Both pilot variants execute native JIT kernels; the baseline compiler is native and the trial compiler is CPython-hosted, so their whole-process times are not comparable. The final separately measured native results are consistent with a substantial reduction; cross-session comparisons remain descriptive.

For these AOT fixtures, literal dispatch is faster and tuple dispatch is near or ahead of handwritten conditions. Mixed dataclass matching takes about **10% longer** in pyperf and about **13% longer** in the paired kernel comparison. Skewed dataclass results are **inconclusive**: the pyperf match series has 18.79% coefficient of variation, and the mean/median comparisons fall on opposite sides of equality. The pyperf comparison does not report that cell as significant. Literal/skewed match also has 11.36% CV. These shared-host observations do not justify a universal speedup or a single aggregate win.

The initial tuple/mixed handwritten-if pyperf series was especially noisy (26.83% CV); its apparent 1.221 mean ratio becomes 1.060 by medians. That historical result remains intact rather than being selected as the headline. Ratios, observed spans, sample SD, CV, raw values, tool identities and all warnings are retained in [final analysis](final-dec4d9f/match-final-analysis.md), its [JSON](final-dec4d9f/match-final-analysis.json), and the [pyperf check output](final-dec4d9f/match-final-pyperf-check.log).

Performance was measured for the default typed configuration. Promoting-int, dynamic-Any and GC combinations were correctness-qualified but were not given a separate timing campaign. These original dispatch microbenchmarks are not upstream pyperformance scores. The typed dataclass baseline uses direct fields under the same static contract. The command example establishes useful execution, not an independently measured application speedup.

## CI state and remaining gate

At the [immutable snapshot](ci/final-snapshot/summary.md), current-head CI [43096685652](https://github.com/den-run-ai/pystachy/actions/runs/43096685652), Lint [43096685712](https://github.com/den-run-ai/pystachy/actions/runs/43096685712) and Performance [43096685661](https://github.com/den-run-ai/pystachy/actions/runs/43096685661) were queued with zero jobs. The PR had no submitted reviews, review threads or discussion entries. The Verification aggregate had not run.

A [fresh read at 20:50:31 UTC](ci/final-monitor-read.json) confirmed the same current head, base, reviews and three queued workflows with zero jobs. The superseded run had additionally created a queued aggregate Verification job; that job had not run either. Monitoring then stopped, leaving all remote runs intact.

On preceding head `dec4d9f1`, both architecture bootstrap jobs, ordinary native JIT corpus halves, the separate Lint workflow and Performance workflow passed their observed tests. The Performance smoke covered eleven workloads and 49 metrics (changes from -3.6% to +2.3%). But Linux/macOS distribution and JIT jobs then failed report uploads. Later installation/package, variant and cache stages were skipped, while nine verification groups remained queued. The observed upload/queue failures do not establish an official service outage or rule out failures in tests that never ran.

Full current-head verification, including the main integration's new Lean checks, remains required. No gates, timeouts or test expectations were weakened to obtain a pass. The source implementation is ready for that verification and review; this evidence does not mark the PR merge-ready.

## Reproduction and evidence layout

Use the repository's pinned Python and LLVM setup and a fresh checkout of the implementation commit. The maintained controller commands are:

```sh
make
python3 -m unittest discover -s bench/match_dispatch -p test_bench.py
python3 bench/match_dispatch/bench.py --smoke --json build/match-smoke.json
python3 bench/match_dispatch/bench.py --modes jit aot --samples 7 \
  --loops 10000 --size 4096 --cpu 0 \
  --keep build/match-final-artifacts \
  --json build/match-final-dispatch-measured.json
```

Select an allowed CPU on a different host. `--keep` and the output paths should be new. Install pyperf 2.11.0, then run the saved [pyperf runner](reproduce/run_match_pyperf.py) with the implementation checkout and prefix:

```sh
python3 /path/to/evidence/reproduce/run_match_pyperf.py /path/to/checkout match-final
python3 -m pyperf check /path/to/checkout/build/match-final-pyperf-if.json
python3 -m pyperf check /path/to/checkout/build/match-final-pyperf-match.json
python3 /path/to/evidence/reproduce/analyze_match_results.py \
  --prefix /path/to/checkout/build/match-final \
  --output-prefix /path/to/checkout/build/match-final-analysis
```

The saved [qualification runner](reproduce/qualify_match.py) calls the repository's own harnesses, records its exact commands and fails on mismatches. Its original layout expects `check_match_matrix.py` beside the checkout, so copy that saved script to the checkout's parent before running `python3 /path/to/evidence/reproduce/qualify_match.py /path/to/checkout`. Do not reuse a stale native compiler across changed source inputs.

To repeat the recorded IR comparison, use a fresh checkout of `dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6`, build it with `make`, then run:

```sh
make ref REF=b40ee875bf72b86804c4f5a300066f4f7c3eb20b
python3 /path/to/evidence/reproduce/run_match_irsame.py /path/to/checkout \
  --candidate dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6 \
  --llvm /path/to/llvm-18/bin --output-dir /path/to/new-irsame-results
```

The [IR runner](reproduce/run_match_irsame.py) requires HEAD to equal the explicit candidate, verifies reference/source/input identity and uses the existing oracle. Its historical default candidate is the earlier `620c35f`, so the explicit argument matters. Exit 1 means a completed comparison with differences that still require review; it is not an automatic pass. For a new integrated-tree run, build and pass `601807e3` explicitly instead, preserving a new output directory and the separate provenance.

This research branch contains the integrated source plus evidence, and is not intended to merge into main. `final-dec4d9f/` holds completed local qualification and measurements; `irsame/` holds the full comparison and integration proofs; `ci/` holds timestamped GitHub evidence; `baseline-620c35f/` and `experiments/` preserve earlier results and rejected ideas. `inventory.json` records SHA-256 and byte length for every evidence file except itself. Raw source/measurement records retain their original labels and bytes. Only this report advances the final status.
