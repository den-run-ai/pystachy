# JSON #969 evidence, 29 October 2026

Research archive only; **do not merge this branch into main**. The curated report is
`docs/reports/json-regression-followup-2026-10-29.md` on its documentation branch.
`evidence.zip` preserves measurements and review evidence without compiler binaries,
runtime caches, toolchain installations or the full generated IR corpus. Its
`manifest.json` records every enclosed file's SHA-256 and byte count.

## Source pins

| Role | Commit | Tree |
|---|---|---|
| alpha.3 | `f5a09d4223139d7255e31051be97fc509e1ca1fe` | `8fef058c9a6de7f69b0baaebaaf087a8e39a79ac` |
| Main before follow-up | `1540bb222fa5f82a7c24f6bb19aaf6db363898dd` | `c9867785a56313861fb1819c5369eb4aff3a5d8e` |
| Early runtime profile, not final #983 | `e67dd309c1b222ccdd7e3d218eb70480f0a9aea5` | `e00e77bc50931963ee05d487bd280d27cde86450` |
| Final runtime-only profile | `912ea029eb2ee1ce6d2097c381a507d79e223874` | `cddfa38684a8af14c54141fa51b4716e416f865b` |
| Measured combined source | `40a2c5ddeab50ffdbcc54dc987577c9127d84470` | `92519c59b2777022e6a8b09649584659316ef775` |
| Runtime #983 final head | `9975692d3d81253cd63d878e372315d39dca9826` | `7ba7f35b47b7995fe85924a37af7c467c4737f0e` |
| Identity #984 measured-code head | `83eceba77b582749f4e1ff9269b0d8c0c6a72969` | `94b69c9ed8d3d53ac27d0e2e79da6b95f87de99b` |

The branch starts after #983's merge, `b8e5c2d3`; the archive's metadata pins the older
sources actually measured. #984's subsequent `11f7ec5` audit-only update changes
ownership/reset tests, not the compiled implementation measured here. Its final CI
and merge status belong in the PR and curated report, not inferred from this archive.

## Contents

- `control-evidence/`: profiles, seven retained timing samples per source/case/mode,
  source hashes, all 270 stdout files, matching stderr logs and 12 Callgrind traces.
  The stdout total is 48 warmups + 168 measured timing runs + 24 timing oracles +
  12 profiled runs + 12 profiling oracles + 6 build outputs. All 216 timing-run
  outputs (warmups and measurements) match their CPython oracle; `stdout-counts.json`
  preserves this checked breakdown.
- `baseline-json/`, `combined-json/`: source/build/profile manifests, complete
  pyperformance input and Callgrind traces plus command/output logs. `runtime-json/`
  is the **earlier e67dd309 runtime checkpoint**, not the final runtime-only result.
- `runtime-final-json/`: the final runtime-only 1,326,402,110-instruction trace,
  stdout/stderr and retrospective provenance. Source `912ea029` differs from final
  PR #983 only in its two opt-in exception manifests; compiler/runtime/library source
  is identical. This instruction-count trial was not CPU-pinned and makes no timing
  claim. Its stdout matches the independently checked early-runtime output.
- `inputs/`: measured typed and observed-Any controls, with SHA-256 matching metadata.
- `oracle/`: 3,871-case source/command manifest, case list, per-case results, original
  summary, library/runtime hashes and corrected classification/diffs. Use the final
  corrected classification for semantic categories; the original summary's narrower
  checkout-path normalization is retained unchanged for auditability. Final review found
  3,825 normalized-identical cases and 46 expected differences: 29 immediate-kind changes,
  15 JSON cases, one synthetic inert fixture and one diagnostic-line change; zero unexpected
  differences, new rejections or new acceptances.
- `scripts/`: original measurement/oracle/classification scripts. The control runner
  and classification annotations contain original workspace paths; adjust only path
  bindings for replay and retain the modified script hash. They are archived research
  scripts, not installed project tools.

Full `old.ll`/`new.ll` and duplicate normalized IR are omitted. Regenerate them with
`compare_ir.py` from pinned source, exact candidate corpus and each revision's own
library. Small review diffs remain enclosed. Archive members contain project data,
source paths and explicit benchmark settings, not process-environment dumps.

## Reproduction

Use CPython 3.13.16, LLVM/Clang 18.1.3, Valgrind 3.22.0, `PYTHONHASHSEED=0` and
private per-source caches. Recorded host: Linux x86-64/glibc 2.39, AMD EPYC 9V74,
CPU 0. Clear inherited `PYSTACHY_*`, `PYTHONPATH` and `PYTHONHOME` settings, then
restore only the intended LLVM path and cache. Run one profiling/timing job at a time.

For the broader JSON workload, unpack the archive, set absolute source/tool paths,
and use identical arguments for the `build` and `profile` stages:

```sh
python3.13 scripts/json_acceptance.py build --variant alpha3=/path/alpha3 \
  --variant main=/path/main --variant combined=/path/combined --candidate combined \
  --out /path/replay --input baseline-json/json_loads.py \
  --python /path/python3.13 --llvm /path/llvm18/bin --cpu 0
python3.13 scripts/json_acceptance.py profile --variant alpha3=/path/alpha3 \
  --variant main=/path/main --variant combined=/path/combined --candidate combined \
  --out /path/replay --input baseline-json/json_loads.py \
  --python /path/python3.13 --llvm /path/llvm18/bin --cpu 0 \
  --valgrind /path/valgrind --profile-loops 300
```

The control commands are `json_decode.py numeric|strings|mixed 3000` and
`json_decode_any.py 2000` for profiles, and 30,000/20,000 loads respectively for
internal timings. `measure_controls.py` records two warmup rounds and seven measured
rounds, alternating source order. See its preserved commands and metadata before
replay. Check every stdout byte against CPython before interpreting a measurement.

Regenerate the full IR oracle with the archived `compare_ir.py`, `--baseline` and
`--candidate` checkouts, explicit `--old`/`--new` hosted-compiler commands,
`--old-build-sha 1540bb222fa5f82a7c24f6bb19aaf6db363898dd`,
`--new-build-sha 40a2c5ddeab50ffdbcc54dc987577c9127d84470`, a new `--out` directory,
`--jobs 2` and no case selectors. Run `classify_ir_oracle.py`, `classify_ir_semantics.py`,
then `finalize_ir_classification.py`, each with that output directory. The final step
records the reviewed JSON/inert/diagnostic classifications; review them anew after any
source change instead of treating this historical annotation as an automatic oracle.

## Limits

The new 32-key controls are not the unavailable historical 124M-instruction input.
Callgrind totals include startup and validation/output. The typed controls and
pyperformance timer stop before final output; the observed-Any timer includes its
loop, checksum assertion and printing. Shared-host timing ranges overlap, so the
small wall-time effects remain inconclusive. The retained observed-Any control has
+1.55% instructions versus pre-follow-up main despite the broader typed decoder's
improvement. Static IR inventories count call sites, not executed work. Full CI and
post-merge verification must be checked separately; this archive is not a release gate.
