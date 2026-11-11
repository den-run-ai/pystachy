# Match performance: interpretation before final timings

The initial implementation was tested and measured in CPython, native JIT, and AOT at commit `620c35f42d8c35d7a27341bbe4ba259b043b959d`. Those results exposed a substantial JIT penalty for tuple and dataclass patterns. The accepted follow-up changes only how the compiler groups generated pattern conjunctions. A short pilot supports the improvement, but the final native rebuild and its new measurements must establish the result for the completed implementation.

## Keep the evidence sets distinct

| Evidence | Code measured | Work per process | Samples | What it establishes |
| --- | --- | --- | --- | --- |
| Initial full controller | `620c35f4` | 2,000 × 4,096 = 8,192,000 dispatches | Seven alternating match/if pairs per cell, six cells, CPython/JIT/AOT | Correct outputs and initial kernel/process timing distributions |
| Initial real pyperf suites | AOT executable from that same controller | 100,000 × 4,096 = 409,600,000 dispatches | Three worker runs × five measured values per variant/cell; 36 worker runs and 180 values total | Longer whole-command AOT timing distributions; these precede the optimization |
| Right-association pilot | Baseline native compiler versus trial hosted compiler, both executing native JIT kernels | 8,192,000 dispatches | Three paired trials for four tuple/dataclass cells | A diagnostic before/after signal and code-generation explanation; process startup is not comparable |
| Final native controller and pyperf | Newly built final source; prefix `match-final` | Read actual settings from the final reports | Read actual sample/worker counts from the final reports | Final JIT/AOT qualification; these results were pending when this note was prepared |

The initial full controller has 252 measured process observations, in addition to its correctness oracles and warm-ups. Final controller runs may select only JIT and AOT while still executing CPython as the checksum oracle. Such a run does not add a new distribution of timed CPython samples.

All ratios below are **handwritten-if time / match time**. Values above 1 favor `match`. The controller reports the median of the pairwise ratios; this is not generally the ratio of the two variant medians. Its span is the smallest through largest observed paired ratio, not a confidence interval.

## Initial results, before the accepted optimization

| Workload | CPython kernel ratio | JIT kernel ratio | AOT kernel ratio | AOT pyperf ratio of means | AOT pyperf ratio of medians |
| --- | --- | --- | --- | --- | --- |
| Literal, mixed | 0.922 | 1.226 | 1.106 | 1.066 | 1.061 |
| Literal, skewed | 0.890 | 1.350 | 0.977 | 1.040 | 1.028 |
| Tuple, mixed | 0.527 | 0.254 | 1.007 | 1.221 | 1.060 |
| Tuple, skewed | 0.630 | 0.321 | 1.339 | 1.276 | 1.312 |
| Dataclass, mixed | 0.268 | 0.224 | 1.307 | 1.191 | 1.199 |
| Dataclass, skewed | 0.292 | 0.448 | 0.923 | 0.898 | 0.895 |

These are workload observations, not a universal ranking of `match` and handwritten conditions. The dispatch lists have mixed and skewed branches, and the tuple/dataclass cases include captures, OR patterns and a guard. Initial native kernel medians were only about 8–72 ms, so pair spans and dispersion belong beside their point estimates.

The initial JIT tuple/mixed and dataclass/mixed ratios correspond to roughly 3.9× and 4.5× more time for `match`. Inspection of the exact JIT cleanup pipeline found that larger generated pattern functions retained redundant staging/definedness control flow and failed to inline, while the handwritten counterparts inlined. The module was below the existing JIT inliner line cutoff. Full AOT optimization largely eliminated this overhead. This diagnosis does not rely on tuple copying, mandatory boxing, a changed global optimization setting, or a removed workload loop.

### The initial tuple/mixed pyperf mean is unstable

The initial handwritten-if series has mean **0.811671 s**, median **0.694797 s**, sample SD **0.217749 s**, and CV **26.827%**. Its observed range is **0.646365–1.322249 s**. Match has mean **0.664987 s** and median **0.655314 s**. Thus a 1.221 ratio of means becomes only 1.060 when comparing medians. A precise 22% speed claim would overstate this evidence. Retain the complete distribution and report the instability.

Other initial AOT pyperf cells were less dispersed, with CVs about 2.5–5.6%. The dataclass/skewed mean ratio of 0.898 means that `match` took about 11% more whole-command time in that measured configuration. Differences near equality should not be declared wins merely because their point estimate is above 1.

## Accepted optimization and short pilot

Generated conjunctions are now right-associated without reordering operands, traversing user guard internals, or changing OR grouping. This lets existing flow analysis see staged assignments before dependent reads. Ordinary capture definedness checks remain in place where needed.

Tuple raw IR shrank from 224 to 180 lines, with six definedness slots reduced to two; dataclass raw IR shrank from 370 to 250 lines, with twelve slots reduced to two. In the exact JIT cleanup pipeline the tuple matcher became fully inlined. The dataclass matcher shrank from 281 to 116 optimized lines, leaving one call site instead of three.

The three-pair pilot measured baseline/trial match-kernel ratios of **1.80×, 1.86×, 2.11× and 2.00×** for tuple/mixed, tuple/skewed, dataclass/mixed and dataclass/skewed respectively. Every pilot result passed checksum/count validation. Its trial if/match ratios were **0.471, 0.673, 0.504 and 0.513**, so this pilot still showed approximately 1.5–2.1× overhead versus handwritten conditions. Final native measurements must replace these pilot estimates in the final performance claim.

An additional safe local code-generation experiment passed correctness checks but showed no consistent timing improvement and was omitted. A proposed global constant-folding rule for capture assignment was rejected after a stale-type-narrowing miscompile was demonstrated. Neither experiment is part of the accepted patch.

## Reading final pyperf and provenance

`pyperf command` measures the entire AOT subprocess, including input construction, validation, warm-up and startup. It discards child stdout/stderr and checks exit status. Checksum correctness therefore comes from the complete controller and the explicit long-run preflight recorded in the manifest. A successful timing worker does not independently verify its hidden output.

Pyperf's five values within each worker run are clustered observations. Report **three workers and fifteen measured values** per variant/cell, rather than implying fifteen independent workers. The analysis script excludes warm-ups and calibration-only runs, uses sample SD with denominator n−1, and reports both mean and median. Its CV >10% flag is a descriptive diagnostic, not pyperf's significance test. It produces no confidence intervals or significance claims.

Use each report's recorded compiler executable SHA-256, AOT executable SHA-256, source-hash manifest, tool versions/hashes, CPU affinity and input-report hashes. The analyzer does not substitute the current checkout or executable for the one recorded during measurement. Local and published commit hashes can differ when a commit is recreated; source/tree equivalence must be established separately. A before/after comparison across the baseline and final sessions is descriptive even when normalized by dispatch count.

## Analyze completed final reports

The script uses the Python standard library, executes no compiler or benchmark, and writes only the explicitly selected analysis outputs. It rejects incomplete reports, missing workload cells, wrong checksums/counts, unexpected controller stderr, duplicate/missing pyperf workers, and controller/binary/revision mismatches between the controller and pyperf manifest.

```bash
python3 /workspace/scratch/0bc6e8bc1edf/analyze_match_results.py \
  --prefix /workspace/scratch/0bc6e8bc1edf/match-main/build/match-final \
  --baseline-prefix /workspace/scratch/0bc6e8bc1edf/match-evidence-baseline-620c35f/match \
  --pilot /workspace/scratch/0bc6e8bc1edf/match-right-association-pilot.json \
  --output-prefix /workspace/scratch/0bc6e8bc1edf/match-main/build/match-final-analysis
```

Inputs are `PREFIX-dispatch-measured.json`, `PREFIX-pyperf-if.json`, `PREFIX-pyperf-match.json`, and `PREFIX-pyperf-manifest.json`. The command writes JSON containing exact statistics and recorded identities, plus Markdown tables. Omitting `--output-prefix` prints Markdown to stdout; `--format json` selects JSON instead.

Baseline source evidence: [controller](sandbox:/workspace/scratch/0bc6e8bc1edf/match-evidence-baseline-620c35f/match-dispatch-measured.json), [if pyperf suite](sandbox:/workspace/scratch/0bc6e8bc1edf/match-evidence-baseline-620c35f/match-pyperf-if.json), [match pyperf suite](sandbox:/workspace/scratch/0bc6e8bc1edf/match-evidence-baseline-620c35f/match-pyperf-match.json), [pyperf manifest](sandbox:/workspace/scratch/0bc6e8bc1edf/match-evidence-baseline-620c35f/match-pyperf-manifest.json), and [right-association pilot](sandbox:/workspace/scratch/0bc6e8bc1edf/match-right-association-pilot.json). The expanded baseline tables are in [match-baseline-analysis.md](sandbox:/workspace/scratch/0bc6e8bc1edf/match-baseline-analysis.md).
