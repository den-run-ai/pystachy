# ctypes prototype validation

Evidence for published code commit [`9371d37daf2397798f02393e95fff0e25a1fefbe`](https://github.com/den-run-ai/pystachy/commit/9371d37daf2397798f02393e95fff0e25a1fefbe), compared with main `f7103067545b43cdcd8ce20dc66b1571425b3a8d`. Local tests used commit `dc449fab60998dbe622858efa50d3ec82b6c81f6`; the GitHub app published the identical Git tree `4afdb91ce38428d58a347633d9ca4dce3b0387e0` with new commit metadata after direct git push lacked credentials. This research branch is **not for merge**. The implementation branch contains the maintained consumer, checker and regression tests.

## Results

| Local check | Result |
|---|---|
| Native bootstrap | Compiler and runtime three-stage fixed points; 836,682 and 18,805 IR lines |
| Fast tests, lint and runtime audit | 436 unit tests; 50 mypy sources; runtime signatures and GC root audit clean |
| CPython recordings | 2,143 recordings, 123 deviations, 11 library files; no failures |
| IR validation | All 2,360 programs accepted by the IR checker and llvm-as |
| Native FFI suite | 178 passed; zero failures or reported skips |
| Focused import/pointer regressions | Six JIT/AOT checks passed |
| llvmlite 0.46.0 | 50 mode/case checks, 800 native-resource lifecycles; 40 checks and 640 lifecycles in Pystachy, including GC stress |
| Full corpus IR comparison | 4,240 inputs: 3,978 exact, 248 IR path-only, 13 diagnostic path-only, one expected new acceptance; no new rejections or unexplained changes |

The strict, unchanged corpus command returned **1**, which is preserved. Classification accepts only complete LLVM string constants with verified byte lengths, or diagnostic source-location paths; all other bytes must match. The compiler, runtime and relative-import regression match baseline exactly.

The llvmlite consumer parses and verifies LLVM assembly, prints canonical IR and disposes its native resources. Its exact output is checked against the installed, unmodified llvmlite Python API. This establishes a useful adapted binding slice, not full llvmlite or Numba compatibility. No performance claim is made.

## Evidence and reproduction

[verification.json](verification.json) records commands, environment, final code and binary identities, earlier failed checks, corrections and unrun suites. [llvmlite.json](llvmlite.json) contains the library/source/input/output hashes and all executed modes. See the tested revision's [example instructions](https://github.com/den-run-ai/pystachy/blob/9371d37daf2397798f02393e95fff0e25a1fefbe/examples/ctypes_llvmlite/README.md) to reproduce the consumer.

The [logs](logs) retain both final checks and the initial hosted scalar-fixture failure. That failure came from checked integer arithmetic in two test expressions; exact min/max literals corrected the fixture without changing its CPython recording. The final native suite passes. Independent review also caught an incorrect rewrite of project-relative ctypes imports; the negative control returned 7, while CPython, main and the corrected implementation return 93.

[summary.json](summary.json) and [status.json](status.json) preserve the corpus outcome. `manifest.json.gz` and `classification.json.gz` contain the full 4,240-case inventory and classifications. [classify.py](classify.py) is the unchanged audit program. Full raw IR captures were not committed; the comparator can be rerun against the pinned source revisions with separate compiler homes and libraries. The classification is evidence from this run, not a replacement test gate.

The full local `make verify` matrix, full GC groups, sanitizers, other platforms, the upstream llvmlite suite and performance benchmarks were not run. CI is reported separately on the pull request.
