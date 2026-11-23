## Hosted compiler coverage

Commit `a130cf51cb1a207c7852c44e651bbf931286e246`: statements **95.5%** (60334 of 63175) and branches **91.9%** (31747 of 34544); 94.2% together, coverage.py's total. 5 suites, 9757 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 9390 passed, 0 failed | 9400 | 6060 s | 92.9% | 88.9% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 196 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 177 | 216 s | 46.1% | 38.6% |
| cache | `tests/cache.sh` | 99 passed, 0 failed | 53 | 391 s | 31.6% | 22.6% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 716 tests, OK | 9 | 116 s | 51.2% | 44.3% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 118 programs | 118 | 273 s | 59.7% | 53.3% |
| **all** | | | **9757** | | **95.5%** | **91.9%** |

The other suites run 1624 statements and 1022 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1731 | 85 | 95.1% | 1464 | 93 | 93.6% | 94.4% | 94.4% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 997 | 37 | 96.3% | 410 | 41 | 90.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/builtin_bases.py` | 299 | 18 | 94.0% | 152 | 18 | 88.2% | 92.0% | 92.0% |
| `src/pystachy_compiler/builtins.py` | 3093 | 156 | 95.0% | 1854 | 155 | 91.6% | 93.7% | 92.8% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 231 | 59 | 74.5% | 112 | 35 | 68.8% | 72.6% | 14.9% |
| `src/pystachy_compiler/callbacks.py` | 183 | 2 | 98.9% | 92 | 3 | 96.7% | 98.2% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1544 | 53 | 96.6% | 950 | 54 | 94.3% | 95.7% | 93.7% |
| `src/pystachy_compiler/class_proof.py` | 470 | 35 | 92.6% | 310 | 33 | 89.4% | 91.3% | 89.1% |
| `src/pystachy_compiler/class_values.py` | 514 | 25 | 95.1% | 264 | 28 | 89.4% | 93.2% | 93.2% |
| `src/pystachy_compiler/containers.py` | 1138 | 43 | 96.2% | 622 | 43 | 93.1% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 396 | 9 | 97.7% | 246 | 7 | 97.2% | 97.5% | 97.5% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/dataflow.py` | 89 | 0 | 100.0% | 56 | 2 | 96.4% | 98.6% | 97.9% |
| `src/pystachy_compiler/declarations.py` | 3056 | 175 | 94.3% | 2076 | 180 | 91.3% | 93.1% | 92.5% |
| `src/pystachy_compiler/diagnostics.py` | 104 | 8 | 92.3% | 22 | 1 | 95.5% | 92.9% | 92.9% |
| `src/pystachy_compiler/driver.py` | 1275 | 261 | 79.5% | 550 | 178 | 67.6% | 75.9% | 62.4% |
| `src/pystachy_compiler/dynamic.py` | 4432 | 244 | 94.5% | 2304 | 262 | 88.6% | 92.5% | 92.5% |
| `src/pystachy_compiler/dynamic_proof.py` | 338 | 5 | 98.5% | 190 | 4 | 97.9% | 98.3% | 92.4% |
| `src/pystachy_compiler/emission.py` | 745 | 18 | 97.6% | 306 | 17 | 94.4% | 96.7% | 95.1% |
| `src/pystachy_compiler/exceptions.py` | 1511 | 51 | 96.6% | 734 | 46 | 93.7% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 5862 | 170 | 97.1% | 3350 | 176 | 94.7% | 96.2% | 96.2% |
| `src/pystachy_compiler/flow.py` | 850 | 4 | 99.5% | 596 | 9 | 98.5% | 99.1% | 98.5% |
| `src/pystachy_compiler/frames.py` | 129 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/functions.py` | 445 | 27 | 93.9% | 238 | 20 | 91.6% | 93.1% | 79.8% |
| `src/pystachy_compiler/gen.py` | 3275 | 3 | 99.9% | 4 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1050 | 35 | 96.7% | 412 | 39 | 90.5% | 94.9% | 94.9% |
| `src/pystachy_compiler/ir.py` | 285 | 3 | 98.9% | 102 | 3 | 97.1% | 98.4% | 95.3% |
| `src/pystachy_compiler/ircheck.py` | 900 | 31 | 96.6% | 672 | 32 | 95.2% | 96.0% | 86.3% |
| `src/pystachy_compiler/lexer.py` | 651 | 27 | 95.9% | 360 | 26 | 92.8% | 94.8% | 94.8% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 5039 | 261 | 94.8% | 3214 | 287 | 91.1% | 93.4% | 93.2% |
| `src/pystachy_compiler/local_versions.py` | 60 | 0 | 100.0% | 40 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 517 | 17 | 96.7% | 278 | 11 | 96.0% | 96.5% | 55.3% |
| `src/pystachy_compiler/lowering.py` | 552 | 2 | 99.6% | 322 | 4 | 98.8% | 99.3% | 99.0% |
| `src/pystachy_compiler/machine_ir.py` | 133 | 1 | 99.2% | 78 | 1 | 98.7% | 99.1% | 93.4% |
| `src/pystachy_compiler/memory_ir.py` | 42 | 5 | 88.1% | 20 | 5 | 75.0% | 83.9% | 71.0% |
| `src/pystachy_compiler/module.py` | 39 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 37 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1890 | 41 | 97.8% | 1104 | 50 | 95.5% | 97.0% | 96.5% |
| `src/pystachy_compiler/parser.py` | 2100 | 104 | 95.0% | 1172 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 306 | 17 | 94.4% | 166 | 16 | 90.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/pipeline.py` | 131 | 7 | 94.7% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 2086 | 103 | 95.1% | 1518 | 116 | 92.4% | 93.9% | 93.8% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2773 | 167 | 94.0% | 1460 | 174 | 88.1% | 91.9% | 91.8% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 4 | 91.5% | 22 | 4 | 81.8% | 88.4% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 130 | 1 | 99.2% | 58 | 2 | 96.6% | 98.4% | 90.4% |
| `src/pystachy_compiler/specs.py` | 365 | 0 | 100.0% | 124 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1994 | 76 | 96.2% | 1094 | 79 | 92.8% | 95.0% | 94.9% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/structure.py` | 112 | 0 | 100.0% | 70 | 2 | 97.1% | 98.9% | 97.8% |
| `src/pystachy_compiler/symbols.py` | 167 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/syntax.py` | 155 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 999 | 46 | 95.4% | 602 | 54 | 91.0% | 93.8% | 93.8% |
| `src/pystachy_compiler/union_arithmetic.py` | 401 | 19 | 95.3% | 216 | 19 | 91.2% | 93.8% | 93.8% |
| `src/pystachy_compiler/union_proof.py` | 1107 | 28 | 97.5% | 806 | 41 | 94.9% | 96.4% | 91.7% |
| `src/pystachy_compiler/union_state.py` | 287 | 2 | 99.3% | 168 | 2 | 98.8% | 99.1% | 99.1% |
| `src/pystachy_compiler/unions.py` | 980 | 45 | 95.4% | 506 | 46 | 90.9% | 93.9% | 93.9% |
| `src/pystachy_compiler/utils.py` | 920 | 36 | 96.1% | 500 | 36 | 92.8% | 94.9% | 90.9% |
| `src/pystachy_compiler/variables.py` | 1928 | 106 | 94.5% | 1198 | 110 | 90.8% | 93.1% | 93.0% |
