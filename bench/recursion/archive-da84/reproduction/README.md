# PR #996 follow-up: reproduction notes

These files preserve the controllers used for the recovered-host performance and validation work. They are **session controllers with ordered dependencies**, not a portable, one-command replay package. Read the source identities and artifact requirements before running anything. Run examples only in a reconstructed workspace with fresh output directories; do not overwrite archived evidence.

For maintained repository entry points, use `bench/recursion/{ordinary_calls,object_calls,json_calls,json_file_calls}.py`, the compiler's `run`/`build` commands, and `tools/perf_smoke.py --base BASE_CHECKOUT --json OUTPUT`. The archived controllers below add specific comparisons, identity gates, and evidence capture; they are not additional supported compiler interfaces.

## Source and workspace identities

The original workspace root was `/workspace/scratch/e858f72517b9`. Most controllers derive that root from their own location; some auxiliary controllers and `toolchain/env.sh` also contain absolute paths. Original probe paths and LLVM input filenames affect literal IR/bitcode comparisons. Relocating files or changing controllers requires a separately identified experiment, not silently relaxing recorded hashes.

| Role | Workspace directory | Exact commit | Bootstrap record |
|---|---|---|---|
| Main | `baselines/main` | `06e3ad5d08514ba31fb231fe4636a962fe6578e3` | `recovery-validation/main/bootstrap.json` |
| Earlier region implementation | `baselines/old-eca` | `eca993b9a4563f7f7865cdeda6e6b22f29d044c1` | `recovery-validation/old-eca/bootstrap.json` |
| Tail-sharing candidate, historical preparation | `pystachy`, before advancing it | `aaec00cc81a862a2b29c117003e7c9cc73e1a3c1` | `recovery-validation/candidate/bootstrap.json` |
| Final early-rejection candidate | `pystachy`, after advancing it | `da84d382ff83f09e46d4ef104e62e6f64e9c37c1` | `recovery-validation/final-da84/bootstrap.json` |

The final tree is `903a72dce156018f83f69f1e8b4d74a6f14e99dd`. Its recorded native compiler SHA256 is `8ee9b55b99c85a1406198643a5405d6e58ef566ec5896f6af3b03daf478b3f75`. Each bootstrap record contains its full tree, source inventory, native hashes, three compiler-IR hashes, three runtime-IR hashes, and log hash. Verify bootstrap commit/tree fields against the intended revision; a `complete` status alone does not identify the source. The final preparation/validation gates require the corresponding fixed points and unchanged source identity. `candidate/bootstrap.json` continues to mean **aaec**, even after the checkout named `pystachy` advances to da84.

The sibling layout also includes:

- `perf-work/`: controllers, helper modules, historical preparations, and final measurements.
- `tail-validation/`: validation controller, prepared corpus, instrumented comparison harness, and captured results.
- `toolchain/`: private tool binaries, environment script, and manifest.
- `baselines/cap512` and `baselines/partial-prefilter`: optional historical experiments based on aaec plus the patches listed below.

## Toolchain and execution conditions

The recovered series used Linux x86-64, CPython **3.13.16**, LLVM/Clang **18.1.3**, and Valgrind **3.22.0**. `toolchain/manifest.json` records distribution URLs, package and executable hashes, Python packages, and sanity checks; its SHA256 is `abecac0463e37ea045c0e32ad445f5418efac20a31de8f02bd12f55b8c8c8488`. The repository's `tools/requirements-dev.txt` supplies the pinned development requirements.

The controllers do not install that toolchain. Reconstruct its private directory layout from the manifest before sourcing `toolchain/env.sh`. They require CPU 0 to be available for affinity, as well as `taskset`, `make`, the LLVM tools, and the recorded shared-library dependencies. Run expensive build, timing, profiling, and validation stages sequentially without other team-owned compiler jobs. This Intel-host series is separate from the historical AMD-host measurements; equal upstream tool versions do not make the recovered binaries or timings interchangeable with the lost environment.

```bash
cd /workspace/scratch/e858f72517b9
source toolchain/env.sh
```

## Historical aaec preparation comes first

Populate the three source directories with the commits above, keeping `pystachy` at aaec for this stage. In a fresh reconstruction, the bootstrap controller takes two positional arguments:

```bash
python recover_bootstrap.py baselines/main recovery-validation/main
python recover_bootstrap.py baselines/old-eca recovery-validation/old-eca
python recover_bootstrap.py pystachy recovery-validation/candidate
python perf-work/measure_recovered.py prepare --output perf-work/results-recovered-three
```

The recorded preparation's first attempt **failed an obsolete descriptor-path assertion** after preparing the programs. The driver opens its shared runtime on fd 8 and unlinks the temporary pathname; checking that pathname's suffix/accessibility after execution was incorrect. It was a capture-harness failure, not a benchmark correctness failure.

The frozen correction is a separate, no-argument controller:

```bash
python perf-work/finish_recovered_prepare.py
```

It requires the specific failed preparation, preserves it under `results-recovered-three/failures/prepare-attempt1/`, verifies the inherited fd's bytes/ELF properties against the normal cache, and finishes the JIT comparisons without rebuilding the prepared compiler/AOT artifacts. Do not run this resume against a successful preparation or an unrelated failure. The archived failed report SHA256 is `cfee2c7bbcb61bf28dff42ce03e01a75acf6323b92212cedb17484f50bb4a5e9`.

Before advancing `pystachy`, the optional historical startup comparison accepts:

```bash
python perf-work/smoke_three_native.py --output perf-work/smoke-recovered-three
```

It is a three-variant extension of the earlier smoke protocol, with its original conditional confirmation logic—not the final JSON kernel series.

## Final da84 preparation and measurements

Advance the clean `pystachy` checkout to da84, retaining the complete historical preparation and its bootstrap records. Build into a new evidence directory:

```bash
python recover_bootstrap.py pystachy recovery-validation/final-da84
python perf-work/prepare_final_recovered.py \
  --output perf-work/results-final-da84 \
  --candidate-commit da84d382ff83f09e46d4ef104e62e6f64e9c37c1 \
  --bootstrap recovery-validation/final-da84/bootstrap.json
python perf-work/run_final_recovered.py counts --output perf-work/results-final-da84
python perf-work/run_final_recovered.py timings --output perf-work/results-final-da84
python perf-work/run_final_recovered.py compile --output perf-work/results-final-da84
```

Final preparation explicitly reuses and rehashes main/eca artifacts, regenerates final-candidate artifacts, and requires literal equality with the prepared aaec raw LLVM, optimized JIT bitcode, and AOT executables. It verifies an actual driver input/runtime capture before accepting reconstructed JIT inputs. To preserve literal bitcode source identity, it temporarily reuses the historical `jit-equivalence/prog.ll` pathname and restores its bytes in `finally`.

The required historical input set is larger than `measurement.json`: retain the five probe sources, every named raw/hosted LLVM and AOT artifact, `jit-equivalence/` inputs/bitcode/disassembly, and the complete `main-cache`, `eca-cache`, and `aaec-cache` directories. Original source paths and the managed-file scratch argument are retained. These artifacts must be included or regenerated by the historical preparation; publishing script bytes alone does not supply them.

The final launcher binds the variants to main/eca/final-candidate and verifies full commit/tree/status/input/native identity before and after each phase. Existing phases cannot be overwritten silently. Preserve failed attempts before any separately documented retry.

The final plan has four JSON labels over three unique sources, six rotated process rounds, and seven measured kernel calls per process: **144 processes / 1,008 measured calls**. Counts cover two JSON cases, three variants and two modes, with eight kernel calls including warm-up per observation. Compilation has **72 samples**. Ordinary/object programs receive artifact-parity checks here, not fresh kernel timings. These phases do not establish a mixed-text whole-JIT startup win.

## Final-source correctness capture

The current validator requires full expected commit and tree arguments. Its preparation is tied to controller, corpus, and harness hashes. On a fresh validation output layout, after bootstrap and outside timing/profile work:

```bash
for phase in prepare fixtures compare; do
  python tail-validation/validate.py "$phase" \
    --expected-candidate-commit da84d382ff83f09e46d4ef104e62e6f64e9c37c1 \
    --expected-candidate-tree 903a72dce156018f83f69f1e8b4d74a6f14e99dd \
    --candidate-build recovery-validation/final-da84/bootstrap.json
done
```

`compare` also audits its capture; the same arguments with action `audit` reread existing evidence without compiling. The controller preserves raw statuses, diagnostics, and compressed IR for the 3,918-case corpus; it permits only explicitly verified library-filename substitutions in diagnostics. Compilation parity is not a runtime-equivalence claim. Fixture modes and their expected execution counts are in the prepared plan. Separate unit-test/CI results must retain their own evidence.

## Historical patches and auxiliary files

Keep these alongside the frozen core controllers (`recover_bootstrap.py`, `measure_recovered.py`, `finish_recovered_prepare.py`, `prepare_final_recovered.py`, `run_final_recovered.py`, `replay_support.py`, `count_support.py`, and `tail-validation/validate.py`):

| Files | Why they matter |
|---|---|
| `perf-work/recovered-ci/ci_smoke_script.py`, `ci_prior_smoke_script.py` | Archived smoke helper snapshots; both match old-eca's `tools/perf_smoke.py`. The dependent controllers also import old-eca's `tools/bench_extended.py` and `tools/bench_pyperformance.py`. |
| `cap512-experiment/{compiler.patch,experiment.patch,manifest.json}` | Reconstruct the rejected aaec-based cap512 candidate. The combined patch includes its focused test and Git-status provenance. This cap was **not adopted**. |
| `perf-work/cap_native_experiment.py`, `perf-work/cap-native-experiment/prepare-harness.py` | The cap experiment records different prepare/timing controller versions. For exact reconstruction, restore the prepare snapshot at the original `perf-work/cap_native_experiment.py` location before `prepare`, then restore the final controller before `timings`. Do not run the nested snapshot in place: its `__file__`-relative paths would be wrong. |
| `perf-work/profile_native_frontend.py`, `perf-work/early_rejection_native.py` | No-argument historical controllers. The first requires the completed cap report; the second requires that profile, the aaec preparation, and the isolated early-rejection source. Their original `pystachy` state is aaec, not da84. Experimental builds here are single hosted builds, not final fixed-point bootstraps. |
| `partial-prefilter-experiment/{compiler.patch,test.patch,experiment.patch,report.json}` and its emission/parity evidence | Reconstruct the accepted early-rejection experiment. Preserve the own-library-home attempt's single `lib/types.py` pathname difference; the later literal comparison used a verified common library/runtime home without normalizing IR. |
| `tail-validation/preparation-aaec00cc/` and `tail-validation/controller-identity-update.patch` | Preserve the original preparation and the later explicit final-identity binding. Do not label the old preparation as validation of da84. |
| `perf-work/results-recovered-three/failures/prepare-attempt1/` | Retains the failed report, original harness, and driver-capture files; the resume is part of the record. |

For output claims, use completed report phases and their captured hashes. A script's presence, a prepared plan, or an interrupted phase is not evidence that a measurement or validation gate passed.
