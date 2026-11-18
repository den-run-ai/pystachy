## Hosted compiler coverage

Commit `9bc02a0f06734c8f2979e8b7bc05e3009a86d263`: statements **95.7%** (54322 of 56767) and branches **92.2%** (28326 of 30738); 94.4% together, coverage.py's total. 5 suites, 8894 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 8544 passed, 0 failed | 8554 | 5448 s | 92.8% | 88.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 165 s | 47.1% | 39.6% |
| cache | `tests/cache.sh` | 98 passed, 0 failed | 52 | 274 s | 32.4% | 23.4% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 584 tests, OK | 9 | 62 s | 50.7% | 43.7% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 104 programs | 104 | 212 s | 57.7% | 51.0% |
| **all** | | | **8894** | | **95.7%** | **92.2%** |

The other suites run 1667 statements and 1027 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1716 | 70 | 95.9% | 1454 | 82 | 94.4% | 95.2% | 95.1% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 997 | 37 | 96.3% | 410 | 41 | 90.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/builtins.py` | 3012 | 145 | 95.2% | 1798 | 145 | 91.9% | 94.0% | 93.0% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 226 | 59 | 73.9% | 110 | 35 | 68.2% | 72.0% | 13.7% |
| `src/pystachy_compiler/callbacks.py` | 181 | 2 | 98.9% | 90 | 3 | 96.7% | 98.2% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1498 | 51 | 96.6% | 916 | 51 | 94.4% | 95.8% | 94.0% |
| `src/pystachy_compiler/class_values.py` | 512 | 26 | 94.9% | 264 | 28 | 89.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/containers.py` | 1123 | 43 | 96.2% | 616 | 43 | 93.0% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 369 | 10 | 97.3% | 232 | 8 | 96.6% | 97.0% | 97.0% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/declarations.py` | 2883 | 175 | 93.9% | 1954 | 174 | 91.1% | 92.8% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 95 | 8 | 91.6% | 22 | 1 | 95.5% | 92.3% | 92.3% |
| `src/pystachy_compiler/driver.py` | 1099 | 166 | 84.9% | 460 | 116 | 74.8% | 81.9% | 66.0% |
| `src/pystachy_compiler/dynamic.py` | 4263 | 253 | 94.1% | 2220 | 271 | 87.8% | 91.9% | 91.9% |
| `src/pystachy_compiler/dynamic_proof.py` | 409 | 4 | 99.0% | 248 | 7 | 97.2% | 98.3% | 93.2% |
| `src/pystachy_compiler/emission.py` | 588 | 16 | 97.3% | 194 | 14 | 92.8% | 96.2% | 94.4% |
| `src/pystachy_compiler/exceptions.py` | 1506 | 50 | 96.7% | 730 | 45 | 93.8% | 95.8% | 95.8% |
| `src/pystachy_compiler/expressions.py` | 5427 | 161 | 97.0% | 3102 | 164 | 94.7% | 96.2% | 96.2% |
| `src/pystachy_compiler/flow.py` | 833 | 4 | 99.5% | 582 | 9 | 98.5% | 99.1% | 98.4% |
| `src/pystachy_compiler/frames.py` | 129 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/functions.py` | 425 | 21 | 95.1% | 230 | 16 | 93.0% | 94.4% | 80.5% |
| `src/pystachy_compiler/gen.py` | 3085 | 3 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1050 | 35 | 96.7% | 412 | 39 | 90.5% | 94.9% | 94.9% |
| `src/pystachy_compiler/ir.py` | 256 | 5 | 98.0% | 80 | 5 | 93.8% | 97.0% | 92.3% |
| `src/pystachy_compiler/ircheck.py` | 500 | 31 | 93.8% | 410 | 31 | 92.4% | 93.2% | 77.7% |
| `src/pystachy_compiler/lexer.py` | 655 | 27 | 95.9% | 362 | 26 | 92.8% | 94.8% | 94.8% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 3754 | 163 | 95.7% | 2326 | 181 | 92.2% | 94.3% | 94.2% |
| `src/pystachy_compiler/local_versions.py` | 60 | 0 | 100.0% | 40 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 510 | 11 | 97.8% | 274 | 7 | 97.4% | 97.7% | 56.0% |
| `src/pystachy_compiler/lowering.py` | 537 | 3 | 99.4% | 310 | 5 | 98.4% | 99.1% | 98.9% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 36 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 29 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1662 | 34 | 98.0% | 1004 | 40 | 96.0% | 97.2% | 96.7% |
| `src/pystachy_compiler/parser.py` | 2098 | 104 | 95.0% | 1170 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 306 | 17 | 94.4% | 166 | 16 | 90.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/pipeline.py` | 130 | 7 | 94.6% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 1778 | 77 | 95.7% | 1304 | 85 | 93.5% | 94.7% | 94.6% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2593 | 164 | 93.7% | 1382 | 168 | 87.8% | 91.6% | 91.5% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 126 | 1 | 99.2% | 58 | 3 | 94.8% | 97.8% | 18.5% |
| `src/pystachy_compiler/specs.py` | 311 | 0 | 100.0% | 96 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1847 | 64 | 96.5% | 1020 | 71 | 93.0% | 95.3% | 95.2% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/symbols.py` | 144 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 833 | 34 | 95.9% | 496 | 41 | 91.7% | 94.4% | 94.4% |
| `src/pystachy_compiler/union_arithmetic.py` | 219 | 14 | 93.6% | 122 | 13 | 89.3% | 92.1% | 92.1% |
| `src/pystachy_compiler/union_proof.py` | 867 | 13 | 98.5% | 620 | 23 | 96.3% | 97.6% | 92.5% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 721 | 31 | 95.7% | 390 | 32 | 91.8% | 94.3% | 94.3% |
| `src/pystachy_compiler/utils.py` | 790 | 28 | 96.5% | 404 | 28 | 93.1% | 95.3% | 92.0% |
| `src/pystachy_compiler/variables.py` | 1866 | 107 | 94.3% | 1164 | 110 | 90.5% | 92.8% | 92.8% |
