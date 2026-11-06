# GC application evidence: 2026-11-06

This directory preserves completed application measurements and preparation
records. Read the [evaluation](../2026-11-06.md) for conclusions and limitations.
[evidence-manifest.json](evidence-manifest.json) maps the original native/preparation
bundle to original paths, byte counts and SHA-256 values.
[additional-evidence-manifest.json](additional-evidence-manifest.json) covers the later
raw measurements, command snapshots and audits. Copied raw records are not reserialized
or normalized; absolute paths identify their original run environment. Generated
summaries record the hashes of the raw files they analyze.

## Completed preparation

Each configuration ran a smoke case, the smoke case with program GC stress,
and a full-scale case checked against CPython's complete stdout and any declared
output artifact. Both final build reports have `complete: true`, and their logs
contain exactly one passing group for every case/configuration pair.

| Suite | Cases | Configurations | Checks per pair | Passing validation runs | Build report and log |
|---|---:|---:|---:|---:|---|
| Native | 9 | 6 | 3 | **162** | [report](preparation/native-builds.json), [log](preparation/native-build.log) |
| Optional backend | 8 | 5 | 3 | **120** | [report](preparation/optional-builds.json), [log](preparation/optional-build.log) |

These are validation-run counts, not compilation counts. The native suite built
36 executables and reused them for its aliases; the optional suite built 16 and
reused them for runtime policies. Exact commands, executable identities, input
identities, oracle hashes and environments are recorded in the reports.

[native-spec.json](preparation/native-spec.json) defines `main`, `main_aa`,
`scalar`, `default`, `atomic_union` and `block`. The `main_aa` control reuses the
same executable as `main`; `block` reuses `default` with the block marker enabled.
[optional-spec.json](preparation/optional-spec.json) defines five configurations:
`native`, `bdw`, `bdw_32m`, `bdw_incremental` and `bdw_generational`. These are
explicit experiment controls and policies; they do not change production
defaults. In particular, native collection thresholds and a BDW initial heap
size are different policies, not matched heap caps.

## Completed native measurements

The nine JSON files in `native/` cover `float`, `chaos`, `raytrace`, `json_loads`,
`json_dumps`, `richards`, `nbody`, `json_retained` and `repair_traces`. Each has
`complete: true` and `all_outputs_match: true`. Their raw samples and original
runner summaries are preserved. Performance interpretation belongs to the
separate evaluation report.

The [optional](optional/), [sensitivity](sensitivity/) and [profile](profile/) records
are now complete in the additional evidence bundle. There are 23 primary/follow-up
result files with 741 samples (626 measured and 115 warmups), plus three separately
instrumented profiling samples. The [CPython output audit](audits/cpython-output-audit.json)
checks all 744. The [local validation receipt](audits/local-validation.json) distinguishes
hosted checks, native correctness runs and unrun integrated suites.

| Result group | Human-readable summary | Structured summary / raw records |
|---|---|---|
| Native allocation/marking | [Native comparisons](native-summary.md) | [Summary](native-summary.json), [raw](native/) |
| Optional BDWGC policies | [Optional comparisons](optional-summary.md) | [Summary](optional-summary.json), [raw](optional/) |
| Pacing and longer union run | [Follow-up comparisons](sensitivity-summary.md) | [Summary](sensitivity-summary.json), [raw/configs](sensitivity/) |
| Instrumented tracing / emitted IR sites | [Evaluation](../2026-11-06.md#compiler-assisted-scalar-union-allocation) | [Counters](profile/json_retained.json), [IR sites](profile/ir-sites.json) |

[Code publication](code-publication.json) maps local source commits to published commits
with identical complete trees. The historical command snapshots in `commands/` use the
original absolute paths; the final preparation specifications are authoritative for
the corrected flags and paths.

## Inputs and optional backend provenance

The preparation records include the [full input manifest](preparation/inputs-full-manifest.json),
[smoke input manifest](preparation/inputs-smoke-manifest.json),
[embedded fixture manifest](preparation/embedded-fixture-manifest.json),
[final BDW overlay manifest](preparation/bdwgc-aot-overlay-manifest.json), and
[linker-flags check](preparation/bdwgc-link-flags-check.json).
They retain generator, input, runtime, header and library identities without
copying the generated data, embedded module, executables or caches.

The optional suite uses `json_retained_memory`, whose static literal input is a
distinct workload from the native suite's file-backed `json_retained`. It also
omits `repair_traces`. Its own `native` configuration supplies the corresponding
comparison workload; the two retained-JSON workloads should not be substituted
for each other.

## Preserved unsuccessful preparation

The first optional build failed with clang's `cannot specify -o when generating
multiple output files` diagnostic. Its specification passed the static archive
path directly. The completed specification forwards it with `-Xlinker`; the
separate linker-flags check records successful compilation and linking stages.
The failed attempt remains explicitly incomplete in
[failed-link-builds.json](preparation/failed-link-builds.json), with its
[log](preparation/failed-link-build.log), [stderr](preparation/failed-link-build.stderr)
and [original specification](preparation/failed-link-spec.json). It is not included
in the 120 completed optional validation runs. The archived final
`optional-spec.json` comes from the original `optional-aot-spec.json`; the failed
specification preserves the original file named `optional-spec.json`.

[pilot-preflight-apps.log](preparation/pilot-preflight-apps.log) is **pilot,
non-headline evidence**. It records an earlier retained-JSON profile and the
initial repair wrapper's rejection at its `json.dumps(list[str])` output boundary.
The finalized wrapper's successful checks are in the completed native report.
The pilot's timings are not part of the nine native measurement files.

The separately archived [compiler validation](compiler-validation/README.md)
has its own compact summary and hash manifest.
