## Hosted compiler coverage

Commit `6c81644536bebeb330d02e778da409fa61d7f3ed`: statements **95.9%** (39019 of 40693) and branches **92.4%** (20548 of 22246); 94.6% together, coverage.py's total. 5 suites, 6070 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5817 passed, 0 failed | 5825 | 2632 s | 94.7% | 90.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 143 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 130 | 123 s | 37.4% | 29.1% |
| cache | `tests/cache.sh` | 68 passed, 0 failed | 34 | 225 s | 28.6% | 19.2% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 142 tests, OK | 2 | 11 s | 48.4% | 41.0% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 79 programs | 79 | 137 s | 57.3% | 50.2% |
| **all** | | | **6070** | | **95.9%** | **92.4%** |

The other suites run 477 statements and 351 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1489 | 72 | 95.2% | 1272 | 84 | 93.4% | 94.3% | 94.3% |
| `src/pystachy_compiler/bigints.py` | 690 | 36 | 94.8% | 288 | 39 | 86.5% | 92.3% | 92.3% |
| `src/pystachy_compiler/builtins.py` | 2347 | 112 | 95.2% | 1416 | 107 | 92.4% | 94.2% | 94.0% |
| `src/pystachy_compiler/calls.py` | 1312 | 55 | 95.8% | 804 | 56 | 93.0% | 94.8% | 92.4% |
| `src/pystachy_compiler/containers.py` | 877 | 33 | 96.2% | 480 | 35 | 92.7% | 95.0% | 95.0% |
| `src/pystachy_compiler/conversions.py` | 297 | 10 | 96.6% | 192 | 9 | 95.3% | 96.1% | 96.1% |
| `src/pystachy_compiler/declarations.py` | 2347 | 143 | 93.9% | 1588 | 136 | 91.4% | 92.9% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 60 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 576 | 77 | 86.6% | 236 | 48 | 79.7% | 84.6% | 68.6% |
| `src/pystachy_compiler/dynamic.py` | 2310 | 154 | 93.3% | 1298 | 182 | 86.0% | 90.7% | 90.7% |
| `src/pystachy_compiler/emission.py` | 511 | 13 | 97.5% | 162 | 10 | 93.8% | 96.6% | 96.3% |
| `src/pystachy_compiler/exceptions.py` | 1169 | 34 | 97.1% | 554 | 30 | 94.6% | 96.3% | 96.3% |
| `src/pystachy_compiler/expressions.py` | 4047 | 130 | 96.8% | 2330 | 120 | 94.8% | 96.1% | 96.1% |
| `src/pystachy_compiler/flow.py` | 785 | 6 | 99.2% | 550 | 10 | 98.2% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 351 | 13 | 96.3% | 192 | 10 | 94.8% | 95.8% | 79.0% |
| `src/pystachy_compiler/gen.py` | 2433 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 952 | 38 | 96.0% | 380 | 43 | 88.7% | 93.9% | 93.9% |
| `src/pystachy_compiler/ir.py` | 363 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 402 | 27 | 93.3% | 330 | 27 | 91.8% | 92.6% | 77.3% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2537 | 75 | 97.0% | 1560 | 82 | 94.7% | 96.2% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 368 | 11 | 97.0% | 192 | 8 | 95.8% | 96.6% | 51.6% |
| `src/pystachy_compiler/lowering.py` | 416 | 3 | 99.3% | 254 | 4 | 98.4% | 99.0% | 98.8% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 30 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 12 | 98.5% | 514 | 23 | 95.5% | 97.4% | 97.1% |
| `src/pystachy_compiler/parser.py` | 2001 | 103 | 94.9% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 937 | 35 | 96.3% | 686 | 33 | 95.2% | 95.8% | 94.8% |
| `src/pystachy_compiler/reflection.py` | 1955 | 144 | 92.6% | 1042 | 138 | 86.8% | 90.6% | 90.5% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 247 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1666 | 65 | 96.1% | 924 | 69 | 92.5% | 94.8% | 94.7% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 753 | 38 | 95.0% | 452 | 46 | 89.8% | 93.0% | 93.0% |
| `src/pystachy_compiler/union_arithmetic.py` | 133 | 3 | 97.7% | 52 | 3 | 94.2% | 96.8% | 96.8% |
| `src/pystachy_compiler/union_proof.py` | 769 | 12 | 98.4% | 550 | 22 | 96.0% | 97.4% | 92.6% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 431 | 28 | 93.5% | 232 | 26 | 88.8% | 91.9% | 91.9% |
| `src/pystachy_compiler/utils.py` | 651 | 27 | 95.9% | 326 | 26 | 92.0% | 94.6% | 93.9% |
| `src/pystachy_compiler/variables.py` | 1772 | 100 | 94.4% | 1110 | 108 | 90.3% | 92.8% | 92.7% |
