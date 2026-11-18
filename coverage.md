## Hosted compiler coverage

Commit `e2b97bb452ac2042a346e915eb9017f6e8f97328`: statements **95.7%** (53937 of 56389) and branches **92.1%** (28132 of 30552); 94.4% together, coverage.py's total. 5 suites, 8750 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 8400 passed, 0 failed | 8410 | 4219 s | 92.7% | 88.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 179 s | 47.1% | 39.6% |
| cache | `tests/cache.sh` | 98 passed, 0 failed | 52 | 301 s | 32.5% | 23.5% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 553 tests, OK | 9 | 67 s | 50.2% | 43.0% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 104 programs | 104 | 218 s | 57.7% | 51.0% |
| **all** | | | **8750** | | **95.7%** | **92.1%** |

The other suites run 1654 statements and 1016 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1716 | 79 | 95.4% | 1454 | 92 | 93.7% | 94.6% | 94.5% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 996 | 37 | 96.3% | 410 | 41 | 90.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/builtins.py` | 3002 | 144 | 95.2% | 1790 | 144 | 92.0% | 94.0% | 93.1% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 226 | 59 | 73.9% | 110 | 35 | 68.2% | 72.0% | 13.7% |
| `src/pystachy_compiler/callbacks.py` | 180 | 2 | 98.9% | 90 | 3 | 96.7% | 98.1% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1495 | 51 | 96.6% | 914 | 51 | 94.4% | 95.8% | 94.0% |
| `src/pystachy_compiler/class_values.py` | 512 | 26 | 94.9% | 264 | 28 | 89.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/containers.py` | 1097 | 43 | 96.1% | 612 | 43 | 93.0% | 95.0% | 95.0% |
| `src/pystachy_compiler/conversions.py` | 369 | 10 | 97.3% | 232 | 8 | 96.6% | 97.0% | 97.0% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/declarations.py` | 2882 | 175 | 93.9% | 1954 | 174 | 91.1% | 92.8% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 95 | 8 | 91.6% | 22 | 1 | 95.5% | 92.3% | 92.3% |
| `src/pystachy_compiler/driver.py` | 1099 | 166 | 84.9% | 460 | 116 | 74.8% | 81.9% | 66.0% |
| `src/pystachy_compiler/dynamic.py` | 4261 | 254 | 94.0% | 2220 | 272 | 87.7% | 91.9% | 91.9% |
| `src/pystachy_compiler/dynamic_proof.py` | 409 | 4 | 99.0% | 248 | 7 | 97.2% | 98.3% | 93.2% |
| `src/pystachy_compiler/emission.py` | 589 | 17 | 97.1% | 196 | 15 | 92.3% | 95.9% | 94.1% |
| `src/pystachy_compiler/exceptions.py` | 1504 | 50 | 96.7% | 730 | 45 | 93.8% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 5359 | 158 | 97.1% | 3062 | 162 | 94.7% | 96.2% | 96.2% |
| `src/pystachy_compiler/flow.py` | 833 | 4 | 99.5% | 582 | 9 | 98.5% | 99.1% | 98.4% |
| `src/pystachy_compiler/functions.py` | 424 | 23 | 94.6% | 230 | 17 | 92.6% | 93.9% | 80.0% |
| `src/pystachy_compiler/gen.py` | 3072 | 3 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1048 | 37 | 96.5% | 412 | 41 | 90.0% | 94.7% | 94.7% |
| `src/pystachy_compiler/ir.py` | 443 | 3 | 99.3% | 32 | 3 | 90.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/ircheck.py` | 476 | 27 | 94.3% | 394 | 27 | 93.1% | 93.8% | 78.3% |
| `src/pystachy_compiler/lexer.py` | 644 | 27 | 95.8% | 360 | 26 | 92.8% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 3717 | 163 | 95.6% | 2300 | 181 | 92.1% | 94.3% | 94.1% |
| `src/pystachy_compiler/local_versions.py` | 60 | 0 | 100.0% | 40 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 509 | 11 | 97.8% | 274 | 7 | 97.4% | 97.7% | 55.9% |
| `src/pystachy_compiler/lowering.py` | 536 | 3 | 99.4% | 310 | 5 | 98.4% | 99.1% | 98.9% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 36 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 28 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1662 | 34 | 98.0% | 1004 | 40 | 96.0% | 97.2% | 96.7% |
| `src/pystachy_compiler/parser.py` | 2098 | 104 | 95.0% | 1170 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 306 | 17 | 94.4% | 166 | 16 | 90.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/pipeline.py` | 130 | 7 | 94.6% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 1732 | 74 | 95.7% | 1272 | 80 | 93.7% | 94.9% | 94.8% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2592 | 164 | 93.7% | 1382 | 168 | 87.8% | 91.6% | 91.5% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 126 | 1 | 99.2% | 58 | 3 | 94.8% | 97.8% | 18.5% |
| `src/pystachy_compiler/specs.py` | 276 | 0 | 100.0% | 86 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1845 | 64 | 96.5% | 1020 | 71 | 93.0% | 95.3% | 95.2% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 833 | 37 | 95.6% | 496 | 45 | 90.9% | 93.8% | 93.8% |
| `src/pystachy_compiler/union_arithmetic.py` | 219 | 14 | 93.6% | 122 | 13 | 89.3% | 92.1% | 92.1% |
| `src/pystachy_compiler/union_proof.py` | 867 | 13 | 98.5% | 620 | 23 | 96.3% | 97.6% | 92.5% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 720 | 31 | 95.7% | 390 | 32 | 91.8% | 94.3% | 94.3% |
| `src/pystachy_compiler/utils.py` | 789 | 28 | 96.5% | 404 | 28 | 93.1% | 95.3% | 92.0% |
| `src/pystachy_compiler/variables.py` | 1864 | 109 | 94.2% | 1164 | 113 | 90.3% | 92.7% | 92.6% |
