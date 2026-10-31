# PR #996 continuation evidence

Start with the [current-main report](../../../docs/reports/recursion-guard-completion.md).
The evaluated source is `ea68529b8a590eb8f3df7200b857e1d16becd7a3`, based on
`07b26e02425d023288ed95a9d2a5077be5aeb45e`. The PR remains draft because
performance acceptance is unresolved. This evidence branch is not a source
branch to merge into main.

## Current evidence

| Record | Purpose |
|---|---|
| [Candidate bootstrap](candidate-ea685/bootstrap.json), [main bootstrap](current-main-07b/bootstrap.json) | Fresh native compiler/runtime fixed points and all consumed input bindings |
| [Hosted validation](candidate-ea685/hosted-validation.json), [native fixtures](candidate-ea685/native-fixtures.json) | 522 local hosted tests; 13 focused native JIT/AOT/stress executions |
| [CI explanation](ci/README-ea685.md), [CI summary](ci/ea685/summary.json) | 59 successes, two expected skips, complete original reports independently remerged, 919 CI unittest executions |
| [Full corpus report](candidate-ea685/corpus/comparison.json.gz) | Losslessly compressed original 3,924-case report, including its strict diagnostic-gate failure |
| [Diagnostic assessment](candidate-ea685/corpus/README.md) | All 29 residual differences proved to be checkout prefixes in identical-source locations; original report remains unchanged |
| [Startup results](startup-ea685/curated-ea685-final.json), [explanation](startup-ea685/ea685-final-readme.txt) | 108 primary observations, 36 longer fnmatch observations, complete tool profiles and inspector/backend linkage |
| [Kernel explanation](kernel-ea685/README.md), [complete observations](kernel-ea685/measurement.json) | 252 timed processes and 24 instruction-count observations |
| [Reproduction audit](startup-ea685/reproduction-ea685-audit.txt) | Authoritative current commands, companion layouts, original archive dependencies and superseded instructions |
| [Source reconstruction](source-reconstruction/source-references.json) | Exact published bases and binary-capable patches for otherwise-local historical source trees |
| [Publication manifest](publication-manifest.json) | Original paths, sizes and SHA256 hashes of the selected evidence files |

The original corpus JSON is 13,011,725 bytes with SHA256
`425b47eb39da4d4dabfe5ec4c0a8be63d6536bb38e23ee338c88238300b2d2a6`.
Its deterministic gzip is 1,537,905 bytes with SHA256
`6cdf47482bd350bca54699de9bff90e524dc456be8b43c8f57ff48393778bb1d`.
Decompression reproduces the exact original bytes, including `status: failed`
and `gate_passed: false`; the separate diagnostic proof explains every flag.

## Reproduction and recovery

The publication is a review selection, not a self-contained execution package.
Frozen controllers bind absolute paths, source/tool versions, private caches,
bootstrap outputs and logs. Follow the reproduction audit before invoking them,
restore the recorded layout or use a separately reviewed adapter, and always
write a new output directory. Original observation reports must not be edited
to match a new environment. Run elapsed phases in a separate quiet window.

Full raw case LLVM, per-case streams, profiles, generated executables and caches
remain in the continuation recovery archive. Published source checkouts and
published evidence can be restored from exact GitHub commits; the archive's
restoration map identifies any omitted published duplicates. The original three
handoff ZIPs supply the historical source/builds and pinned toolchain and remain
dependencies. Preserve Unix permissions and symlinks during extraction.

## Historical records are separate

`checkpoints/` and older `ci/` subdirectories retain failed and successful
intermediate work. In particular, `156fc` failed its first bootstrap, `860b`
failed two stale attribute expectations in CI, and `db14` corrected those
expectations. Its reused local build and old-main count-only series do not
claim a fresh bootstrap or completed elapsed phase. The `ea685` series uses
fresh current-main and candidate builds.

The `candidate-ea685/inspection-summary.json` snapshot predates backend linkage.
The completed v2 linkage in `startup-ea685/` is authoritative. The original
startup publication selection and planning instructions remain historical;
`reproduction-ea685-audit.txt` supplies the corrected execution instructions.

Previously unpublished da84 evidence was published at
`1b7080e164ab68a8fcde042162428d9131c9f533`. The older missing
`recursion-region-startup-diagnostics.json` is still missing. Neither this
publication nor the new inspector claims to reconstruct it.
