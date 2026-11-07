# Pystachy v0.3.0-alpha.2 qualification

Research evidence for [PR #1140](https://github.com/den-run-ai/pystachy/pull/1140).
This branch is an evidence record and must not be merged into `main`.
It records completed local qualification and actual PR CI. It does not assert
completion of subsequent main release gates, GitHub/Docker publication or PyPI upload.

The [7 November 2026 main snapshot](main-gates-snapshot.json) records Installation
(7/7), Lint, Packages, performance smoke and advisory Coverage (20/20) passing on
`26f61d57`. Full CI and Variants were still running; alpha.2 publication was pending.

| Source | Commit | Tree |
|---|---|---|
| Alpha.1 baseline | `2556085e7165a34465e6cede5d93c895e416cad8` | `603280df000457e48724644e51c51e3b52379811` |
| Audited alpha.2 | `eeca23bbc8c2aa6c37ce904e3d2bf79a2a94e789` | `31c775bcf5eb3212deabeaad8777c8df25ec6c6f` |
| Final PR head | `c4f85144fb5652ef2e5998d36163421fa8fd4557` | `e8ebc8a8f84b150f4047f85b830297f2d701c5a3` |
| Tested PR merge | `49e1f0e9a0d86cfc97ab9a386bbe4ab1110d80fc` | `e8ebc8a8f84b150f4047f85b830297f2d701c5a3` |
| Merged main | `26f61d57ea857b3210ce7501ff6eb3743b39f91c` | `e8ebc8a8f84b150f4047f85b830297f2d701c5a3` |

[Source identity](source-identity.json) records the complete audit-to-main delta.
Compiler, runtime, libraries and corpus inputs are unchanged; the delta consists
of verification scheduling, miniui verification, tests and documentation.
The tested-merge tree equality comes from the captured CI identity review; that
synthetic merge object was not available in the packaging checkout.

## Complete local IR/acceptance audit

Pinned CPython 3.13.16 and LLVM 18.1.3; two audit workers, each compiler process
limited to 180 seconds, with `PYSTACHY_IRCHECK=1`. The baseline native compiler
came from verified main CI run 42369525994, solely as a diagnostic baseline;
it was not reused as a cross-run CI bootstrap. Its SHA-256 is
`0c34862a3f606184d14f8c9e06650e5c7e3493b73b9543530f01f7fdd3f5963e`.
The candidate compiler SHA-256 is
`a825851e234039fbe6c97aa0ba460b9e5484c7f7ba53e4ec3ae61f5b5b1f0756`.
Candidate compiler/runtime fixed points were 875,344/19,907 IR lines.

All **4,341 cases** completed: **3,753 raw-identical**, **588 differences**,
**60 acceptance gains**, **zero new rejections**, timeouts or abnormal exits.
All **511 changed accepted modules** assembled with LLVM 18.1.3.

| Exhaustive difference category | Cases |
|---|---:|
| Proven unchanged-library checkout strings | 216 |
| Acceptance gains: 52 expected, 8 documented deviations | 60 |
| Rejection diagnostics: 71 checkout locations, 6 expected changes | 77 |
| Reviewed field-error-table correspondence | 127 |
| Substantive accepted IR changes | 108 |

The 108 comprise 58 metatype guards, 13 JSON-repair class-identity changes,
17 mixed field/class changes, five callback cases, four `ascii` exception-edge
changes, two compiler-home constants and nine individual type-identity cases.
The separate 121-case accepted-IR review includes 13 path/table cases already
counted among the 127; do not add them twice. No unexplained cases remain.
The field-table structural helper alone cannot establish fallback indexing or
receiver-tag validity; its [independent source/lifecycle review](audit/field-table-review.json)
and eight unit/44 native normal-and-GC comparisons supply that evidence.
The original, modified `dynany_graph` fixture was also checked independently;
[its preserved result](audit/legacy-graph.json) records both acceptance and four native comparisons.

The compressed [complete classification](audit/complete-audit-review.json.gz)
retains all 4,341 rows. [Inputs](audit/inputs.json.gz),
[per-case command/status/hash records](audit/results.jsonl.gz),
[LLVM results](audit/llvm-verification.json.gz) and supporting diagnostic,
field-table and accepted-IR reviews are retained under `audit/`.

## Actual PR CI and corrected validation claims

[CI run 42383313528](https://github.com/den-run-ai/pystachy/actions/runs/42383313528)
passed all 16 jobs. [Qualification](pr-ci/qualification.json) and the
[complete checks snapshot](pr-ci/final-checks.json) record 4,241 cases in each
native mode, 8,482 exact case/mode pairs, both architecture bootstraps and the
seven sampled variants. Full main matrices remain a separate release gate.
The slowest AOT job took 800 seconds, within the unchanged 15-minute limit.
Runtime-cache passed 134 checks; GC self-compilation passed in 392 seconds with
5,149 collections, interval 5000 and the unchanged 600-second guard.

Earlier [GC CI 42369606227](https://github.com/den-run-ai/pystachy/actions/runs/42369606227)
failed its guard; [native CI 42379906054](https://github.com/den-run-ai/pystachy/actions/runs/42379906054)
exceeded the job limit after completing its case checks. Those failures are not
relabelled as passes. Compiler retry removal, cache/GC scheduling and distinct
JIT/AOT groups supplied the fixes; no coverage or time limit was relaxed.
[Mode-contract controls](pr-ci/mode-contract-review.json) reject missing/duplicate
cases, wrong modes/counts and compiler/source/toolchain/bootstrap identity drift.

[Lint 42383313555](https://github.com/den-run-ai/pystachy/actions/runs/42383313555)
passed address/undefined sanitizer probes with leak detection enabled, including
the expected missing-release negative-control failure. This closes the recorded
**local** LeakSanitizer environment limitation; local success with leak detection
disabled was never equivalent evidence. The corrected miniui test used the direct
AOT runtime setting and observed **1,187 collections**. The earlier driver-only
setting did not prove AOT stress. [Local optional qualification](optional/local-qualification.json)
retains both limitations and corrections, plus DLPack and microGPT outcomes.
The [review snapshot](pr-ci/external-review.json) records completed automated code
review with no findings; it records no security-review result or submitted approval.

## Reproduce and inspect

The original top-level shell command was not separately archived. The following
replays the retained runner with its recorded parameters; actual per-case command
arrays and compiler hashes are in `audit/results.jsonl.gz` and `audit/inputs.json.gz`.
Prepare clean `alpha1-audit` and `alpha2-audit` checkouts at the commits above,
bootstrap with pinned tools, and record the resulting compiler identities. A
rebuild is not assumed to reproduce an archived compiler binary byte for byte.

```sh
export WORK=/path/to/qualification
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin
python3.13 scripts/run_ir_audit.py \
  --root "$WORK/alpha2-audit" --old-root "$WORK/alpha1-audit" \
  --output "$WORK/recaptured-audit" --llvm "$PYSTACHY_LLVM" \
  --jobs 2 --timeout 180
python3.13 scripts/classify_ir_audit.py "$WORK/recaptured-audit"
python3.13 scripts/verify_changed_llvm.py "$WORK/recaptured-audit" \
  --llvm-as "$PYSTACHY_LLVM/llvm-as"
python3 verify_evidence.py
```

Run these commands from this evidence directory. The classifier preserves
semantic differences for review; rerunning it does not replace that review.
Raw IR, binaries and datasets are intentionally omitted. Captured content hashes
identify the original bytes; new checkout spellings can change raw IR strings.
For readable JSON, use `gzip -dc audit/complete-audit-review.json.gz`.

[Provenance](provenance.json) maps every retained source record to its original
hash and packaged hash. Absolute scratch-root spellings are presented as `$WORK`,
including embedded witness text; original content hashes remain unchanged.
Thus this is a qualification package, not an unmodified raw-byte archive.
[SHA256SUMS](SHA256SUMS) covers every packaged file except itself.
No runtime suites were rerun while assembling this package.
